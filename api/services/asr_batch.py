import asyncio
import contextlib
import io
import time
import wave
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
import structlog

from config import get_settings

LOGGER = structlog.get_logger(__name__)


@dataclass
class BatchASRConfig:
    language: str = "auto"
    model: str = "whisper/medium"
    compute_type: Optional[str] = "int8_float16"
    beam_size: int = 5
    enable_diarization: bool = False
    enable_alignment: bool = False
    batch_window_sec: float = 5.0
    max_batch_window_sec: float = 10.0
    flush_interval_sec: float = 1.0
    max_buffer_sec: float = 60.0


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


class BatchASRClient:
    def __init__(self, base_url: str, timeout_sec: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_sec)

    async def close(self) -> None:
        await self._client.aclose()

    async def transcribe(
        self,
        audio_wav: bytes,
        config: BatchASRConfig,
        *,
        request_id: str,
    ) -> Dict:
        data = {
            "language": config.language,
            "model": config.model,
            "compute_type": config.compute_type or "",
            "vad_filter": True,
            "vad_threshold": 0.5,
            "beam_size": config.beam_size,
            "enable_diarization": str(config.enable_diarization).lower(),
            "enable_alignment": str(config.enable_alignment).lower(),
            "request_id": request_id,
        }
        files = {"file": ("audio.wav", audio_wav, "audio/wav")}
        response = await self._client.post("/transcribe", data=data, files=files)
        response.raise_for_status()
        return response.json()


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        buffer.seek(0)
        return buffer.read()


class SessionState:
    def __init__(
        self,
        session_id: str,
        config: BatchASRConfig,
        sample_rate: int,
        asr_client: BatchASRClient,
        send_event: Callable[[Dict], Awaitable[None]],
        insight_callback: Callable[[str], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.sample_rate = sample_rate
        self._asr_client = asr_client
        self._send_event = send_event
        self._insight_callback = insight_callback
        self._pending = bytearray()
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=4)
        self._worker_task = asyncio.create_task(self._consume_queue())
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._closed = False
        self._last_flush_at = time.time()
        self._last_audio_at = time.time()
        self._batch_index = 0
        self._transcript_accumulated = ""
        self._total_tokens = 0
        self._total_batches = 0
        self._total_audio_seconds = 0.0
        self._max_pending_bytes = int(config.max_buffer_sec * sample_rate * 2)
        self._min_batch_samples = int(config.batch_window_sec * sample_rate)
        self._max_batch_samples = int(config.max_batch_window_sec * sample_rate)

    def _pending_duration(self) -> float:
        return len(self._pending) / float(self.sample_rate * 2)

    async def append_audio(self, pcm_bytes: bytes) -> None:
        if self._closed:
            return
        async with self._lock:
            self._last_audio_at = time.time()
            if len(self._pending) + len(pcm_bytes) > self._max_pending_bytes:
                excess = len(self._pending) + len(pcm_bytes) - self._max_pending_bytes
                if excess > 0:
                    del self._pending[:excess]
            self._pending.extend(pcm_bytes)
            await self._maybe_enqueue_chunk()

    async def flush(self, *, force: bool = False) -> None:
        async with self._lock:
            await self._maybe_enqueue_chunk(force=force)

    async def close(self) -> Dict[str, float]:
        if self._closed:
            return self._summary_payload()
        self._closed = True
        await self.flush(force=True)
        await self._queue.join()
        await self._queue.put(None)
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker_task
        self._flush_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._flush_task
        return self._summary_payload()

    @property
    def closed(self) -> bool:
        return self._closed

    async def _flush_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self.config.flush_interval_sec)
                if self._closed:
                    break
                duration = self._pending_duration()
                idle_time = time.time() - self._last_flush_at
                if duration >= (self._min_batch_samples / self.sample_rate):
                    await self.flush()
                elif duration > 0 and idle_time >= self.config.max_batch_window_sec:
                    await self.flush(force=True)
        except asyncio.CancelledError:
            pass

    async def _maybe_enqueue_chunk(self, force: bool = False) -> None:
        while self._pending:
            samples_available = len(self._pending) // 2
            if samples_available <= 0:
                break
            if not force and samples_available < self._min_batch_samples:
                break
            take_samples = min(samples_available, self._max_batch_samples)
            if take_samples <= 0:
                break
            take_bytes = take_samples * 2
            chunk = bytes(self._pending[:take_bytes])
            del self._pending[:take_bytes]
            self._last_flush_at = time.time()
            await self._queue.put(chunk)
            if not force:
                break

    async def _consume_queue(self) -> None:
        try:
            while True:
                chunk = await self._queue.get()
                if chunk is None:
                    self._queue.task_done()
                    break
                try:
                    await self._process_chunk(chunk)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception(
                        "batch_chunk_failed", session_id=self.session_id, error=str(exc)
                    )
                    await self._send_event(
                        {
                            "event": "batch_error",
                            "session_id": self.session_id,
                            "message": str(exc),
                        }
                    )
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            pass

    async def _process_chunk(self, chunk: bytes) -> None:
        wav_bytes = _pcm16_to_wav(chunk, self.sample_rate)
        duration_sec = len(chunk) / float(self.sample_rate * 2)
        self._batch_index += 1
        request_id = f"{self.session_id}-batch-{self._batch_index}"
        result = await self._asr_client.transcribe(
            wav_bytes,
            self.config,
            request_id=request_id,
        )
        text = (result.get("text") or "").strip()
        tokens = len(text.split())
        self._total_audio_seconds += duration_sec
        self._total_batches += 1
        self._total_tokens += tokens

        payload = {
            "event": "batch_processed",
            "session_id": self.session_id,
            "batch_index": self._batch_index,
            "duration_sec": round(duration_sec, 3),
            "transcript_chars": len(text),
            "model": self.config.model,
            "diarization": self.config.enable_diarization,
        }
        await self._send_event(payload)

        if text:
            if self._transcript_accumulated:
                self._transcript_accumulated = f"{self._transcript_accumulated} {text}".strip()
            else:
                self._transcript_accumulated = text
            await self._insight_callback(self._transcript_accumulated)

    def _summary_payload(self) -> Dict[str, float]:
        return {
            "total_batches": float(self._total_batches),
            "total_audio_seconds": float(round(self._total_audio_seconds, 3)),
            "total_tokens": float(self._total_tokens),
        }


class BatchSessionManager:
    def __init__(self, asr_client: BatchASRClient) -> None:
        self._asr_client = asr_client
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        session_id: str,
        config: BatchASRConfig,
        sample_rate: int,
        send_event: Callable[[Dict], Awaitable[None]],
        insight_callback: Callable[[str], Awaitable[None]],
    ) -> SessionState:
        session = SessionState(
            session_id=session_id,
            config=config,
            sample_rate=sample_rate,
            asr_client=self._asr_client,
            send_event=send_event,
            insight_callback=insight_callback,
        )
        async with self._lock:
            self._sessions[session_id] = session
        LOGGER.info("batch_session_created", session_id=session_id)
        return session

    async def get(self, session_id: str) -> Optional[SessionState]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def pop(self, session_id: str) -> Optional[SessionState]:
        async with self._lock:
            return self._sessions.pop(session_id, None)


settings = get_settings()
ASR_BASE = f"http://{settings.asr_host}:{settings.asr_port}"
batch_asr_client = BatchASRClient(ASR_BASE)
batch_session_manager = BatchSessionManager(batch_asr_client)


def parse_batch_config(payload: Dict[str, Any]) -> BatchASRConfig:
    min_window = float(payload.get("batch_window_sec", 5.0))
    max_window = float(payload.get("max_batch_window_sec", min_window * 2.0))
    min_window = _clamp(min_window, 3.0, 15.0)
    max_window = _clamp(max_window, min_window, 20.0)
    config = BatchASRConfig(
        language=payload.get("language", "auto"),
        model=payload.get("model", "whisper/medium"),
        compute_type=payload.get("compute_type"),
        beam_size=int(payload.get("beam_size", 5)),
        enable_diarization=bool(payload.get("enable_diarization", False)),
        enable_alignment=bool(payload.get("enable_alignment", False)),
        batch_window_sec=min_window,
        max_batch_window_sec=max_window,
        flush_interval_sec=float(payload.get("flush_interval_sec", 1.0)),
        max_buffer_sec=float(payload.get("max_buffer_sec", 60.0)),
    )
    return config


async def shutdown_batch_asr() -> None:
    await batch_asr_client.close()

import asyncio
import contextlib
import io
import json
import time
import wave
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, List

import structlog

from config import get_settings
from services.asr_client import transcribe_audio_bytes
from services.room_manager import room_manager
from services.llm_client import chat_completion
from services.llm_router import LLMTarget

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
    provider: str = "paneas"


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


class BatchASRClient:
    def __init__(self, base_url: str, timeout_sec: float = 30.0) -> None:  # noqa: D401 - kept for compatibility
        self._base_url = base_url
        self._timeout_sec = timeout_sec

    async def close(self) -> None:  # pragma: no cover - retained for interface compatibility
        return None

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
        return await transcribe_audio_bytes(
            audio_bytes=audio_wav,
            filename="audio.wav",
            content_type="audio/wav",
            options=data,
            provider=config.provider,
        )


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
        room_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.sample_rate = sample_rate
        self.room_id = room_id
        self.role = role
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

        # LLM Diarization tracking
        self._last_diarization_batch = 0
        self._diarization_interval_batches = 6  # Diarize every 6 batches (~30 seconds)
        self._diarization_task = None
        self._diarization_results = []
        self._is_diarizing = False

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

        # Perform final diarization if enabled
        if self.config.enable_diarization and self._transcript_accumulated:
            # Wait for any pending diarization to complete
            if self._diarization_task and not self._diarization_task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await self._diarization_task

            # Perform final diarization
            await self._perform_llm_diarization()

            # Send final diarization event
            if self._diarization_results:
                await self._send_event({
                    "event": "final_diarization",
                    "session_id": self.session_id,
                    "conversation": self._diarization_results,
                    "total_messages": len(self._diarization_results),
                })

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

        if text:
            if self._transcript_accumulated:
                self._transcript_accumulated = f"{self._transcript_accumulated} {text}".strip()
            else:
                self._transcript_accumulated = text
            await self._insight_callback(self._transcript_accumulated)
        transcript_snapshot = self._transcript_accumulated

        # Atualiza sala se aplicável
        if self.room_id and self.role:
            room_manager.update_transcript(
                room_id=self.room_id,
                session_id=self.session_id,
                transcript=transcript_snapshot,
            )

        payload = {
            "event": "batch_processed",
            "session_id": self.session_id,
            "batch_index": self._batch_index,
            "duration_sec": round(duration_sec, 3),
            "transcript_chars": len(text),
            "text": text,
            "transcript": transcript_snapshot,
            "tokens": tokens,
            "total_tokens": int(self._total_tokens),
            "model": self.config.model,
            "diarization": self.config.enable_diarization,
        }
        await self._send_event(payload)

        # Trigger LLM diarization periodically if enabled
        if self.config.enable_diarization and text:
            # Check if we should run diarization
            batches_since_last = self._batch_index - self._last_diarization_batch
            if batches_since_last >= self._diarization_interval_batches:
                self._last_diarization_batch = self._batch_index
                # Run diarization in background
                if self._diarization_task and not self._diarization_task.done():
                    # Cancel previous diarization if still running
                    self._diarization_task.cancel()
                self._diarization_task = asyncio.create_task(self._perform_llm_diarization())

    def _summary_payload(self) -> Dict[str, Any]:
        return {
            "total_batches": float(self._total_batches),
            "total_audio_seconds": float(round(self._total_audio_seconds, 3)),
            "total_tokens": float(self._total_tokens),
            "transcript": self._transcript_accumulated,
        }

    async def _perform_llm_diarization(self) -> None:
        """Perform LLM diarization on the accumulated transcript."""
        if self._is_diarizing or not self._transcript_accumulated:
            return

        self._is_diarizing = True
        try:
            LOGGER.info(
                "llm_diarization_started",
                session_id=self.session_id,
                batch_index=self._batch_index,
                transcript_length=len(self._transcript_accumulated),
            )

            # Prepare the diarization prompt
            diarization_prompt = f"""Você é um especialista em análise de transcrições de call center. Separe a transcrição em diálogo entre "Atendente" e "Cliente".

CARACTERÍSTICAS PARA IDENTIFICAÇÃO:

ATENDENTE (Operador/Vendedor):
- Se apresenta com nome e empresa (ex: "Meu nome é Carlos, sou da Claro")
- Faz perguntas sobre dados pessoais (CPF, nome completo, endereço)
- Oferece produtos, planos ou serviços
- Explica condições, valores e benefícios
- Usa linguagem mais formal e técnica
- Faz perguntas procedimentais ("Posso confirmar seus dados?")
- Pede confirmações ("Correto?", "Ok?", "Tudo bem?")
- Agradece e se despede formalmente

CLIENTE:
- Responde às perguntas do atendente
- Geralmente fala menos em cada turno
- Fornece dados pessoais quando solicitado
- Faz perguntas sobre o serviço
- Aceita ou recusa ofertas ("Sim", "Não", "Vamos", "Ok")
- Expressa dúvidas ou problemas pessoais
- Fala de forma mais informal

REGRAS IMPORTANTES:
1. O primeiro "Oi" ou "Alô" geralmente é do CLIENTE atendendo a ligação
2. Quem se apresenta com nome e empresa é SEMPRE o Atendente
3. Respostas curtas como "Sim", "Ok", "Tá" são geralmente do Cliente
4. Mantenha a ordem cronológica exata das falas
5. Cada mudança de speaker deve ser uma nova entrada
6. Corrija pequenos erros de transcrição mas mantenha o sentido

FORMATO DE SAÍDA:
Retorne APENAS um JSON array, sem explicações:
[{{"speaker": "Cliente", "text": "..."}}, {{"speaker": "Atendente", "text": "..."}}]

Transcrição para separar:
{self._transcript_accumulated}"""

            # Call LLM for diarization
            llm_payload = {
                "model": "paneas-q32b",
                "messages": [
                    {"role": "user", "content": diarization_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4000,
            }

            llm_response = await chat_completion(
                llm_payload,
                target=LLMTarget.INT4,
            )

            # Parse LLM response
            llm_content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to parse the JSON response
            conversation = []
            try:
                # Clean up the response
                cleaned_response = llm_content.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response.replace('```json\n', '').replace('```\n', '').replace('```', '')
                elif cleaned_response.startswith('```'):
                    cleaned_response = cleaned_response.replace('```\n', '').replace('```', '')

                conversation = json.loads(cleaned_response)

                if isinstance(conversation, list) and len(conversation) > 0:
                    self._diarization_results = conversation

                    # Send diarization update event
                    await self._send_event({
                        "event": "diarization_update",
                        "session_id": self.session_id,
                        "batch_index": self._batch_index,
                        "conversation": conversation,
                        "total_messages": len(conversation),
                    })

                    LOGGER.info(
                        "llm_diarization_completed",
                        session_id=self.session_id,
                        messages_count=len(conversation),
                    )

            except json.JSONDecodeError as e:
                LOGGER.error(
                    "llm_diarization_parse_error",
                    session_id=self.session_id,
                    error=str(e),
                    response_preview=llm_content[:200],
                )

        except Exception as e:
            LOGGER.exception(
                "llm_diarization_failed",
                session_id=self.session_id,
                error=str(e),
            )
        finally:
            self._is_diarizing = False


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
        room_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> SessionState:
        session = SessionState(
            session_id=session_id,
            config=config,
            sample_rate=sample_rate,
            asr_client=self._asr_client,
            send_event=send_event,
            insight_callback=insight_callback,
            room_id=room_id,
            role=role,
        )
        async with self._lock:
            self._sessions[session_id] = session
        LOGGER.info(
            "batch_session_created",
            session_id=session_id,
            room_id=room_id,
            role=role,
        )
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
    min_window = _clamp(min_window, 0.5, 15.0)
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
        provider=str(payload.get("provider", "paneas")).lower(),
    )
    return config


async def shutdown_batch_asr() -> None:
    await batch_asr_client.close()

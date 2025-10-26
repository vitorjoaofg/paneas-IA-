import asyncio
import base64
import io
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading
from queue import Queue

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from faster_whisper import WhisperModel
from httpx import Client

MODELS_ROOT = Path(os.environ.get("MODELS_DIR", "/models"))
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "whisper/medium")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "int8_float16")
MODEL_REPLICAS = int(os.environ.get("MODEL_REPLICAS", "1"))
GPU_DEVICE = os.environ.get("CUDA_VISIBLE_DEVICES", "0").split(",")[0]
DIAR_SERVICE_URL = os.environ.get("DIAR_SERVICE_URL", "http://diar:9003/diarize")

app = FastAPI(title="ASR Service", version="1.0.0")


class ASRService:
    def __init__(self, model_name: str, compute_type: str, replicas: int) -> None:
        self.default_model_name = model_name
        self.default_compute_type = compute_type
        self._replicas = max(1, replicas)
        self._model_pools: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._global_lock = threading.Lock()
        # Pre-load default pool so the first request avoids the download cost.
        self._ensure_model_pool(model_name, compute_type)

    def _warmup(self, model: WhisperModel) -> None:
        dummy_audio = np.zeros(16000, dtype=np.float32)
        list(model.transcribe(dummy_audio, beam_size=1))

    @staticmethod
    def _resolve_model_path(model_name: str) -> Path:
        candidate = MODELS_ROOT / model_name
        if candidate.exists():
            return candidate
        alt_path = MODELS_ROOT / "whisper" / model_name
        if alt_path.exists():
            return alt_path
        raise RuntimeError(f"Model path not found: {candidate}")

    def _create_model(self, model_name: str, compute_type: str) -> WhisperModel:
        model_path = self._resolve_model_path(model_name)
        whisper_model = WhisperModel(
            str(model_path),
            device="cuda",
            compute_type=compute_type,
            cpu_threads=8,
            num_workers=4,
            download_root=str(MODELS_ROOT),
        )
        self._warmup(whisper_model)
        return whisper_model

    def _ensure_model_pool(self, model_name: str, compute_type: str) -> Dict[str, Any]:
        key = (model_name, compute_type)
        pool = self._model_pools.get(key)
        if pool is not None:
            return pool

        with self._global_lock:
            pool = self._model_pools.get(key)
            if pool is not None:
                return pool

            models: List[WhisperModel] = []
            for _ in range(self._replicas):
                models.append(self._create_model(model_name, compute_type))

            queue: Queue = Queue(maxsize=len(models))
            for idx in range(len(models)):
                queue.put(idx)

            pool = {"models": models, "queue": queue}
            self._model_pools[key] = pool
            return pool

    def transcribe(self, audio: np.ndarray, sample_rate: int, options: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        opts = dict(options)
        language = opts.get("language", "auto")
        if language and str(language).lower() == "auto":
            language = None

        model_name = str(opts.get("model", self.default_model_name))
        compute_type = str(opts.get("compute_type", self.default_compute_type))

        pool = self._ensure_model_pool(model_name, compute_type)
        queue: Queue = pool["queue"]
        idx = queue.get()
        model = pool["models"][idx]

        vad_threshold = float(opts.get("vad_threshold", 0.5))
        vad_filter = _to_bool(opts.get("vad_filter", True), default=True)
        beam_size = int(opts.get("beam_size", 5))
        enable_alignment = _to_bool(opts.get("enable_alignment", False))
        enable_diarization = _to_bool(opts.get("enable_diarization", False))

        try:
            segments, info = model.transcribe(
                audio,
                beam_size=beam_size,
                best_of=3,
                vad_filter=vad_filter,
                vad_parameters=dict(
                    threshold=vad_threshold,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=500,
                ),
                language=language,
            )
        finally:
            queue.put(idx)

        duration_seconds = float(len(audio) / sample_rate)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        result_segments = []
        for segment in segments:
            result = {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text,
                "words": [],
            }
            if enable_alignment and segment.words:
                result["words"] = [
                    {
                        "start": float(word.start),
                        "end": float(word.end),
                        "word": word.word,
                        "confidence": float(word.probability or 0.0),
                    }
                    for word in segment.words
                ]
            result_segments.append(result)

        if enable_diarization:
            diar_segments = self._diarize(audio, sample_rate)
            self._apply_diarization(result_segments, diar_segments)

        detected_language = getattr(info, "language", None) or (language or "unknown")

        return {
            "request_id": options.get("request_id", str(uuid.uuid4())),
            "duration_seconds": duration_seconds,
            "processing_time_ms": elapsed_ms,
            "language": detected_language,
            "text": " ".join(segment["text"].strip() for segment in result_segments).strip(),
            "segments": result_segments,
            "metadata": {
                "model": model_name,
                "compute_type": compute_type,
                "gpu_id": int(GPU_DEVICE or 0),
            },
        }

    def _diarize(self, audio: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        if not DIAR_SERVICE_URL:
            return []
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            sf.write(tmp.name, audio, sample_rate)
            tmp.seek(0)
            files = {"file": ("audio.wav", tmp.read(), "audio/wav")}
        try:
            with Client(timeout=30.0) as client:
                response = client.post(DIAR_SERVICE_URL, files=files)
                response.raise_for_status()
                payload = response.json()
                return payload.get("segments", [])
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _apply_diarization(segments: List[Dict[str, Any]], diar_segments: List[Dict[str, Any]]) -> None:
        if not diar_segments:
            for segment in segments:
                segment["speaker"] = "SPEAKER_00"
            return

        for segment in segments:
            mid_point = (segment["start"] + segment["end"]) / 2
            candidates = [
                diar for diar in diar_segments if diar["start"] <= mid_point <= diar["end"]
            ]
            if candidates:
                segment["speaker"] = candidates[0]["speaker"]
            else:
                segment["speaker"] = "SPEAKER_00"


def load_audio(contents: bytes) -> tuple[np.ndarray, int]:
    with io.BytesIO(contents) as buffer:
        audio, sr = sf.read(buffer)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    target_sr = 16000
    if sr != target_sr:
        # Resample using numpy simple method to avoid heavy deps
        duration = audio.shape[0] / sr
        target_length = int(duration * target_sr)
        audio = np.interp(
            np.linspace(0.0, 1.0, target_length),
            np.linspace(0.0, 1.0, audio.shape[0]),
            audio,
        )
        sr = target_sr
    return audio.astype(np.float32), int(sr)


service = ASRService(model_name=DEFAULT_MODEL, compute_type=COMPUTE_TYPE, replicas=MODEL_REPLICAS)


def decode_audio_chunk(chunk_b64: str, encoding: str) -> np.ndarray:
    if encoding.lower() != "pcm16":
        raise ValueError(f"Unsupported encoding: {encoding}")
    raw = base64.b64decode(chunk_b64)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


class StreamingSession:
    def __init__(
        self,
        request_id: str,
        sample_rate: int,
        options: Dict[str, Any],
        min_slice_seconds: float = 1.5,
        context_seconds: float = 2.5,
        min_emit_seconds: float = 0.0,
    ) -> None:
        self.request_id = request_id
        self.sample_rate = sample_rate
        self.options = options
        self.min_slice_seconds = min_slice_seconds
        self.context_seconds = max(context_seconds, 0.0)
        self._max_context_samples = int(self.context_seconds * self.sample_rate)

        self._pending_audio: List[np.ndarray] = []
        self._context_audio = np.zeros(0, dtype=np.float32)
        self._processed_seconds = 0.0

        self._segments: List[Dict[str, Any]] = []
        self._history_text = ""
        self._metadata: Dict[str, Any] = {
            "model": str(options.get("model", DEFAULT_MODEL)),
            "compute_type": str(options.get("compute_type", COMPUTE_TYPE)),
            "gpu_id": int(GPU_DEVICE or 0),
        }
        self._last_sent_text = ""
        self._last_emit_ts: float = 0.0
        self.min_emit_seconds = max(min_emit_seconds, 0.0)
        self._pending_emit = False

    def append_chunk(self, chunk: np.ndarray) -> None:
        if chunk.size == 0:
            return
        self._pending_audio.append(chunk.astype(np.float32))

    def pending_duration(self) -> float:
        total_samples = sum(arr.shape[0] for arr in self._pending_audio)
        return total_samples / float(self.sample_rate or 1)

    def should_transcribe(self) -> bool:
        return self.pending_duration() >= self.min_slice_seconds

    def _assemble_audio(self) -> Tuple[np.ndarray, int, int]:
        if not self._pending_audio:
            return np.empty(0, dtype=np.float32), 0, 0

        new_audio = np.concatenate(self._pending_audio, axis=0)
        if self._context_audio.size:
            audio = np.concatenate([self._context_audio, new_audio])
        else:
            audio = new_audio
        return audio, self._context_audio.shape[0], new_audio.shape[0]

    def _update_context(self, audio: np.ndarray) -> None:
        if self._max_context_samples <= 0 or audio.size == 0:
            self._context_audio = np.zeros(0, dtype=np.float32)
            return
        if audio.shape[0] <= self._max_context_samples:
            self._context_audio = audio.copy()
        else:
            self._context_audio = audio[-self._max_context_samples :].copy()

    def ingest_transcription(
        self,
        result: Dict[str, Any],
        audio: np.ndarray,
        context_samples: int,
        new_samples: int,
    ) -> bool:
        context_duration = context_samples / float(self.sample_rate or 1)
        new_duration = new_samples / float(self.sample_rate or 1)
        base_time = max(self._processed_seconds - context_duration, 0.0)
        new_segments_added = False

        metadata = result.get("metadata") or {}
        if metadata:
            self._metadata.update(metadata)

        for segment in result.get("segments", []):
            local_start = float(segment.get("start", 0.0))
            local_end = float(segment.get("end", 0.0))
            global_start = base_time + local_start
            global_end = base_time + local_end

            if global_end <= self._processed_seconds + 1e-3:
                continue

            clipped_start = max(global_start, self._processed_seconds)
            clipped_text = (segment.get("text") or "").strip()
            if not clipped_text:
                continue

            words_payload: List[Dict[str, Any]] = []
            for word in segment.get("words") or []:
                w_start = base_time + float(word.get("start", local_start))
                w_end = base_time + float(word.get("end", local_end))
                if w_end <= self._processed_seconds + 1e-3:
                    continue
                words_payload.append(
                    {
                        "start": max(w_start, self._processed_seconds),
                        "end": w_end,
                        "word": word.get("word", ""),
                        "confidence": float(word.get("confidence") or word.get("probability") or 0.0),
                    }
                )

            segment_payload = {
                "start": clipped_start,
                "end": global_end,
                "text": clipped_text,
                "speaker": segment.get("speaker"),
                "words": words_payload,
            }
            self._segments.append(segment_payload)
            if self._history_text:
                self._history_text = f"{self._history_text} {clipped_text}".strip()
            else:
                self._history_text = clipped_text
            new_segments_added = True

        self._processed_seconds += new_duration
        self._pending_audio = []
        self._update_context(audio)

        if new_segments_added:
            self._pending_emit = True

        return new_segments_added

    def has_new_text(self, now: float) -> bool:
        if not self._pending_emit:
            return False
        if self.min_emit_seconds <= 0.0:
            return True
        return (now - self._last_emit_ts) >= self.min_emit_seconds

    def mark_sent(self) -> None:
        self._last_sent_text = self._history_text
        self._last_emit_ts = time.time()
        self._pending_emit = False

    def build_response(self, is_final: bool) -> Dict[str, Any]:
        segments = []
        for segment in self._segments:
            payload = {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
            }
            if segment.get("speaker") is not None:
                payload["speaker"] = segment["speaker"]
            payload["words"] = [dict(word) for word in segment.get("words", [])]
            segments.append(payload)

        return {
            "event": "final" if is_final else "partial",
            "is_final": is_final,
            "request_id": self.request_id,
            "text": self._history_text,
            "segments": segments,
            "metadata": dict(self._metadata),
        }

    def has_history(self) -> bool:
        return bool(self._segments or self._history_text)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "up",
        "model": service.default_model_name,
        "compute_type": service.default_compute_type,
    }


@app.post("/transcribe")
async def transcribe(  # noqa: PLR0913
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model: str = Form(DEFAULT_MODEL),
    enable_diarization: bool = Form(False),
    enable_alignment: bool = Form(False),
    compute_type: str = Form(COMPUTE_TYPE),
    vad_filter: bool = Form(True),
    vad_threshold: float = Form(0.5),
    beam_size: int = Form(5),
    request_id: str | None = Form(None),
):
    contents = await file.read()
    audio, sample_rate = load_audio(contents)
    options = {
        "language": language,
        "model": model,
        "enable_diarization": enable_diarization,
        "enable_alignment": enable_alignment,
        "compute_type": compute_type,
        "vad_filter": vad_filter,
        "vad_threshold": vad_threshold,
        "beam_size": beam_size,
    }
    if request_id:
        options["request_id"] = request_id
    result = service.transcribe(audio, sample_rate, options)
    return result


async def _run_transcription(
    session: StreamingSession,
    *,
    force: bool = False,
    is_final: bool = False,
) -> Optional[Dict[str, Any]]:
    if not force and not is_final and not session.should_transcribe():
        return None

    audio, context_samples, new_samples = session._assemble_audio()
    if audio.size == 0:
        if is_final:
            return session.build_response(is_final=True)
        return None

    options = {**session.options, "request_id": session.request_id}
    loop = asyncio.get_running_loop()
    result: Dict[str, Any] = await loop.run_in_executor(
        None, service.transcribe, audio, session.sample_rate, options
    )
    new_segments = session.ingest_transcription(result, audio, context_samples, new_samples)
    print(
        "stream_transcribe",
        session.request_id,
        context_samples / float(session.sample_rate or 1),
        new_samples / float(session.sample_rate or 1),
        session._processed_seconds,
        new_segments,
        flush=True,
    )

    if not is_final:
        if session.has_new_text(time.time()):
            print("stream_emit_partial", session.request_id, flush=True)
            return session.build_response(is_final=False)
        return None

    if not session.has_history():
        return {
            "event": "final",
            "is_final": True,
            "request_id": session.request_id,
            "text": "",
            "segments": [],
            "metadata": dict(session._metadata),
        }
    return session.build_response(is_final=True)


@app.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())
    await websocket.send_json({"event": "ready", "session_id": session_id})

    try:
        message = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await websocket.send_json({"event": "error", "message": "Invalid JSON payload"})
        await websocket.close(code=1003)
        return

    if message.get("event") != "start":
        await websocket.send_json({"event": "error", "message": "Expected start event"})
        await websocket.close(code=4400)
        return

    sample_rate = int(message.get("sample_rate", 16000))
    encoding = message.get("encoding", "pcm16")
    language = message.get("language", "auto")
    model = message.get("model", DEFAULT_MODEL)
    beam_size = int(message.get("beam_size", 5))
    vad_filter = bool(message.get("vad_filter", True))
    vad_threshold = float(message.get("vad_threshold", 0.5))

    options = {
        "language": language,
        "model": model,
        "beam_size": beam_size,
        "vad_filter": vad_filter,
        "vad_threshold": vad_threshold,
        "enable_alignment": bool(message.get("enable_alignment", False)),
        "enable_diarization": bool(message.get("enable_diarization", False)),
        "compute_type": message.get("compute_type", COMPUTE_TYPE),
    }

    session = StreamingSession(
        request_id=session_id,
        sample_rate=sample_rate,
        options=options,
        min_slice_seconds=float(message.get("emit_interval_sec", 1.5)),
    )

    await websocket.send_json({"event": "session_started", "session_id": session_id})

    client_disconnected = False
    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "message": "Invalid JSON payload"})
                continue
            except WebSocketDisconnect:
                client_disconnected = True
                break

            event = payload.get("event")
            if event == "audio":
                chunk_b64 = payload.get("chunk")
                if not chunk_b64:
                    await websocket.send_json({"event": "error", "message": "Missing chunk data"})
                    continue
                try:
                    chunk = decode_audio_chunk(chunk_b64, encoding)
                except ValueError as exc:
                    await websocket.send_json({"event": "error", "message": str(exc)})
                    continue

                session.append_chunk(chunk)
                response_payload = await _run_transcription(session)
                if response_payload:
                    try:
                        await websocket.send_json(response_payload)
                        session.mark_sent()
                    except WebSocketDisconnect:
                        client_disconnected = True
                        break

            elif event == "stop":
                final_payload = await _run_transcription(session, force=True, is_final=True)
                if final_payload is None and session.has_history():
                    final_payload = session.build_response(is_final=True)
                if final_payload is not None and not client_disconnected:
                    try:
                        await websocket.send_json(final_payload)
                        session.mark_sent()
                    except WebSocketDisconnect:
                        client_disconnected = True
                if not client_disconnected:
                    try:
                        await websocket.send_json({"event": "session_ended", "session_id": session_id})
                    except WebSocketDisconnect:
                        client_disconnected = True
                if not client_disconnected:
                    try:
                        await websocket.close()
                    except (WebSocketDisconnect, RuntimeError):
                        client_disconnected = True
                return
            else:
                await websocket.send_json({"event": "error", "message": f"Unknown event: {event}"})

    finally:
        if not client_disconnected and websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except (WebSocketDisconnect, RuntimeError):
                pass
BOOLEAN_TRUE = {"1", "true", "yes", "on", "y"}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in BOOLEAN_TRUE
    return bool(value)

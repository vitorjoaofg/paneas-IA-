import asyncio
import io
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf
from fastapi import FastAPI
from httpx import AsyncClient
from faster_whisper import WhisperModel
from minio import Minio
from prometheus_fastapi_instrumentator import Instrumentator

MODELS_ROOT = Path(os.environ.get("MODELS_DIR", "/models"))
MODEL_NAME = os.environ.get("MODEL_NAME", "large-v3-turbo")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "aistack")
MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
DIAR_SERVICE_URL = os.environ.get("DIAR_SERVICE_URL", "http://diar:9003/diarize")

app = FastAPI(title="Align Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


class AudioAligner:
    def __init__(self) -> None:
        model_path = MODELS_ROOT / MODEL_NAME
        if not model_path.exists():
            alt_path = MODELS_ROOT / "whisper" / MODEL_NAME
            if alt_path.exists():
                model_path = alt_path
            else:
                raise RuntimeError(f"Whisper model not found at {model_path}")
        self.model = WhisperModel(
            str(model_path),
            device="cuda",
            compute_type="float16",
            cpu_threads=8,
            num_workers=2,
        )
        self.minio = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        self._warmup()

    def _warmup(self) -> None:
        dummy_audio = np.zeros(16000, dtype=np.float32)
        list(self.model.transcribe(dummy_audio, beam_size=1, word_timestamps=True))

    async def download_audio(self, uri: str) -> Path:
        if uri.startswith("s3://"):
            bucket, _, object_name = uri[5:].partition("/")
            tmp_dir = tempfile.mkdtemp(prefix="align-audio-")
            target_path = Path(tmp_dir) / Path(object_name).name
            await asyncio.to_thread(
                self.minio.fget_object,
                bucket,
                object_name,
                str(target_path),
            )
            return target_path
        return Path(uri)

    def _load_audio(self, path: Path) -> np.ndarray:
        audio, sr = sf.read(path)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if sr != 16000:
            duration = audio.shape[0] / sr
            target = int(duration * 16000)
            audio = np.interp(
                np.linspace(0.0, 1.0, target),
                np.linspace(0.0, 1.0, audio.shape[0]),
                audio,
            )
        return audio.astype(np.float32)

    def align(self, audio: np.ndarray) -> Dict[str, Any]:
        start = time.perf_counter()
        segments, info = self.model.transcribe(
            audio,
            beam_size=5,
            best_of=3,
            word_timestamps=True,
            vad_filter=True,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        data = []
        for segment in segments:
            words = [
                {
                    "start": float(word.start),
                    "end": float(word.end),
                    "word": word.word,
                    "confidence": float(word.probability or 0.0),
                }
                for word in segment.words or []
            ]
            data.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment.text,
                    "words": words,
                }
            )
        return {
            "segments": data,
            "language": info.language,
            "duration_seconds": float(len(audio) / 16000.0),
            "processing_time_ms": elapsed_ms,
        }

    async def diarize(self, audio_path: Path, num_speakers: int | None) -> List[Dict[str, Any]]:
        try:
            async with AsyncClient(timeout=30.0) as client:
                with audio_path.open("rb") as handle:
                    files = {"file": (audio_path.name, handle, "audio/wav")}
                    data: Dict[str, Any] = {}
                    if num_speakers:
                        data["num_speakers"] = str(num_speakers)
                    response = await client.post(DIAR_SERVICE_URL, files=files, data=data)
                    response.raise_for_status()
                    return response.json().get("segments", [])
        except Exception as exc:  # noqa: BLE001
            return []

    @staticmethod
    def merge_diarization(segments: List[Dict[str, Any]], diar_segments: List[Dict[str, Any]]) -> None:
        if not diar_segments:
            return
        for segment in segments:
            mid_point = (segment["start"] + segment["end"]) / 2
            candidates = [
                d for d in diar_segments if d["start"] <= mid_point <= d["end"]
            ]
            if candidates:
                segment["speaker"] = candidates[0]["speaker"]
            else:
                segment["speaker"] = "SPEAKER_00"


service = AudioAligner()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "up", "model": MODEL_NAME}


@app.post("/align_diarize")
async def align_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    request_id = payload.get("transcript_id", str(uuid.uuid4()))
    audio_uri = payload.get("audio_uri")
    if not audio_uri:
        return {"job_id": request_id, "status": "failed", "reason": "missing_audio_uri"}

    audio_path = await service.download_audio(audio_uri)
    audio = service._load_audio(audio_path)
    alignment = service.align(audio)

    if payload.get("enable_diarization"):
        diar_segments = await service.diarize(audio_path, payload.get("num_speakers"))
        service.merge_diarization(alignment["segments"], diar_segments)

    result = {
        "job_id": request_id,
        "status": "completed",
        "results": alignment,
    }
    return result

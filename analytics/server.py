import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

import librosa
import numpy as np
from fastapi import FastAPI
from minio import Minio
from pydantic import BaseModel
from redis.asyncio import Redis

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "aistack")
MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB_CELERY", "1"))

app = FastAPI(title="Speech Analytics Service", version="1.0.0")


class SpeechAnalyticsRequest(BaseModel):
    call_id: uuid.UUID
    audio_uri: str
    transcript_uri: str
    analysis_types: List[str]
    keywords: List[str] = []


class AnalyticsEngine:
    def __init__(self) -> None:
        self.minio = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        self.redis: Redis | None = None

    async def connect(self) -> None:
        self.redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.close()
            self.redis = None

    async def submit_job(self, payload: SpeechAnalyticsRequest) -> uuid.UUID:
        job_id = uuid.uuid4()
        await self._set_status(job_id, "processing")
        asyncio.create_task(self._process_job(job_id, payload))
        return job_id

    async def _process_job(self, job_id: uuid.UUID, payload: SpeechAnalyticsRequest) -> None:
        try:
            audio_path = await asyncio.to_thread(self._download_from_minio, payload.audio_uri)
            data, sr = librosa.load(audio_path, sr=16000)
            results: Dict[str, Any] = {}
            if "vad_advanced" in payload.analysis_types:
                results["vad"] = self._compute_vad(data, sr)
            if "prosody" in payload.analysis_types:
                results["prosody"] = self._compute_prosody(data, sr)
            if "emotion" in payload.analysis_types:
                results["emotion"] = self._compute_emotion(data, sr)
            if "keywords" in payload.analysis_types:
                results["keywords"] = self._keyword_spotting(data, sr, payload.keywords)
            if "summary" in payload.analysis_types:
                results["summary"] = self._summarize_transcript(payload.transcript_uri)

            await self._store_result(job_id, {"status": "completed", "results": results})
        except Exception as exc:  # noqa: BLE001
            await self._store_result(job_id, {"status": "failed", "error": str(exc)})

    def _download_from_minio(self, uri: str) -> Path:
        if not uri.startswith("s3://"):
            return Path(uri)
        bucket, _, object_name = uri[5:].partition("/")
        target = Path("/tmp") / Path(object_name).name
        self.minio.fget_object(bucket, object_name, str(target))
        return target

    @staticmethod
    def _compute_vad(data: np.ndarray, sr: int) -> Dict[str, Any]:
        energy = np.abs(librosa.feature.rms(y=data)).mean()
        speech_ratio = float(min(1.0, energy * 10))
        return {"speech_ratio": speech_ratio, "silence_segments": []}

    @staticmethod
    def _compute_prosody(data: np.ndarray, sr: int) -> Dict[str, Any]:
        tempo, _ = librosa.beat.beat_track(y=data, sr=sr)
        pitch = librosa.yin(data, fmin=50, fmax=400, sr=sr)
        return {
            "avg_pause_duration_ms": 450,
            "overlapping_speech_ratio": 0.12,
            "speech_rate_wpm": float(tempo * 2),
            "avg_pitch": float(np.nanmean(pitch)),
        }

    @staticmethod
    def _compute_emotion(data: np.ndarray, sr: int) -> Dict[str, Any]:
        spec = librosa.feature.melspectrogram(y=data, sr=sr)
        intensity = float(np.mean(spec))
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": len(data) / sr,
                    "arousal": intensity * 0.1,
                    "valence": 0.5,
                }
            ]
        }

    @staticmethod
    def _keyword_spotting(data: np.ndarray, sr: int, keywords: List[str]) -> List[str]:
        return keywords

    def _summarize_transcript(self, uri: str) -> str:
        if not uri.startswith("s3://"):
            return "Resumo indisponível"
        bucket, _, object_name = uri[5:].partition("/")
        response = self.minio.get_object(bucket, object_name)
        content = response.read()
        response.close()
        response.release_conn()
        try:
            text = json.loads(content).get("text", "")
        except json.JSONDecodeError:
            text = content.decode("utf-8")
        return text[:200]

    async def _set_status(self, job_id: uuid.UUID, status: str) -> None:
        if self.redis is None:
            raise RuntimeError("Redis client not initialized")
        await self.redis.set(f"analytics:{job_id}", json.dumps({"status": status}))

    async def _store_result(self, job_id: uuid.UUID, data: Dict[str, Any]) -> None:
        if self.redis is None:
            raise RuntimeError("Redis client not initialized")
        await self.redis.set(f"analytics:{job_id}", json.dumps(data))

    async def get_job(self, job_id: uuid.UUID) -> Dict[str, Any]:
        if self.redis is None:
            raise RuntimeError("Redis client not initialized")
        data = await self.redis.get(f"analytics:{job_id}")
        if data is None:
            return {"status": "not_found"}
        return json.loads(data)


engine = AnalyticsEngine()


@app.on_event("startup")
async def startup() -> None:
    await engine.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.close()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up"}


@app.post("/analytics/speech", status_code=202)
async def submit(payload: SpeechAnalyticsRequest) -> Dict[str, Any]:
    job_id = await engine.submit_job(payload)
    return {"job_id": str(job_id), "status": "processing"}


@app.get("/analytics/speech/{job_id}")
async def get_job(job_id: uuid.UUID) -> Dict[str, Any]:
    data = await engine.get_job(job_id)
    return {"job_id": str(job_id), **data}

import io
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from TTS.api import TTS
from minio import Minio
import torch
from prometheus_fastapi_instrumentator import Instrumentator

MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/models/xtts"))
VOICES_DIR = Path(os.environ.get("VOICES_DIR", "/voices"))
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "aistack")
MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
SAMPLE_RATE = int(os.environ.get("TTS_SAMPLE_RATE", "16000"))

VOICES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TTS Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


class TTSRequest(BaseModel):
    text: str
    language: str = "pt"
    speaker_reference: str | None = None
    streaming: bool = False
    format: str = "wav"


class TTSService:
    def __init__(self) -> None:
        if not MODELS_DIR.exists():
            raise RuntimeError(f"XTTS model directory not found: {MODELS_DIR}")
        config_path = None
        speakers_path = None
        for file in MODELS_DIR.glob("*.json"):
            if file.name.endswith("config.json"):
                config_path = file
        # Look for the XTTS speakers embedding file.
        candidate = MODELS_DIR / "speakers_xtts.pth"
        if candidate.exists():
            speakers_path = candidate
        kwargs: Dict[str, Any] = {
            "model_path": str(MODELS_DIR),
            "progress_bar": False,
            "gpu": True,
        }
        if config_path:
            kwargs["config_path"] = str(config_path)
        self.tts = TTS(**kwargs)
        self.available_speakers: List[str] = []
        if speakers_path and speakers_path.exists():
            try:
                data = torch.load(str(speakers_path), map_location="cpu")
                if isinstance(data, dict):
                    self.available_speakers = [str(name) for name in data.keys()]
            except Exception:  # noqa: BLE001
                pass
        if self.available_speakers:
            print(f"[TTS] Loaded {len(self.available_speakers)} speakers. Defaulting to {self.available_speakers[0]}")
        else:
            print("[TTS] No speaker list found, will rely on caller-provided references.")
        self.minio = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        self._warmup()

    def _warmup(self) -> None:
        speaker = self.available_speakers[0] if self.available_speakers else None
        try:
            self.tts.tts(
                text="Warmup",
                speaker_wav=None,
                speaker=speaker,
                language="pt",
            )
        except Exception:
            pass

    def _download_voice(self, uri: str) -> Path:
        if uri.startswith("s3://"):
            bucket, _, object_name = uri[5:].partition("/")
            target = VOICES_DIR / Path(object_name).name
            if not target.exists():
                self.minio.fget_object(bucket, object_name, str(target))
            return target
        return Path(uri)

    def synthesize(self, payload: TTSRequest) -> Dict[str, Any]:
        speaker_wav = None
        speaker_id = None
        if payload.speaker_reference:
            speaker_path = self._download_voice(payload.speaker_reference)
            if not speaker_path.exists():
                raise HTTPException(status_code=404, detail="Speaker reference not found")
            speaker_wav = str(speaker_path)
        else:
            if self.available_speakers:
                speaker_id = self.available_speakers[0]

        audio = self.tts.tts(
            text=payload.text,
            speaker_wav=speaker_wav,
            speaker=speaker_id,
            language=payload.language,
        )
        audio = np.array(audio, dtype=np.float32)
        peak = np.max(np.abs(audio)) or 1.0
        audio = audio / peak
        buffer = io.BytesIO()
        sf.write(buffer, audio, SAMPLE_RATE, format="WAV")
        return {
            "request_id": str(uuid.uuid4()),
            "sample_rate": SAMPLE_RATE,
            "duration_seconds": audio.shape[0] / SAMPLE_RATE,
            "format": payload.format,
            "content_type": "audio/wav",
            "audio_bytes": buffer.getvalue(),
        }


service = TTSService()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up", "model": "XTTS-v2"}


@app.post("/synthesize")
async def synthesize(payload: TTSRequest) -> Any:
    result = service.synthesize(payload)
    headers = {
        "X-Request-ID": result["request_id"],
        "X-Audio-Sample-Rate": str(result["sample_rate"]),
        "X-Audio-Duration": f"{result['duration_seconds']:.3f}",
    }
    return Response(content=result["audio_bytes"], media_type=result["content_type"], headers=headers)

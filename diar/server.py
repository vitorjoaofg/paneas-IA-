import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from pyannote.audio import Pipeline
import torch

CACHE_DIR = Path(os.environ.get("EMBEDDINGS_CACHE", "/cache/embeddings"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_NAME = os.environ.get("PYANNOTE_MODEL", "pyannote/speaker-diarization-3.1")
HF_TOKEN = os.environ.get("HF_TOKEN")

app = FastAPI(title="Diarization Service", version="1.0.0")


class DiarizationEngine:
    def __init__(self) -> None:
        if HF_TOKEN is None:
            raise RuntimeError("HF_TOKEN must be set for Pyannote models")
        self.pipeline = Pipeline.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)
        self.pipeline.to(torch.device("cuda"))

    def diarize(self, audio_path: Path, num_speakers: int | None) -> List[Dict[str, Any]]:
        if num_speakers:
            diarization = self.pipeline(audio_path, num_speakers=num_speakers)
        else:
            diarization = self.pipeline(audio_path)
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                {
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                    "speaker": speaker,
                }
            )
        return segments


engine = DiarizationEngine()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up", "model": MODEL_NAME}


@app.post("/diarize")
async def diarize_endpoint(
    file: UploadFile = File(...),
    num_speakers: int | None = Form(None),
) -> Dict[str, Any]:
    contents = await file.read()
    audio_hash = hashlib.sha256(contents).hexdigest()
    cache_file = CACHE_DIR / f"{audio_hash}.wav"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    if not cache_file.exists():
        with cache_file.open("wb") as handle:
            handle.write(contents)
    segments = engine.diarize(cache_file, num_speakers)
    return {"segments": segments}

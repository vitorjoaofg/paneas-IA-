import io
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from faster_whisper import WhisperModel
from httpx import Client

MODELS_ROOT = Path(os.environ.get("MODELS_DIR", "/models"))
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "large-v3-turbo")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "fp16")
GPU_DEVICE = os.environ.get("CUDA_VISIBLE_DEVICES", "0").split(",")[0]
DIAR_SERVICE_URL = os.environ.get("DIAR_SERVICE_URL", "http://diar:9003/diarize")

app = FastAPI(title="ASR Service", version="1.0.0")


class ASRService:
    def __init__(self, model_name: str, compute_type: str) -> None:
        model_path = MODELS_ROOT / model_name
        if not model_path.exists():
            alt_path = MODELS_ROOT / "whisper" / model_name
            if alt_path.exists():
                model_path = alt_path
            else:
                raise RuntimeError(f"Model path not found: {model_path}")

        self.model_name = model_name
        self.compute_type = compute_type
        self.model = WhisperModel(
            str(model_path),
            device="cuda",
            compute_type=compute_type,
            cpu_threads=8,
            num_workers=4,
            download_root=str(MODELS_ROOT),
        )
        self._warmup()

    def _warmup(self) -> None:
        dummy_audio = np.zeros(16000, dtype=np.float32)
        list(self.model.transcribe(dummy_audio, beam_size=1))

    def transcribe(self, audio: np.ndarray, sample_rate: int, options: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        language = options.get("language", "auto")
        if language and str(language).lower() == "auto":
            language = None

        segments, info = self.model.transcribe(
            audio,
            beam_size=int(options.get("beam_size", 5)),
            best_of=3,
            vad_filter=options.get("vad_filter", True),
            vad_parameters=dict(
                threshold=float(options.get("vad_threshold", 0.5)),
                min_speech_duration_ms=250,
                min_silence_duration_ms=500,
            ),
            language=language,
        )

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
            if options.get("enable_alignment") and segment.words:
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

        if options.get("enable_diarization"):
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
                "model": self.model_name,
                "compute_type": self.compute_type,
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


service = ASRService(model_name=DEFAULT_MODEL, compute_type=COMPUTE_TYPE)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "up", "model": service.model_name, "compute_type": service.compute_type}


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

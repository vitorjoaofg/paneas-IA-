import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from pyannote.audio import Pipeline
import torch
from prometheus_fastapi_instrumentator import Instrumentator

CACHE_DIR = Path(os.environ.get("EMBEDDINGS_CACHE", "/cache/embeddings"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Set HuggingFace cache to use local models
os.environ["HF_HOME"] = "/models"
os.environ["TRANSFORMERS_CACHE"] = "/models"

MODEL_NAME = os.environ.get("PYANNOTE_MODEL", "pyannote/speaker-diarization-3.1")
HF_TOKEN = os.environ.get("HF_TOKEN")

app = FastAPI(title="Diarization Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


class DiarizationEngine:
    def __init__(self) -> None:
        # Load model from HuggingFace Hub or local cache
        if HF_TOKEN:
            self.pipeline = Pipeline.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)
        else:
            self.pipeline = Pipeline.from_pretrained(MODEL_NAME)
        self.pipeline.to(torch.device("cuda"))

        # Optimize batch processing for faster inference
        # Configure batch sizes for segmentation and embedding components
        if hasattr(self.pipeline, '_segmentation') and hasattr(self.pipeline._segmentation, 'model'):
            self.pipeline._segmentation.batch_size = 32
        if hasattr(self.pipeline, '_embedding') and hasattr(self.pipeline._embedding, 'model'):
            self.pipeline._embedding.batch_size = 32

    def _consolidate_speakers(self, segments: List[Dict[str, Any]], target_speakers: int) -> List[Dict[str, Any]]:
        """Consolidate segments to exactly target_speakers by merging least-speaking speakers."""
        if not segments:
            return segments

        # Count segments per speaker
        speaker_counts = {}
        for seg in segments:
            speaker = seg["speaker"]
            if speaker not in speaker_counts:
                speaker_counts[speaker] = 0
            speaker_counts[speaker] += 1

        current_speakers = len(speaker_counts)
        print(f"[CONSOLIDATE] Current speakers: {current_speakers}, target: {target_speakers}")

        if current_speakers <= target_speakers:
            return segments

        # Sort speakers by segment count (ascending)
        sorted_speakers = sorted(speaker_counts.items(), key=lambda x: x[1])

        # Keep the top N speakers, merge the rest into the least-speaking kept speaker
        speakers_to_keep = [s[0] for s in sorted_speakers[-(target_speakers):]]
        speakers_to_merge = [s[0] for s in sorted_speakers[:-(target_speakers)]]

        # Merge into the least-speaking kept speaker
        merge_target = speakers_to_keep[0]

        print(f"[CONSOLIDATE] Keeping: {speakers_to_keep}, merging {speakers_to_merge} into {merge_target}")

        # Create mapping
        speaker_map = {}
        for i, speaker in enumerate(sorted(speakers_to_keep)):
            speaker_map[speaker] = f"SPEAKER_{i:02d}"
        for speaker in speakers_to_merge:
            speaker_map[speaker] = speaker_map[merge_target]

        # Apply mapping to segments
        consolidated_segments = []
        for seg in segments:
            consolidated_seg = seg.copy()
            consolidated_seg["speaker"] = speaker_map[seg["speaker"]]
            consolidated_segments.append(consolidated_seg)

        return consolidated_segments

    def diarize(self, audio_path: Path, num_speakers: int | None) -> List[Dict[str, Any]]:
        # Optimize with speaker constraints to avoid unnecessary clustering
        print(f"[DIAR] Diarizing with num_speakers={num_speakers}")
        if num_speakers:
            print(f"[DIAR] Forcing exactly {num_speakers} speakers")
            diarization = self.pipeline(
                audio_path,
                num_speakers=num_speakers,
                min_speakers=num_speakers,
                max_speakers=num_speakers,
            )
        else:
            # When not specified, constrain to reasonable range (1-10 speakers)
            diarization = self.pipeline(
                audio_path,
                min_speakers=1,
                max_speakers=10,
            )
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                {
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                    "speaker": speaker,
                }
            )

        # Consolidate to exact number of speakers if specified
        if num_speakers and num_speakers > 0:
            segments = self._consolidate_speakers(segments, num_speakers)

        return segments


engine = DiarizationEngine()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up", "model": MODEL_NAME}


@app.post("/diarize")
async def diarize_endpoint(
    file: UploadFile = File(...),
    num_speakers: str | None = Form(None),  # Accept as string first
) -> Dict[str, Any]:
    # Convert string to int if provided
    if num_speakers:
        try:
            num_speakers = int(num_speakers)
        except (ValueError, TypeError):
            num_speakers = None

    print(f"[ENDPOINT] Received request with num_speakers={num_speakers}")
    contents = await file.read()
    audio_hash = hashlib.sha256(contents).hexdigest()
    cache_file = CACHE_DIR / f"{audio_hash}.wav"

    # Process from memory using temporary file to reduce I/O
    if cache_file.exists():
        # Use cached file if available
        segments = engine.diarize(cache_file, num_speakers)
    else:
        # Process from memory using temporary file, then cache result
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(contents)
            tmp_file.flush()

        try:
            # Process from temporary file
            segments = engine.diarize(tmp_path, num_speakers)
            # Save to cache for future requests (use shutil.move for cross-filesystem support)
            shutil.move(str(tmp_path), str(cache_file))
        except Exception:
            # Clean up temp file on error
            tmp_path.unlink(missing_ok=True)
            raise

    return {"segments": segments}

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from pyannote.audio import Pipeline
import torch
from prometheus_fastapi_instrumentator import Instrumentator

CACHE_DIR = Path(os.environ.get("EMBEDDINGS_CACHE", "/cache/embeddings"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache for diarization results (separate from embeddings cache)
DIARIZATION_CACHE_DIR = Path(os.environ.get("DIARIZATION_CACHE", "/cache/diarization"))
DIARIZATION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DIARIZATION_CACHE_TTL_HOURS = int(os.environ.get("DIARIZATION_CACHE_TTL_HOURS", "24"))

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

    def _merge_consecutive_same_speaker(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge consecutive segments from the same speaker that are very close together.
        This fixes common segmentation errors where a single utterance is split.

        QUALITY IMPROVEMENT: Reduces false speaker changes
        """
        if not segments or len(segments) <= 1:
            return segments

        merged = []
        current = segments[0].copy()

        for next_seg in segments[1:]:
            # If same speaker and gap is very small (< 0.5s), merge
            gap = next_seg["start"] - current["end"]

            if next_seg["speaker"] == current["speaker"] and gap < 0.5:
                # Merge: extend current segment to include next
                current["end"] = next_seg["end"]
                print(f"[MERGE] Merged {current['speaker']} segments: {current['start']:.2f}-{current['end']:.2f} (gap: {gap:.2f}s)")
            else:
                # Different speaker or gap too large: save current and start new
                merged.append(current)
                current = next_seg.copy()

        # Don't forget the last segment
        merged.append(current)

        print(f"[POSTPROCESS] Segments reduced: {len(segments)} -> {len(merged)} (merged {len(segments) - len(merged)})")
        return merged

    def diarize(self, audio_path: Path, num_speakers: int | None) -> List[Dict[str, Any]]:
        # Optimize with speaker constraints to avoid unnecessary clustering
        print(f"[DIAR] Diarizing with num_speakers={num_speakers}")

        # QUALITY IMPROVEMENT: Tuned parameters for better accuracy
        diarization_params = {
            # Minimum duration of a speech segment (in seconds)
            # Higher = fewer false short segments, better quality
            "min_duration_on": 0.5,  # Default: 0.0, aumentado para evitar segmentos muito curtos

            # Minimum duration of silence between segments (in seconds)
            # Higher = less sensitive to brief pauses
            "min_duration_off": 0.3,  # Default: 0.0, evita trocas em pausas breves
        }

        if num_speakers:
            print(f"[DIAR] Forcing exactly {num_speakers} speakers")
            diarization = self.pipeline(
                audio_path,
                num_speakers=num_speakers,
                min_speakers=num_speakers,
                max_speakers=num_speakers,
                **diarization_params,
            )
        else:
            # When not specified, constrain to reasonable range (1-10 speakers)
            diarization = self.pipeline(
                audio_path,
                min_speakers=1,
                max_speakers=10,
                **diarization_params,
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

        # QUALITY IMPROVEMENT: Post-process to merge consecutive segments from same speaker
        segments = self._merge_consecutive_same_speaker(segments)

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

    # OPTIMIZATION: Check diarization result cache first
    speakers_str = str(num_speakers) if num_speakers else "auto"
    result_cache_file = DIARIZATION_CACHE_DIR / f"{audio_hash}_{speakers_str}.json"

    if result_cache_file.exists():
        # Check if cache is still valid (TTL)
        cache_age_hours = (time.time() - result_cache_file.stat().st_mtime) / 3600
        if cache_age_hours < DIARIZATION_CACHE_TTL_HOURS:
            print(f"[CACHE HIT] Using cached diarization result (age: {cache_age_hours:.1f}h)")
            with open(result_cache_file, "r") as f:
                cached_data = json.load(f)
            return {"segments": cached_data["segments"]}
        else:
            print(f"[CACHE EXPIRED] Cache is {cache_age_hours:.1f}h old (TTL: {DIARIZATION_CACHE_TTL_HOURS}h)")

    print("[CACHE MISS] Processing diarization")

    # Check wav file cache
    cache_file = CACHE_DIR / f"{audio_hash}.wav"

    # Process from memory using temporary file to reduce I/O
    if cache_file.exists():
        # Use cached wav file if available
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
            # Save wav to cache for future requests
            shutil.move(str(tmp_path), str(cache_file))
        except Exception:
            # Clean up temp file on error
            tmp_path.unlink(missing_ok=True)
            raise

    # OPTIMIZATION: Cache the diarization result
    try:
        result_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(result_cache_file, "w") as f:
            json.dump({"segments": segments, "num_speakers": num_speakers}, f)
        print(f"[CACHE SAVE] Saved diarization result to cache")
    except Exception as e:
        print(f"[CACHE WARNING] Failed to save result cache: {e}")

    return {"segments": segments}

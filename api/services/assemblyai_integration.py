import os
import time
import httpx
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")
ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com/v2"


async def transcribe_with_assemblyai(
    audio_file_path: str,
    language: str = "pt",
    num_speakers: int = 2
) -> Dict[str, Any]:
    """
    Transcribe audio using AssemblyAI with speaker diarization.

    Returns dict with format:
    {
        "text": str,
        "segments": List[{"start": float, "end": float, "text": str, "speaker": str}],
        "processing_time_ms": int,
        "metadata": dict
    }
    """
    if not ASSEMBLYAI_API_KEY:
        raise ValueError("ASSEMBLYAI_API_KEY not configured")

    start_time = time.time()

    headers = {"authorization": ASSEMBLYAI_API_KEY}

    # Step 1: Upload audio file
    logger.info(f"[AssemblyAI] Uploading audio file: {audio_file_path}")
    async with httpx.AsyncClient(timeout=300.0) as client:
        with open(audio_file_path, "rb") as f:
            upload_response = await client.post(
                f"{ASSEMBLYAI_BASE_URL}/upload",
                headers=headers,
                content=f.read()
            )

        if upload_response.status_code != 200:
            raise Exception(f"Upload failed: {upload_response.text}")

        audio_url = upload_response.json()["upload_url"]
        logger.info(f"[AssemblyAI] Audio uploaded: {audio_url}")

        # Step 2: Request transcription with diarization
        transcript_request = {
            "audio_url": audio_url,
            "speaker_labels": True,
            "speakers_expected": num_speakers,
            "language_code": language if language != "auto" else "pt"
        }

        logger.info(f"[AssemblyAI] Requesting transcription with diarization")
        transcript_response = await client.post(
            f"{ASSEMBLYAI_BASE_URL}/transcript",
            headers=headers,
            json=transcript_request
        )

        if transcript_response.status_code != 200:
            raise Exception(f"Transcription request failed: {transcript_response.text}")

        transcript_id = transcript_response.json()["id"]
        logger.info(f"[AssemblyAI] Transcription ID: {transcript_id}")

        # Step 3: Poll for completion
        max_polls = 300  # 5 minutes max
        poll_count = 0
        while poll_count < max_polls:
            polling_response = await client.get(
                f"{ASSEMBLYAI_BASE_URL}/transcript/{transcript_id}",
                headers=headers
            )

            result = polling_response.json()
            status = result["status"]

            logger.info(f"[AssemblyAI] Poll {poll_count}: status={status}")

            if status == "completed":
                logger.info(f"[AssemblyAI] Transcription completed after {poll_count} polls")
                break
            elif status == "error":
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"[AssemblyAI] Transcription failed: {error_msg}")
                raise Exception(f"Transcription failed: {error_msg}")

            poll_count += 1
            await asyncio.sleep(1)

        if poll_count >= max_polls:
            raise Exception(f"AssemblyAI polling timeout after {max_polls} seconds")

        # Step 4: Format response
        logger.info(f"[AssemblyAI] Transcription completed")

        # Extract segments with speaker labels
        segments = []
        for utterance in result.get("utterances", []):
            segments.append({
                "start": utterance["start"] / 1000.0,  # Convert ms to seconds
                "end": utterance["end"] / 1000.0,
                "text": utterance["text"],
                "words": [],
                "speaker": f"SPEAKER_{utterance['speaker']}"  # SPEAKER_A, SPEAKER_B, etc
            })

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Get audio duration (in seconds)
        audio_duration = result.get("audio_duration", 0.0)
        if audio_duration and audio_duration > 1000:
            # AssemblyAI returns duration in milliseconds, convert to seconds
            audio_duration = audio_duration / 1000.0

        return {
            "text": result["text"],
            "segments": segments,
            "duration_seconds": float(audio_duration),
            "processing_time_ms": processing_time_ms,
            "metadata": {
                "model": "assemblyai-best",
                "compute_type": "assemblyai-managed",
                "gpu_id": -1,
            }
        }

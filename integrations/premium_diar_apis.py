"""
Premium Diarization APIs Integration.
Provides fallback to AssemblyAI and Deepgram for high-accuracy diarization.
"""

import logging
import os
import httpx
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# API credentials from environment
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

ASSEMBLYAI_ENABLED = bool(ASSEMBLYAI_API_KEY)
DEEPGRAM_ENABLED = bool(DEEPGRAM_API_KEY)


class AssemblyAIDiarization:
    """AssemblyAI diarization API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.upload_url = "https://api.assemblyai.com/v2/upload"
        self.transcript_url = "https://api.assemblyai.com/v2/transcript"
        self.headers = {"authorization": api_key}

    def _upload_file(self, audio_path: Path) -> str:
        """Upload audio file to AssemblyAI."""
        with open(audio_path, "rb") as f:
            response = httpx.post(
                self.upload_url,
                headers=self.headers,
                files={"file": f},
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()["upload_url"]

    def diarize(self, audio_path: Path, num_speakers: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Diarize audio using AssemblyAI.

        Args:
            audio_path: Path to audio file
            num_speakers: Expected number of speakers (optional)

        Returns:
            List of diarized segments
        """
        logger.info(f"Using AssemblyAI for diarization: {audio_path}")

        # Upload audio
        audio_url = self._upload_file(audio_path)

        # Request transcription with diarization
        json_data = {
            "audio_url": audio_url,
            "speaker_labels": True,
            "language_code": "pt"
        }

        if num_speakers:
            json_data["speakers_expected"] = num_speakers

        response = httpx.post(
            self.transcript_url,
            json=json_data,
            headers=self.headers,
            timeout=30.0
        )
        response.raise_for_status()

        transcript_id = response.json()["id"]

        # Poll for completion
        poll_url = f"{self.transcript_url}/{transcript_id}"
        max_retries = 60  # 5 minutes max
        retry_delay = 5

        for _ in range(max_retries):
            response = httpx.get(poll_url, headers=self.headers, timeout=10.0)
            response.raise_for_status()

            result = response.json()
            status = result["status"]

            if status == "completed":
                # Convert to our format
                segments = []
                for utterance in result.get("utterances", []):
                    segments.append({
                        "start": utterance["start"] / 1000.0,  # ms to seconds
                        "end": utterance["end"] / 1000.0,
                        "text": utterance["text"],
                        "speaker": f"SPEAKER_{utterance['speaker']:02d}"
                    })

                logger.info(f"AssemblyAI diarization complete: {len(segments)} segments")
                return segments

            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                raise Exception(f"AssemblyAI transcription failed: {error_msg}")

            time.sleep(retry_delay)

        raise TimeoutError("AssemblyAI transcription timed out")


class DeepgramDiarization:
    """Deepgram diarization API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.deepgram.com/v1/listen"
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav"
        }

    def diarize(self, audio_path: Path, num_speakers: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Diarize audio using Deepgram.

        Args:
            audio_path: Path to audio file
            num_speakers: Expected number of speakers (optional)

        Returns:
            List of diarized segments
        """
        logger.info(f"Using Deepgram for diarization: {audio_path}")

        # Build query params
        params = {
            "diarize": "true",
            "language": "pt",
            "punctuate": "true",
            "utterances": "true"
        }

        # Deepgram doesn't support num_speakers hint directly
        # but we can still pass it for future compatibility

        # Read and send audio file
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        response = httpx.post(
            self.api_url,
            params=params,
            headers=self.headers,
            content=audio_data,
            timeout=60.0
        )
        response.raise_for_status()

        result = response.json()

        # Parse utterances
        segments = []
        for utterance in result.get("results", {}).get("utterances", []):
            segments.append({
                "start": utterance["start"],
                "end": utterance["end"],
                "text": utterance["transcript"],
                "speaker": f"SPEAKER_{utterance['speaker']:02d}"
            })

        logger.info(f"Deepgram diarization complete: {len(segments)} segments")
        return segments


def diarize_with_premium_api(
    audio_path: Path,
    num_speakers: Optional[int] = None,
    preferred_api: str = "assemblyai"
) -> Optional[List[Dict[str, Any]]]:
    """
    Diarize audio using premium APIs as fallback.

    Args:
        audio_path: Path to audio file
        num_speakers: Expected number of speakers
        preferred_api: "assemblyai" or "deepgram"

    Returns:
        List of diarized segments or None if APIs unavailable
    """
    if preferred_api == "assemblyai" and ASSEMBLYAI_ENABLED:
        try:
            client = AssemblyAIDiarization(ASSEMBLYAI_API_KEY)
            return client.diarize(audio_path, num_speakers)
        except Exception as e:
            logger.error(f"AssemblyAI diarization failed: {e}")
            # Try Deepgram as fallback
            if DEEPGRAM_ENABLED:
                try:
                    client = DeepgramDiarization(DEEPGRAM_API_KEY)
                    return client.diarize(audio_path, num_speakers)
                except Exception as e2:
                    logger.error(f"Deepgram diarization also failed: {e2}")

    elif preferred_api == "deepgram" and DEEPGRAM_ENABLED:
        try:
            client = DeepgramDiarization(DEEPGRAM_API_KEY)
            return client.diarize(audio_path, num_speakers)
        except Exception as e:
            logger.error(f"Deepgram diarization failed: {e}")
            # Try AssemblyAI as fallback
            if ASSEMBLYAI_ENABLED:
                try:
                    client = AssemblyAIDiarization(ASSEMBLYAI_API_KEY)
                    return client.diarize(audio_path, num_speakers)
                except Exception as e2:
                    logger.error(f"AssemblyAI diarization also failed: {e2}")

    logger.warning("No premium diarization APIs available or configured")
    return None


def is_premium_api_available() -> Dict[str, bool]:
    """Check which premium APIs are available."""
    return {
        "assemblyai": ASSEMBLYAI_ENABLED,
        "deepgram": DEEPGRAM_ENABLED,
        "any": ASSEMBLYAI_ENABLED or DEEPGRAM_ENABLED
    }

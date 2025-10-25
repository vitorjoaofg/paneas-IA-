from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from .asr import TranscriptSegment


class AlignDiarizeRequest(BaseModel):
    transcript_id: UUID
    transcript: dict
    audio_uri: str
    enable_alignment: bool = True
    enable_diarization: bool = True
    num_speakers: Optional[int] = None


class AlignDiarizeResponse(BaseModel):
    job_id: UUID
    status: str
    estimated_completion_ms: int | None = None

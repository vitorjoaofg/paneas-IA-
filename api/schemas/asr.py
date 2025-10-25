from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WordAlignment(BaseModel):
    start: float
    end: float
    word: str
    confidence: float | None = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    words: Optional[List[WordAlignment]] = None
    speaker: Optional[str] = None


class ASRMetadata(BaseModel):
    model: str
    compute_type: str
    gpu_id: int


class ASRResponse(BaseModel):
    request_id: UUID
    duration_seconds: float
    processing_time_ms: int
    language: str
    text: str
    segments: List[TranscriptSegment]
    metadata: ASRMetadata


class ASRRequest(BaseModel):
    language: str = Field(default="auto")
    model: str = Field(default="large-v3-turbo")
    enable_diarization: bool = Field(default=False)
    enable_alignment: bool = Field(default=False)
    compute_type: str = Field(default="fp16")
    vad_filter: bool = Field(default=True)
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    beam_size: int = Field(default=5, ge=1, le=10)

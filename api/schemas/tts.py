from uuid import UUID

from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
    language: str = "pt"
    speaker_reference: str | None = None
    streaming: bool = False
    format: str = "wav"


class TTSResponse(BaseModel):
    request_id: UUID
    format: str
    sample_rate: int
    duration_seconds: float
    content_type: str

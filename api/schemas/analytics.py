from typing import List
from uuid import UUID

from pydantic import BaseModel


class SpeechAnalyticsRequest(BaseModel):
    call_id: UUID
    audio_uri: str
    transcript_uri: str
    analysis_types: List[str]
    keywords: List[str] = []


class AnalyticsJobResponse(BaseModel):
    job_id: UUID
    status: str


class AnalyticsResult(BaseModel):
    job_id: UUID
    status: str
    results: dict | None = None

from typing import List
from uuid import UUID

from pydantic import BaseModel


class OCRBlock(BaseModel):
    bbox: List[int]
    text: str
    confidence: float


class OCRPageMetadata(BaseModel):
    processing_time_ms: int
    engine: str


class OCRPage(BaseModel):
    page_num: int
    text: str
    blocks: List[OCRBlock]
    metadata: OCRPageMetadata


class OCRResponse(BaseModel):
    request_id: UUID
    pages: List[OCRPage]

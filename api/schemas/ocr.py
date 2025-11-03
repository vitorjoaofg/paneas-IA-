from typing import List, Optional, Dict
from uuid import UUID

from pydantic import BaseModel


class OCRBlock(BaseModel):
    bbox: List[int]
    text: str
    confidence: float


class DocumentTypeInfo(BaseModel):
    """Information about detected document type."""
    type: str
    confidence: float
    detected_by: str
    matched_patterns: List[str] = []


class ExtractedEntity(BaseModel):
    """Entity extracted from document text."""
    type: str
    value: str
    raw_value: str
    confidence: float
    position: Optional[Dict[str, int]] = None
    validated: bool = False


class OCRPageMetadata(BaseModel):
    processing_time_ms: int
    engine: str


class OCRPage(BaseModel):
    page_num: int
    text: str
    blocks: List[OCRBlock]
    document_type: Optional[DocumentTypeInfo] = None
    entities: List[ExtractedEntity] = []
    metadata: OCRPageMetadata


class OCRResponse(BaseModel):
    request_id: UUID
    pages: List[OCRPage]

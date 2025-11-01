import json
import shutil
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from schemas.analytics import AnalyticsJobResponse, AnalyticsResult, SpeechAnalyticsRequest
from services.analytics_client import get_job, submit_job

router = APIRouter(prefix="/api/v1", tags=["analytics"])


class SaveTranscriptRequest(BaseModel):
    filename: str
    data: dict


class SaveTranscriptResponse(BaseModel):
    path: str
    filename: str


class UploadFileResponse(BaseModel):
    path: str
    filename: str
    size: int


@router.post("/analytics/upload-audio", response_model=UploadFileResponse)
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file to /tmp for analytics processing"""
    try:
        # Validate file extension
        allowed_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.opus'}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Generate unique filename
        import time
        timestamp = int(time.time() * 1000)
        safe_filename = f"analytics_audio_{timestamp}{file_ext}"
        file_path = Path("/tmp") / safe_filename

        # Save uploaded file
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        file_size = file_path.stat().st_size

        return UploadFileResponse(
            path=str(file_path),
            filename=safe_filename,
            size=file_size
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload audio: {str(e)}")


@router.post("/analytics/save-transcript", response_model=SaveTranscriptResponse)
async def save_transcript(payload: SaveTranscriptRequest):
    """Save a transcript JSON to /tmp for analytics processing"""
    try:
        file_path = Path("/tmp") / payload.filename

        # Write JSON to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload.data, f, ensure_ascii=False, indent=2)

        return SaveTranscriptResponse(
            path=str(file_path),
            filename=payload.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save transcript: {str(e)}")


@router.post("/analytics/speech", response_model=AnalyticsJobResponse, status_code=202)
async def submit_analytics(payload: SpeechAnalyticsRequest):
    response = await submit_job(payload.model_dump(mode="json"))
    return AnalyticsJobResponse.model_validate(response)


@router.get("/analytics/speech/{job_id}", response_model=AnalyticsResult)
async def get_analytics(job_id: UUID):
    response = await get_job(job_id)
    return AnalyticsResult.model_validate(response)

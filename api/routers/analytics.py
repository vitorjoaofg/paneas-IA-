from uuid import UUID

from fastapi import APIRouter

from schemas.analytics import AnalyticsJobResponse, AnalyticsResult, SpeechAnalyticsRequest
from services.analytics_client import get_job, submit_job

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.post("/analytics/speech", response_model=AnalyticsJobResponse, status_code=202)
async def submit_analytics(payload: SpeechAnalyticsRequest):
    response = await submit_job(payload.model_dump(mode="json"))
    return AnalyticsJobResponse.model_validate(response)


@router.get("/analytics/speech/{job_id}", response_model=AnalyticsResult)
async def get_analytics(job_id: UUID):
    response = await get_job(job_id)
    return AnalyticsResult.model_validate(response)

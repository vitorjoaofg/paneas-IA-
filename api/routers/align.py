from fastapi import APIRouter

from schemas.align import AlignDiarizeRequest, AlignDiarizeResponse
from services.align_client import submit

router = APIRouter(prefix="/api/v1", tags=["align"])


@router.post("/align_diarize", response_model=AlignDiarizeResponse, status_code=202)
async def align_and_diarize(payload: AlignDiarizeRequest):
    result = await submit(payload.model_dump(mode="json"))
    return AlignDiarizeResponse.model_validate(result)

import time
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from schemas.asr import ASRRequest, ASRResponse
from services import asr_client
from utils.pii_masking import PIIMasker

router = APIRouter(prefix="/api/v1", tags=["asr"])


def build_request(
    language: str = Form("auto"),
    model: str = Form("large-v3-turbo"),
    enable_diarization: bool = Form(False),
    enable_alignment: bool = Form(False),
    compute_type: str = Form("fp16"),
    vad_filter: bool = Form(True),
    vad_threshold: float = Form(0.5),
    beam_size: int = Form(5),
) -> ASRRequest:
    return ASRRequest(
        language=language,
        model=model,
        enable_diarization=enable_diarization,
        enable_alignment=enable_alignment,
        compute_type=compute_type,
        vad_filter=vad_filter,
        vad_threshold=vad_threshold,
        beam_size=beam_size,
    )


@router.post("/asr", response_model=ASRResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    payload: ASRRequest = Depends(build_request),
):
    request_id = uuid.uuid4()
    start = time.perf_counter()
    options = payload.model_dump()
    options["request_id"] = str(request_id)

    raw_result = await asr_client.transcribe(file=file, options=options)
    raw_result["request_id"] = request_id
    raw_result["processing_time_ms"] = int((time.perf_counter() - start) * 1000)
    raw_result["text"] = PIIMasker.mask_text(raw_result.get("text", ""))
    for segment in raw_result.get("segments", []):
        segment["text"] = PIIMasker.mask_text(segment.get("text", ""))
    return ASRResponse.model_validate(raw_result)

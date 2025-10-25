import uuid

from fastapi import APIRouter, File, Form, UploadFile

from schemas.ocr import OCRResponse
from services.ocr_client import run_ocr

router = APIRouter(prefix="/api/v1", tags=["ocr"])


@router.post("/ocr", response_model=OCRResponse)
async def process_document(
    file: UploadFile = File(...),
    languages: str = Form('["pt"]'),
    output_format: str = Form("json"),
    use_gpu: bool = Form(True),
    deskew: bool = Form(True),
    denoise: bool = Form(False),
):
    payload = {
        "languages": languages,
        "output_format": output_format,
        "use_gpu": use_gpu,
        "deskew": deskew,
        "denoise": denoise,
    }
    result = await run_ocr(file, payload)
    result["request_id"] = uuid.UUID(result.get("request_id", uuid.uuid4().hex))
    return OCRResponse.model_validate(result)

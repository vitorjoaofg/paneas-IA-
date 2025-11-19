import uuid

from fastapi import APIRouter, File, Form, UploadFile

from ocr_pipeline import process_document as interpret_document
from schemas.ocr import OCRResponse, OCRStructuredResponse
from services.ocr_client import run_ocr

router = APIRouter(prefix="/api/v1", tags=["ocr"])


@router.post("/ocr", response_model=OCRStructuredResponse)
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
    structured = interpret_document(result, doc_type=None, use_llm=False)
    return OCRStructuredResponse(
        ocr=OCRResponse.model_validate(result),
        structured=structured,
    )

import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel
import structlog

from schemas.asr import ASRRequest, ASRResponse
from services import asr_client
from services.transcription_postprocess import postprocess_transcription
from utils.pii_masking import PIIMasker

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["asr"])


class TranscribePathRequest(BaseModel):
    audio_path: str
    language: str = "pt"
    task: str = "transcribe"
    enable_diarization: bool = False


def build_request(
    language: str = Form("auto"),
    model: str = Form("whisper/medium"),
    enable_diarization: bool = Form(False),
    enable_alignment: bool = Form(False),
    enable_llm_postprocess: bool = Form(False),
    num_speakers: int | None = Form(None),
    compute_type: str = Form("int8_float16"),
    vad_filter: bool = Form(True),
    vad_threshold: float = Form(0.5),
    beam_size: int = Form(5),
    provider: str = Form("paneas"),
) -> ASRRequest:
    return ASRRequest(
        language=language,
        model=model,
        enable_diarization=enable_diarization,
        enable_alignment=enable_alignment,
        enable_llm_postprocess=enable_llm_postprocess,
        num_speakers=num_speakers,
        compute_type=compute_type,
        vad_filter=vad_filter,
        vad_threshold=vad_threshold,
        beam_size=beam_size,
        provider=provider,
    )


@router.post("/asr", response_model=ASRResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    payload: ASRRequest = Depends(build_request),
):
    request_id = uuid.uuid4()
    start = time.perf_counter()
    options = payload.model_dump()
    provider = options.pop("provider", "paneas")
    enable_llm_postprocess = options.pop("enable_llm_postprocess", False)
    options["request_id"] = str(request_id)

    raw_result = await asr_client.transcribe(
        file=file,
        options=options,
        provider=provider,
    )
    raw_result["request_id"] = request_id
    raw_result["processing_time_ms"] = int((time.perf_counter() - start) * 1000)

    # Apply PII masking first
    raw_result["text"] = PIIMasker.mask_text(raw_result.get("text", ""))
    for segment in raw_result.get("segments", []):
        segment["text"] = PIIMasker.mask_text(segment.get("text", ""))

    # Apply LLM post-processing if enabled
    if enable_llm_postprocess:
        LOGGER.info("applying_llm_postprocess", request_id=str(request_id))
        try:
            postprocess_result = await postprocess_transcription(
                full_text=raw_result["text"],
                segments=raw_result.get("segments", []),
                model="gpt-4o-mini",
                process_segments=False,  # Desabilitado para performance
            )

            # Save original text before replacing
            raw_result["raw_text"] = raw_result["text"]

            # Update with improved versions (apenas texto completo)
            raw_result["text"] = postprocess_result["improved_text"]

            LOGGER.info(
                "llm_postprocess_complete",
                request_id=str(request_id),
                notes=postprocess_result.get("processing_notes"),
            )
        except Exception as e:
            LOGGER.error(
                "llm_postprocess_failed",
                request_id=str(request_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue without post-processing on error

    return ASRResponse.model_validate(raw_result)


@router.post("/asr/transcribe", response_model=ASRResponse)
async def transcribe_from_path(payload: TranscribePathRequest):
    """Transcribe audio from a file path (for already uploaded files)"""
    request_id = uuid.uuid4()
    start = time.perf_counter()

    # Verify file exists
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {payload.audio_path}")

    # Read file and create an UploadFile-like object
    with open(audio_path, 'rb') as f:
        file_content = f.read()

    # Create a mock UploadFile
    from io import BytesIO
    from fastapi import UploadFile as FastAPIUploadFile

    mock_file = FastAPIUploadFile(
        filename=audio_path.name,
        file=BytesIO(file_content)
    )

    options = {
        "language": payload.language,
        "model": "whisper/medium",
        "enable_diarization": payload.enable_diarization,
        "enable_alignment": False,
        "compute_type": "int8_float16",
        "vad_filter": True,
        "vad_threshold": 0.5,
        "beam_size": 5,
        "request_id": str(request_id)
    }

    raw_result = await asr_client.transcribe(
        file=mock_file,
        options=options,
        provider="paneas",
    )

    raw_result["request_id"] = request_id
    raw_result["processing_time_ms"] = int((time.perf_counter() - start) * 1000)
    raw_result["text"] = PIIMasker.mask_text(raw_result.get("text", ""))
    for segment in raw_result.get("segments", []):
        segment["text"] = PIIMasker.mask_text(segment.get("text", ""))

    return ASRResponse.model_validate(raw_result)

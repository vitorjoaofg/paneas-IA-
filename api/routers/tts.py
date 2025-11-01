import uuid

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

from schemas.tts import TTSRequest
from services import tts_client

router = APIRouter(prefix="/api/v1", tags=["tts"])


@router.post("/tts")
async def synthesize(payload: TTSRequest):
    result = await tts_client.synthesize(payload.model_dump())
    headers = {
        "X-Request-ID": result.get("request_id", str(uuid.uuid4())),
    }
    if result.get("sample_rate"):
        headers["X-Audio-Sample-Rate"] = result["sample_rate"]
    if result.get("duration"):
        headers["X-Audio-Duration"] = result["duration"]
    return Response(content=result["audio"], media_type=result["content_type"], headers=headers)


@router.post("/tts/stream")
async def synthesize_stream(payload: TTSRequest):
    """
    Stream TTS audio chunks as they are generated

    Returns a streaming response with audio/wav chunks
    """
    headers = {
        "X-Request-ID": str(uuid.uuid4()),
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    }

    return StreamingResponse(
        tts_client.synthesize_stream(payload.model_dump()),
        media_type="audio/wav",
        headers=headers
    )

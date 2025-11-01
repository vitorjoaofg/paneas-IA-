import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from config import get_settings

router = APIRouter(prefix="/api/v1", tags=["diarization"])

settings = get_settings()


@router.post("/diar")
async def diarize_audio(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    use_llm: bool = Form(True),  # LLM mode is now the default
):
    """
    Realiza diarização de áudio - identifica diferentes speakers

    Modos disponíveis:
    - use_llm=True (padrão): Usa transcrição + LLM para separar canais (mais rápido)
    - use_llm=False: Usa modelo de diarização tradicional (mais lento, mais preciso para múltiplos speakers)
    """
    if use_llm:
        # LLM mode: Just return a message indicating client should use ASR + LLM flow
        return {
            "mode": "llm",
            "message": "Use ASR transcription first, then apply LLM diarization on the frontend",
            "info": "LLM diarization is handled client-side for better performance"
        }

    # Traditional diarization mode
    # Prepare form data
    files = {"file": (file.filename, await file.read(), file.content_type)}
    data = {}
    if num_speakers is not None:
        data["num_speakers"] = num_speakers

    # Call diarization service
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "http://diar:9003/diarize",
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Diarization service unavailable: {str(e)}")

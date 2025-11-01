import uuid
from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client, request_with_retry

_settings = get_settings()


async def synthesize(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.tts_host}:{_settings.tts_port}/synthesize"

    headers = {"Content-Type": "application/json"}
    body = {"request_id": str(uuid.uuid4()), **payload}
    response = await request_with_retry(
        "POST",
        url,
        client=client,
        json=body,
        headers=headers,
        timeout=60.0,
    )
    return {
        "audio": response.content,
        "content_type": response.headers.get("content-type", "audio/wav"),
        "request_id": response.headers.get("x-request-id"),
        "sample_rate": response.headers.get("x-audio-sample-rate"),
        "duration": response.headers.get("x-audio-duration"),
    }


async def synthesize_stream(payload: Dict[str, Any]):
    """
    Generator function that streams audio chunks from the TTS service

    Yields audio chunks as they arrive from the TTS service
    """
    client = await get_http_client()
    url = f"http://{_settings.tts_host}:{_settings.tts_port}/synthesize"

    headers = {"Content-Type": "application/json"}
    body = {"request_id": str(uuid.uuid4()), **payload}

    # Use streaming request
    async with client.stream(
        "POST",
        url,
        json=body,
        headers=headers,
        timeout=60.0,
    ) as response:
        # Yield chunks as they arrive
        async for chunk in response.aiter_bytes(chunk_size=8192):
            yield chunk

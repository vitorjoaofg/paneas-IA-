import uuid
from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client

_settings = get_settings()


async def synthesize(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.tts_host}:{_settings.tts_port}/synthesize"

    headers = {"Content-Type": "application/json"}
    body = {"request_id": str(uuid.uuid4()), **payload}
    response = await client.post(url, json=body, headers=headers)
    response.raise_for_status()
    return {
        "audio": response.content,
        "content_type": response.headers.get("content-type", "audio/wav"),
        "request_id": response.headers.get("x-request-id"),
        "sample_rate": response.headers.get("x-audio-sample-rate"),
        "duration": response.headers.get("x-audio-duration"),
    }

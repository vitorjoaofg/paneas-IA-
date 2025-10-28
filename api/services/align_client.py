from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client, request_with_retry

_settings = get_settings()


async def submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.align_host}:{_settings.align_port}/align_diarize"
    response = await request_with_retry(
        "POST",
        url,
        client=client,
        json=payload,
        timeout=20.0,
    )
    return response.json()

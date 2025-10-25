from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client

_settings = get_settings()


async def submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.align_host}:{_settings.align_port}/align_diarize"
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return response.json()

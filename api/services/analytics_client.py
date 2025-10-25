from typing import Any, Dict
from uuid import UUID

from config import get_settings
from services.http_client import get_http_client

_settings = get_settings()


async def submit_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.analytics_host}:{_settings.analytics_port}/analytics/speech"
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return response.json()


async def get_job(job_id: UUID) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.analytics_host}:{_settings.analytics_port}/analytics/speech/{job_id}"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()

from typing import Any, Dict
from uuid import UUID

from config import get_settings
from services.http_client import get_http_client, request_with_retry

_settings = get_settings()


async def submit_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.analytics_host}:{_settings.analytics_port}/analytics/speech"
    response = await request_with_retry(
        "POST",
        url,
        client=client,
        json=payload,
        timeout=15.0,
    )
    return response.json()


async def get_job(job_id: UUID) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.analytics_host}:{_settings.analytics_port}/analytics/speech/{job_id}"
    response = await request_with_retry(
        "GET",
        url,
        client=client,
        timeout=10.0,
    )
    return response.json()

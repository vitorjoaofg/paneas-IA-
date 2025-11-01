from __future__ import annotations

from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client, request_with_retry

_settings = get_settings()


async def consulta_processo(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/consulta"
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=60.0)
    return response.json()


async def listar_processos(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/listar"
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=60.0)
    return response.json()


async def obter_manifesto() -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/tools"
    response = await request_with_retry("GET", url, client=client, timeout=30.0)
    return response.json()

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


async def listar_processos_pje(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/pje/listar"
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=60.0)
    return response.json()


async def consulta_processo_pje(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/pje/consulta"
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=60.0)
    return response.json()


async def buscar_detalhes_pje(link_publico: str) -> Dict[str, Any]:
    """Busca detalhes completos de um processo PJE pelo link público."""
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/pje/consulta"
    response = await request_with_retry("POST", url, client=client, json={"link_publico": link_publico}, timeout=60.0)
    return response.json()


async def listar_processos_tjrj(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/tjrj/listar"
    # TJRJ scraper takes ~90s due to Playwright + anti-bot delays
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=120.0)
    return response.json()


async def consulta_processo_tjrj(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/tjrj/consulta"
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=120.0)
    return response.json()


async def obter_manifesto() -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/tools"
    response = await request_with_retry("GET", url, client=client, timeout=30.0)
    return response.json()


async def test_tjrj_pje_auth_page3(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Testa extração de processo da página 3 do TJRJ PJE autenticado."""
    client = await get_http_client()
    url = f"http://{_settings.scrapper_host}:{_settings.scrapper_port}/v1/processos/tjrj-pje-auth/test-page3"
    # PJE autenticado pode levar muito tempo (login + navegação + paginação)
    response = await request_with_retry("POST", url, client=client, json=payload, timeout=300.0)
    return response.json()

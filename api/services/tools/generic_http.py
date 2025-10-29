"""
Generic HTTP tool for making external API calls
"""
import json
from typing import Any, Dict, Optional
import httpx
import structlog

LOGGER = structlog.get_logger(__name__)


async def generic_http_call(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Faz uma chamada HTTP genérica para APIs externas
    """
    LOGGER.info("generic_http_call", url=url, method=method)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Preparar request
            request_kwargs = {
                "method": method.upper(),
                "url": url,
            }

            if headers:
                request_kwargs["headers"] = headers

            if params:
                request_kwargs["params"] = params

            if data and method.upper() in ["POST", "PUT", "PATCH"]:
                request_kwargs["json"] = data

            # Fazer requisição
            response = await client.request(**request_kwargs)

            LOGGER.info(
                "generic_http_response",
                status_code=response.status_code,
                url=url
            )

            # Tentar parsear como JSON
            try:
                result = response.json()
            except:
                result = {"text": response.text, "status_code": response.status_code}

            return {
                "success": True,
                "status_code": response.status_code,
                "data": result
            }

    except Exception as e:
        LOGGER.error("generic_http_error", error=str(e), url=url)
        return {
            "success": False,
            "error": str(e)
        }


async def age_predictor(base_url: str, nome: str, **kwargs) -> Dict[str, Any]:
    """
    Prevê a idade com base no nome usando API agify.io
    """
    # Construir URL completa
    if "?" in base_url:
        url = base_url  # Já tem parâmetros
    else:
        url = f"{base_url}?name={nome}"

    return await generic_http_call(url, method="GET")


async def external_api_call(
    base_url: str,
    endpoint: str = "",
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Faz chamada para qualquer API externa
    """
    # Construir URL completa
    url = base_url.rstrip("/")
    if endpoint:
        url = f"{url}/{endpoint.lstrip('/')}"

    return await generic_http_call(
        url=url,
        method=method,
        headers=headers,
        params=params,
        data=body
    )
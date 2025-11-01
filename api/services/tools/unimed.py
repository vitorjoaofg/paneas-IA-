"""
Tool para consulta de dados na API Unimed
"""

from typing import Any, Dict, Optional

import httpx
import structlog

LOGGER = structlog.get_logger(__name__)


async def unimed_consult(
    cpf: str,
    data_nascimento: str,
    base_url: str = "https://unimed-central-cobranca.paneas.net/api/v1",
    cidade: str = "Natal_Tasy",
    tipo: str = "Contratos",
    protocolo: Optional[str] = "0",
) -> Dict[str, Any]:
    """
    Consulta dados de beneficiário na API Unimed

    Args:
        base_url: URL base da API (ex: https://unimed-central-cobranca.paneas.net/api/v1)
        cidade: Cidade do protocolo (ex: Natal_Tasy)
        tipo: Tipo de consulta (ex: Contratos)
        protocolo: Número do protocolo (opcional)
        cpf: CPF do beneficiário (apenas números)
        data_nascimento: Data de nascimento (formato: AAAAMMDD ou AAAA-MM-DD)

    Returns:
        Dict com os dados do beneficiário ou mensagem de erro
    """
    LOGGER.info(
        "unimed_consult_start",
        base_url=base_url,
        cidade=cidade,
        tipo=tipo,
        cpf=cpf[:3] + "***",  # Mask CPF for logging
    )

    try:
        # Normalizar CPF (remover pontos e traços)
        cpf_normalizado = cpf.replace(".", "").replace("-", "")

        # Normalizar data de nascimento (remover traços se presente)
        data_normalizada = data_nascimento.replace("-", "")

        # Construir URL
        url_base = base_url.rstrip("/")
        endpoint = f"{url_base}/{cidade}/{tipo}"

        # Parâmetros da query
        params = {
            "cpf": cpf_normalizado,
            "data_nascimento": data_normalizada,
        }

        if protocolo:
            params["protocolo"] = protocolo

        # Fazer requisição
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(endpoint, params=params)

            # Log da resposta
            LOGGER.info(
                "unimed_consult_response",
                status_code=response.status_code,
                cidade=cidade,
                tipo=tipo,
            )

            # Verificar status
            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Beneficiário não encontrado",
                    "status_code": 404,
                }

            if response.status_code == 400:
                return {
                    "success": False,
                    "error": "Parâmetros inválidos",
                    "status_code": 400,
                    "details": response.text,
                }

            # Raise para outros erros HTTP
            response.raise_for_status()

            # Parse JSON
            data = response.json()

            return {
                "success": True,
                "data": data,
                "status_code": response.status_code,
            }

    except httpx.TimeoutException:
        LOGGER.error("unimed_consult_timeout", base_url=base_url)
        return {
            "success": False,
            "error": "Timeout ao consultar API Unimed",
            "details": "A requisição excedeu o tempo limite de 30 segundos",
        }

    except httpx.HTTPStatusError as e:
        LOGGER.error(
            "unimed_consult_http_error",
            status_code=e.response.status_code,
            error=str(e),
        )
        return {
            "success": False,
            "error": f"Erro HTTP {e.response.status_code}",
            "details": str(e),
        }

    except httpx.RequestError as e:
        LOGGER.error("unimed_consult_request_error", error=str(e))
        return {
            "success": False,
            "error": "Erro ao fazer requisição",
            "details": str(e),
        }

    except Exception as e:
        LOGGER.error(
            "unimed_consult_unexpected_error",
            error=type(e).__name__,
            details=str(e),
        )
        return {
            "success": False,
            "error": f"Erro inesperado: {type(e).__name__}",
            "details": str(e),
        }

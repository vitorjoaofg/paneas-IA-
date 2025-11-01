"""
Tool para consulta de clima usando API Open-Meteo (gratuita, sem API key)
"""

from typing import Any, Dict

import httpx
import structlog

LOGGER = structlog.get_logger(__name__)


async def get_weather(
    cidade: str,
    pais: str = "Brasil"
) -> Dict[str, Any]:
    """
    Consulta o clima atual de uma cidade usando Open-Meteo API

    Args:
        cidade: Nome da cidade (ex: Natal, São Paulo, Rio de Janeiro)
        pais: País (padrão: Brasil)

    Returns:
        Dict com informações do clima
    """
    LOGGER.info("weather_query_start", cidade=cidade, pais=pais)

    try:
        # Coordenadas de algumas cidades brasileiras conhecidas
        coordenadas = {
            "natal": {"lat": -5.7945, "lon": -35.2110, "nome": "Natal"},
            "sao paulo": {"lat": -23.5505, "lon": -46.6333, "nome": "São Paulo"},
            "rio de janeiro": {"lat": -22.9068, "lon": -43.1729, "nome": "Rio de Janeiro"},
            "brasilia": {"lat": -15.7801, "lon": -47.9292, "nome": "Brasília"},
            "fortaleza": {"lat": -3.7172, "lon": -38.5433, "nome": "Fortaleza"},
            "recife": {"lat": -8.0476, "lon": -34.8770, "nome": "Recife"},
            "salvador": {"lat": -12.9714, "lon": -38.5014, "nome": "Salvador"},
            "belo horizonte": {"lat": -19.9167, "lon": -43.9345, "nome": "Belo Horizonte"},
        }

        # Normalizar nome da cidade
        cidade_lower = cidade.lower().strip()

        # Buscar coordenadas
        if cidade_lower not in coordenadas:
            return {
                "success": False,
                "error": f"Cidade '{cidade}' não encontrada. Cidades disponíveis: {', '.join([v['nome'] for v in coordenadas.values()])}"
            }

        coords = coordenadas[cidade_lower]

        # Consultar API Open-Meteo (gratuita, sem API key)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "timezone": "America/Sao_Paulo"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})

            # Interpretar código do tempo
            weather_code = current.get("weather_code", 0)
            weather_descriptions = {
                0: "Céu limpo",
                1: "Principalmente limpo",
                2: "Parcialmente nublado",
                3: "Nublado",
                45: "Neblina",
                48: "Neblina com geada",
                51: "Garoa leve",
                53: "Garoa moderada",
                55: "Garoa forte",
                61: "Chuva leve",
                63: "Chuva moderada",
                65: "Chuva forte",
                71: "Neve leve",
                73: "Neve moderada",
                75: "Neve forte",
                77: "Granizo",
                80: "Pancadas de chuva leve",
                81: "Pancadas de chuva moderada",
                82: "Pancadas de chuva forte",
                85: "Pancadas de neve leve",
                86: "Pancadas de neve forte",
                95: "Tempestade",
                96: "Tempestade com granizo leve",
                99: "Tempestade com granizo forte"
            }

            condicao = weather_descriptions.get(weather_code, "Condição desconhecida")

            resultado = {
                "success": True,
                "cidade": coords["nome"],
                "pais": pais,
                "temperatura": current.get("temperature_2m"),
                "sensacao_termica": current.get("apparent_temperature"),
                "umidade": current.get("relative_humidity_2m"),
                "condicao": condicao,
                "precipitacao": current.get("precipitation"),
                "vento_kmh": current.get("wind_speed_10m"),
                "unidade_temp": data.get("current_units", {}).get("temperature_2m", "°C"),
                "horario": current.get("time")
            }

            LOGGER.info(
                "weather_query_success",
                cidade=coords["nome"],
                temperatura=resultado["temperatura"]
            )

            return resultado

    except httpx.TimeoutException:
        LOGGER.error("weather_query_timeout", cidade=cidade)
        return {
            "success": False,
            "error": "Timeout ao consultar API de clima"
        }

    except httpx.HTTPStatusError as e:
        LOGGER.error("weather_query_http_error", status_code=e.response.status_code)
        return {
            "success": False,
            "error": f"Erro HTTP {e.response.status_code}",
            "details": str(e)
        }

    except Exception as e:
        LOGGER.error("weather_query_error", error=type(e).__name__, details=str(e))
        return {
            "success": False,
            "error": f"Erro ao consultar clima: {type(e).__name__}",
            "details": str(e)
        }

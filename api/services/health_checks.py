import asyncio
import socket
import time
from typing import Dict, Tuple
from urllib.parse import urlparse

import asyncpg
from httpx import RequestError
from minio import Minio

from config import get_settings
from services.http_client import get_http_client
from services.redis_client import get_redis

_settings = get_settings()

HTTP_TARGETS: Dict[str, str] = {
    "asr": f"http://{_settings.asr_host}:{_settings.asr_port}/health",
    "tts": f"http://{_settings.tts_host}:{_settings.tts_port}/health",
    "llm_fp16": f"http://{_settings.llm_fp16_host}:{_settings.llm_fp16_port}/health",
    "llm_int4": f"http://{_settings.llm_int4_host}:{_settings.llm_int4_port}/health",
    "ocr": f"http://{_settings.ocr_host}:{_settings.ocr_port}/health",
    "align": f"http://{_settings.align_host}:{_settings.align_port}/health",
    "diar": f"http://{_settings.diar_host}:{_settings.diar_port}/health",
    "analytics": f"http://{_settings.analytics_host}:{_settings.analytics_port}/health",
}


async def _check_http(name: str, url: str) -> Tuple[str, Dict]:
    client = await get_http_client()
    start = time.perf_counter()
    try:
        response = await client.get(url, timeout=5.0)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.status_code == 200:
            payload = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            return name, {"status": "up", "latency_ms": latency_ms, "details": payload}
        return (
            name,
            {
                "status": "degraded",
                "latency_ms": latency_ms,
                "details": {"status_code": response.status_code},
            },
        )
    except RequestError as exc:
        return name, {"status": "down", "details": {"error": str(exc)}}


async def _check_postgres() -> Tuple[str, Dict]:
    start = time.perf_counter()
    try:
        conn = await asyncpg.connect(
            host=_settings.postgres_host,
            port=_settings.postgres_port,
            user=_settings.postgres_user,
            password=_settings.postgres_password,
            database=_settings.postgres_db,
            timeout=5.0,
        )
        await conn.execute("SELECT 1")
        await conn.close()
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "postgres", {"status": "up", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        return "postgres", {"status": "down", "details": {"error": str(exc)}}


async def _check_redis() -> Tuple[str, Dict]:
    start = time.perf_counter()
    try:
        redis = await get_redis()
        pong = await redis.ping()
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "redis", {"status": "up", "latency_ms": latency_ms, "details": {"pong": pong}}
    except Exception as exc:  # noqa: BLE001
        return "redis", {"status": "down", "details": {"error": str(exc)}}


async def _check_minio() -> Tuple[str, Dict]:
    start = time.perf_counter()
    try:
        endpoint = _settings.minio_endpoint
        if endpoint.startswith("http"):
            parsed = urlparse(endpoint)
            endpoint_host = parsed.netloc
            secure = parsed.scheme == "https"
        else:
            endpoint_host = endpoint
            secure = _settings.minio_secure
        client = Minio(
            endpoint_host,
            access_key=_settings.minio_access_key,
            secret_key=_settings.minio_secret_key,
            secure=secure,
        )
        await asyncio.to_thread(client.list_buckets)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "minio", {"status": "up", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        return "minio", {"status": "down", "details": {"error": str(exc)}}


async def _check_celery() -> Tuple[str, Dict]:
    # Basic TCP connectivity test against broker port to indicate Celery availability
    start = time.perf_counter()
    try:
        parsed = urlparse(_settings.celery_broker_url)
        host = parsed.hostname or _settings.redis_host
        port = parsed.port or _settings.redis_port
        await asyncio.to_thread(_probe_socket, host, port)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "celery", {"status": "up", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        return "celery", {"status": "down", "details": {"error": str(exc)}}


def _probe_socket(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3.0):
        return


async def gather_health() -> Dict[str, Dict]:
    tasks = [
        _check_http(name, url) for name, url in HTTP_TARGETS.items()
    ]
    tasks.extend((_check_postgres(), _check_redis(), _check_minio(), _check_celery()))
    results = await asyncio.gather(*tasks)
    return {name: result for name, result in results}

import math
import time
from typing import Callable

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import get_settings
from services.redis_client import get_redis

_settings = get_settings()

ROUTE_LIMITS = {
    "/api/v1/asr": _settings.rate_limit_asr,
    "/api/v1/ocr": _settings.rate_limit_ocr,
    "/api/v1/chat/completions": _settings.rate_limit_llm,
    "/api/v1/tts": _settings.rate_limit_tts,
}

WINDOW_SECONDS = 60
LOGGER = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        # Skip rate limiting for metrics and WebSocket endpoints
        if path == "/metrics" or path.startswith("/api/v1/asr/stream"):
            return await call_next(request)

        client_ip = request.headers.get("X-Forwarded-For", request.client.host)
        route_key = self._match_route(path)
        limit = ROUTE_LIMITS.get(route_key, _settings.rate_limit_global)

        try:
            redis = await get_redis()
            window = math.floor(time.time() / WINDOW_SECONDS)
            key = f"rl:{route_key}:{client_ip}:{window}"
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, WINDOW_SECONDS)

            remaining = max(limit - current, 0)
            reset = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)

            if current > limit:
                headers = {
                    "Retry-After": str(reset),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                }
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers=headers)

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset)
            return response
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "rate_limit_fail_open",
                path=path,
                client_ip=client_ip,
                error=str(exc),
            )
            response = await call_next(request)
            response.headers.setdefault("X-RateLimit-Limit", str(limit))
            response.headers.setdefault("X-RateLimit-Remaining", "unavailable")
            response.headers.setdefault("X-RateLimit-Reset", "unavailable")
            return response

    @staticmethod
    def _match_route(path: str) -> str:
        for route in ROUTE_LIMITS.keys():
            if path.startswith(route):
                return route
        return "global"

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import get_settings

_settings = get_settings()

EXCLUDED_PATHS = {"/api/v1/health", "/metrics", "/api/v1/asr/stream"}


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        tokens = _settings.api_tokens
        if not tokens:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        token = auth_header.split(" ", 1)[1]
        if token not in tokens:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)

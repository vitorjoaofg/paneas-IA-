import time

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        # Skip middleware for long-running requests and WebSocket connections
        # to avoid BaseHTTPMiddleware timeout issues
        if request.url.path in ["/api/v1/asr", "/api/v1/diar", "/api/v1/asr/stream"]:
            # Check if diarization is enabled (form data parsing is complex in middleware)
            # So we just skip middleware for all ASR/diar requests and WebSocket
            response = await call_next(request)
            return response

        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        # Get API key info if available
        api_key_info = getattr(request.state, "api_key_info", None)
        api_key_id = api_key_info.get('id') if api_key_info else None
        api_key_name = api_key_info.get('name') if api_key_info else None

        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=getattr(request.state, "request_id", None),
            api_key_id=str(api_key_id) if api_key_id else None,
            api_key_name=api_key_name,
            client_ip=request.headers.get("X-Forwarded-For", request.client.host),
        )
        return response

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

        # Skip middleware for long-running ASR requests with diarization
        # to avoid BaseHTTPMiddleware timeout issues
        if request.url.path in ["/api/v1/asr", "/api/v1/diar"]:
            # Check if diarization is enabled (form data parsing is complex in middleware)
            # So we just skip middleware for all ASR/diar requests
            response = await call_next(request)
            return response

        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=getattr(request.state, "request_id", None),
            client_ip=request.headers.get("X-Forwarded-For", request.client.host),
        )
        return response

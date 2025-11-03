import asyncio
from typing import Callable
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from services.api_key_manager import validate_api_key, update_last_used
from services.auth_service import decode_access_token, get_user_by_id

EXCLUDED_PATHS = {"/api/v1/health", "/metrics", "/api/v1/asr/stream", "/auth/google/login", "/auth/google/callback"}


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        # Allow CORS preflight requests (OPTIONS) without authentication
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow public access to frontend static files (anything not under /api/ or /metrics)
        if not path.startswith("/api/") and path != "/metrics":
            return await call_next(request)

        if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse({"detail": "Unauthorized - Authentication required"}, status_code=401)

        # Extract token/key
        token = auth_header.split(" ", 1)[1]

        # Determine if it's an API key (sk-proj-*) or JWT token (eyJ*)
        if token.startswith("sk-proj-"):
            # API Key authentication
            key_info = await validate_api_key(token)

            if not key_info:
                return JSONResponse({"detail": "Unauthorized - Invalid API key"}, status_code=401)

            # Attach key info to request state for use in handlers
            request.state.api_key_info = key_info
            request.state.auth_type = "api_key"

            # Update last_used_at asynchronously (fire and forget, don't block request)
            asyncio.create_task(update_last_used(key_info['id']))

        elif token.startswith("eyJ"):
            # JWT token authentication
            payload = decode_access_token(token)

            if not payload:
                return JSONResponse({"detail": "Unauthorized - Invalid or expired token"}, status_code=401)

            # Get user info from database
            user_id = payload.get("sub")
            if not user_id:
                return JSONResponse({"detail": "Unauthorized - Invalid token payload"}, status_code=401)

            try:
                user = await get_user_by_id(UUID(user_id))
            except Exception:
                return JSONResponse({"detail": "Unauthorized - Invalid user"}, status_code=401)

            if not user:
                return JSONResponse({"detail": "Unauthorized - User not found or inactive"}, status_code=401)

            # Attach user info to request state
            request.state.user_info = user
            request.state.auth_type = "jwt"

        else:
            return JSONResponse({"detail": "Unauthorized - Invalid token format"}, status_code=401)

        return await call_next(request)

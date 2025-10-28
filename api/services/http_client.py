from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from httpx import AsyncClient, Limits, Timeout
from tenacity import AsyncRetrying, RetryError, retry_if_exception_type, stop_after_attempt, wait_exponential

_http_client: AsyncClient | None = None


async def get_http_client() -> AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = AsyncClient(
            timeout=Timeout(30.0, connect=5.0, read=30.0),
            limits=Limits(max_connections=200, max_keepalive_connections=100),
        )
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class TransientHTTPError(Exception):
    """Raised for retryable HTTP status codes (5xx)."""


async def request_with_retry(
    method: str,
    url: str,
    *,
    client: Optional[AsyncClient] = None,
    retry_attempts: int = 3,
    retry_logger: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> httpx.Response:
    """Issue an HTTP request with exponential backoff retry on transport/5xx errors."""
    session = client or await get_http_client()
    logger = retry_logger or logging.getLogger("services.http_client")

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(retry_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.TimeoutException, TransientHTTPError)
        ),
        reraise=True,
    ):
        with attempt:
            try:
                response = await session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if 500 <= status_code < 600:
                    logger.warning(
                        "http_request_retryable_error",
                        extra={
                            "method": method,
                            "url": url,
                            "status_code": status_code,
                            "attempt_number": attempt.retry_state.attempt_number,
                        },
                    )
                    raise TransientHTTPError(str(exc)) from exc
                raise

    # Should not reach here because AsyncRetrying with reraise=True propagates the last error.
    raise RuntimeError("Unexpected retry termination")  # pragma: no cover

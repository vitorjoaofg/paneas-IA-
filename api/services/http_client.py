from httpx import AsyncClient, Timeout

_http_client: AsyncClient | None = None


async def get_http_client() -> AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = AsyncClient(timeout=Timeout(120.0, connect=5.0))
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None

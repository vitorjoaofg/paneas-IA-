from redis.asyncio import Redis

from config import get_settings

_settings = get_settings()

_redis_cache: Redis | None = None


async def get_redis() -> Redis:
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = Redis(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_db_cache,
            decode_responses=True,
        )
    return _redis_cache


async def close_redis() -> None:
    global _redis_cache
    if _redis_cache is not None:
        await _redis_cache.close()
        _redis_cache = None

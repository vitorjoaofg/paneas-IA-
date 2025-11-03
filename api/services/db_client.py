"""Database client for PostgreSQL using asyncpg."""

import asyncpg
from functools import lru_cache
from typing import Optional
from contextlib import asynccontextmanager

from config import get_settings

_settings = get_settings()
_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=_settings.postgres_host,
            port=_settings.postgres_port,
            user=_settings.postgres_user,
            password=_settings.postgres_password,
            database=_settings.postgres_db,
            min_size=5,
            max_size=20,
            command_timeout=10.0,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_db_connection():
    """Context manager for database connections."""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        yield connection

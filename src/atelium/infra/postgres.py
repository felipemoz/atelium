from __future__ import annotations
import logging

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.postgres_dsn,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("PostgreSQL pool created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def ping_postgres() -> bool:
    try:
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        return True
    except Exception as exc:
        logger.error("PostgreSQL ping failed: %s", exc)
        return False

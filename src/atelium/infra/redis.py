from __future__ import annotations
import logging
from typing import Any

import redis.asyncio as aioredis

from ..config import settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


async def ping_redis() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception as exc:
        logger.error("Redis ping failed: %s", exc)
        return False


# ------------------------------------------------------------------
# Agent registry helpers (Redis Stack / RediSearch)
# ------------------------------------------------------------------

async def register_agent_vector(
    redis: aioredis.Redis,
    agent_name: str,
    version: str,
    capability_vector: bytes,
    input_types: list[str],
    max_concurrent: int = 10,
) -> None:
    import time
    key = f"agent:{agent_name}"
    await redis.hset(key, mapping={
        "name": agent_name,
        "version": version,
        "capability_vector": capability_vector,
        "input_types": ",".join(input_types),
        "max_concurrent_pipelines": max_concurrent,
        "registered_at": time.time(),
    })


async def ensure_vector_index(redis: aioredis.Redis, dim: int = 1536) -> None:
    """Create RediSearch index if it doesn't exist."""
    try:
        await redis.ft("agent_capabilities").info()
    except Exception:
        try:
            await redis.ft("agent_capabilities").create_index(
                fields=[
                    {"type": "TAG", "name": "name"},
                    {"type": "TAG", "name": "input_types"},
                    {"type": "VECTOR", "name": "capability_vector", "attributes": {
                        "TYPE": "FLOAT32",
                        "DIM": dim,
                        "DISTANCE_METRIC": "COSINE",
                    }},
                ],
                definition={"PREFIX": ["agent:"]},
            )
            logger.info("Created agent_capabilities RediSearch index (dim=%d)", dim)
        except Exception as exc:
            logger.error("Failed to create vector index: %s", exc)

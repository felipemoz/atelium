from fastapi import APIRouter
from ...infra.redis import ping_redis
from ...infra.postgres import ping_postgres
from ...infra.ollama import get_ollama

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    redis_ok = await ping_redis()
    pg_ok = await ping_postgres()
    ollama_ok = await get_ollama().ping()

    all_ok = redis_ok and pg_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "redis": redis_ok,
        "postgres": pg_ok,
        "ollama": ollama_ok,
    }


@router.get("/ready")
async def ready():
    return {"status": "ready"}

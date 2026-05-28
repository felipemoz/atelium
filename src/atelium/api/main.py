from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import agents, pipelines, hitl, health
from ..infra.redis import close_redis
from ..infra.postgres import close_pool
from ..infra.nats import close_nats
from ..config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    await close_redis()
    await close_pool()
    await close_nats()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Atelium",
        description="Fault-Tolerant Agent Network Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(pipelines.router, prefix="/api/v1")
    app.include_router(hitl.router, prefix="/api/v1")

    # Prometheus metrics
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app)
    except ImportError:
        pass

    return app


app = create_app()

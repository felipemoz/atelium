from __future__ import annotations
from typing import Annotated

from fastapi import Depends

from ..infra.redis import get_redis
from ..infra.postgres import get_pool
from ..infra.ollama import get_ollama, OllamaClient
from ..core.state import StepStateManager
from ..core.router import EmergentRouter
from ..runtime.executor import AgentExecutor
from ..runtime.graph import PipelineGraph
from ..runtime.registry import AgentRegistry


async def get_state_manager() -> StepStateManager:
    redis = await get_redis()
    pool = await get_pool()
    return StepStateManager(redis_client=redis, postgres_pool=pool)


async def get_router() -> EmergentRouter:
    redis = await get_redis()
    pool = await get_pool()
    ollama = get_ollama()
    return EmergentRouter(redis_client=redis, postgres_pool=pool, embedder=ollama)


async def get_executor(
    state: Annotated[StepStateManager, Depends(get_state_manager)],
    router: Annotated[EmergentRouter, Depends(get_router)],
) -> AgentExecutor:
    return AgentExecutor(
        state_manager=state,
        llm_client=get_ollama(),
        router=router,
    )


async def get_pipeline_graph(
    state: Annotated[StepStateManager, Depends(get_state_manager)],
    executor: Annotated[AgentExecutor, Depends(get_executor)],
    router: Annotated[EmergentRouter, Depends(get_router)],
) -> PipelineGraph:
    return PipelineGraph(state_manager=state, executor=executor, router=router)


async def get_registry() -> AgentRegistry:
    return AgentRegistry()

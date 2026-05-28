from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_pipeline_graph, get_state_manager, get_registry
from ...runtime.graph import PipelineGraph
from ...core.state import StepStateManager
from ...runtime.registry import AgentRegistry

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class RunRequest(BaseModel):
    manifest_name: str
    input: dict


class PipelineResponse(BaseModel):
    pipeline_id: str
    status: str
    elapsed_ms: int | None = None


@router.post("/run", response_model=PipelineResponse)
async def run_pipeline(
    req: RunRequest,
    graph: Annotated[PipelineGraph, Depends(get_pipeline_graph)],
    registry: Annotated[AgentRegistry, Depends(get_registry)],
):
    manifest = await registry.get(req.manifest_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent {req.manifest_name!r} not registered")

    pipeline = await graph.run(manifest=manifest, input_data=req.input)
    return PipelineResponse(
        pipeline_id=str(pipeline.pipeline_id),
        status=pipeline.status.value,
        elapsed_ms=pipeline.elapsed_ms,
    )


@router.get("/{pipeline_id}/steps")
async def get_pipeline_steps(
    pipeline_id: UUID,
    state: Annotated[StepStateManager, Depends(get_state_manager)],
):
    steps = await state.load_pipeline_steps(pipeline_id)
    if not steps:
        raise HTTPException(status_code=404, detail="Pipeline not found or has no steps")
    return [
        {
            "step_id": str(s.step_id),
            "agent_name": s.agent_name,
            "status": s.status.value,
            "iteration": s.iteration,
            "elapsed_ms": s.elapsed_ms,
            "tokens_used": s.tokens_used,
            "cost_usd": s.cost_usd,
        }
        for s in steps
    ]


@router.get("/{pipeline_id}/steps/{step_id}")
async def get_step(
    pipeline_id: UUID,
    step_id: UUID,
    state: Annotated[StepStateManager, Depends(get_state_manager)],
):
    step = await state.load_step(step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Step not found")
    return {
        "step_id": str(step.step_id),
        "pipeline_id": str(step.pipeline_id),
        "agent_name": step.agent_name,
        "status": step.status.value,
        "iteration": step.iteration,
        "input": step.input,
        "output": step.output,
        "validation_errors": step.validation_errors,
        "elapsed_ms": step.elapsed_ms,
        "tokens_used": step.tokens_used,
        "cost_usd": step.cost_usd,
    }

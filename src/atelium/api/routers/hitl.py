from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_state_manager
from ...core.state import StepStateManager
from ...core.models import StepStatus
from ...infra import publish

router = APIRouter(prefix="/hitl", tags=["hitl"])


class HITLDecision(BaseModel):
    approved: bool
    output: dict | None = None
    rejection_reason: str | None = None


@router.post("/{step_id}/decide", status_code=200)
async def decide(
    step_id: UUID,
    decision: HITLDecision,
    state: Annotated[StepStateManager, Depends(get_state_manager)],
):
    step = await state.load_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if step.status != StepStatus.WAITING_HITL:
        raise HTTPException(
            status_code=409,
            detail=f"Step is not waiting for HITL (status={step.status.value})",
        )

    if decision.approved:
        if decision.output:
            step.output = decision.output
        step.status = StepStatus.SUCCEEDED
    else:
        step.mark_failed([decision.rejection_reason or "Rejected by human reviewer"])

    await state.save_step(step)

    await publish("atelium.hitl.decided", {
        "step_id": str(step_id),
        "pipeline_id": str(step.pipeline_id),
        "approved": decision.approved,
    })

    return {"step_id": str(step_id), "status": step.status.value}


@router.get("/pending")
async def list_pending(
    state: Annotated[StepStateManager, Depends(get_state_manager)],
):
    """Returns WAITING_HITL steps (requires PostgreSQL query)."""
    from ...infra.postgres import get_pool
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT step_id, pipeline_id, agent_name, started_at FROM steps WHERE status = 'waiting_hitl' ORDER BY started_at"
    )
    return [
        {
            "step_id": str(r["step_id"]),
            "pipeline_id": str(r["pipeline_id"]),
            "agent_name": r["agent_name"],
            "waiting_since": r["started_at"].isoformat(),
        }
        for r in rows
    ]

from __future__ import annotations
import json
import logging
from uuid import UUID
from datetime import datetime

from .models import Step, StepStatus, StepSummary, CompensationStatus

logger = logging.getLogger(__name__)

_STEP_HOT_TTL = 86400  # 24h in Redis


def _step_key(step_id: UUID) -> str:
    return f"step:{step_id}"


def _pipeline_steps_key(pipeline_id: UUID) -> str:
    return f"pipeline:{pipeline_id}:steps"


class StepStateManager:
    """Hot path via Redis; cold archive via PostgreSQL."""

    def __init__(self, redis_client=None, postgres_pool=None):
        self._redis = redis_client
        self._pg = postgres_pool

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_step(self, step: Step) -> None:
        await self._save_hot(step)
        await self._save_cold(step)

    async def _save_hot(self, step: Step) -> None:
        if not self._redis:
            return
        data = _serialize_step(step)
        key = _step_key(step.step_id)
        await self._redis.setex(key, _STEP_HOT_TTL, json.dumps(data))
        await self._redis.sadd(_pipeline_steps_key(step.pipeline_id), str(step.step_id))

    async def _save_cold(self, step: Step) -> None:
        if not self._pg:
            return
        try:
            data = _serialize_step(step)
            await self._pg.execute(
                """
                INSERT INTO steps (
                    step_id, pipeline_id, parent_step_id, branch_id, agent_name,
                    agent_version, status, iteration, input, output,
                    validation_errors, snapshot, tokens_used, cost_usd,
                    started_at, completed_at, elapsed_ms
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17
                )
                ON CONFLICT (step_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    iteration = EXCLUDED.iteration,
                    output = EXCLUDED.output,
                    validation_errors = EXCLUDED.validation_errors,
                    snapshot = EXCLUDED.snapshot,
                    tokens_used = EXCLUDED.tokens_used,
                    cost_usd = EXCLUDED.cost_usd,
                    completed_at = EXCLUDED.completed_at,
                    elapsed_ms = EXCLUDED.elapsed_ms
                """,
                step.step_id, step.pipeline_id, step.parent_step_id, step.branch_id,
                step.agent_name, step.agent_version, step.status.value, step.iteration,
                json.dumps(step.input), json.dumps(step.output) if step.output else None,
                json.dumps(step.validation_errors), json.dumps(step.snapshot) if step.snapshot else None,
                step.tokens_used, step.cost_usd, step.started_at, step.completed_at, step.elapsed_ms,
            )
        except Exception as exc:
            logger.error("Failed to archive step %s: %s", step.step_id, exc)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def load_step(self, step_id: UUID) -> Step | None:
        step = await self._load_hot(step_id)
        if step:
            return step
        return await self._load_cold(step_id)

    async def _load_hot(self, step_id: UUID) -> Step | None:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(_step_key(step_id))
            if raw:
                return _deserialize_step(json.loads(raw))
        except Exception as exc:
            logger.warning("Redis load failed for step %s: %s", step_id, exc)
        return None

    async def _load_cold(self, step_id: UUID) -> Step | None:
        if not self._pg:
            return None
        try:
            row = await self._pg.fetchrow(
                "SELECT * FROM steps WHERE step_id = $1", step_id
            )
            if row:
                return _row_to_step(row)
        except Exception as exc:
            logger.error("PG load failed for step %s: %s", step_id, exc)
        return None

    async def load_pipeline_steps(self, pipeline_id: UUID) -> list[Step]:
        steps: list[Step] = []
        if self._redis:
            try:
                ids = await self._redis.smembers(_pipeline_steps_key(pipeline_id))
                for sid in ids:
                    s = await self._load_hot(UUID(sid.decode()))
                    if s:
                        steps.append(s)
                if steps:
                    steps.sort(key=lambda s: s.started_at)
                    return steps
            except Exception:
                pass
        if self._pg:
            try:
                rows = await self._pg.fetch(
                    "SELECT * FROM steps WHERE pipeline_id = $1 ORDER BY started_at", pipeline_id
                )
                return [_row_to_step(r) for r in rows]
            except Exception as exc:
                logger.error("PG load pipeline steps failed: %s", exc)
        return steps

    # ------------------------------------------------------------------
    # Context window
    # ------------------------------------------------------------------

    async def build_context_window(
        self, pipeline_id: UUID, current_step_id: UUID, max_summaries: int = 10
    ) -> list[StepSummary]:
        steps = await self.load_pipeline_steps(pipeline_id)
        summaries = []
        for s in steps:
            if s.step_id == current_step_id:
                break
            if s.status == StepStatus.SUCCEEDED:
                summaries.append(s.to_summary())
        return summaries[-max_summaries:]

    # ------------------------------------------------------------------
    # Fork / Merge
    # ------------------------------------------------------------------

    async def fork_step(
        self, parent: Step, branch_inputs: list[dict], agent_names: list[str], agent_version: str = "0.0.0"
    ) -> list[Step]:
        branches = []
        for i, (inp, name) in enumerate(zip(branch_inputs, agent_names)):
            child = Step(
                pipeline_id=parent.pipeline_id,
                agent_name=name,
                agent_version=agent_version,
                input=inp,
                parent_step_id=parent.step_id,
                branch_id=f"{parent.step_id}:branch:{i}",
            )
            child.context_window = list(parent.context_window)
            await self.save_step(child)
            branches.append(child)
        return branches

    async def merge_steps(self, steps: list[Step]) -> dict:
        merged: dict = {}
        for s in steps:
            if s.output:
                merged.update(s.output)
        return merged


# ------------------------------------------------------------------
# Serialization helpers
# ------------------------------------------------------------------

def _serialize_step(step: Step) -> dict:
    return {
        "step_id": str(step.step_id),
        "pipeline_id": str(step.pipeline_id),
        "parent_step_id": str(step.parent_step_id) if step.parent_step_id else None,
        "branch_id": step.branch_id,
        "agent_name": step.agent_name,
        "agent_version": step.agent_version,
        "status": step.status.value,
        "iteration": step.iteration,
        "input": step.input,
        "output": step.output,
        "validation_errors": step.validation_errors,
        "snapshot": step.snapshot,
        "tokens_used": step.tokens_used,
        "cost_usd": step.cost_usd,
        "started_at": step.started_at.isoformat(),
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "elapsed_ms": step.elapsed_ms,
        "otel_trace_id": step.otel_trace_id,
        "langfuse_trace_id": step.langfuse_trace_id,
    }


def _deserialize_step(data: dict) -> Step:
    step = Step(
        pipeline_id=UUID(data["pipeline_id"]),
        agent_name=data["agent_name"],
        agent_version=data["agent_version"],
        input=data["input"],
    )
    step.step_id = UUID(data["step_id"])
    step.parent_step_id = UUID(data["parent_step_id"]) if data.get("parent_step_id") else None
    step.branch_id = data.get("branch_id")
    step.status = StepStatus(data["status"])
    step.iteration = data["iteration"]
    step.output = data.get("output")
    step.validation_errors = data.get("validation_errors", [])
    step.snapshot = data.get("snapshot")
    step.tokens_used = data.get("tokens_used", 0)
    step.cost_usd = data.get("cost_usd", 0.0)
    step.started_at = datetime.fromisoformat(data["started_at"])
    step.completed_at = datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
    step.elapsed_ms = data.get("elapsed_ms")
    step.otel_trace_id = data.get("otel_trace_id", "")
    step.langfuse_trace_id = data.get("langfuse_trace_id", "")
    return step


def _row_to_step(row) -> Step:
    step = Step(
        pipeline_id=row["pipeline_id"],
        agent_name=row["agent_name"],
        agent_version=row["agent_version"],
        input=json.loads(row["input"]) if isinstance(row["input"], str) else row["input"],
    )
    step.step_id = row["step_id"]
    step.parent_step_id = row.get("parent_step_id")
    step.branch_id = row.get("branch_id")
    step.status = StepStatus(row["status"])
    step.iteration = row["iteration"]
    raw_output = row.get("output")
    step.output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
    raw_errors = row.get("validation_errors", "[]")
    step.validation_errors = json.loads(raw_errors) if isinstance(raw_errors, str) else (raw_errors or [])
    raw_snap = row.get("snapshot")
    step.snapshot = json.loads(raw_snap) if isinstance(raw_snap, str) else raw_snap
    step.tokens_used = row.get("tokens_used", 0)
    step.cost_usd = float(row.get("cost_usd", 0.0))
    step.started_at = row["started_at"]
    step.completed_at = row.get("completed_at")
    step.elapsed_ms = row.get("elapsed_ms")
    return step

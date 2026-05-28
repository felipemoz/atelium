from __future__ import annotations
import asyncio
import logging
from uuid import UUID

from ..manifest.schema import AgentManifest, DelegationMode, AggregationMode, MergeStrategy
from ..config import settings
from .models import (
    Step, Pipeline, PipelineStatus, AggregationResult, StepStatus,
)
from .state import StepStateManager

logger = logging.getLogger(__name__)


class TopologyManager:
    """Orchestrates 1:1, 1:N (fan-out), and N:1 (fan-in) topologies."""

    def __init__(self, state_manager: StepStateManager):
        self._state = state_manager

    # ------------------------------------------------------------------
    # Fan-out  (1:N)
    # ------------------------------------------------------------------

    async def fan_out(
        self,
        parent_step: Step,
        manifest: AgentManifest,
        executor,  # AgentExecutor injected at runtime
    ) -> list[Step]:
        topo = manifest.spec.topology
        if not hasattr(topo, "delegates") or not topo.delegates:
            raise ValueError("fan_out requires topology.delegates list")

        branch_steps = await self._state.fork_step(
            parent=parent_step,
            branch_inputs=[parent_step.input] * len(topo.delegates),
            agent_names=[d.agent for d in topo.delegates],
        )

        tasks = [executor.execute_step(s) for s in branch_steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed = []
        for step, result in zip(branch_steps, results):
            if isinstance(result, Exception):
                step.mark_failed([str(result)])
                logger.error("Branch step %s failed: %s", step.step_id, result)
            else:
                completed.append(step)
        return completed

    # ------------------------------------------------------------------
    # Fan-in  (N:1)
    # ------------------------------------------------------------------

    async def fan_in(
        self,
        branch_steps: list[Step],
        manifest: AgentManifest,
        pipeline: Pipeline,
    ) -> AggregationResult:
        topo = manifest.spec.topology
        agg = topo.aggregation
        timeout_s = settings.hitl_timeout_ms / 1000

        pending_ids = {s.step_id for s in branch_steps if s.status != StepStatus.SUCCEEDED}

        deadline = asyncio.get_event_loop().time() + timeout_s
        completed_steps: list[Step] = []
        timed_out_steps: list[Step] = []

        for s in branch_steps:
            if s.status == StepStatus.SUCCEEDED:
                completed_steps.append(s)
            else:
                timed_out_steps.append(s)

        if agg.mode == AggregationMode.WAIT_ALL:
            pass  # already partitioned above; caller handles timeout
        elif agg.mode == AggregationMode.WAIT_QUORUM:
            threshold = agg.quorum_threshold or (len(branch_steps) // 2 + 1)
            if len(completed_steps) < threshold:
                logger.warning(
                    "Quorum not reached: %d/%d (need %d)",
                    len(completed_steps), len(branch_steps), threshold,
                )

        merged = await self._merge_outputs(completed_steps, agg.merge_strategy)
        return AggregationResult(
            completed=completed_steps,
            timed_out=timed_out_steps,
            merged_output=merged,
        )

    async def _merge_outputs(
        self, steps: list[Step], strategy: MergeStrategy
    ) -> dict:

        if strategy == MergeStrategy.UNION:
            merged: dict = {}
            for s in steps:
                if s.output:
                    merged.update(s.output)
            return merged

        elif strategy == MergeStrategy.INTERSECTION:
            if not steps:
                return {}
            keys = set(steps[0].output or {})
            for s in steps[1:]:
                keys &= set(s.output or {})
            merged = {}
            for k in keys:
                # last-write wins for intersection keys
                for s in steps:
                    if s.output and k in s.output:
                        merged[k] = s.output[k]
            return merged

        elif strategy == MergeStrategy.FIRST_WINS:
            for s in steps:
                if s.output:
                    return dict(s.output)
            return {}

        elif strategy == MergeStrategy.LAST_WINS:
            merged = {}
            for s in steps:
                if s.output:
                    merged = dict(s.output)
            return merged

        elif strategy == MergeStrategy.CUSTOM:
            # Custom merge delegates to a dedicated agent; return raw list for caller
            return {"_branches": [s.output for s in steps if s.output]}

        # Default: UNION
        merged = {}
        for s in steps:
            if s.output:
                merged.update(s.output)
        return merged

    # ------------------------------------------------------------------
    # Pipeline lifecycle helpers
    # ------------------------------------------------------------------

    def mark_pipeline_terminal(
        self, pipeline: Pipeline, failed: bool = False, compensated: bool = False
    ) -> None:
        if compensated:
            pipeline.status = PipelineStatus.COMPENSATED
            pipeline.completed_at = __import__("datetime").datetime.utcnow()
        elif failed:
            pipeline.mark_failed()
        else:
            pipeline.mark_succeeded()

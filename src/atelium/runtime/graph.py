from __future__ import annotations
import asyncio
import logging
from uuid import UUID

from ..manifest.schema import AgentManifest, DelegationMode, AggregationMode
from ..core.models import Pipeline, Step, PipelineStatus, StepStatus
from ..core.state import StepStateManager
from ..core.topology import TopologyManager
from ..core.saga import SagaCoordinator
from ..core.router import EmergentRouter, RoutingRequest
from .executor import AgentExecutor
from ..infra import publish

logger = logging.getLogger(__name__)


class PipelineGraph:
    """
    Top-level pipeline orchestrator.
    Implements the three topologies: 1:1, 1:N fan-out, N:1 fan-in.
    """

    def __init__(
        self,
        state_manager: StepStateManager,
        executor: AgentExecutor,
        router: EmergentRouter | None = None,
    ):
        self._state = state_manager
        self._executor = executor
        self._router = router
        self._topology = TopologyManager(state_manager)
        self._saga = SagaCoordinator()

    async def run(
        self,
        manifest: AgentManifest,
        input_data: dict,
        pipeline_id: UUID | None = None,
    ) -> Pipeline:
        pipeline = Pipeline(manifest_name=manifest.metadata.name)
        if pipeline_id:
            pipeline.pipeline_id = pipeline_id

        await publish("atelium.pipeline.started", {
            "pipeline_id": str(pipeline.pipeline_id),
            "manifest_name": manifest.metadata.name,
        })

        topo = manifest.spec.topology
        mode = topo.delegation.mode

        try:
            if mode == DelegationMode.DIRECT:
                await self._run_direct(pipeline, manifest, input_data)

            elif mode == DelegationMode.DELEGATE:
                await self._run_fan_out(pipeline, manifest, input_data)

            elif mode == DelegationMode.ROUTE_BEST:
                await self._run_emergent(pipeline, manifest, input_data, n=1)

            elif mode == DelegationMode.ROUTE_N:
                await self._run_emergent(pipeline, manifest, input_data, n=topo.delegation.n or 1)

            elif mode == DelegationMode.ROUTE_ALL:
                await self._run_emergent(pipeline, manifest, input_data, n=0)

        except Exception as exc:
            logger.error("Pipeline %s failed: %s", pipeline.pipeline_id, exc)
            pipeline.mark_failed()

        await publish("atelium.pipeline.completed", {
            "pipeline_id": str(pipeline.pipeline_id),
            "status": pipeline.status.value,
        })
        return pipeline

    # ------------------------------------------------------------------
    # 1:1 Direct execution
    # ------------------------------------------------------------------

    async def _run_direct(
        self, pipeline: Pipeline, manifest: AgentManifest, input_data: dict
    ) -> None:
        step = Step(
            pipeline_id=pipeline.pipeline_id,
            agent_name=manifest.metadata.name,
            agent_version=manifest.metadata.version,
            input=input_data,
        )

        # Build context window from prior pipeline steps
        step.context_window = await self._state.build_context_window(
            pipeline.pipeline_id, step.step_id
        )

        step = await self._executor.execute_step(step, manifest)

        if step.status == StepStatus.SUCCEEDED:
            pipeline.mark_succeeded()
        else:
            await self._handle_failure(pipeline, step, manifest)

    # ------------------------------------------------------------------
    # 1:N Fan-out
    # ------------------------------------------------------------------

    async def _run_fan_out(
        self, pipeline: Pipeline, manifest: AgentManifest, input_data: dict
    ) -> None:
        topo = manifest.spec.topology
        delegates = topo.delegates or []

        if not delegates:
            logger.warning("DELEGATE mode with no delegates — falling back to DIRECT")
            await self._run_direct(pipeline, manifest, input_data)
            return

        # Execute all branches concurrently
        tasks = []
        branch_steps = []
        for delegate in delegates:
            step = Step(
                pipeline_id=pipeline.pipeline_id,
                agent_name=delegate.agent,
                agent_version="latest",
                input={**input_data, **(delegate.input_override or {})},
            )
            branch_steps.append(step)

        # We need manifests for each delegate agent — use a stub manifest derived from parent
        # In a full implementation, each delegate would have its own loaded manifest
        results = await asyncio.gather(
            *[self._executor.execute_step(s, manifest) for s in branch_steps],
            return_exceptions=True,
        )

        completed = []
        failed = []
        for step, result in zip(branch_steps, results):
            if isinstance(result, Exception):
                step.mark_failed([str(result)])
                failed.append(step)
            elif result.status == StepStatus.SUCCEEDED:
                completed.append(result)
            else:
                failed.append(result)

        agg_result = await self._topology.fan_in(completed + failed, manifest, pipeline)

        if agg_result.completed:
            pipeline.mark_succeeded()
        else:
            pipeline.mark_failed()

    # ------------------------------------------------------------------
    # Emergent routing
    # ------------------------------------------------------------------

    async def _run_emergent(
        self,
        pipeline: Pipeline,
        manifest: AgentManifest,
        input_data: dict,
        n: int,
    ) -> None:
        if not self._router:
            logger.warning("Emergent routing requested but no router configured")
            await self._run_direct(pipeline, manifest, input_data)
            return

        request = RoutingRequest(
            task_description=manifest.spec.task.description,
            input_types=manifest.spec.accepts.types,
            pipeline_id=str(pipeline.pipeline_id),
            required_capabilities=list(manifest.spec.capabilities),
        )

        routing_mode = manifest.spec.topology.delegation.mode
        decisions = await self._router.route(request, mode=routing_mode, n=n or 100)

        if not decisions:
            logger.error("No agents found for emergent routing")
            pipeline.mark_failed()
            return

        steps = []
        for decision in decisions:
            step = Step(
                pipeline_id=pipeline.pipeline_id,
                agent_name=decision.agent_name,
                agent_version=decision.agent_version,
                input=input_data,
            )
            steps.append(step)

        results = await asyncio.gather(
            *[self._executor.execute_step(s, manifest) for s in steps],
            return_exceptions=True,
        )

        any_success = any(
            not isinstance(r, Exception) and r.status == StepStatus.SUCCEEDED
            for r in results
        )
        if any_success:
            pipeline.mark_succeeded()
        else:
            pipeline.mark_failed()

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    async def _handle_failure(
        self, pipeline: Pipeline, step: Step, manifest: AgentManifest
    ) -> None:
        if step.status == StepStatus.WAITING_HITL:
            pipeline.status = PipelineStatus.WAITING_HITL
            return

        # Attempt SAGA compensation
        from ..core.models import SagaEntryStatus
        committed = [
            e for e in pipeline.saga_log
            if e.status == SagaEntryStatus.COMMITTED
        ]
        if committed:
            comp_result = await self._saga.compensate(
                pipeline, step.step_id, self._executor._mcp
            )
            if comp_result.failure_count == 0:
                pipeline.status = PipelineStatus.COMPENSATED
                pipeline.completed_at = __import__("datetime").datetime.utcnow()
                return

        pipeline.mark_failed()

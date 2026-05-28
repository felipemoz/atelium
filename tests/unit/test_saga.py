"""Tests for SagaCoordinator."""
from __future__ import annotations
import pytest
from uuid import uuid4

from atelium.core.models import (
    Pipeline, Step, SagaEntry, SagaEntryStatus, IrreversibilityClass,
)
from atelium.core.saga import SagaCoordinator
from atelium.manifest.schema import (
    AgentManifest, AgentMetadata, AgentSpec, ModelSpec, AcceptsSpec,
    TaskSpec, SagaSpec, TopologySpec, BlastRadiusSpec, ObservabilitySpec,
    SelfHealingSpec, SelfHealingStrategy, IrreversibleAction, IrreversibilityRequires,
)


def _make_manifest(
    irreversible=None, snapshot_before=None, compensating_action="rollback"
) -> AgentManifest:
    saga = SagaSpec(
        irreversible_actions=irreversible or [],
        snapshot_before=snapshot_before or [],
        compensating_action=compensating_action,
    )
    task = TaskSpec(
        description="test",
        prompt_template="test {x}",
        self_healing=SelfHealingSpec(
            strategy=SelfHealingStrategy.RETRY_WITH_FEEDBACK,
            max_iterations=2,
            feedback_template="fix: {validation_errors}",
        ),
    )
    return AgentManifest(
        metadata=AgentMetadata(name="saga-agent", owner="test", version="0.1.0"),
        spec=AgentSpec(
            model=ModelSpec(name="llama3"),
            capabilities=["test"],
            accepts=AcceptsSpec(types=["text"]),
            task=task,
            saga=saga,
            topology=TopologySpec(),
            blast_radius=BlastRadiusSpec(),
            observability=ObservabilitySpec(),
        ),
    )


class TestSagaCoordinator:
    def setup_method(self):
        self.coord = SagaCoordinator()

    def _make_step(self) -> Step:
        return Step(
            pipeline_id=uuid4(),
            agent_name="saga-agent",
            agent_version="0.1.0",
            input={"x": 1},
        )

    def _make_pipeline(self) -> Pipeline:
        return Pipeline(manifest_name="saga-agent")

    def test_classify_reversible(self):
        manifest = _make_manifest()
        cls = self.coord.classify_action("send_email", manifest)
        assert cls == IrreversibilityClass.REVERSIBLE

    def test_classify_irreversible(self):
        manifest = _make_manifest(
            irreversible=[IrreversibleAction(
                name="delete_account",
                requires=IrreversibilityRequires.PRE_CONFIRMATION,
            )]
        )
        cls = self.coord.classify_action("delete_account", manifest)
        assert cls == IrreversibilityClass.IRREVERSIBLE

    def test_classify_compensable(self):
        manifest = _make_manifest(snapshot_before=["charge_card"])
        cls = self.coord.classify_action("charge_card", manifest)
        assert cls == IrreversibilityClass.COMPENSABLE

    def test_register_step_adds_to_saga_log(self):
        manifest = _make_manifest()
        pipeline = self._make_pipeline()
        step = self._make_step()
        entry = self.coord.register_step(pipeline, step, manifest)
        assert entry is not None
        assert len(pipeline.saga_log) == 1
        assert pipeline.saga_log[0].compensating_action == "rollback"

    def test_register_step_no_compensating_action(self):
        manifest = _make_manifest(compensating_action=None)
        pipeline = self._make_pipeline()
        step = self._make_step()
        # SagaSpec allows compensating_action=None for agents that don't need it
        # register_step should return None
        # but our default has a value; test with explicit None
        manifest.spec.saga.compensating_action = None
        entry = self.coord.register_step(pipeline, step, manifest)
        assert entry is None
        assert len(pipeline.saga_log) == 0

    @pytest.mark.asyncio
    async def test_compensate_reverses_committed_entries(self):
        pipeline = self._make_pipeline()
        step = self._make_step()

        entry = SagaEntry(
            pipeline_id=pipeline.pipeline_id,
            step_id=step.step_id,
            agent_name="saga-agent",
            action_name="charge_card",
            irreversibility_class=IrreversibilityClass.COMPENSABLE,
            compensating_action="refund",
            status=SagaEntryStatus.COMMITTED,
        )
        pipeline.saga_log.append(entry)

        result = await self.coord.compensate(pipeline, step.step_id, mcp_executor=None)
        assert result.success_count == 1
        assert result.failure_count == 0
        assert entry.status == SagaEntryStatus.COMPENSATED

    @pytest.mark.asyncio
    async def test_compensate_skips_irreversible(self):
        pipeline = self._make_pipeline()
        step = self._make_step()

        entry = SagaEntry(
            pipeline_id=pipeline.pipeline_id,
            step_id=step.step_id,
            agent_name="saga-agent",
            action_name="delete_data",
            irreversibility_class=IrreversibilityClass.IRREVERSIBLE,
            compensating_action="noop",
            status=SagaEntryStatus.COMMITTED,
        )
        pipeline.saga_log.append(entry)

        result = await self.coord.compensate(pipeline, step.step_id, mcp_executor=None)
        # IRREVERSIBLE entries are acknowledged but not truly compensated
        assert entry.status == SagaEntryStatus.COMPENSATED  # best-effort

    def test_needs_gate(self):
        manifest = _make_manifest(
            irreversible=[IrreversibleAction(
                name="send_wire",
                requires=IrreversibilityRequires.PRE_CONFIRMATION,
            )]
        )
        req = self.coord.needs_gate("send_wire", manifest)
        assert req == IrreversibilityRequires.PRE_CONFIRMATION

    def test_needs_snapshot(self):
        manifest = _make_manifest(snapshot_before=["charge"])
        assert self.coord.needs_snapshot("charge", manifest) is True
        assert self.coord.needs_snapshot("other", manifest) is False

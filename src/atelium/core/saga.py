from __future__ import annotations
import logging
from uuid import UUID

from ..manifest.schema import AgentManifest, IrreversibilityRequires
from .models import (
    Step, Pipeline, SagaEntry, SagaEntryStatus,
    IrreversibilityClass, CompensationResult,
)

logger = logging.getLogger(__name__)


class SagaCoordinator:
    def classify_action(
        self, action_name: str, manifest: AgentManifest
    ) -> IrreversibilityClass:
        for action in manifest.spec.saga.irreversible_actions:
            if action.name == action_name:
                return IrreversibilityClass.IRREVERSIBLE
        if action_name in manifest.spec.saga.snapshot_before:
            return IrreversibilityClass.COMPENSABLE
        return IrreversibilityClass.REVERSIBLE

    def register_step(
        self, pipeline: Pipeline, step: Step, manifest: AgentManifest
    ) -> SagaEntry | None:
        comp_action = manifest.spec.saga.compensating_action
        if not comp_action:
            return None

        entry = SagaEntry(
            pipeline_id=pipeline.pipeline_id,
            step_id=step.step_id,
            agent_name=step.agent_name,
            action_name=step.agent_name,
            irreversibility_class=IrreversibilityClass.COMPENSABLE,
            compensating_action=comp_action,
            snapshot=step.snapshot,
        )
        pipeline.saga_log.append(entry)
        return entry

    def snapshot_before_action(self, step: Step, action_name: str, state: dict) -> None:
        step.snapshot = {"action": action_name, "state": state}

    async def compensate(
        self,
        pipeline: Pipeline,
        from_step_id: UUID,
        mcp_executor=None,
    ) -> CompensationResult:
        committed = [
            e for e in reversed(pipeline.saga_log)
            if e.status == SagaEntryStatus.COMMITTED
        ]

        for entry in committed:
            if entry.irreversibility_class == IrreversibilityClass.IRREVERSIBLE:
                logger.warning(
                    "Cannot compensate irreversible action '%s' for step %s",
                    entry.action_name,
                    entry.step_id,
                )
                entry.status = SagaEntryStatus.COMPENSATED  # best-effort acknowledgment
                continue

            entry.status = SagaEntryStatus.COMPENSATING
            try:
                if mcp_executor:
                    await mcp_executor.execute(entry.compensating_action, entry.snapshot)
                entry.status = SagaEntryStatus.COMPENSATED
                logger.info("Compensated step %s via '%s'", entry.step_id, entry.compensating_action)
            except Exception as exc:
                entry.status = SagaEntryStatus.FAILED
                logger.error("Compensation failed for step %s: %s", entry.step_id, exc)

        return CompensationResult(entries=committed)

    def needs_gate(self, action_name: str, manifest: AgentManifest) -> IrreversibilityRequires:
        for action in manifest.spec.saga.irreversible_actions:
            if action.name == action_name:
                return action.requires
        return IrreversibilityRequires.NONE

    def needs_snapshot(self, action_name: str, manifest: AgentManifest) -> bool:
        return action_name in manifest.spec.saga.snapshot_before

"""Tests for SelfHealingLoop."""
from __future__ import annotations
from uuid import uuid4

from atelium.core.models import Step, StepStatus, GuardResult, GuardAction, FailedCriterion
from atelium.core.self_healing import SelfHealingLoop
from atelium.manifest.schema import (
    AgentManifest, AgentMetadata, AgentSpec, ModelSpec, AcceptsSpec,
    TaskSpec, SagaSpec, TopologySpec, BlastRadiusSpec, ObservabilitySpec,
    SelfHealingSpec, SelfHealingStrategy, SuccessCriterion, CriterionType,
)


def _make_manifest() -> AgentManifest:
    task = TaskSpec(
        description="test",
        prompt_template="Analyze: {input}",
        success_criteria=[
            SuccessCriterion(field="status", type=CriterionType.ENUM, values=["ok"])
        ],
        self_healing=SelfHealingSpec(
            strategy=SelfHealingStrategy.RETRY_WITH_FEEDBACK,
            max_iterations=3,
            feedback_template=(
                "Your output had errors:\n{validation_errors}\n"
                "Criteria:\n{success_criteria}\n"
                "Fix fields: {failed_fields}"
            ),
        ),
    )
    return AgentManifest(
        metadata=AgentMetadata(name="heal-agent", owner="test", version="0.1.0"),
        spec=AgentSpec(
            model=ModelSpec(name="llama3"),
            capabilities=["test"],
            accepts=AcceptsSpec(types=["text"]),
            task=task,
            saga=SagaSpec(),
            topology=TopologySpec(),
            blast_radius=BlastRadiusSpec(),
            observability=ObservabilitySpec(),
        ),
    )


class TestSelfHealingLoop:
    def setup_method(self):
        self.healer = SelfHealingLoop()

    def _make_step(self, output=None, iteration=1) -> Step:
        step = Step(
            pipeline_id=uuid4(),
            agent_name="heal-agent",
            agent_version="0.1.0",
            input={"input": "test data"},
        )
        step.output = output or {"status": "error"}
        step.iteration = iteration
        return step

    def test_prepare_for_retry_increments_iteration(self):
        step = self._make_step(iteration=0)
        step = self.healer.prepare_step_for_retry(step)
        assert step.iteration == 1
        assert step.status == StepStatus.SELF_HEALING
        assert step.output is None
        assert step.validation_errors == []

    def test_build_feedback_messages_appends(self):
        manifest = _make_manifest()
        step = self._make_step(output={"status": "error"})
        guard_result = GuardResult(
            passed=False,
            action=GuardAction.SELF_HEAL,
            failed_criteria=[
                FailedCriterion(field="status", expected="one of ['ok']", actual="error")
            ],
        )
        original_messages = [
            {"role": "system", "content": "Analyze: test data"},
            {"role": "user", "content": '{"input": "test data"}'},
        ]
        messages = self.healer.build_feedback_messages(step, guard_result, manifest, original_messages)

        # Should have: original system, original user, assistant (output), user (feedback)
        assert len(messages) == 4
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert "status" in messages[3]["content"]

    def test_build_feedback_no_output(self):
        manifest = _make_manifest()
        step = self._make_step()
        step.output = None
        guard_result = GuardResult(
            passed=False,
            action=GuardAction.SELF_HEAL,
            failed_criteria=[
                FailedCriterion(field="status", expected="one of ['ok']", actual=None)
            ],
        )
        messages = self.healer.build_feedback_messages(step, guard_result, manifest, [])
        # Only feedback message appended (no assistant message when output is None)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

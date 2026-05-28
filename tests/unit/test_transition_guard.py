"""Tests for TransitionGuardEngine."""
from __future__ import annotations
import pytest
from uuid import uuid4

from atelium.core.models import Step, GuardAction
from atelium.core.transition_guard import TransitionGuardEngine
from atelium.manifest.schema import (
    AgentManifest, AgentMetadata, AgentSpec, ModelSpec, AcceptsSpec,
    TaskSpec, SagaSpec, TopologySpec, BlastRadiusSpec, ObservabilitySpec,
    SelfHealingSpec, SelfHealingStrategy, SuccessCriterion, CriterionType,
    FailureCriterion, FailureAction,
)


def _make_manifest(
    criteria=None,
    transition_guard=None,
    failure_criteria=None,
    max_iterations=2,
) -> AgentManifest:
    task = TaskSpec(
        description="test",
        prompt_template="test {input}",
        success_criteria=criteria or [],
        failure_criteria=failure_criteria or [],
        transition_guard=transition_guard,
        self_healing=SelfHealingSpec(
            strategy=SelfHealingStrategy.RETRY_WITH_FEEDBACK,
            max_iterations=max_iterations,
            feedback_template="Fix: {validation_errors}",
        ),
    )
    return AgentManifest(
        metadata=AgentMetadata(name="test-agent", owner="test", version="0.1.0"),
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


def _make_step(output=None, iteration=0) -> Step:
    step = Step(
        pipeline_id=uuid4(),
        agent_name="test-agent",
        agent_version="0.1.0",
        input={"input": "hello"},
    )
    step.output = output
    step.iteration = iteration
    return step


class TestTransitionGuard:
    def setup_method(self):
        self.engine = TransitionGuardEngine()

    def test_passes_with_no_criteria(self):
        manifest = _make_manifest()
        step = _make_step(output={"result": "ok"})
        result = self.engine.evaluate(step, manifest)
        assert result.passed
        assert result.action == GuardAction.PROCEED

    def test_enum_criterion_pass(self):
        criteria = [SuccessCriterion(field="status", type=CriterionType.ENUM, values=["ok", "done"])]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"status": "ok"})
        result = self.engine.evaluate(step, manifest)
        assert result.passed

    def test_enum_criterion_fail_self_heal(self):
        criteria = [SuccessCriterion(field="status", type=CriterionType.ENUM, values=["ok", "done"])]
        manifest = _make_manifest(criteria=criteria, max_iterations=3)
        step = _make_step(output={"status": "error"}, iteration=0)
        result = self.engine.evaluate(step, manifest)
        assert not result.passed
        assert result.action == GuardAction.SELF_HEAL

    def test_enum_criterion_fail_hitl_after_max_iterations(self):
        criteria = [SuccessCriterion(field="status", type=CriterionType.ENUM, values=["ok"])]
        manifest = _make_manifest(criteria=criteria, max_iterations=2)
        step = _make_step(output={"status": "error"}, iteration=2)
        result = self.engine.evaluate(step, manifest)
        assert not result.passed
        assert result.action == GuardAction.HITL

    def test_float_criterion_pass(self):
        criteria = [SuccessCriterion(field="score", type=CriterionType.FLOAT, min=0.8)]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"score": 0.95})
        result = self.engine.evaluate(step, manifest)
        assert result.passed

    def test_float_criterion_fail(self):
        criteria = [SuccessCriterion(field="score", type=CriterionType.FLOAT, min=0.8)]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"score": 0.5})
        result = self.engine.evaluate(step, manifest)
        assert not result.passed
        assert result.failed_criteria[0].field == "score"

    def test_string_min_length(self):
        criteria = [SuccessCriterion(field="text", type=CriterionType.STRING, min_length=10)]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"text": "hi"})
        result = self.engine.evaluate(step, manifest)
        assert not result.passed

    def test_transition_guard_expression_pass(self):
        manifest = _make_manifest(transition_guard="output['score'] > 0.7 and output['status'] == 'ok'")
        step = _make_step(output={"score": 0.9, "status": "ok"})
        result = self.engine.evaluate(step, manifest)
        assert result.passed

    def test_transition_guard_expression_fail(self):
        manifest = _make_manifest(transition_guard="output['score'] > 0.7")
        step = _make_step(output={"score": 0.5})
        result = self.engine.evaluate(step, manifest)
        assert not result.passed

    def test_failure_criteria_compensate(self):
        fc = [FailureCriterion(
            condition="output.get('fatal') == True",
            action=FailureAction.COMPENSATE,
            description="fatal error",
        )]
        manifest = _make_manifest(
            criteria=[SuccessCriterion(field="status", type=CriterionType.ENUM, values=["ok"])],
            failure_criteria=fc,
        )
        step = _make_step(output={"status": "error", "fatal": True})
        result = self.engine.evaluate(step, manifest)
        assert result.action == GuardAction.COMPENSATE

    def test_dot_notation_field(self):
        criteria = [SuccessCriterion(field="meta.confidence", type=CriterionType.FLOAT, min=0.5)]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"meta": {"confidence": 0.8}})
        result = self.engine.evaluate(step, manifest)
        assert result.passed

    def test_missing_field_fails(self):
        criteria = [SuccessCriterion(field="missing_field", type=CriterionType.FLOAT, min=0.5)]
        manifest = _make_manifest(criteria=criteria)
        step = _make_step(output={"other": 1.0})
        result = self.engine.evaluate(step, manifest)
        assert not result.passed

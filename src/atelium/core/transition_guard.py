from __future__ import annotations
from simpleeval import EvalWithCompoundTypes, NameNotDefined, InvalidExpression

from ..manifest.schema import AgentManifest, FailureAction, CriterionType
from .models import Step, GuardResult, GuardAction, FailedCriterion


_EVAL_FUNCTIONS = {
    "contains": lambda s, sub: sub in s if s else False,
    "len": lambda x: len(x) if x else 0,
    "exists": lambda x: x is not None,
}


def _get_field(data: dict | None, path: str) -> object:
    """Resolve dot-notation path in a dict. Returns None if missing."""
    if data is None:
        return None
    parts = path.split(".")
    current: object = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _eval_expr(expr: str, step: Step) -> bool:
    ctx: dict[str, object] = {
        "output": step.output or {},
        "input": step.input,
        "elapsed_ms": step.elapsed_ms or 0,
        "iteration": step.iteration,
        "null": None,
    }
    evaluator = EvalWithCompoundTypes(names=ctx, functions=_EVAL_FUNCTIONS)
    try:
        return bool(evaluator.eval(expr))
    except (NameNotDefined, InvalidExpression, KeyError, TypeError):
        return False


def _validate_criterion(criterion, step: Step) -> FailedCriterion | None:
    value = _get_field(step.output, criterion.field)

    if criterion.type == CriterionType.ENUM:
        if value not in (criterion.values or []):
            return FailedCriterion(
                field=criterion.field,
                expected=f"one of {criterion.values}",
                actual=value,
            )

    elif criterion.type == CriterionType.FLOAT:
        if value is None:
            return FailedCriterion(criterion.field, "float", None)
        v = float(value)
        if criterion.min is not None and v < criterion.min:
            return FailedCriterion(criterion.field, f">= {criterion.min}", v)
        if criterion.max is not None and v > criterion.max:
            return FailedCriterion(criterion.field, f"<= {criterion.max}", v)

    elif criterion.type == CriterionType.INTEGER:
        if value is None:
            return FailedCriterion(criterion.field, "integer", None)
        v = int(value)
        if criterion.min is not None and v < criterion.min:
            return FailedCriterion(criterion.field, f">= {criterion.min}", v)
        if criterion.max is not None and v > criterion.max:
            return FailedCriterion(criterion.field, f"<= {criterion.max}", v)

    elif criterion.type == CriterionType.BOOLEAN:
        if criterion.value is not None and value != criterion.value:
            return FailedCriterion(criterion.field, str(criterion.value), value)

    elif criterion.type == CriterionType.STRING:
        if value is None:
            return FailedCriterion(criterion.field, "string", None)
        s = str(value)
        if criterion.min_length is not None and len(s) < criterion.min_length:
            return FailedCriterion(criterion.field, f"len >= {criterion.min_length}", len(s))
        if criterion.max_length is not None and len(s) > criterion.max_length:
            return FailedCriterion(criterion.field, f"len <= {criterion.max_length}", len(s))

    elif criterion.type == CriterionType.REGEX:
        import re
        if not value or not re.match(criterion.pattern or "", str(value)):
            return FailedCriterion(criterion.field, f"matches /{criterion.pattern}/", value)

    return None


class TransitionGuardEngine:
    def evaluate(self, step: Step, manifest: AgentManifest) -> GuardResult:
        task = manifest.spec.task
        errors: list[FailedCriterion] = []

        # 1. Check success criteria
        for criterion in task.success_criteria:
            failure = _validate_criterion(criterion, step)
            if failure:
                errors.append(failure)

        if not errors:
            # 2. Evaluate transition_guard expression
            if task.transition_guard:
                if not _eval_expr(task.transition_guard, step):
                    errors.append(FailedCriterion(
                        field="transition_guard",
                        expected="true",
                        actual="false",
                    ))

        if not errors:
            return GuardResult(passed=True, action=GuardAction.PROCEED)

        # 3. Check failure_criteria — first match wins
        for rule in task.failure_criteria:
            if _eval_expr(rule.condition, step):
                action = _failure_action_to_guard(rule.action)
                return GuardResult(passed=False, failed_criteria=errors, action=action)

        # 4. Default: self-heal or HITL
        sh = task.self_healing
        if step.iteration < sh.max_iterations:
            return GuardResult(passed=False, failed_criteria=errors, action=GuardAction.SELF_HEAL)

        return GuardResult(passed=False, failed_criteria=errors, action=GuardAction.HITL)


def _failure_action_to_guard(action: FailureAction) -> GuardAction:
    mapping = {
        FailureAction.COMPENSATE: GuardAction.COMPENSATE,
        FailureAction.ESCALATE_HUMAN: GuardAction.HITL,
        FailureAction.CIRCUIT_BREAKER: GuardAction.CIRCUIT_BREAK,
        FailureAction.RETRY: GuardAction.SELF_HEAL,
        FailureAction.ABORT: GuardAction.ABORT,
    }
    return mapping[action]

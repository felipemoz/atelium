from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

from .schema import (
    AgentManifest,
    AggregationMode,
    MergeStrategy,
    DelegationMode,
    IrreversibilityRequires,
)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    severity: Severity
    field: str
    message: str

    def __str__(self) -> str:
        icon = "✗" if self.severity == Severity.ERROR else "⚠"
        return f"{icon} [{self.field}] {self.message}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def is_valid_strict(self) -> bool:
        return len(self.issues) == 0

    def add_error(self, field: str, message: str) -> None:
        self.issues.append(ValidationIssue(Severity.ERROR, field, message))

    def add_warning(self, field: str, message: str) -> None:
        self.issues.append(ValidationIssue(Severity.WARNING, field, message))


_GENERIC_CAPABILITY_PATTERNS = [
    "general purpose",
    "handle anything",
    "do everything",
    "all tasks",
]


def validate_manifest(manifest: AgentManifest, strict: bool = False) -> ValidationResult:
    result = ValidationResult()

    _check_capabilities(manifest, result)
    _check_mcps(manifest, result)
    _check_task(manifest, result)
    _check_saga(manifest, result)
    _check_topology(manifest, result)
    _check_blast_radius(manifest, result)
    _check_observability(manifest, result)

    return result


def _check_capabilities(manifest: AgentManifest, result: ValidationResult) -> None:
    for cap in manifest.spec.capabilities:
        if len(cap) < 5 or len(cap) > 200:
            result.add_error("spec.capabilities", f"Capability '{cap[:30]}...' must be 5–200 characters")
        for pattern in _GENERIC_CAPABILITY_PATTERNS:
            if pattern in cap.lower():
                result.add_warning("spec.capabilities", f"Capability '{cap}' is too generic — be more specific")


def _check_mcps(manifest: AgentManifest, result: ValidationResult) -> None:
    forbidden = set(manifest.spec.blast_radius.forbidden)
    for mcp in manifest.spec.mcps:
        if mcp.name in forbidden:
            result.add_error(
                f"spec.mcps[{mcp.name}]",
                f"MCP connector '{mcp.name}' is listed in blast_radius.forbidden",
            )


def _check_task(manifest: AgentManifest, result: ValidationResult) -> None:
    task = manifest.spec.task

    if task.transition_guard:
        _validate_expression_syntax(task.transition_guard, "spec.task.transition_guard", result)

    for i, fc in enumerate(task.failure_criteria):
        _validate_expression_syntax(fc.condition, f"spec.task.failure_criteria[{i}].condition", result)

    has_retry = any(fc.action.value == "retry" for fc in task.failure_criteria)
    if has_retry and manifest.spec.task.self_healing.strategy.value == "noop":
        result.add_warning(
            "spec.task",
            "failure_criteria has action=retry but self_healing.strategy is noop",
        )


def _check_saga(manifest: AgentManifest, result: ValidationResult) -> None:
    for action in manifest.spec.saga.irreversible_actions:
        if action.dry_run and not action.dry_run_output_field:
            result.add_error(
                f"spec.saga.irreversible_actions[{action.name}]",
                "dry_run=true requires dry_run_output_field to be set",
            )


def _check_topology(manifest: AgentManifest, result: ValidationResult) -> None:
    agg = manifest.spec.topology.aggregation

    if agg.mode == AggregationMode.QUORUM and agg.quorum_threshold is None:
        result.add_error(
            "spec.topology.aggregation",
            "mode=quorum requires quorum_threshold to be set",
        )

    if agg.merge_strategy == MergeStrategy.CUSTOM and not agg.merge_agent:
        result.add_error(
            "spec.topology.aggregation",
            "merge_strategy=custom requires merge_agent to be set",
        )

    delegation = manifest.spec.topology.delegation
    if delegation.mode == DelegationMode.ROUTE_N and delegation.n is None:
        result.add_error(
            "spec.topology.delegation",
            "mode=route_n requires n to be set",
        )


def _check_blast_radius(manifest: AgentManifest, result: ValidationResult) -> None:
    br = manifest.spec.blast_radius
    hitl_required = set(br.human_approval_required)
    irreversible_names = {a.name for a in manifest.spec.saga.irreversible_actions}

    for action in hitl_required:
        if action not in irreversible_names:
            result.add_warning(
                "spec.blast_radius.human_approval_required",
                f"Action '{action}' is in human_approval_required but not in saga.irreversible_actions",
            )


def _check_observability(manifest: AgentManifest, result: ValidationResult) -> None:
    obs = manifest.spec.observability
    if obs.pii_masking and not obs.pii_fields:
        result.add_warning(
            "spec.observability",
            "pii_masking=true but pii_fields is empty — nothing will be masked",
        )


def _validate_expression_syntax(expr: str, field: str, result: ValidationResult) -> None:
    from simpleeval import EvalWithCompoundTypes, NameNotDefined
    try:
        evaluator = EvalWithCompoundTypes()
        evaluator.names = {
            "output": {}, "input": {}, "elapsed_ms": 0, "iteration": 0, "null": None
        }
        evaluator.eval(expr)
    except NameNotDefined:
        pass  # expected — names are only available at runtime
    except SyntaxError as e:
        result.add_error(field, f"Expression syntax error: {e}")
    except Exception:
        pass  # other eval errors are runtime, not syntax

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class StepStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SELF_HEALING = "self_healing"
    WAITING_HITL = "waiting_hitl"
    SUCCEEDED = "succeeded"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    ABORTED = "aborted"


class PipelineStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"
    WAITING_HITL = "waiting_hitl"


class CompensationStatus(str, Enum):
    NOT_NEEDED = "not_needed"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SagaEntryStatus(str, Enum):
    COMMITTED = "committed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class IrreversibilityClass(str, Enum):
    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"


class GuardAction(str, Enum):
    PROCEED = "proceed"
    SELF_HEAL = "self_heal"
    HITL = "hitl"
    COMPENSATE = "compensate"
    CIRCUIT_BREAK = "circuit_break"
    ABORT = "abort"


@dataclass
class StepSummary:
    step_id: UUID
    agent_name: str
    summary: str
    output_fields: dict
    status: StepStatus


@dataclass
class Step:
    pipeline_id: UUID
    agent_name: str
    agent_version: str
    input: dict

    step_id: UUID = field(default_factory=uuid4)
    parent_step_id: UUID | None = None
    branch_id: str | None = None
    merge_step_id: UUID | None = None

    output: dict | None = None
    context_window: list[StepSummary] = field(default_factory=list)

    status: StepStatus = StepStatus.PENDING
    iteration: int = 0

    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    elapsed_ms: int | None = None

    validation_errors: list[str] = field(default_factory=list)
    compensation_status: CompensationStatus = CompensationStatus.NOT_NEEDED
    snapshot: dict | None = None

    tokens_used: int = 0
    cost_usd: float = 0.0
    otel_trace_id: str = ""
    langfuse_trace_id: str = ""

    def mark_started(self) -> None:
        self.status = StepStatus.EXECUTING
        self.started_at = datetime.utcnow()

    def mark_completed(self, output: dict) -> None:
        self.output = output
        self.status = StepStatus.SUCCEEDED
        self.completed_at = datetime.utcnow()
        self.elapsed_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

    def mark_failed(self, errors: list[str]) -> None:
        self.validation_errors = errors
        self.status = StepStatus.FAILED
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.elapsed_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

    def to_summary(self) -> StepSummary:
        output_fields: dict = {}
        if self.output:
            output_fields = {k: v for k, v in self.output.items() if not isinstance(v, (dict, list))}
        return StepSummary(
            step_id=self.step_id,
            agent_name=self.agent_name,
            summary=f"{self.agent_name} [{self.status}]",
            output_fields=output_fields,
            status=self.status,
        )


@dataclass
class SagaEntry:
    pipeline_id: UUID
    step_id: UUID
    agent_name: str
    action_name: str
    irreversibility_class: IrreversibilityClass
    compensating_action: str

    entry_id: UUID = field(default_factory=uuid4)
    status: SagaEntryStatus = SagaEntryStatus.COMMITTED
    snapshot: dict | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Pipeline:
    manifest_name: str

    pipeline_id: UUID = field(default_factory=uuid4)
    status: PipelineStatus = PipelineStatus.RUNNING
    root_step_id: UUID | None = None
    current_step_ids: list[UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    saga_log: list[SagaEntry] = field(default_factory=list)

    def mark_succeeded(self) -> None:
        self.status = PipelineStatus.SUCCEEDED
        self.completed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        self.status = PipelineStatus.FAILED
        self.completed_at = datetime.utcnow()

    @property
    def elapsed_ms(self) -> int | None:
        if self.completed_at:
            return int((self.completed_at - self.created_at).total_seconds() * 1000)
        return None


@dataclass
class FailedCriterion:
    field: str
    expected: str
    actual: object
    condition: str | None = None
    action: str | None = None


@dataclass
class GuardResult:
    passed: bool
    action: GuardAction
    failed_criteria: list[FailedCriterion] = field(default_factory=list)

    def error_messages(self) -> list[str]:
        msgs = []
        for fc in self.failed_criteria:
            msgs.append(f"Field '{fc.field}': expected {fc.expected}, got {fc.actual!r}")
        return msgs


@dataclass
class RoutingDecision:
    agent_name: str
    agent_version: str
    affinity_score: float
    semantic_similarity: float = 0.0
    success_rate: float = 0.0
    recency_score: float = 0.0
    load_score: float = 0.0


@dataclass
class AggregationResult:
    completed: list[Step]
    timed_out: list[Step]
    merged_output: dict


@dataclass
class CompensationResult:
    entries: list[SagaEntry]

    @property
    def success_count(self) -> int:
        return sum(1 for e in self.entries if e.status == SagaEntryStatus.COMPENSATED)

    @property
    def failure_count(self) -> int:
        return sum(1 for e in self.entries if e.status == SagaEntryStatus.FAILED)

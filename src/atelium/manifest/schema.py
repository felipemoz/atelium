from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FailureAction(str, Enum):
    COMPENSATE = "compensate"
    ESCALATE_HUMAN = "escalate_human"
    CIRCUIT_BREAKER = "circuit_breaker"
    RETRY = "retry"
    ABORT = "abort"


class SelfHealingStrategy(str, Enum):
    RETRY_WITH_FEEDBACK = "retry_with_feedback"
    REPLAN = "replan"
    NOOP = "noop"


class DelegationMode(str, Enum):
    ROUTE_BEST = "route_best"
    ROUTE_ALL = "route_all"
    ROUTE_N = "route_n"


class AggregationMode(str, Enum):
    WAIT_ALL = "wait_all"
    QUORUM = "quorum"
    BEST_EFFORT = "best_effort"
    FIRST = "first"


class MergeStrategy(str, Enum):
    UNION = "union"
    INTERSECTION = "intersection"
    WEIGHTED_VOTE = "weighted_vote"
    CUSTOM = "custom"


class OnTimeout(str, Enum):
    BEST_EFFORT = "best_effort"
    ABORT = "abort"
    ESCALATE_HUMAN = "escalate_human"


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    LITELLM = "litellm"


class KnowledgeAccess(str, Enum):
    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


class IrreversibilityRequires(str, Enum):
    PRE_CONFIRMATION = "pre_confirmation"
    POST_NOTIFICATION = "post_notification"
    NONE = "none"


class CriterionType(str, Enum):
    STRING = "string"
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    REGEX = "regex"
    JSON_SCHEMA = "json_schema"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ModelSpec(BaseModel):
    provider: LLMProvider = LLMProvider.OLLAMA
    name: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout_ms: int = Field(default=30_000, ge=1_000)
    seed: int | None = None


class AcceptsSpec(BaseModel):
    types: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    schema_ref: str | None = None


class RateLimit(BaseModel):
    requests_per_minute: int = 60
    burst: int = 10


class McpSpec(BaseModel):
    name: str
    version: str
    scopes: list[str] = Field(default_factory=list)
    rate_limit: RateLimit | None = None


class KnowledgeNamespace(BaseModel):
    name: str
    access: KnowledgeAccess = KnowledgeAccess.READ_ONLY
    top_k: int = 5
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class KnowledgeSpec(BaseModel):
    namespaces: list[KnowledgeNamespace] = Field(default_factory=list)
    embed_model: str | None = None


class SuccessCriterion(BaseModel):
    field: str
    type: CriterionType
    # type-specific
    values: list[str] | None = None        # enum
    min: float | None = None               # float, integer
    max: float | None = None               # float, integer
    min_length: int | None = None          # string, array
    max_length: int | None = None          # string
    pattern: str | None = None            # string (regex), regex type
    value: bool | None = None             # boolean
    schema_ref: str | None = None         # json_schema


class FailureCriterion(BaseModel):
    condition: str
    action: FailureAction


class SelfHealingSpec(BaseModel):
    strategy: SelfHealingStrategy = SelfHealingStrategy.RETRY_WITH_FEEDBACK
    max_iterations: int = Field(default=3, ge=1, le=10)
    feedback_template: str = (
        "Your previous response did not satisfy the required criteria:\n"
        "{validation_errors}\n\n"
        "Please try again. Requirements:\n{success_criteria}"
    )


class TaskSpec(BaseModel):
    description: str
    prompt_template: str = "{input}"
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    failure_criteria: list[FailureCriterion] = Field(default_factory=list)
    self_healing: SelfHealingSpec = Field(default_factory=SelfHealingSpec)
    transition_to: str | None = None
    transition_guard: str | None = None


class IrreversibleAction(BaseModel):
    name: str
    requires: IrreversibilityRequires = IrreversibilityRequires.NONE
    dry_run: bool = False
    dry_run_output_field: str | None = None


class SagaSpec(BaseModel):
    compensating_action: str | None = None
    irreversible_actions: list[IrreversibleAction] = Field(default_factory=list)
    snapshot_before: list[str] = Field(default_factory=list)
    compensation_timeout_ms: int = 30_000
    idempotency_key_field: str | None = None


class DelegationSpec(BaseModel):
    mode: DelegationMode = DelegationMode.ROUTE_BEST
    n: int | None = None
    fallback: str | None = None


class AggregationSpec(BaseModel):
    mode: AggregationMode = AggregationMode.WAIT_ALL
    quorum_threshold: float | None = None
    timeout: str = "120s"
    on_timeout: OnTimeout = OnTimeout.BEST_EFFORT
    merge_strategy: MergeStrategy = MergeStrategy.UNION
    merge_agent: str | None = None


class TopologySpec(BaseModel):
    delegation: DelegationSpec = Field(default_factory=DelegationSpec)
    aggregation: AggregationSpec = Field(default_factory=AggregationSpec)


class BlastRadiusSpec(BaseModel):
    max_write_systems: list[str] = Field(default_factory=list)
    max_read_systems: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    human_approval_required: list[str] = Field(default_factory=list)
    max_concurrent_pipelines: int = 10
    max_tokens_per_day: int | None = None


class AlertRule(BaseModel):
    condition: str
    channel: str
    message: str


class ObservabilitySpec(BaseModel):
    traces: bool = True
    cost_tracking: bool = True
    pii_masking: bool = False
    pii_fields: list[str] = Field(default_factory=list)
    log_step_memory: bool = False
    langfuse_project: str | None = None
    alert_on: list[AlertRule] = Field(default_factory=list)


class AgentSpec(BaseModel):
    model: ModelSpec
    capabilities: list[str] = Field(min_length=1, max_length=20)
    accepts: AcceptsSpec = Field(default_factory=AcceptsSpec)
    mcps: list[McpSpec] = Field(default_factory=list)
    knowledge: KnowledgeSpec = Field(default_factory=KnowledgeSpec)
    task: TaskSpec
    saga: SagaSpec = Field(default_factory=SagaSpec)
    topology: TopologySpec = Field(default_factory=TopologySpec)
    blast_radius: BlastRadiusSpec = Field(default_factory=BlastRadiusSpec)
    observability: ObservabilitySpec = Field(default_factory=ObservabilitySpec)


class AgentMetadata(BaseModel):
    name: str
    owner: str
    version: str
    tags: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9-]{2,62}$", v):
            raise ValueError("name must match ^[a-z][a-z0-9-]{2,62}$")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("version must be valid semver (MAJOR.MINOR.PATCH)")
        return v


class AgentManifest(BaseModel):
    apiVersion: str = "atelium/v1alpha1"
    kind: str = "Agent"
    metadata: AgentMetadata
    spec: AgentSpec

    @field_validator("apiVersion")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        if v != "atelium/v1alpha1":
            raise ValueError("apiVersion must be atelium/v1alpha1")
        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v != "Agent":
            raise ValueError("kind must be Agent")
        return v

    def capability_strings(self) -> list[str]:
        return self.spec.capabilities

    def is_terminal(self) -> bool:
        return self.spec.task.transition_to is None

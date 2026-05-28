# Atelium — Core Runtime Specification

## Overview

The Core Runtime is the execution engine of Atelium. It sits between the FastAPI gateway and the external infrastructure (NATS, Redis, PostgreSQL) and implements all fault-tolerance primitives defined in the thesis.

```
FastAPI / CLI
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                   CORE RUNTIME                       │
│                                                      │
│  ┌──────────────────┐   ┌───────────────────────┐   │
│  │  Emergent Router  │   │  Topology Manager     │   │
│  │  (affinity score) │   │  (1:N / N:1 / 1:1)   │   │
│  └────────┬─────────┘   └──────────┬────────────┘   │
│           │                        │                 │
│           ▼                        ▼                 │
│  ┌─────────────────────────────────────────────┐    │
│  │           LangGraph Execution Engine         │    │
│  │   (agent DAG, checkpointing, state graph)    │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                               │
│         ┌───────────┼───────────┐                   │
│         ▼           ▼           ▼                   │
│  ┌────────────┐ ┌────────┐ ┌──────────────────┐    │
│  │ Transition │ │ SAGA-A │ │ Step-Resident     │    │
│  │   Guard    │ │ Coord. │ │ State Manager     │    │
│  │  + Healer  │ │        │ │                   │    │
│  └────────────┘ └────────┘ └──────────────────┘    │
└─────────────────────────────────────────────────────┘
      │           │           │           │
    NATS        Redis       Redis       PostgreSQL
  (events)    (hot state)  Stack(vec)  (archive)
```

---

## Data Structures

### `Step`

The atomic unit of execution. Every agent invocation produces exactly one Step.

```python
@dataclass
class Step:
    # Identity
    step_id: UUID
    pipeline_id: UUID
    agent_name: str
    agent_version: str

    # Causal chain (Step-Resident State)
    parent_step_id: Optional[UUID]     # None for root step
    branch_id: Optional[str]           # set when step is part of a 1:N fan-out
    merge_step_id: Optional[UUID]      # set on the step that merges N:1 results

    # Inputs / Outputs
    input: dict                        # full input payload
    output: Optional[dict]             # None while executing
    context_window: list[StepSummary]  # visible_history of ancestor steps

    # Execution state
    status: StepStatus                 # see enum below
    iteration: int                     # self-healing iteration count, starts at 0
    started_at: datetime
    completed_at: Optional[datetime]
    elapsed_ms: Optional[int]

    # Fault tolerance
    validation_errors: list[str]       # populated by Transition Guard on failure
    compensation_status: CompensationStatus
    snapshot: Optional[dict]           # pre-action snapshot for SAGA-A

    # Observability
    tokens_used: int
    cost_usd: float
    otel_trace_id: str
    langfuse_trace_id: str
```

```python
class StepStatus(str, Enum):
    PENDING       = "pending"
    EXECUTING     = "executing"
    SELF_HEALING  = "self_healing"
    WAITING_HITL  = "waiting_hitl"
    SUCCEEDED     = "succeeded"
    COMPENSATING  = "compensating"
    COMPENSATED   = "compensated"
    FAILED        = "failed"
    ABORTED       = "aborted"
```

```python
class CompensationStatus(str, Enum):
    NOT_NEEDED    = "not_needed"
    PENDING       = "pending"
    IN_PROGRESS   = "in_progress"
    COMPLETED     = "completed"
    FAILED        = "failed"
```

### `Pipeline`

```python
@dataclass
class Pipeline:
    pipeline_id: UUID
    manifest_name: str          # root agent that started this pipeline
    status: PipelineStatus
    root_step_id: UUID
    current_step_ids: list[UUID]  # >1 during 1:N fan-out
    created_at: datetime
    completed_at: Optional[datetime]
    saga_log: list[SagaEntry]   # ordered log of all SAGA-A events
```

### `StepSummary` (context window entry)

```python
@dataclass
class StepSummary:
    step_id: UUID
    agent_name: str
    summary: str           # LLM-generated or structured summary of output
    output_fields: dict    # key fields extracted from output
    status: StepStatus
```

---

## Component 1 — Transition Guard Engine

### Responsibility

Evaluates `spec.task.success_criteria` and `spec.task.failure_criteria` after every agent invocation. Decides whether to: advance to next agent, trigger self-healing, escalate to HITL, or compensate.

### Interface

```python
class TransitionGuardEngine:
    def evaluate(self, step: Step, manifest: AgentManifest) -> GuardResult:
        ...

@dataclass
class GuardResult:
    passed: bool
    failed_criteria: list[FailedCriterion]
    action: GuardAction        # PROCEED | SELF_HEAL | HITL | COMPENSATE | CIRCUIT_BREAK | ABORT

@dataclass
class FailedCriterion:
    field: str
    expected: str
    actual: Any
    condition: Optional[str]   # for failure_criteria conditions
    action: str
```

### Evaluation Algorithm

```
evaluate(step, manifest):
  errors = []

  # 1. Check success criteria
  for criterion in manifest.spec.task.success_criteria:
    value = get_field(step.output, criterion.field)
    if not validate(value, criterion):
      errors.append(FailedCriterion(criterion.field, ...))

  if not errors:
    # 2. Evaluate transition guard expression
    guard_ok = eval_expression(
      manifest.spec.task.transition_guard,
      context={output: step.output, input: step.input, elapsed_ms: step.elapsed_ms}
    )
    if guard_ok:
      return GuardResult(passed=True, action=PROCEED)
    else:
      errors.append(FailedCriterion("transition_guard", ...))

  # 3. Check failure criteria — first matching rule wins
  for rule in manifest.spec.task.failure_criteria:
    if eval_expression(rule.condition, context):
      return GuardResult(passed=False, failed_criteria=errors, action=rule.action)

  # 4. Default: self-heal if iterations remain
  if step.iteration < manifest.spec.task.self_healing.max_iterations:
    return GuardResult(passed=False, failed_criteria=errors, action=SELF_HEAL)
  else:
    return GuardResult(passed=False, failed_criteria=errors, action=HITL)
```

### Expression Evaluator

Uses [simpleeval](https://github.com/danthedeckie/simpleeval) (MIT) as sandboxed expression engine.

Registered names injected into evaluation context:

```python
eval_context = {
    "output":     step.output or {},
    "input":      step.input,
    "elapsed_ms": step.elapsed_ms or 0,
    "iteration":  step.iteration,
    "null":       None,
}
```

Registered functions:

```python
eval_functions = {
    "contains": lambda s, sub: sub in s if s else False,
    "len":      lambda x: len(x) if x else 0,
    "exists":   lambda x: x is not None,
}
```

---

## Component 2 — Self-Healing Loop

### Responsibility

When the Transition Guard returns `action=SELF_HEAL`, builds a feedback prompt and re-invokes the agent LLM within the same Step (incrementing `iteration`).

### Interface

```python
class SelfHealingLoop:
    def heal(self, step: Step, guard_result: GuardResult, manifest: AgentManifest) -> Step:
        ...
```

### Algorithm

```
heal(step, guard_result, manifest):
  # 1. Build feedback prompt
  validation_errors = format_errors(guard_result.failed_criteria)
  success_criteria  = format_criteria(manifest.spec.task.success_criteria)
  failed_fields     = [c.field for c in guard_result.failed_criteria]

  feedback = manifest.spec.task.self_healing.feedback_template.format(
    validation_errors = validation_errors,
    success_criteria  = success_criteria,
    failed_fields     = failed_fields,
  )

  # 2. Build new messages list: original prompt + agent response + feedback
  messages = [
    SystemMessage(content=build_system_prompt(manifest)),
    HumanMessage(content=format_input(step.input)),
    AIMessage(content=json.dumps(step.output)),    # previous (invalid) response
    HumanMessage(content=feedback),                # correction request
  ]

  # 3. Re-invoke LLM
  step.iteration += 1
  step.status = StepStatus.SELF_HEALING
  persist_step(step)   # write to Redis before re-invoke

  new_output = invoke_llm(manifest.spec.model, messages)

  # 4. Update step
  step.output = parse_output(new_output)
  step.status = StepStatus.EXECUTING
  return step
```

### State Transitions

```
EXECUTING ──[Guard FAIL, iter < max]──▶ SELF_HEALING
SELF_HEALING ──[LLM responds]──▶ EXECUTING (iteration++)
EXECUTING ──[Guard PASS]──▶ SUCCEEDED
EXECUTING ──[Guard FAIL, iter >= max]──▶ [failure_criteria action]
```

### Redis Keys

```
step:{step_id}:state          → StepStatus (string)
step:{step_id}:iteration      → int
step:{step_id}:output         → JSON (latest output)
step:{step_id}:validation_errors → JSON list
```

TTL: 24 hours for active steps, promoted to PostgreSQL on completion.

---

## Component 3 — SAGA-A Coordinator

### Responsibility

Maintains the SAGA log for each pipeline. On step failure (after self-healing and HITL are exhausted), executes compensating actions in reverse order.

### Interface

```python
class SagaCoordinator:
    def register_step(self, step: Step, manifest: AgentManifest) -> None:
        """Called after step SUCCEEDED — records in saga log."""

    def snapshot(self, step: Step, action_name: str) -> None:
        """Called before an action listed in saga.snapshot_before."""

    def compensate(self, pipeline: Pipeline, from_step_id: UUID) -> CompensationResult:
        """Executes compensating actions from from_step_id backwards."""

    def classify_action(self, action_name: str, manifest: AgentManifest) -> IrreversibilityClass:
        """Returns REVERSIBLE | COMPENSABLE | IRREVERSIBLE."""

    def gate_irreversible(self, action_name: str, step: Step, manifest: AgentManifest) -> GateResult:
        """Applies pre_confirmation or dry_run gate before executing irreversible action."""
```

### SAGA Log Entry

```python
@dataclass
class SagaEntry:
    entry_id: UUID
    pipeline_id: UUID
    step_id: UUID
    agent_name: str
    action_name: str
    irreversibility_class: IrreversibilityClass
    compensating_action: str
    status: SagaEntryStatus       # COMMITTED | COMPENSATING | COMPENSATED | FAILED
    snapshot: Optional[dict]
    timestamp: datetime
```

### Compensation Algorithm

```
compensate(pipeline, from_step_id):
  # 1. Collect all COMMITTED entries up to from_step_id (reverse order)
  entries = saga_log.entries_before(from_step_id, status=COMMITTED)
  entries.reverse()

  results = []
  for entry in entries:
    if entry.irreversibility_class == IRREVERSIBLE:
      # Cannot undo — send post-notification, mark as acknowledged
      notify(entry.agent_name, entry.action_name, "compensation_attempted_irreversible")
      entry.status = COMPENSATED  # best-effort
    else:
      # Execute compensating action
      entry.status = COMPENSATING
      try:
        result = execute_mcp_action(entry.compensating_action, entry.snapshot)
        entry.status = COMPENSATED
      except Exception as e:
        entry.status = FAILED
        # Continue compensating remaining entries (best-effort)
    results.append(entry)

  return CompensationResult(entries=results)
```

### Irreversibility Gate

```
gate_irreversible(action_name, step, manifest):
  config = manifest.saga.irreversible_actions[action_name]

  if config.dry_run:
    # 1. Run in simulation mode
    dry_result = execute_mcp_action(action_name, step.input, dry_run=True)
    preview = get_field(dry_result, config.dry_run_output_field)

    # 2. Emit preview event — pause until human confirms
    nats.publish("atelium.hitl.dry_run_review", {
      pipeline_id: step.pipeline_id,
      step_id: step.step_id,
      action: action_name,
      preview: preview,
    })
    step.status = WAITING_HITL
    wait_for_approval(step)

  elif config.requires == "pre_confirmation":
    nats.publish("atelium.hitl.pre_confirmation", {
      pipeline_id: step.pipeline_id,
      action: action_name,
      context: step.output,
    })
    step.status = WAITING_HITL
    wait_for_approval(step)
```

### PostgreSQL Schema

```sql
CREATE TABLE saga_log (
  entry_id          UUID PRIMARY KEY,
  pipeline_id       UUID NOT NULL,
  step_id           UUID NOT NULL,
  agent_name        TEXT NOT NULL,
  action_name       TEXT NOT NULL,
  irreversibility   TEXT NOT NULL,  -- reversible | compensable | irreversible
  compensating_fn   TEXT NOT NULL,
  status            TEXT NOT NULL,
  snapshot          JSONB,
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_saga_pipeline ON saga_log (pipeline_id, created_at);
CREATE INDEX idx_saga_step     ON saga_log (step_id);
```

---

## Component 4 — Emergent Router

### Responsibility

Given a task context (step input + goal description), selects the best agent(s) from the registry using the affinity scoring formula.

### Interface

```python
class EmergentRouter:
    def route(
        self,
        task: RoutingRequest,
        mode: DelegationMode,
        n: int = 1,
    ) -> list[RoutingDecision]:
        ...

@dataclass
class RoutingRequest:
    pipeline_id: UUID
    task_description: str      # natural language description of what needs to be done
    input_types: list[str]     # from current step output types
    required_capabilities: Optional[list[str]]  # optional override

@dataclass
class RoutingDecision:
    agent_name: str
    agent_version: str
    affinity_score: float
    score_breakdown: ScoreBreakdown

@dataclass
class ScoreBreakdown:
    semantic_similarity: float   # α · cosine(cᵢ, eₛ)
    success_rate: float          # β · SR(aᵢ, τ)
    recency: float               # γ · exp(-λ · age)
    load: float                  # δ · (1 - ρ)
```

### Affinity Scoring Formula

```
affinity(aᵢ, s) = α · cosine(cᵢ, eₛ) + β · SR(aᵢ, τ) + γ · exp(-λ · age(aᵢ)) + δ · (1 - ρ(aᵢ))

Where:
  cᵢ       = capability embedding vector of agent aᵢ (stored in Redis Stack)
  eₛ       = embedding of current task step s (computed at routing time)
  SR(aᵢ,τ) = success rate of aᵢ on task type τ (from PostgreSQL step archive)
  age(aᵢ)  = days since last successful execution (recency decay)
  ρ(aᵢ)   = current load (active pipelines / max_concurrent_pipelines)
  λ        = 0.1 (recency decay constant)

Default weights (from E4 sensitivity analysis):
  α = 0.50, β = 0.30, γ = 0.10, δ = 0.10
```

### Algorithm

```
route(task, mode, n):
  # 1. Embed task description
  eₛ = embed(task.task_description)   # using platform default embed model

  # 2. Candidate retrieval — Redis Stack vector search (ANN, top-50)
  candidates = redis_stack.search(
    index="agent_capabilities",
    query_vector=eₛ,
    top_k=50,
    filter={"input_types": {"$contains_any": task.input_types}}
  )

  # 3. Score candidates with full affinity formula
  scored = []
  for agent in candidates:
    sr   = postgres.query("SELECT success_rate FROM agent_stats WHERE name=$1 AND task_type=$2", agent.name, infer_task_type(task))
    age  = (now() - agent.last_success_at).days
    load = redis.get(f"agent:{agent.name}:active_pipelines") / agent.max_concurrent_pipelines

    score = (
      ALPHA * cosine(agent.capability_vector, eₛ) +
      BETA  * (sr or 0.5) +
      GAMMA * exp(-LAMBDA * age) +
      DELTA * (1 - min(load, 1.0))
    )
    scored.append((agent, score))

  # 4. Sort and select
  scored.sort(key=lambda x: x[1], reverse=True)

  if mode == ROUTE_BEST:
    return [scored[0]]
  elif mode == ROUTE_N:
    return scored[:n]
  elif mode == ROUTE_ALL:
    return scored  # all above threshold (default: affinity > 0.4)
```

### Redis Stack Index

```
FT.CREATE agent_capabilities
  ON HASH PREFIX 1 agent:
  SCHEMA
    name TEXT
    version TEXT
    owner TEXT
    input_types TAG
    status TAG
    capability_vector VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE
```

### Agent Registration (on `atelium register`)

```
register(manifest):
  # 1. Compute capability embedding
  cap_vector = embed(mean(manifest.spec.capabilities))

  # 2. Store in Redis Stack
  redis.hset(f"agent:{manifest.metadata.name}", {
    name: manifest.metadata.name,
    version: manifest.metadata.version,
    owner: manifest.metadata.owner,
    input_types: ",".join(manifest.spec.accepts.input_types),
    status: "active",
    capability_vector: cap_vector.tobytes(),
  })

  # 3. Store full manifest + lineage in PostgreSQL
  postgres.upsert("agent_registry", {
    name:        manifest.metadata.name,
    version:     manifest.metadata.version,
    manifest:    manifest.to_json(),
    registered_at: now(),
  })
```

---

## Component 5 — Step-Resident State Manager

### Responsibility

Manages the full lifecycle of Step state: creation, persistence (Redis hot + PostgreSQL archive), context window construction for downstream agents, and fork/merge semantics for 1:N/N:1 topologies.

### Interface

```python
class StepStateManager:
    def create_step(self, pipeline_id: UUID, agent_name: str, input: dict,
                    parent_step_id: Optional[UUID] = None,
                    branch_id: Optional[str] = None) -> Step:

    def persist_hot(self, step: Step) -> None:
        """Write step to Redis (24h TTL)."""

    def archive(self, step: Step) -> None:
        """Write completed step to PostgreSQL."""

    def build_context_window(self, step: Step, manifest: AgentManifest) -> list[StepSummary]:
        """Collect ancestor steps to pass as context to next agent."""

    def fork(self, parent_step: Step, agent_names: list[str]) -> list[Step]:
        """Create N child steps for 1:N fan-out."""

    def merge(self, branch_steps: list[Step], manifest: AgentManifest) -> dict:
        """Merge N outputs into single payload for N:1 aggregation."""

    def replay(self, step_id: UUID) -> Step:
        """Load step from PostgreSQL archive for deterministic replay."""
```

### Context Window Construction

```
build_context_window(step, manifest):
  # Walk the causal chain upward
  ancestors = []
  current = step.parent_step_id

  while current is not None:
    ancestor = load_step(current)   # Redis first, then PostgreSQL
    ancestors.append(StepSummary(
      step_id:      ancestor.step_id,
      agent_name:   ancestor.agent_name,
      summary:      summarize(ancestor.output),  # extract key fields
      output_fields: extract_key_fields(ancestor.output),
      status:       ancestor.status,
    ))
    current = ancestor.parent_step_id

  # Respect visible_history window (future: spec.task.visible_history)
  return list(reversed(ancestors))  # chronological order
```

### Fork/Merge for 1:N → N:1

```
fork(parent_step, agent_names):
  branches = []
  for i, name in enumerate(agent_names):
    child = create_step(
      pipeline_id    = parent_step.pipeline_id,
      agent_name     = name,
      input          = parent_step.output,   # parent output is child input
      parent_step_id = parent_step.step_id,
      branch_id      = f"{parent_step.step_id}:{i}",
    )
    branches.append(child)
  return branches


merge(branch_steps, manifest):
  mode     = manifest.spec.topology.aggregation.merge_strategy
  outputs  = [s.output for s in branch_steps if s.status == SUCCEEDED]

  if mode == "union":
    result = {}
    for o in outputs:
      result.update(o)             # last-write-wins on conflict
    return result

  elif mode == "intersection":
    # Keep only fields identical across all outputs
    keys = set.intersection(*[set(o.keys()) for o in outputs])
    return {k: outputs[0][k] for k in keys if all(o[k] == outputs[0][k] for o in outputs)}

  elif mode == "weighted_vote":
    # Weight each output by source agent's affinity score
    weights = {s.agent_name: router.last_affinity_score(s.agent_name) for s in branch_steps}
    return weighted_merge(outputs, weights)

  elif mode == "custom":
    # Delegate to merge_agent
    merge_agent = manifest.spec.topology.aggregation.merge_agent
    return invoke_agent(merge_agent, {"results": outputs})
```

### PostgreSQL Schema

```sql
CREATE TABLE steps (
  step_id           UUID PRIMARY KEY,
  pipeline_id       UUID NOT NULL,
  agent_name        TEXT NOT NULL,
  agent_version     TEXT NOT NULL,
  parent_step_id    UUID REFERENCES steps(step_id),
  branch_id         TEXT,
  merge_step_id     UUID REFERENCES steps(step_id),
  input             JSONB NOT NULL,
  output            JSONB,
  context_window    JSONB,
  status            TEXT NOT NULL,
  iteration         INT DEFAULT 0,
  started_at        TIMESTAMPTZ NOT NULL,
  completed_at      TIMESTAMPTZ,
  elapsed_ms        INT,
  validation_errors JSONB,
  compensation_status TEXT DEFAULT 'not_needed',
  snapshot          JSONB,
  tokens_used       INT DEFAULT 0,
  cost_usd          NUMERIC(10, 6) DEFAULT 0,
  otel_trace_id     TEXT,
  langfuse_trace_id TEXT
);

CREATE INDEX idx_steps_pipeline    ON steps (pipeline_id, started_at);
CREATE INDEX idx_steps_parent      ON steps (parent_step_id);
CREATE INDEX idx_steps_agent       ON steps (agent_name, status);
CREATE INDEX idx_steps_status      ON steps (status) WHERE status NOT IN ('succeeded', 'aborted');
```

---

## Component 6 — Topology Manager

### Responsibility

Coordinates multi-agent topologies: 1:1 (pipeline), 1:N (fan-out/delegation), N:1 (fan-in/aggregation). Manages timeouts and `on_timeout` strategies.

### Interface

```python
class TopologyManager:
    def execute_step(self, step: Step, manifest: AgentManifest) -> StepResult:
        """Execute a single step (1:1)."""

    def delegate(self, parent_step: Step, manifest: AgentManifest) -> list[StepResult]:
        """Fan-out based on delegation mode."""

    def aggregate(self, branch_steps: list[Step], manifest: AgentManifest) -> AggregationResult:
        """Collect and merge branch results."""
```

### Pipeline Execution Flow

```
execute_pipeline(manifest_name, input):
  pipeline = create_pipeline(manifest_name)
  manifest = registry.get(manifest_name)
  root_step = state_manager.create_step(pipeline.id, manifest_name, input)

  current_step = root_step
  current_manifest = manifest

  while True:
    # 1. Execute current agent
    output = invoke_langgraph_agent(current_step, current_manifest)
    current_step.output = output
    current_step.status = EXECUTING

    # 2. Transition Guard
    guard = transition_guard.evaluate(current_step, current_manifest)

    if guard.action == SELF_HEAL:
      current_step = self_healer.heal(current_step, guard, current_manifest)
      continue  # re-evaluate

    elif guard.action == HITL:
      nats.publish("atelium.hitl.escalation", {...})
      current_step.status = WAITING_HITL
      resume_token = wait_for_hitl(current_step)
      # On resume: update output from HITL, re-evaluate guard
      continue

    elif guard.action in (COMPENSATE, CIRCUIT_BREAK, ABORT):
      saga_coordinator.compensate(pipeline, current_step.step_id)
      pipeline.status = FAILED
      break

    # 3. Guard passed — persist and check for next step
    current_step.status = SUCCEEDED
    state_manager.archive(current_step)
    saga_coordinator.register_step(current_step, current_manifest)

    next_agent = current_manifest.spec.task.transition_to
    if next_agent is None:
      pipeline.status = SUCCEEDED
      break

    # 4. Routing: emergent or static
    if is_emergent(next_agent):
      decisions = router.route(RoutingRequest(...), current_manifest.topology.delegation.mode)
      next_agents = [d.agent_name for d in decisions]
    else:
      next_agents = [next_agent]  # static transition

    # 5. Topology — delegation
    if len(next_agents) == 1:
      next_manifest = registry.get(next_agents[0])
      current_step = state_manager.create_step(
        pipeline.id, next_agents[0], current_step.output,
        parent_step_id=current_step.step_id
      )
      current_manifest = next_manifest

    else:
      # 1:N fan-out
      branch_steps = topology_manager.delegate(current_step, current_manifest)
      results = aggregate(branch_steps, current_manifest)
      merged_output = results.merged_output

      # N:1 merge step
      merge_step = state_manager.create_step(
        pipeline.id, "__merge__", merged_output,
        parent_step_id=current_step.step_id
      )
      current_step = merge_step
```

### Aggregation with Timeout

```
aggregate(branch_steps, manifest):
  cfg     = manifest.spec.topology.aggregation
  timeout = parse_duration(cfg.timeout)
  mode    = cfg.mode

  completed = []
  deadline  = now() + timeout

  # Subscribe to NATS for step completion events
  with nats.subscribe(f"atelium.step.completed.{pipeline_id}") as sub:
    while now() < deadline:
      event = sub.next_message(timeout=1s)
      if event:
        step = load_step(event.step_id)
        if step.status == SUCCEEDED:
          completed.append(step)

      if mode == "wait_all" and len(completed) == len(branch_steps):
        break
      elif mode == "quorum":
        threshold = cfg.quorum_threshold * len(branch_steps)
        if len(completed) >= threshold:
          break
      elif mode == "first" and len(completed) >= 1:
        break

  # Timeout handling
  timed_out = [s for s in branch_steps if s not in completed]
  if timed_out:
    if cfg.on_timeout == "best_effort":
      pass   # proceed with what we have
    elif cfg.on_timeout == "abort":
      raise TimeoutAbortError(timed_out)
    elif cfg.on_timeout == "escalate_human":
      nats.publish("atelium.hitl.timeout", {...})
      wait_for_hitl(...)

  merged = state_manager.merge(completed, manifest)
  return AggregationResult(completed=completed, timed_out=timed_out, merged_output=merged)
```

---

## NATS JetStream — Event Schema

All events use subject pattern `atelium.<domain>.<event>`.

| Subject | Publisher | Subscriber | Payload |
|---|---|---|---|
| `atelium.step.started` | Runtime | Observability | `{step_id, pipeline_id, agent_name}` |
| `atelium.step.completed` | Runtime | Topology, Observability | `{step_id, pipeline_id, status}` |
| `atelium.step.failed` | Transition Guard | SAGA Coordinator | `{step_id, guard_result}` |
| `atelium.hitl.escalation` | Self-Healing / Guard | Portal, notification | `{step_id, reason, context}` |
| `atelium.hitl.dry_run_review` | SAGA Coordinator | Portal | `{step_id, action, preview}` |
| `atelium.hitl.pre_confirmation` | SAGA Coordinator | Portal | `{step_id, action, context}` |
| `atelium.hitl.response` | Portal / human | Runtime (resume) | `{step_id, approved, updated_output}` |
| `atelium.pipeline.completed` | Runtime | CLI, Portal | `{pipeline_id, status, root_step_id}` |
| `atelium.circuit_breaker.open` | Guard | Router | `{agent_name, until}` |

### JetStream Configuration

```
Streams:
  atelium-steps:
    subjects: [atelium.step.*]
    retention: limits
    max_age: 7d
    replicas: 1 (dev) / 3 (prod)

  atelium-hitl:
    subjects: [atelium.hitl.*]
    retention: interest
    max_age: 30d
    ack_policy: explicit   # HITL events must be explicitly acknowledged
```

---

## LangGraph Integration

Each agent in Atelium runs as a LangGraph `StateGraph`. The runtime wraps manifest execution in a standard graph topology.

```python
def build_agent_graph(manifest: AgentManifest) -> CompiledGraph:
    graph = StateGraph(AgentState)

    graph.add_node("invoke_llm",    invoke_llm_node(manifest))
    graph.add_node("guard",         transition_guard_node(manifest))
    graph.add_node("self_heal",     self_heal_node(manifest))
    graph.add_node("saga_snapshot", saga_snapshot_node(manifest))
    graph.add_node("execute_mcps",  execute_mcps_node(manifest))

    graph.set_entry_point("invoke_llm")

    graph.add_edge("invoke_llm",    "guard")
    graph.add_conditional_edges("guard", route_guard_result, {
        "proceed":    "execute_mcps",
        "self_heal":  "self_heal",
        "hitl":       END,          # pipeline suspends; resumes via HITL event
        "compensate": END,
        "abort":      END,
    })
    graph.add_edge("self_heal",     "invoke_llm")   # loop back
    graph.add_edge("execute_mcps",  "saga_snapshot")
    graph.add_edge("saga_snapshot", END)

    # LangGraph checkpointing → Redis for hot state
    checkpointer = RedisCheckpointer(redis_client)
    return graph.compile(checkpointer=checkpointer)
```

---

## Runtime Configuration

```yaml
# atelium/config/runtime.yaml
runtime:
  embed_model: nomic-embed-text    # via Ollama, MIT license
  embed_dim: 768

  routing:
    alpha: 0.50
    beta:  0.30
    gamma: 0.10
    delta: 0.10
    lambda: 0.1
    min_affinity_threshold: 0.40
    candidate_pool_size: 50

  step_store:
    hot_ttl_seconds: 86400         # 24h in Redis
    archive_on: [succeeded, failed, compensated, aborted]

  circuit_breaker:
    failure_threshold: 3           # failures before opening
    timeout_ms: 60000              # 60s before half-open retry

  hitl:
    default_timeout_ms: 3600000   # 1h before escalation expires
    channels: [nats]               # notification channels
```

# Atelium Agent Manifest — Specification v1.0

## Overview

The Agent Manifest is the declarative contract every agent registered in Atelium must provide. It is the single source of truth that drives:

- **Identity & discovery** — registry indexing, semantic search, ownership
- **Transition Guard** — success/failure criteria and self-healing loop
- **SAGA-A** — compensating actions and irreversibility classification
- **Emergent Routing** — capability vector used for affinity scoring
- **Step-Resident State** — step snapshot and replay configuration
- **Blast Radius** — permission boundary enforcement
- **Observability** — tracing, cost tracking, PII handling

```
apiVersion: atelium/v1alpha1
kind: Agent
```

---

## Top-Level Structure

```yaml
apiVersion: atelium/v1alpha1   # required, fixed value
kind: Agent                    # required, fixed value
metadata:                      # required
  name: string
  owner: string
  version: string
  tags: [string]
  description: string
spec:                          # required
  model: ModelSpec
  capabilities: [string]
  accepts: AcceptsSpec
  mcps: [McpSpec]
  knowledge: KnowledgeSpec
  task: TaskSpec
  saga: SagaSpec
  topology: TopologySpec
  blast_radius: BlastRadiusSpec
  observability: ObservabilitySpec
```

---

## `metadata`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique slug within the registry. Pattern: `[a-z][a-z0-9-]{2,62}` |
| `owner` | string | yes | Email or team identifier. Used for CODEOWNERS-style notifications |
| `version` | string | yes | Semantic version `MAJOR.MINOR.PATCH`. Registry keeps full lineage |
| `tags` | []string | no | Free-form labels for filtering and grouping |
| `description` | string | no | Human-readable summary (shown in Agent Portal) |

**Validation rules:**
- `name` must be unique across the registry at any given version
- `version` must be strictly greater than the previous registered version for the same `name`
- `owner` must resolve to a known identity in OpenFGA

---

## `spec.model`

Defines the LLM backend. All providers must be OSS and self-hostable.

```yaml
model:
  provider: ollama | vllm | litellm
  name: string              # e.g. llama3:70b, mistral:7b, deepseek-r1:32b
  temperature: float        # 0.0–2.0, default: 0.7
  max_tokens: integer       # default: 4096
  timeout_ms: integer       # per-call timeout, default: 30000
  seed: integer             # optional, for reproducibility in experiments
```

**Notes:**
- `provider: ollama` runs via local Ollama daemon
- `provider: vllm` targets a vLLM OpenAI-compatible endpoint
- `provider: litellm` allows routing to any OSS backend via LiteLLM proxy
- Setting `seed` enables deterministic outputs for experiment reproducibility (E1–E5)

---

## `spec.capabilities`

Natural language strings describing what this agent can do. These are embedded by Qdrant (HNSW) at registration time and form the basis of affinity scoring in Emergent Routing.

```yaml
capabilities:
  - "contract review and classification"
  - "jurisdiction analysis Brazil"
  - "LGPD compliance verification"
  - "legal risk identification"
```

**Rules:**
- Minimum 1, maximum 20 strings
- Each string: 5–200 characters
- Strings should be action-oriented ("do X", "analyze Y", "generate Z")
- Vague strings ("general purpose", "handle anything") trigger a registry warning

The embedding vector `cᵢ` for affinity scoring is computed as the mean of individual capability embeddings:

```
cᵢ = mean(embed(c) for c in capabilities)
```

---

## `spec.accepts`

Declares what input this agent expects. Used by the Emergent Router for type-safe routing and by the Transition Guard for input validation.

```yaml
accepts:
  input_types: [string]        # semantic type labels
  required_fields: [string]    # dot-notation field paths that must be present
  optional_fields: [string]    # fields consumed if present
  schema_ref: string           # optional: path to JSON Schema file in registry
```

**Example:**
```yaml
accepts:
  input_types: [contract_document, legal_text]
  required_fields: [document_text, document_type]
  optional_fields: [source_url, metadata.language]
```

---

## `spec.mcps`

MCP (Model Context Protocol) connectors this agent is authorized to use. Enforces least-privilege access.

```yaml
mcps:
  - name: string              # registered MCP connector name
    version: string           # semver constraint, e.g. "^2.1"
    scopes: [string]          # e.g. [read:issues, write:comments]
    rate_limit:
      requests_per_minute: integer
      burst: integer
```

**Rules:**
- Only connectors listed in `blast_radius.max_write_systems` or `max_read_systems` may appear here
- Write scopes (e.g. `write:*`, `create:*`, `delete:*`) automatically increase blast radius classification
- Connectors in `blast_radius.forbidden` cannot be listed here — the manifest will fail validation

---

## `spec.knowledge`

RAG namespaces this agent may query. All namespaces are scoped within the Atelium Knowledge Fabric (pgvector).

```yaml
knowledge:
  namespaces:
    - name: string
      access: read-only | read-write
      top_k: integer           # default: 5
      similarity_threshold: float  # default: 0.75
  embed_model: string          # embedding model for queries, default: platform default
```

**Rules:**
- `read-write` access requires explicit approval in `blast_radius.human_approval_required`
- `top_k` and `similarity_threshold` can be tuned per namespace

---

## `spec.task`

The core contract of the agent. Drives the Transition Guard Engine and Self-Healing Loop.

```yaml
task:
  description: string

  success_criteria:
    - field: string            # dot-notation path in output, e.g. output.jurisdiction
      type: string | float | integer | boolean | enum | regex | json_schema
      # type-specific constraints (see below)

  failure_criteria:
    - condition: string        # expression language (see Condition DSL)
      action: compensate | escalate_human | circuit_breaker | retry | abort

  self_healing:
    strategy: retry_with_feedback | replan | noop
    max_iterations: integer    # default: 3
    feedback_template: string  # template with {validation_errors} and {success_criteria}

  transition_to: string        # name of next agent, or null for terminal
  transition_guard: string     # boolean expression; must evaluate true to proceed
```

### Success Criteria — Type-Specific Constraints

| `type` | Additional fields | Example |
|---|---|---|
| `string` | `min_length`, `max_length`, `pattern` (regex) | `min_length: 10` |
| `float` | `min`, `max` | `min: 0.75, max: 1.0` |
| `integer` | `min`, `max` | `min: 1` |
| `boolean` | `value` | `value: true` |
| `enum` | `values: [string]` | `values: [LOW, MEDIUM, HIGH]` |
| `regex` | `pattern` | `pattern: "^[A-Z]{2}$"` |
| `json_schema` | `schema_ref` | `schema_ref: schemas/output-v1.json` |

### Condition DSL

Failure criteria use a simple expression language evaluated against the step context:

```
output.<field>              # access output field
input.<field>               # access input field  
elapsed_ms                  # wall-clock time since task start
iteration                   # current self-healing iteration number
agent.<name>.status         # status of another agent in same pipeline

# Operators: ==, !=, <, >, <=, >=, AND, OR, NOT, null
# Functions: contains(str, substr), len(list), exists(field)
```

**Examples:**
```yaml
failure_criteria:
  - condition: "output.jurisdiction == null"
    action: compensate
  - condition: "output.confidence < 0.50"
    action: escalate_human
  - condition: "elapsed_ms > 45000"
    action: circuit_breaker
  - condition: "iteration >= 3 AND output.confidence < 0.75"
    action: escalate_human
```

### Failure Actions

| Action | Behavior | SAGA-A Interaction |
|---|---|---|
| `compensate` | Executes `saga.compensating_action`, marks step as rolled back | Triggers SAGA-A compensating transaction |
| `escalate_human` | Pauses pipeline, sends HITL notification via configured channel | Suspends SAGA-A timeout clock |
| `circuit_breaker` | Marks agent as unavailable for `circuit_breaker_timeout_ms`, reroutes | Triggers SAGA-A abort if no alternative route |
| `retry` | Retries without self-healing feedback | Counts against `self_healing.max_iterations` |
| `abort` | Terminates pipeline immediately with error | Triggers all upstream compensating actions |

### Self-Healing Loop State Machine

```
EXECUTING
    │
    ▼
[Guard evaluates]──PASS──▶ TRANSITION_TO_NEXT
    │
   FAIL
    │
    ▼
[iteration < max_iterations?]──NO──▶ [failure_criteria action]
    │
   YES
    │
    ▼
SELF_HEALING (build feedback, re-invoke LLM)
    │
    ▼
EXECUTING (iteration++)
```

---

## `spec.saga`

SAGA-A configuration — the Atelium extension of the SAGA pattern for non-deterministic, multi-topology agent transactions.

```yaml
saga:
  compensating_action: string    # MCP tool call or internal action to undo this step
  
  irreversible_actions:
    - name: string               # action name as declared in spec.mcps
      requires: pre_confirmation | post_notification | none
      dry_run: boolean           # if true, runs in simulation mode first
      dry_run_output_field: string  # field to check in dry-run output before real execution

  snapshot_before: [string]      # list of action names that trigger state snapshot
  
  compensation_timeout_ms: integer   # max time to complete compensation, default: 30000
  idempotency_key_field: string      # output field used as idempotency key for retries
```

### Irreversibility Classification

Every action in `irreversible_actions` is classified at execution time:

| Class | Definition | Example | Compensation |
|---|---|---|---|
| `reversible` | Can be fully undone | Write to internal DB | Delete the record |
| `compensable` | Cannot be undone but effect can be offset | Create Jira ticket | Close ticket with note |
| `irreversible` | Cannot be undone or offset | Send email notification | Post-notification only |

Actions not listed in `irreversible_actions` are assumed `reversible`.

**Rules:**
- Any `irreversible` action with `requires: pre_confirmation` will pause the pipeline until human approves
- `dry_run: true` requires `dry_run_output_field` — the runtime checks this field before allowing real execution
- `snapshot_before` triggers PostgreSQL-backed step snapshot that can be used for replay

---

## `spec.topology`

Declares how this agent participates in 1:N (delegation) and N:1 (aggregation) topologies.

```yaml
topology:
  delegation:
    mode: route_best | route_all | route_n
    n: integer                  # required if mode: route_n
    fallback: string            # agent name to use if routing fails

  aggregation:
    mode: wait_all | quorum | best_effort | first
    quorum_threshold: float     # required if mode: quorum, e.g. 0.6 = 60% must respond
    timeout: duration           # e.g. 120s, 5m
    on_timeout: best_effort | abort | escalate_human
    merge_strategy: union | intersection | weighted_vote | custom
    merge_agent: string         # required if merge_strategy: custom
```

### Delegation Modes

| Mode | Behavior |
|---|---|
| `route_best` | Routes to single highest-affinity agent (1:1) |
| `route_all` | Fan-out to all capable agents (1:N) |
| `route_n` | Fan-out to top-N agents by affinity score |

### Aggregation Modes

| Mode | Semantics | Consistency | Resilience |
|---|---|---|---|
| `wait_all` | Wait for all N responses | Highest | Lowest (one failure = timeout) |
| `quorum` | Wait for `quorum_threshold` fraction | Medium | Medium |
| `best_effort` | Collect responses until timeout, proceed with what arrived | Lowest | Highest |
| `first` | Use first response that passes Transition Guard | Low | High |

### Merge Strategies

| Strategy | Description |
|---|---|
| `union` | Combine all non-null fields; conflicts resolved by last-write-wins |
| `intersection` | Keep only fields present in all responses with identical values |
| `weighted_vote` | Each response weighted by source agent's affinity score |
| `custom` | Delegate merge logic to `merge_agent` (must accept list of outputs) |

---

## `spec.blast_radius`

Defines the maximum impact boundary of this agent. Enforced at runtime by the Atelium permission layer (OpenFGA).

```yaml
blast_radius:
  max_write_systems: [string]          # systems this agent may write to
  max_read_systems: [string]           # systems this agent may read from
  forbidden: [string]                  # systems this agent must NEVER access
  human_approval_required: [string]    # specific actions requiring HITL
  max_concurrent_pipelines: integer    # default: 10
  max_tokens_per_day: integer          # cost ceiling, default: unlimited
```

**Rules:**
- Any MCP scope that writes to a system not in `max_write_systems` is rejected at runtime
- `forbidden` is enforced at the network layer (not just policy) — connections are blocked
- If `human_approval_required` contains an action that `saga.irreversible_actions` does not list, validation warns but does not fail

---

## `spec.observability`

```yaml
observability:
  traces: boolean              # emit OpenTelemetry spans, default: true
  cost_tracking: boolean       # track token usage and cost per step, default: true
  pii_masking: boolean         # mask PII fields in logs/traces, default: false
  pii_fields: [string]         # dot-notation fields to mask if pii_masking: true
  log_step_memory: boolean     # persist full step state to PostgreSQL for replay, default: false
  langfuse_project: string     # Langfuse project name for this agent, default: agent name
  alert_on:
    - condition: string        # Condition DSL expression
      channel: string          # notification channel (slack, email, webhook)
      message: string
```

---

## Validation Rules Summary

The Atelium CLI (`atelium validate --manifest <file>`) enforces the following at registration time:

| Rule | Severity |
|---|---|
| `apiVersion` and `kind` must match fixed values | ERROR |
| `metadata.name` must match `[a-z][a-z0-9-]{2,62}` | ERROR |
| `metadata.version` must be valid semver and greater than previous | ERROR |
| `spec.capabilities` must have 1–20 entries of 5–200 chars | ERROR |
| MCP connectors must not reference `blast_radius.forbidden` systems | ERROR |
| `irreversible_actions` with `dry_run: true` must have `dry_run_output_field` | ERROR |
| `topology.aggregation.mode: quorum` must have `quorum_threshold` | ERROR |
| `topology.aggregation.merge_strategy: custom` must have `merge_agent` | ERROR |
| `transition_guard` expression must be syntactically valid | ERROR |
| `failure_criteria` conditions must be syntactically valid | ERROR |
| Capability strings that are too generic ("general purpose") | WARNING |
| `blast_radius.human_approval_required` actions not in `saga.irreversible_actions` | WARNING |
| `pii_masking: true` without `pii_fields` | WARNING |
| No `self_healing` defined when `failure_criteria` has `action: retry` | WARNING |

---

## Complete Example — `contract-reviewer` Agent

```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: contract-reviewer
  owner: legal-team@company.com
  version: 1.3.0
  tags: [legal, contracts, BR, compliance]
  description: "Classifies legal contracts by jurisdiction and identifies compliance risks"

spec:
  model:
    provider: ollama
    name: llama3:70b
    temperature: 0.1
    max_tokens: 4096
    timeout_ms: 45000

  capabilities:
    - "contract review and classification"
    - "jurisdiction analysis Brazil"
    - "LGPD compliance verification"
    - "legal risk identification"

  accepts:
    input_types: [contract_document, legal_text]
    required_fields: [document_text, document_type]
    optional_fields: [metadata.language, metadata.source]

  mcps:
    - name: jira
      version: "^2.1"
      scopes: [read:issues, write:comments]
      rate_limit:
        requests_per_minute: 60
        burst: 10
    - name: confluence
      version: "^3.0"
      scopes: [read:pages]

  knowledge:
    namespaces:
      - name: legal-contracts-br
        access: read-only
        top_k: 8
        similarity_threshold: 0.80
      - name: lgpd-compliance
        access: read-only
        top_k: 5

  task:
    description: "Classify contract by jurisdiction and identify legal risks"

    success_criteria:
      - field: output.jurisdiction
        type: enum
        values: [BR, US, EU, OTHER]
      - field: output.risk_level
        type: enum
        values: [LOW, MEDIUM, HIGH, CRITICAL]
      - field: output.confidence
        type: float
        min: 0.75
        max: 1.0
      - field: output.summary
        type: string
        min_length: 50

    failure_criteria:
      - condition: "output.jurisdiction == null"
        action: compensate
      - condition: "output.confidence < 0.50"
        action: escalate_human
      - condition: "elapsed_ms > 45000"
        action: circuit_breaker
      - condition: "iteration >= 2 AND output.confidence < 0.75"
        action: escalate_human

    self_healing:
      strategy: retry_with_feedback
      max_iterations: 3
      feedback_template: |
        Your previous response did not satisfy the required criteria:
        {validation_errors}

        Please try again. Requirements:
        {success_criteria}

        Pay special attention to: {failed_fields}

    transition_to: legal-risk-agent
    transition_guard: >
      output.jurisdiction != null
      AND output.confidence >= 0.75
      AND output.risk_level != null

  saga:
    compensating_action: delete_review_draft
    irreversible_actions:
      - name: send_legal_notification
        requires: pre_confirmation
        dry_run: true
        dry_run_output_field: output.notification_preview
    snapshot_before: [write_to_crm, create_jira_ticket]
    compensation_timeout_ms: 30000
    idempotency_key_field: output.contract_hash

  topology:
    delegation:
      mode: route_best
      fallback: generic-document-reviewer
    aggregation:
      mode: wait_all
      timeout: 120s
      on_timeout: best_effort
      merge_strategy: weighted_vote

  blast_radius:
    max_write_systems: [jira, confluence, internal-crm]
    max_read_systems: [legal-contracts-br, lgpd-compliance, jira, confluence]
    forbidden: [production-db, billing-api, hr-records, payroll]
    human_approval_required: [send_legal_notification, approve_contract]
    max_concurrent_pipelines: 5
    max_tokens_per_day: 500000

  observability:
    traces: true
    cost_tracking: true
    pii_masking: true
    pii_fields: [input.document_text, output.summary]
    log_step_memory: true
    langfuse_project: legal-pipeline
    alert_on:
      - condition: "output.risk_level == CRITICAL"
        channel: slack
        message: "CRITICAL risk detected in contract {input.document_type} by {metadata.owner}"
```

---

## Minimal Example — Simple Terminal Agent

An agent with no downstream transition, no SAGA-A, no topology:

```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: sentiment-classifier
  owner: analytics@company.com
  version: 0.1.0

spec:
  model:
    provider: ollama
    name: mistral:7b
    temperature: 0.0

  capabilities:
    - "text sentiment analysis"
    - "emotion classification"

  accepts:
    input_types: [text]
    required_fields: [text]

  task:
    description: "Classify sentiment of input text"
    success_criteria:
      - field: output.sentiment
        type: enum
        values: [positive, neutral, negative]
      - field: output.score
        type: float
        min: 0.0
        max: 1.0

  blast_radius:
    max_write_systems: []
    max_read_systems: []
    forbidden: []

  observability:
    traces: true
    cost_tracking: true
```

---

## JSON Schema (abbreviated)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AteliumAgentManifest",
  "type": "object",
  "required": ["apiVersion", "kind", "metadata", "spec"],
  "properties": {
    "apiVersion": { "type": "string", "const": "atelium/v1alpha1" },
    "kind": { "type": "string", "const": "Agent" },
    "metadata": {
      "type": "object",
      "required": ["name", "owner", "version"],
      "properties": {
        "name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,62}$" },
        "owner": { "type": "string", "minLength": 3 },
        "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
        "tags": { "type": "array", "items": { "type": "string" } },
        "description": { "type": "string" }
      }
    },
    "spec": {
      "type": "object",
      "required": ["model", "capabilities", "accepts", "task", "blast_radius"],
      "properties": {
        "model": {
          "type": "object",
          "required": ["provider", "name"],
          "properties": {
            "provider": { "type": "string", "enum": ["ollama", "vllm", "litellm"] },
            "name": { "type": "string" },
            "temperature": { "type": "number", "minimum": 0.0, "maximum": 2.0 },
            "max_tokens": { "type": "integer", "minimum": 1 },
            "timeout_ms": { "type": "integer", "minimum": 1000 },
            "seed": { "type": "integer" }
          }
        },
        "capabilities": {
          "type": "array",
          "minItems": 1,
          "maxItems": 20,
          "items": { "type": "string", "minLength": 5, "maxLength": 200 }
        }
      }
    }
  }
}
```

Full JSON Schema available at: `architecture/schemas/agent-manifest-v1alpha1.json`

---

## Versioning and Evolution

| Version | Changes |
|---|---|
| `v1alpha1` | Initial spec. All fields subject to change |
| `v1beta1` (planned) | Stabilize `task` and `saga` sections; add `spec.runtime` for multi-step agents |
| `v1` (planned) | Stable API; backward compatibility guaranteed |

Breaking changes between alpha versions are announced via `atelium registry changelog`.

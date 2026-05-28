# Architectural Pattern Catalog for Multi-Agent Systems

> Status: initial draft — each pattern will be expanded with formal context, forces, consequences, and implementation examples.

---

## Pattern 1: Agent Registry

**Category:** Infrastructure / Discovery

**Problem:**
In an organization with multiple agents, no centralized mechanism tracks which agents exist, who created them, which tools they access, and whether they are healthy.

**Solution:**
A central registry where each agent declares its manifest. The registry resolves dependencies, verifies permissions, and exposes a searchable catalog.

**Distributed systems analogue:** Consul, Backstage, Kubernetes API Server

**Components:**
- Agent Manifest (declaration)
- Registry API (agent CRUD)
- Per-agent Health Check Endpoint
- Permission diff in pull requests

**Forces:**
- Visibility across the entire fleet
- Prevention of duplication ("an agent for this already exists")
- Foundation for governance and auditability

**Consequences:**
- Single point of truth (requires high availability)
- Bootstrapping problem: agents must be registered before running

---

## Pattern 2: SAGA-A (SAGA for Agents)

**Category:** Distributed Transactions

**Problem:**
A multi-agent workflow executes real-world actions in sequence (writes to CRM, sends email, creates ticket). If an agent fails mid-flow, the distributed state becomes inconsistent.

**Solution:**
Each agent declares a `compensating_action` in its manifest. A SAGA coordinator (choreography via events or orchestration via LLM supervisor) triggers compensations in reverse order on failure.

**Analogue:** SAGA pattern (Garcia-Molina & Salem, 1987) adapted

**LLM agent-specific extensions (SAGA-A):**

| Extension | Description |
|---|---|
| `irreversible: true` | Action that cannot be undone — requires `pre_confirmation` |
| `compensating_action` | Reversal action declared in the manifest |
| `dry_run_gate` | Mandatory simulated execution before high-impact actions |
| `idempotency_key` | Execution cache by hash(input + tool_calls) for safe retries |
| `cognitive_snapshot` | Snapshot of memory/RAG state before execution |

**Rollback flow:**
```
[A] → [B] → [C: FAILURE]
              ↓
        saga.rollback emitted
              ↓
        [B].compensating_action executed
              ↓
        [A].compensating_action executed
```

**Forces:**
- Eventual consistency in multi-agent workflows
- No need for 2PC (incompatible with LLM latency)

**Consequences:**
- Irreversible actions create "points of no return" in the workflow
- LLM compensations may produce output different from expected (non-determinism)

---

## Pattern 3: Connector Fabric (MCP Registry)

**Category:** Integration / Connectivity

**Problem:**
Each agent connects directly to external tools (Jira, GitHub, database) via custom code. Without standardization, each integration is unique, with no versioning or scope control.

**Solution:**
A registry of versioned MCP Servers, analogous to npm. Agents declare connector dependencies in their manifest with explicit scopes. The platform resolves versions and injects authorized connections.

**Analogue:** npm/pip for connectors; Istio for traffic control

**Structure:**
```yaml
mcps:
  - name: jira
    version: "^2.1"
    scopes: [read:issues, write:comments]
    # NOT allowed: delete:issues, admin:project
```

**Forces:**
- Principle of least privilege per agent
- Audit of who accesses what
- Breaking change detection between MCP versions

**Consequences:**
- Requires a review process for new scopes (may create friction)
- MCP servers must be maintained and versioned

---

## Pattern 4: Knowledge Namespace

**Category:** Data / Shared RAG

**Problem:**
Each agent maintains its own vector index. This results in data duplication, inconsistency between knowledge bases, and multiplied ingestion costs.

**Solution:**
A centralized Knowledge Fabric with namespaces per domain. Agents declare which namespaces they may read. The platform guarantees isolation and access attribution.

**Analogue:** Database schemas with row-level security; IAM policies for S3 buckets

**Structure:**
```yaml
knowledge:
  namespaces:
    - name: legal-contracts
      access: read-only
    - name: compliance-br
      access: read-only
  # NOT allowed: financial-data, hr-records
```

**Forces:**
- Single source of truth for organizational knowledge
- Centralized ingestion and embedding cost
- Attribution: which agent read which chunk at which moment

**Consequences:**
- RAG multi-tenancy is technically complex (metadata filtering does not scale linearly)
- Requires namespace governance (who can create, who can write)

---

## Pattern 5: Agent Choreography (A2A Event-Driven)

**Category:** Communication / Composition

**Problem:**
In centralized orchestration, an LLM supervisor knows all agents and decides each step. This creates tight coupling, additional latency (LLM round-trips), and a single point of failure.

**Solution:**
Agents publish events to a bus (NATS). Other agents react to events of interest. No central agent knows the complete flow.

**Analogue:** Event-driven microservices; Choreography vs. Orchestration (Hohpe & Woolf)

**When to use choreography:**
- Workflows with well-defined steps and stable contracts
- Low-latency requirements
- High resilience (no SPOF)

**When to use orchestration:**
- Open-ended workflows where the LLM needs to reason about the next step
- Frequently changing workflows
- Easier debugging (linear trace)

**Decision metrics (basis for Experiment E2):**

| Criterion | Choreography | Orchestration |
|---|---|---|
| Latency | Lower | Higher (LLM round-trips) |
| Resilience | High (no SPOF) | Medium (supervisor is SPOF) |
| Flexibility | Low (fixed contract) | High (LLM decides) |
| Observability | Difficult (causal tracing) | Easy (linear trace) |
| Token cost | Lower | Higher |

---

## Pattern 6: Blast Radius Boundary

**Category:** Security / Governance

**Problem:**
A compromised, misconfigured, or prompt-injected agent can propagate damage across the entire infrastructure if there is no isolation.

**Solution:**
Each agent operates within a declared blast radius — the maximum set of systems it may affect. The platform blocks out-of-scope actions at runtime.

**Analogue:** Kubernetes RBAC + NetworkPolicy; AWS IAM least privilege

**Structure:**
```yaml
blast_radius:
  max_write_systems: [jira, slack-channel-legal]
  max_read_systems: [legal-contracts-rag, jira, confluence]
  forbidden: [production-db, billing-api, user-pii]
  human_approval_required: [send_external_email, approve_contract]
```

**Forces:**
- Damage containment on failure or attack
- Auditable requirement for compliance (LGPD, SOC2)

**Consequences:**
- Requires a runtime enforcement platform (not just declaration)
- May limit legitimate agents if blast radius is poorly calibrated

---

## Pattern 7: Agent Manifest as Contract

**Category:** Governance / DevOps

**Problem:**
There is no standard for declaring what an agent is, what it can do, and what its dependencies are. This prevents deployment automation, permission review, and discovery.

**Solution:**
A standardized YAML format (Agent Manifest) that serves as the contract between the agent and the platform. Analogous to Dockerfile for containers or Chart.yaml for Helm.

**Minimum specification:**
```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: string
  owner: string          # responsible team
  version: semver
spec:
  model: string          # llama3, mistral, qwen2 via Ollama or vLLM (OSS only)
  mcps: []               # connectors with scopes
  knowledge: {}          # RAG namespaces
  task: {}               # success, failure, and transition criteria
  a2a: {}                # communication contracts
  saga: {}               # compensating actions
  blast_radius: {}       # maximum impact scope
  observability: {}      # telemetry settings
```

**Forces:**
- Foundation for the entire lifecycle: register → deploy → observe → retire
- Enables permission diffs in PRs ("this agent gained access to billing-api")
- Semantic versioning with breaking change detection

---

## Pattern 8: Transition Guard

**Category:** Contracts / Composition

**Problem:**
Agents transition to the next network node even when their task is incomplete or their output does not satisfy the downstream agent's preconditions. The incomplete task propagates silently, corrupting the state of all subsequent agents that assumed unsatisfied preconditions.

**Neural analogue:** A neuron that has not reached its activation threshold should not propagate a signal. The Transition Guard is the **threshold** of the agent network.

**Solution:**
Each agent explicitly declares in its manifest: (a) what constitutes success for its task, (b) what constitutes failure, and (c) the condition that must be true to transition to the next agent. The platform blocks the transition if the guard is not satisfied and automatically triggers SAGA-A.

**Specification:**
```yaml
spec:
  task:
    description: "Classify contract by jurisdiction"

    success_criteria:
      - field: output.jurisdiction
        type: enum
        values: [BR, US, EU]
      - field: output.confidence
        type: float
        min: 0.85

    failure_criteria:
      - condition: "output.jurisdiction == null"
        action: compensate         # triggers upstream SAGA-A
      - condition: "output.confidence < 0.5"
        action: escalate_human     # pauses, awaits human review
      - condition: "elapsed > 30s"
        action: circuit_breaker    # does not transition, does not propagate

    transition_to: legal-agent
    transition_guard: "output.jurisdiction != null AND output.confidence >= 0.85"
```

**What happens when the guard fails:**

```
[Classifier Agent] → evaluates transition_guard → FAIL
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         compensate     escalate_human   circuit_breaker
         (SAGA-A)       (human pause)    (silent abort
         reverts         awaits input     with failure log)
         upstream        before continuing
```

**Relationship with SAGA-A:**
The Transition Guard is **failure detection** — SAGA-A is the **failure response**. The two patterns are complementary: without Transition Guard, SAGA-A is never triggered because the failure is not detected before the transition.

**Forces:**
- Failures are detected at the agent boundary, not propagated downstream
- Explicit and auditable interface contract between agents
- Foundation for H5: makes it testable that incomplete tasks corrupt networks

**Consequences:**
- Requires agent output to be structured enough for guard evaluation
- Agents with free-form output (plain text) need an intermediate evaluation parser
- May introduce latency if the guard requires an additional LLM call for evaluation

---

## Pattern Map

```
DEVELOPMENT          RUNTIME               OPERATIONS
─────────────────────────────────────────────────────────
Agent Manifest  →   Agent Registry    →   Blast Radius
(contract)          (discovery)           (security)
      │                  │
      │           Connector Fabric    →   SAGA-A
      │           (tools)                 (transactions)
      │                  │                    ▲
      │           Knowledge Namespace         │
      │           (data)                      │
      │                                       │
      └──► Transition Guard ────────────────►┘
           (success criteria,     triggers SAGA-A
            failure and           if guard fails
            transition)
                   │
                   ▼
             Choreography
             (A2A composition)
```

---

## Pattern 9: Emergent Routing

**Category:** Composition / Discovery

**Problem:**
In networks with thousands of agents, pre-defined choreography is not feasible — no designer can map all possible routes. Centralized orchestration creates a SPOF and does not scale. A mechanism is needed by which agents autonomously discover the next most capable node, without supervision and without a pre-defined DAG.

**Neural analogue:** Attention mechanism in Transformers — each token calculates affinity (Q·K) with all others and routes to the most relevant ones, with no pre-defined rule.

**Solution:**
After passing the Transition Guard, the agent queries the Registry with its output as a query. The Registry returns a probabilistic ranking of agents with the highest capability affinity. The agent routes to the best candidate — or to the top K in 1:N delegation.

```
Agent A completes task → output: {type: contract_classified, jurisdiction: BR}
        │
        ▼
Registry.route(output, context) → ranking:
  legal-agent-BR      score: 0.94
  compliance-agent    score: 0.81
  summarizer-agent    score: 0.67
        │
        ▼
Agent A routes to legal-agent-BR  ← no DAG, no supervisor
```

**How the Registry calculates affinity:**
- Each agent publishes its `capabilities` as a semantic vector in the manifest
- The emitting agent's output is embedded and compared by similarity
- Score combines: semantic similarity + historical success rate + average latency + current load

**Receiving agent manifest:**
```yaml
spec:
  capabilities:
    - "contract review"
    - "jurisdiction analysis BR"
    - "legal compliance LGPD"
  accepts:
    input_types: [contract_classified, legal_document]
    required_fields: [jurisdiction, document_text]
```

**Three routing modes:**

| Mode | Topology | Description |
|---|---|---|
| `route_best` | 1:1 | Routes to agent with highest score |
| `route_top_k` | 1:N | Delegates to top K agents in parallel |
| `route_quorum` | 1:N→N:1 | Delegates to K, aggregates when quorum completes |

**Forces:**
- Scales to thousands of agents without manual choreography
- Routes adapt dynamically as agents enter/exit the registry
- Emergent specialization: agents better at a task are naturally preferred

**Consequences:**
- Requires Registry with vector search capability (Redis Stack / pgvector)
- Non-deterministic routes make exact workflow reproduction difficult
- Audit must record which route was chosen and why (score log)

---

## Pattern 10: Network Topologies (1:N and N:1)

**Category:** Composition / Aggregation

**Problem:**
Real workflows require parallel delegation (1:N) and result aggregation (N:1). Without explicit declaration of the topology and aggregation strategy, behavior on partial failure is undefined — especially in N:1, where one agent awaits multiple upstreams.

**Valid topologies:**

```
1:1  Direct pipeline
     A ──► B

1:N  Fan-out (parallel delegation)
     A ──► B
       ──► C
       ──► D

N:1  Fan-in (aggregation, join)
     B ──►
     C ──► E
     D ──►

N:N  EXCLUDED — no clear aggregation semantics, produces chaos
```

**Neural analogue:**
```
1:N  →  divergence between layers (one layer feeds many)
N:1  →  pooling / aggregation (many layers converge into one)
N:N  →  full attention — not the model of this architecture
```

**The core N:1 problem: partial failure**

```
             ┌──► agent B (completed) ──┐
agent A ─────┤                          ├──► agent E (waiting)
             ├──► agent C (completed) ──┤
             └──► agent D (FAILED)   ───┘
```

Three aggregation strategies — must be declared in agent E's manifest:

| Strategy | Behavior | When to use |
|---|---|---|
| `wait_all` | Blocks until all deliver or timeout | E's output depends on all inputs |
| `quorum` | Proceeds if K of N deliver | Partial failure tolerance is acceptable |
| `best_effort` | Proceeds with what arrived, marks missing | E's output is partially valid |

**Aggregating agent manifest (N:1):**
```yaml
spec:
  task:
    aggregation:
      mode: quorum            # wait_all | quorum | best_effort
      quorum_size: 2          # minimum N to proceed
      timeout: 60s
      on_timeout: best_effort # graceful degradation after timeout
      on_partial_failure:
        action: compensate_completed  # SAGA-A for agents that already completed
        mark_incomplete: true         # records which inputs were missing

    success_criteria:
      - field: output.aggregated_results
        type: array
        min_length: "{{ aggregation.quorum_size }}"
```

**SAGA-A in N:1 topologies:**

When agent D fails after B and C have already completed:
- `wait_all` → compensates B and C, triggers full SAGA-A
- `quorum` → proceeds without D, records partial failure, does not compensate B and C
- `best_effort` → proceeds without D, output marked as incomplete

**Delegating agent manifest (1:N):**
```yaml
spec:
  task:
    delegation:
      mode: route_top_k
      k: 3
      strategy: parallel      # parallel | sequential_fallback
      collect_via: fan_in     # reference to aggregating agent
      on_all_failed: compensate_self
```

**Forces:**
- Explicit and auditable partial failure behavior
- Configurable graceful degradation per workflow
- SAGA-A knows exactly what to compensate in each topology

**Consequences:**
- Quorum and best_effort produce potentially incomplete outputs — downstream must handle this
- Timeout in wait_all can propagate as cascading latency

---

## Pattern Map (updated)

```
DEVELOPMENT                RUNTIME                    OPERATIONS
──────────────────────────────────────────────────────────────────
Agent Manifest         →   Agent Registry         →   Blast Radius
(contract)                 (discovery +               (security)
      │                     capability embedding)
      │                          │
      │                    Emergent Routing  ←────────────────┐
      │                    (1:1 probabilistic)               │
      │                          │                            │
      │                    ┌─────┴──────┐                     │
      │                   1:N          N:1                    │
      │                 (fan-out)    (fan-in/                  │
      │                              aggregation)             │
      │                    └─────┬──────┘                     │
      │                          │                            │
      │                  Connector Fabric    →   SAGA-A ──────┘
      │                  (tools)                 (compensates
      │                          │                by topology)
      │                  Knowledge Namespace         ▲
      │                  (data)                      │
      │                                              │
      └──► Transition Guard ────────────────────────►┘
           (success criteria +     triggers SAGA-A
            self-healing loop)     if guard fails
```

---

## Pattern 11: Step-Coupled Memory

**Category:** State / Memory

**Problem:**
In networks with emergent routing and dynamic topologies, agent-coupled memory creates two problems: dynamically discovered agents have no context, and in 1:N/N:1 topologies state fragments without a synchronization mechanism. Current frameworks conflate processing capability (agent) with state (memory), forcing stateful agents that cannot be freely substituted or routed.

**Principle:**
> **Agent = processing capability** (stateless, substitutable, routable)
> **Step = unit of state and memory** (stateful, immutable after completion)

**Solution:**
Memory is coupled to the step, not the agent. The step is the object that travels through the network — it carries the task, input, accumulated memory, and output. The agent receives the step, processes it, and returns the enriched step. The agent is merely the processor; the step is the state carrier.

```
Step = {
  id:        uuid
  task:      task description
  input:     input data
  memory:    [ previous step output, step before that, ... ]
  output:    result of this agent (filled after execution)
  metadata:  { agent, timestamp, score, branch_id }
}
```

**Behavior by topology:**

```
1:1 — memory grows linearly
  Step₀ → Agent A → Step₁{memory:[A]}
         → Agent B → Step₂{memory:[A,B]}

1:N — step cloned at fork point
  Step₂{memory:[A,B]}
    → branch B: Step₂ᵦ{memory:[A,B], branch:B} → Agent C
    → branch C: Step₂꜀{memory:[A,B], branch:C} → Agent D
  Each branch accumulates independently from the same snapshot

N:1 — steps merged at aggregator
  Step₃ᵦ{memory:[A,B,C]}  ┐
  Step₃꜀{memory:[A,B,D]}  ├─► merge ─► Step₄{memory:[A,B,C,D,E]}
  Step₃_d{memory:[A,B,E]} ┘
```

**Manifest:**
```yaml
spec:
  memory:
    scope: step                      # coupled to step, not agent
    append_output: true              # output is added to step.memory
    visible_history: last_3          # agent sees N previous steps, not everything

    on_branch:
      strategy: clone                # each branch receives snapshot of current step

    on_merge:
      strategy: union                # unions all branch outputs
      conflict_resolution: voting    # voting | last_write_wins | manual
```

**What this solves:**

| Problem | Solution |
|---|---|
| Dynamically discovered agent has no context | Receives the complete step |
| 1:N: how much context each branch receives | Snapshot at the fork point |
| N:1: how to aggregate divergent contexts | Merge policy declared in aggregator |
| SAGA-A: what was the state before the action | Step is immutable — native snapshot |
| Workflow replay | Step sequence is the complete log |
| LLM context window | visible_history limits what the agent receives |

**Relationship with Emergent Routing:**
Step-Coupled Memory is what makes Emergent Routing possible. Any agent with the right capability can pick up any step — because the step carries everything needed. The agent does not need its own context.

**Analogues:**
- **Functional programming** — pure function receives state, returns new state without side effects
- **Event sourcing** — the step log is the source of truth, current state is derived
- **Git commits** — each commit is an immutable snapshot; branches diverge and merge

**Forces:**
- Agents are completely stateless — substitutable, scalable, routable
- Trivial replay and debugging — step sequence is the complete log
- SAGA-A has a native snapshot for compensation — the step before the action is preserved
- Manageable context window — visible_history prevents unbounded growth

**Consequences:**
- Steps grow in size over long workflows — visible_history is essential
- Merge in N:1 with real conflict requires an explicit policy or human escalation
- Step immutability requires storage — cannot be in-memory only for long workflows

---

## Pattern Map (final)

```
DEVELOPMENT                RUNTIME                       OPERATIONS
─────────────────────────────────────────────────────────────────────
Agent Manifest         →   Agent Registry            →   Blast Radius
(contract)                 (discovery +                  (security)
      │                     capability embedding)
      │                          │
      │                    Emergent Routing
      │                    (probabilistic routing)
      │                          │
      │                   ┌──────┴──────┐
      │                  1:N           N:1
      │               (fan-out)    (fan-in / merge)
      │                   └──────┬──────┘
      │                          │
      │              Step-Coupled Memory ──────────────────────┐
      │              (state travels with the step)             │
      │                          │                             │
      │                  Connector Fabric    →   SAGA-A ───────┘
      │                  (MCP tools)             (compensates by
      │                          │                topology +
      │                  Knowledge Namespace      step snapshot)
      │                  (shared RAG)                 ▲
      │                                               │
      └──► Transition Guard + Self-Healing ──────────►┘
           (success criteria, iteration,    triggers SAGA-A
            correction loop)               if guard exhausted
                   │
                   ▼
             HITL (genuine ambiguity only)
```

---

## Patterns to Document Next

- **Agent Versioning & Canary** — gradual rollout of new agent version
- **Cognitive Snapshot** — reasoning checkpoint for debugging (derived from Step-Coupled Memory)
- **Human-in-the-Loop Gate** — pattern for human approval on critical actions
- **Agent Circuit Breaker** — stops routing to agents with high failure rate

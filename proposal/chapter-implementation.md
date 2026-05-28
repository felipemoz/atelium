# Chapter 7 — Atelium: Reference Platform for Fault-Tolerant Agent Networks

## 7.1 Motivation

Previous chapters formalized the architectural patterns, established the hypotheses, and described the experiments that validate them. This chapter describes **Atelium** — the OSS reference implementation that serves simultaneously as:

1. **Validation artifact** — the platform where Studies 1, 2, and 3 experiments are executed
2. **Proof of viability** — demonstrates that the proposed patterns are implementable with available technology
3. **Community contribution** — a reusable platform for researchers and practitioners

Following Design Science Research methodology [Hevner et al., 2004], the artifact is not merely a byproduct of the research — it is a contribution in itself, evaluated by criteria of utility, completeness, and generality.

---

## 7.2 Platform Overview

Atelium is an **Identity Platform (IdP) for agents** — analogous to what Backstage does for software services, but with native primitives for the unique properties of LLM agents: non-determinism, irreversible actions, dynamic routing, and distributed state.

```
┌─────────────────────────────────────────────────────────┐
│                    ATELIUM PLATFORM                      │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Agent Portal │  │ Registry API │  │  CLI (atelium)│  │
│  │ (catalog,    │  │ (CRUD,       │  │  scaffold,    │  │
│  │  ownership,  │  │  routing,    │  │  register,    │  │
│  │  cost)       │  │  health)     │  │  deploy)      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └─────────────────┼──────────────────┘          │
│                           │                             │
│  ┌────────────────────────▼────────────────────────┐    │
│  │               CORE RUNTIME                       │    │
│  │                                                  │    │
│  │  Transition Guard Engine   Self-Healing Loop     │    │
│  │  SAGA-A Coordinator        Step-Resident State   │    │
│  │  Emergent Router           Topology Manager      │    │
│  └────────────────────────┬────────────────────────┘    │
│                           │                             │
│  ┌──────────────┐  ┌──────┴───────┐  ┌───────────────┐  │
│  │ Connector    │  │  Knowledge   │  │ Observability  │  │
│  │ Fabric       │  │  Fabric      │  │ (OTel +        │  │
│  │ (MCP         │  │  (RAG        │  │  Langfuse)     │  │
│  │  registry)   │  │  namespaces) │  │               │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 7.3 The Agent as a First-Class Entity

The central difference between Atelium and existing platforms (LangSmith, Microsoft Agent 365) is that the agent is an **entity with its own identity**, not merely an ephemeral process.

Every agent registered on the platform has:

| Property | Description | Traditional software analogue |
|---|---|---|
| **Identity** | UUID + name + semantic version | Container image tag |
| **Owner** | Responsible team/person | CODEOWNERS |
| **Capabilities** | Semantic capability vector | API contract |
| **MCP Scopes** | Authorized tools | IAM policy |
| **Knowledge ACL** | Accessible RAG namespaces | Database permissions |
| **Task Contract** | Success criteria + transition guard | SLO definition |
| **SAGA Config** | Compensating actions per action | Rollback script |
| **Blast Radius** | Maximum impactable systems | Network policy |
| **Lineage** | Version and deploy history | Git history |

---

## 7.4 Agent Manifest — Complete Specification

The Agent Manifest is the declarative contract that every agent registered on the platform must provide. It is the central artifact connecting all proposed patterns.

```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: contract-reviewer
  owner: legal-team@company.com
  version: 1.3.0
  tags: [legal, contracts, BR, compliance]

spec:
  # --- LLM Model (OSS only) ---
  model:
    provider: ollama
    name: llama3:70b
    temperature: 0.1          # low for classification tasks
    max_tokens: 4096

  # --- Capabilities (foundation of Emergent Routing) ---
  capabilities:
    - "contract review and classification"
    - "jurisdiction analysis Brazil"
    - "LGPD compliance verification"
    - "legal risk identification"
  accepts:
    input_types: [contract_document, legal_text]
    required_fields: [document_text, document_type]

  # --- MCP connectors (principle of least privilege) ---
  mcps:
    - name: jira
      version: "^2.1"
      scopes: [read:issues, write:comments]
    - name: confluence
      version: "^3.0"
      scopes: [read:pages]

  # --- Knowledge namespaces (shared RAG) ---
  knowledge:
    namespaces:
      - name: legal-contracts-br
        access: read-only
      - name: lgpd-compliance
        access: read-only

  # --- Task contract (Transition Guard) ---
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

    failure_criteria:
      - condition: "output.jurisdiction == null"
        action: compensate
      - condition: "output.confidence < 0.50"
        action: escalate_human
      - condition: "elapsed_ms > 45000"
        action: circuit_breaker

    self_healing:
      strategy: retry_with_feedback
      max_iterations: 3
      feedback_template: |
        Your previous response did not satisfy the required criteria:
        {validation_errors}
        Please try again considering: {success_criteria}

    transition_to: legal-risk-agent
    transition_guard: >
      output.jurisdiction != null
      AND output.confidence >= 0.75
      AND output.risk_level != null

  # --- SAGA-A (fault tolerance) ---
  saga:
    compensating_action: delete_review_draft
    irreversible_actions:
      - name: send_legal_notification
        requires: pre_confirmation
        dry_run: true
    snapshot_before: [write_to_crm, create_jira_ticket]

  # --- Topology (1:N and N:1) ---
  topology:
    delegation:
      mode: route_best            # 1:1 by default
    aggregation:
      mode: wait_all
      timeout: 120s
      on_timeout: best_effort

  # --- Blast radius ---
  blast_radius:
    max_write_systems: [jira, confluence]
    max_read_systems: [legal-contracts-br, lgpd-compliance, jira]
    forbidden: [production-db, billing-api, hr-records]
    human_approval_required: [send_legal_notification, approve_contract]

  # --- Observability ---
  observability:
    traces: true
    cost_tracking: true
    pii_masking: true
    log_step_memory: true         # persists step for replay
```

---

## 7.5 How Experiments Use the Platform

### Experiment E1 — Framework Analysis (Paper 1)

Atelium does not execute LangGraph/CrewAI/AutoGen — it provides the **FTEP evaluation protocol** as a CLI tool:

```bash
atelium eval ftep --framework langgraph --dimensions all \
                  --pipeline canonical-4agent \
                  --inject-failure position=2,3,4 \
                  --runs 30 \
                  --output results/e1-langgraph.json
```

The CLI runs each framework on the canonical pipeline, injects failures, measures state consistency, and generates the comparative matrix. This resolves the inter-rater reliability problem: evaluation is automated and reproducible.

### Experiment E2 — Induced Failure without vs. with SAGA-A (Paper 1)

```bash
# Baseline: pipeline without SAGA-A
atelium benchmark saga \
  --manifest examples/contract-pipeline.yaml \
  --saga-a false \
  --inject-failure position=3 \
  --runs 50

# Treatment: pipeline with SAGA-A
atelium benchmark saga \
  --manifest examples/contract-pipeline.yaml \
  --saga-a true \
  --inject-failure position=3 \
  --runs 50
```

Automatically collected metrics: state consistency score, detection time, compensated actions.

### Experiment E3 — Transition Guard with Self-Healing (Paper 1, H5+H6)

```bash
atelium run pipeline examples/contract-pipeline.yaml \
  --transition-guard false \
  --inject-failure position=classifier \
  --runs 50

atelium run pipeline examples/contract-pipeline.yaml \
  --transition-guard true \
  --self-healing true \
  --inject-failure position=classifier \
  --runs 50
```

Measures: downstream propagation rate of invalid output, number of HITL escalations, self-resolution rate via self-healing.

### Experiment E4 — Emergent Routing (Paper 2)

```bash
# Seed the registry with 47 specialized agents
atelium registry seed examples/agent-registry-47.yaml

# Run routing benchmark
atelium benchmark routing \
  --tasks benchmark/200-tasks.json \
  --methods random,round-robin,emergent,oracle \
  --alpha 0.50 --beta 0.30 --gamma 0.10 --delta 0.10 \
  --runs 5 \
  --output results/e4-routing.json
```

### Experiment E5 — SRS Necessity (Paper 2, Theorem 1)

```bash
# Inject dynamic re-routing (40 events)
atelium benchmark srs \
  --rerouting-events 40 \
  --memory-mode agent-stateful \
  --runs 20 \
  --output results/e5-agent-stateful.json

atelium benchmark srs \
  --rerouting-events 40 \
  --memory-mode step-resident \
  --runs 20 \
  --output results/e5-step-resident.json
```

Measures: context completeness after re-routing (expected: 0.38 vs. 1.00).

---

## 7.6 OSS Technical Stack

All components follow the OSS principle declared in [OSS-PRINCIPLES.md]:

| Layer | Component | License | Rationale |
|---|---|---|---|
| Agent Runtime | LangGraph | MIT | Stateful DAG, native checkpointing |
| Registry + Routing | Redis Stack (RediSearch) | RSALv2/SSPL | ANN sub-linear, self-hostable |
| Event Bus (A2A) | NATS JetStream | Apache 2.0 | Low latency, persistence, OSS |
| Step Store (hot) | Redis | BSD 3-Clause | In-flight state, TTL, pub/sub |
| Step Store (archive) | PostgreSQL | PostgreSQL License | Durable persistence, replay |
| Knowledge / RAG | pgvector | PostgreSQL License | Namespaces on existing Postgres |
| LLM Runtime | Ollama + Llama 3 70B | MIT + Meta License | OSS, local, no API key |
| Observability | Langfuse + OpenTelemetry | MIT + Apache 2.0 | Native LLM tracing, OSS |
| Auth/Permissions | OpenFGA | Apache 2.0 | Relational access control, OSS |
| API Gateway | FastAPI | MIT | Native Python, async, OpenAPI |

---

## 7.7 Deployment Architecture

The platform can be deployed in three configurations to cover different research and production scenarios:

**Mode 1 — Local (laptop, experiments)**
```
Docker Compose: Redis + NATS + PostgreSQL + Ollama + Langfuse
Setup time: ~10 minutes
Requirements: 16GB RAM, optional GPU
```

**Mode 2 — Cluster (scale experiments)**
```
Kubernetes + provided Helm charts
Registry: up to 10k agents tested
Step store: automatic sharding via PostgreSQL
```

**Mode 3 — Production (practitioner validation)**
```
HA: Redis Cluster, NATS cluster, PostgreSQL replication
Monitoring: Grafana + Prometheus + Langfuse
Auth: OpenFGA + Keycloak
```

---

## 7.8 Artifact Evaluation Criteria (DSR)

Following Hevner et al. [2004], the artifact is evaluated on five dimensions:

| Criterion | Metric | Target |
|---|---|---|
| **Utility** | Adoption rate by practitioners (post-experiment survey) | ≥ 70% would consider using in production |
| **Completeness** | Coverage of implemented vs. proposed patterns | 100% of 11 patterns with reference implementation |
| **Generality** | Works with LangGraph, CrewAI, AutoGen without modification | 3/3 frameworks integrated |
| **Efficiency** | Routing overhead vs. direct call | ≤ 15ms p95 for registry query |
| **Reproducibility** | Experiments reproducible by third parties | All 5 experiments with fixed seed |

---

## 7.9 Research Development Roadmap

Artifact development follows the dissertation milestones:

```
Month 1-2:   atelium CLI + Agent Manifest parser + basic Registry
Month 3:     Transition Guard Engine + Self-Healing Loop
Month 4:     SAGA-A Coordinator + Step-Resident State
Month 5:     Emergent Router (Redis Stack + affinity scoring)
Month 6:     1:N and N:1 topologies + Merge Engine
Month 7:     FTEP CLI (experiments E1-E3)
Month 8:     Routing benchmark (experiments E4-E5)
Month 9-10:  Practitioner evaluation + feedback collection
Month 11-12: Refinement, writing, defense
```

---

## 7.10 Relationship with Concurrent Work

| Platform | Type | Agent as entity? | SAGA-A? | Emergent Routing? | OSS? |
|---|---|---|---|---|---|
| Microsoft Agent 365 | Proprietary | Partial | No | No | No |
| LangSmith | SaaS | No (trace-only) | No | No | No |
| SagaLLM | Custom architecture | No | Partial | No | Yes |
| ALAS | Domain-specific | No | Partial | No | Yes |
| Agent Identity URI | Naming/discovery | Yes (naming) | No | No | Yes |
| **Atelium** | **OSS control plane** | **Yes (complete)** | **Yes** | **Yes** | **Yes** |

The gap persists: no existing platform treats the agent as a first-class entity with identity, governance, SAGA-A, Transition Guard, Emergent Routing, and Step-Resident State integrated as a coherent system.

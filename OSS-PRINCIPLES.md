# Atelium — OSS Principles & Definitive Stack

## Fundamental Rule

> Every technology used in the reference implementation and experiments must be 100% open source and self-hostable.

Proprietary systems (Agent 365, LangSmith, GPT-4, Claude) may be cited and compared in the literature review, but **never as a dependency of the produced artifact**.

---

## Definitive Stack

Decisions made and locked. Changes require explicit justification.

### Execution Layer

| Role | Technology | License | Decision |
|---|---|---|---|
| Agent runtime | **LangGraph** | MIT | Stateful DAG with native checkpointing — direct support for Transition Guard and Step-Resident State |
| LLM serving (local) | **Ollama** | MIT | Zero-config for experiments and laptop dev |
| LLM serving (production) | **vLLM** | Apache 2.0 | OpenAI-compatible API, high performance |

### Communication Layer

| Role | Technology | License | Decision |
|---|---|---|---|
| A2A event bus | **NATS JetStream** | Apache 2.0 | Low latency, native persistence, streams and consumers |
| API Gateway | **FastAPI** | MIT | Async Python, automatic OpenAPI, same ecosystem as runtime |
| CLI | **Typer** (Python) | MIT | Same process as runtime — no serialization between CLI and core |

### State Layer

| Role | Technology | License | Decision |
|---|---|---|---|
| Step Store (hot) | **Redis** | BSD 3-Clause | In-flight step state, automatic TTL, pub/sub for notifications |
| Step Store (archive) | **PostgreSQL** | PostgreSQL License | Durable persistence, replay, audit trail |
| Vector registry | **Redis Stack** (RediSearch) | RSALv2 / SSPL | Vector similarity search for Emergent Router affinity scoring |
| Metadata registry | **PostgreSQL** | PostgreSQL License | Agent ownership, versioning, and lineage |
| Knowledge / RAG | **pgvector** | PostgreSQL License | RAG namespaces on existing Postgres — zero extra infra |
| Cache | **Redis** | BSD 3-Clause | Shared with hot Step Store |

### Observability Layer

| Role | Technology | License | Decision |
|---|---|---|---|
| LLM tracing | **Langfuse** | MIT | Native LLM tracing, OSS self-hostable |
| Instrumentation | **OpenTelemetry** | Apache 2.0 | Industry standard, vendor-neutral |
| Metrics | **Prometheus** | Apache 2.0 | Pull-based, integrates with Langfuse and NATS |
| Dashboards | **Grafana** | AGPL 3.0 | Self-hostable, native data sources |

### Security Layer

| Role | Technology | License | Decision |
|---|---|---|---|
| Relational authorization | **OpenFGA** | Apache 2.0 | Blast radius enforcement, MCP scopes, knowledge ACLs |
| Identity provider | **Keycloak** | Apache 2.0 | OIDC/OAuth2 for CLI, Portal, and API |

### LLM Models (open weights)

| Model | License | Use |
|---|---|---|
| Llama 3 70B (Meta) | Llama 3 Community | General-purpose agent — default in experiments |
| Mistral 7B | Apache 2.0 | Lightweight agent, low cost |
| DeepSeek-R1 32B | MIT | Complex reasoning tasks |
| Qwen2 | Apache 2.0 | Multilingual |

### Infrastructure

| Role | Technology | License | Decision |
|---|---|---|---|
| Containers | **Docker Compose** | Apache 2.0 | Local / experiment mode |
| Orchestration | **Kubernetes + Helm** | Apache 2.0 | Cluster and production mode |

---

## Dependency Diagram

```
CLI (Typer)
    │
    ▼
FastAPI ──────────────────────────────────────────────┐
    │                                                 │
    ▼                                                 ▼
Core Runtime (LangGraph)                      Registry API
    │                                          │
    ├── NATS JetStream (A2A events)            ├── Redis Stack (vector search)
    ├── Redis (hot step store)                 └── PostgreSQL (metadata)
    ├── PostgreSQL (step archive)
    ├── pgvector (RAG namespaces)
    ├── OpenFGA (blast radius)
    └── Langfuse + OTel (observability)
```

---

## Evaluation Criteria for New Dependencies

Before adding any technology to the project:

1. **OSI-approved license?** (MIT, Apache 2.0, BSD, GPL, MPL)
2. **Self-hostable without usage restrictions?**
3. **No mandatory API key or external service dependency?**
4. **Source code available and auditable?**

If any answer is **no** → technology is not approved.

> **Redis Stack note:** The RSALv2/SSPL license restricts use as a managed service, but allows unrestricted self-hosting. Approved for use in the artifact.

---

## Note on Comparison with Proprietary Systems

The paper **can and should** compare results with proprietary systems (Agent 365, LangSmith, GPT-4o) as market baselines in the discussion section. This strengthens the relevance of the work without creating a technical dependency.

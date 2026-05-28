# Atelium — Registry API Specification

## Overview

The Registry API is the HTTP interface that exposes the Core Runtime to the CLI, Agent Portal, and external integrations. Built with FastAPI (MIT), it provides automatic OpenAPI documentation and async request handling.

```
Base URL:  http://localhost:8000
Docs:      http://localhost:8000/docs      (Swagger UI)
           http://localhost:8000/redoc     (ReDoc)
OpenAPI:   http://localhost:8000/openapi.json
```

### Authentication

All endpoints require a Bearer token issued by Keycloak. The token is validated against OpenFGA for per-resource authorization.

```
Authorization: Bearer <token>
```

In local dev mode (`ATELIUM_AUTH_DISABLED=true`), auth is bypassed.

---

## Common Response Envelope

All responses follow a consistent envelope:

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req-7f3a2c1d",
    "timestamp": "2026-03-15T14:22:10Z",
    "version": "1.0.0"
  }
}
```

Error responses:

```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'contract-reviewer' not found in registry",
    "details": { ... }
  },
  "meta": { ... }
}
```

### Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Manifest failed schema validation |
| `AGENT_NOT_FOUND` | 404 | Agent name/version not in registry |
| `VERSION_CONFLICT` | 409 | Registered version is not greater than existing |
| `FORBIDDEN_SYSTEM` | 400 | Manifest references a forbidden system |
| `PIPELINE_NOT_FOUND` | 404 | Pipeline ID not found |
| `STEP_NOT_FOUND` | 404 | Step ID not found |
| `HITL_NOT_FOUND` | 404 | HITL request ID not found |
| `HITL_EXPIRED` | 410 | HITL request timed out |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Token lacks permission for this resource |
| `INFRA_ERROR` | 503 | Redis / PostgreSQL / NATS unreachable |

---

## Resource: `/agents`

### `POST /agents`

Register a new agent or a new version of an existing agent.

**Request:**

```json
{
  "manifest": {
    "apiVersion": "atelium/v1alpha1",
    "kind": "Agent",
    "metadata": {
      "name": "contract-reviewer",
      "owner": "legal-team@company.com",
      "version": "1.3.0",
      "tags": ["legal", "contracts", "BR"]
    },
    "spec": { ... }
  },
  "force": false
}
```

**Response `201 Created`:**

```json
{
  "data": {
    "name": "contract-reviewer",
    "version": "1.3.0",
    "status": "active",
    "capability_vector_dim": 768,
    "registered_at": "2026-03-15T14:22:10Z",
    "registry_url": "/agents/contract-reviewer"
  }
}
```

**Behavior:**
1. Validates manifest against JSON Schema (returns `422` on error)
2. Checks version is strictly greater than previous (returns `409` if not)
3. Computes capability embedding via Ollama (`nomic-embed-text`)
4. Writes to Redis Stack index `agent_capabilities`
5. Writes full manifest + lineage entry to PostgreSQL
6. Marks previous version as `superseded`

---

### `GET /agents`

List registered agents.

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `tag` | string (repeatable) | Filter by tag |
| `owner` | string | Filter by owner |
| `status` | string | `active` \| `deprecated` \| `superseded` \| `all` — default: `active` |
| `search` | string | Semantic search on capabilities (ANN via Redis Stack) |
| `input_type` | string | Filter by accepted input type |
| `limit` | int | Max results — default: 20, max: 100 |
| `offset` | int | Pagination offset — default: 0 |

**Response `200 OK`:**

```json
{
  "data": {
    "agents": [
      {
        "name": "contract-reviewer",
        "version": "1.3.0",
        "owner": "legal-team@company.com",
        "status": "active",
        "tags": ["legal", "contracts", "BR"],
        "capabilities": ["contract review and classification", "..."],
        "affinity_score": 0.94,
        "stats": {
          "executions_7d": 142,
          "success_rate_7d": 0.915,
          "avg_elapsed_ms": 12400,
          "hitl_rate_7d": 0.042
        }
      }
    ],
    "total": 47,
    "limit": 20,
    "offset": 0
  }
}
```

---

### `GET /agents/{name}`

Get a specific agent. Returns the latest active version unless `@version` is specified.

**Path:** `/agents/contract-reviewer` or `/agents/contract-reviewer@1.2.0`

**Response `200 OK`:**

```json
{
  "data": {
    "name": "contract-reviewer",
    "version": "1.3.0",
    "status": "active",
    "manifest": { ... },
    "capability_vector": null,
    "registered_at": "2026-03-15T14:22:10Z",
    "stats": { ... },
    "lineage": [
      { "version": "1.3.0", "registered_at": "...", "status": "active" },
      { "version": "1.2.0", "registered_at": "...", "status": "superseded" },
      { "version": "1.0.0", "registered_at": "...", "status": "deprecated" }
    ]
  }
}
```

---

### `DELETE /agents/{name}`

Deprecates an agent (soft delete — excluded from routing but preserved in lineage).

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `version` | string | Specific version to deprecate — default: current |
| `reason` | string | Stored in lineage |

**Response `200 OK`:**

```json
{
  "data": {
    "name": "contract-reviewer",
    "version": "1.3.0",
    "status": "deprecated",
    "deprecated_at": "2026-03-15T14:22:10Z"
  }
}
```

---

### `POST /agents/{name}/route`

Find the best agent(s) for a given task. Core of the Emergent Router.

**Request:**

```json
{
  "task_description": "Classify this NDA contract by jurisdiction and identify LGPD risks",
  "input_types": ["contract_document"],
  "mode": "route_best",
  "n": 1,
  "exclude": ["contract-reviewer@1.0.0"],
  "weights": {
    "alpha": 0.50,
    "beta": 0.30,
    "gamma": 0.10,
    "delta": 0.10
  }
}
```

**Response `200 OK`:**

```json
{
  "data": {
    "decisions": [
      {
        "agent_name": "contract-reviewer",
        "agent_version": "1.3.0",
        "affinity_score": 0.94,
        "score_breakdown": {
          "semantic_similarity": 0.91,
          "success_rate": 0.915,
          "recency": 0.98,
          "load": 0.20
        },
        "weighted_score": 0.94
      }
    ],
    "routing_mode": "route_best",
    "candidates_evaluated": 47,
    "elapsed_ms": 8
  }
}
```

---

## Resource: `/pipelines`

### `POST /pipelines`

Start a new pipeline execution.

**Request:**

```json
{
  "root_agent": "contract-reviewer",
  "input": {
    "document_text": "...",
    "document_type": "NDA"
  },
  "options": {
    "saga_a": true,
    "transition_guard": true,
    "self_healing": true,
    "inject_failure": null
  }
}
```

**Response `202 Accepted`:**

```json
{
  "data": {
    "pipeline_id": "pipeline-7f3a2c1d",
    "status": "running",
    "root_agent": "contract-reviewer",
    "root_step_id": "step-4a2b1c3d",
    "created_at": "2026-03-15T14:22:10Z",
    "events_url": "/pipelines/pipeline-7f3a2c1d/events"
  }
}
```

---

### `GET /pipelines`

List pipelines.

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `status` | string | `running` \| `succeeded` \| `failed` \| `waiting_hitl` \| `all` |
| `root_agent` | string | Filter by root agent name |
| `since` | datetime | ISO 8601 — default: last 24h |
| `limit` | int | Default: 20 |
| `offset` | int | Default: 0 |

**Response `200 OK`:**

```json
{
  "data": {
    "pipelines": [
      {
        "pipeline_id": "pipeline-7f3a2c1d",
        "root_agent": "contract-reviewer",
        "status": "running",
        "current_agents": ["legal-risk-agent"],
        "steps_completed": 1,
        "steps_total": null,
        "created_at": "2026-03-15T14:22:10Z",
        "elapsed_ms": 8200
      }
    ],
    "total": 3,
    "limit": 20,
    "offset": 0
  }
}
```

---

### `GET /pipelines/{pipeline_id}`

Get full pipeline detail including step tree.

**Response `200 OK`:**

```json
{
  "data": {
    "pipeline_id": "pipeline-7f3a2c1d",
    "status": "succeeded",
    "root_agent": "contract-reviewer",
    "created_at": "2026-03-15T14:22:10Z",
    "completed_at": "2026-03-15T14:22:25Z",
    "elapsed_ms": 15300,
    "summary": {
      "steps": 2,
      "total_tokens": 5995,
      "total_cost_usd": 0.0,
      "hitl_count": 0,
      "self_healing_iterations": 0
    },
    "steps": [
      {
        "step_id": "step-4a2b1c3d",
        "agent_name": "contract-reviewer",
        "agent_version": "1.3.0",
        "status": "succeeded",
        "iteration": 0,
        "elapsed_ms": 8200,
        "output": {
          "jurisdiction": "BR",
          "risk_level": "MEDIUM",
          "confidence": 0.91
        }
      },
      {
        "step_id": "step-8e5f2b1a",
        "agent_name": "legal-risk-agent",
        "agent_version": "2.1.0",
        "status": "succeeded",
        "iteration": 0,
        "elapsed_ms": 7100,
        "parent_step_id": "step-4a2b1c3d",
        "output": { ... }
      }
    ],
    "saga_log": [
      {
        "step_id": "step-4a2b1c3d",
        "action": "write_to_crm",
        "irreversibility": "compensable",
        "compensating_action": "delete_review_draft",
        "status": "committed"
      }
    ]
  }
}
```

---

### `DELETE /pipelines/{pipeline_id}`

Cancel a running pipeline and trigger SAGA-A compensation.

**Response `200 OK`:**

```json
{
  "data": {
    "pipeline_id": "pipeline-7f3a2c1d",
    "status": "compensated",
    "compensation": {
      "steps_compensated": 2,
      "steps_failed": 0,
      "irreversible_notified": 0
    }
  }
}
```

---

### `GET /pipelines/{pipeline_id}/events`

Server-Sent Events stream for real-time pipeline monitoring.

```
GET /pipelines/pipeline-7f3a2c1d/events
Accept: text/event-stream
```

**Event stream:**

```
event: step_started
data: {"step_id":"step-4a2b1c3d","agent_name":"contract-reviewer","timestamp":"..."}

event: step_self_healing
data: {"step_id":"step-4a2b1c3d","iteration":1,"validation_errors":["output.confidence < 0.75"]}

event: step_succeeded
data: {"step_id":"step-4a2b1c3d","elapsed_ms":8200,"output":{"jurisdiction":"BR",...}}

event: step_started
data: {"step_id":"step-8e5f2b1a","agent_name":"legal-risk-agent","timestamp":"..."}

event: pipeline_succeeded
data: {"pipeline_id":"pipeline-7f3a2c1d","elapsed_ms":15300}
```

---

### `POST /pipelines/{pipeline_id}/replay`

Replay a pipeline from a specific step using the archived step snapshot.

**Request:**

```json
{
  "from_step_id": "step-4a2b1c3d"
}
```

**Response `202 Accepted`:**

```json
{
  "data": {
    "pipeline_id": "pipeline-9b2c3d4e",
    "replayed_from": "pipeline-7f3a2c1d",
    "from_step_id": "step-4a2b1c3d",
    "status": "running"
  }
}
```

---

## Resource: `/steps`

### `GET /steps/{step_id}`

Get a single step by ID.

**Response `200 OK`:**

```json
{
  "data": {
    "step_id": "step-4a2b1c3d",
    "pipeline_id": "pipeline-7f3a2c1d",
    "agent_name": "contract-reviewer",
    "agent_version": "1.3.0",
    "parent_step_id": null,
    "branch_id": null,
    "status": "succeeded",
    "iteration": 0,
    "input": { ... },
    "output": { "jurisdiction": "BR", "risk_level": "MEDIUM", "confidence": 0.91 },
    "context_window": [ ... ],
    "validation_errors": [],
    "started_at": "2026-03-15T14:22:10Z",
    "completed_at": "2026-03-15T14:22:18Z",
    "elapsed_ms": 8200,
    "tokens_used": 3104,
    "cost_usd": 0.0,
    "otel_trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "langfuse_trace_id": "clv2x..."
  }
}
```

---

## Resource: `/hitl`

### `GET /hitl`

List pending HITL requests.

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `status` | string | `pending` \| `approved` \| `rejected` \| `expired` \| `all` — default: `pending` |
| `pipeline_id` | string | Filter by pipeline |
| `agent` | string | Filter by agent name |

**Response `200 OK`:**

```json
{
  "data": {
    "requests": [
      {
        "hitl_id": "hitl-9f2a1b3c",
        "pipeline_id": "pipeline-7f3a2c1d",
        "step_id": "step-4a2b1c3d",
        "agent_name": "contract-reviewer",
        "reason": "low_confidence",
        "reason_detail": "output.confidence = 0.48 < threshold 0.50",
        "current_output": { "jurisdiction": "BR", "confidence": 0.48 },
        "created_at": "2026-03-15T14:22:10Z",
        "expires_at": "2026-03-15T15:22:10Z",
        "status": "pending"
      }
    ],
    "total": 2
  }
}
```

---

### `POST /hitl/{hitl_id}/approve`

Approve a HITL request, optionally overriding output fields.

**Request:**

```json
{
  "override_output": {
    "confidence": 0.82,
    "risk_level": "HIGH"
  },
  "comment": "Reviewed manually — HIGH risk due to missing data processing clause"
}
```

**Response `200 OK`:**

```json
{
  "data": {
    "hitl_id": "hitl-9f2a1b3c",
    "status": "approved",
    "pipeline_id": "pipeline-7f3a2c1d",
    "pipeline_status": "running",
    "approved_at": "2026-03-15T14:27:05Z",
    "approved_by": "user@company.com"
  }
}
```

**Behavior:** Publishes `atelium.hitl.response` to NATS, which resumes the suspended pipeline execution.

---

### `POST /hitl/{hitl_id}/reject`

Reject a HITL request, triggering SAGA-A compensation.

**Request:**

```json
{
  "reason": "Incorrect jurisdiction classification — document is EU, not BR"
}
```

**Response `200 OK`:**

```json
{
  "data": {
    "hitl_id": "hitl-9f2a1b3c",
    "status": "rejected",
    "pipeline_id": "pipeline-7f3a2c1d",
    "pipeline_status": "compensated",
    "compensation": {
      "steps_compensated": 1,
      "steps_failed": 0
    }
  }
}
```

---

## Resource: `/health`

### `GET /health`

Basic liveness check.

**Response `200 OK`:**

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### `GET /health/ready`

Readiness check — verifies all infrastructure dependencies are reachable.

**Response `200 OK`:**

```json
{
  "status": "ready",
  "checks": {
    "postgresql": "ok",
    "redis":      "ok",
    "nats":       "ok",
    "ollama":     "ok"
  }
}
```

**Response `503 Service Unavailable`** (if any dependency is down):

```json
{
  "status": "not_ready",
  "checks": {
    "postgresql": "ok",
    "redis":      "ok",
    "nats":       "error: connection refused",
    "ollama":     "ok"
  }
}
```

---

## Resource: `/metrics`

### `GET /metrics`

Prometheus metrics endpoint (scraped by Prometheus every 15s).

```
# HELP atelium_pipelines_total Total pipelines by status
# TYPE atelium_pipelines_total counter
atelium_pipelines_total{status="succeeded"} 1042
atelium_pipelines_total{status="failed"} 38
atelium_pipelines_total{status="compensated"} 12

# HELP atelium_step_duration_ms Step execution duration in milliseconds
# TYPE atelium_step_duration_ms histogram
atelium_step_duration_ms_bucket{agent="contract-reviewer",le="5000"} 14
atelium_step_duration_ms_bucket{agent="contract-reviewer",le="15000"} 128
atelium_step_duration_ms_bucket{agent="contract-reviewer",le="45000"} 142
atelium_step_duration_ms_sum{agent="contract-reviewer"} 1760800
atelium_step_duration_ms_count{agent="contract-reviewer"} 142

# HELP atelium_self_healing_iterations Self-healing iterations per step
# TYPE atelium_self_healing_iterations histogram
atelium_self_healing_iterations_bucket{agent="contract-reviewer",le="0"} 118
atelium_self_healing_iterations_bucket{agent="contract-reviewer",le="1"} 136
atelium_self_healing_iterations_bucket{agent="contract-reviewer",le="3"} 142

# HELP atelium_hitl_total HITL escalations by reason
# TYPE atelium_hitl_total counter
atelium_hitl_total{agent="contract-reviewer",reason="low_confidence"} 6

# HELP atelium_routing_affinity_score Affinity scores at routing time
# TYPE atelium_routing_affinity_score histogram
atelium_routing_affinity_score_bucket{le="0.5"} 3
atelium_routing_affinity_score_bucket{le="0.7"} 18
atelium_routing_affinity_score_bucket{le="0.9"} 41
atelium_routing_affinity_score_bucket{le="1.0"} 47

# HELP atelium_registry_query_ms Registry ANN query duration in milliseconds
# TYPE atelium_registry_query_ms histogram
atelium_registry_query_ms_bucket{le="5"} 39
atelium_registry_query_ms_bucket{le="10"} 46
atelium_registry_query_ms_bucket{le="15"} 47
```

---

## FastAPI Application Structure

```python
# atelium/api/main.py

from fastapi import FastAPI
from atelium.api.routers import agents, pipelines, steps, hitl, health

app = FastAPI(
    title="Atelium Registry API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(agents.router,    prefix="/agents",    tags=["Agents"])
app.include_router(pipelines.router, prefix="/pipelines", tags=["Pipelines"])
app.include_router(steps.router,     prefix="/steps",     tags=["Steps"])
app.include_router(hitl.router,      prefix="/hitl",      tags=["HITL"])
app.include_router(health.router,    tags=["Health"])

# Prometheus metrics
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# OpenTelemetry
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)
```

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| `POST /agents` | 10 req/min per token |
| `POST /pipelines` | 100 req/min per token |
| `POST /agents/{name}/route` | 500 req/min per token |
| `GET /metrics` | No auth required, no limit |
| All other GETs | 300 req/min per token |

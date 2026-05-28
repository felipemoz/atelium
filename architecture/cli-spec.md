# Atelium CLI — Specification

## Overview

The `atelium` CLI is the primary interface for developers and researchers interacting with the platform. Built with [Typer](https://typer.tiangolo.com/) (MIT), it runs in the same Python process as the Core Runtime — no serialization boundary between CLI commands and internal components.

```
atelium <command-group> <command> [OPTIONS] [ARGS]
```

### Installation

```bash
pip install atelium
# or from source:
git clone https://github.com/atelium/atelium && cd atelium
pip install -e ".[cli]"
```

### Configuration

The CLI reads from `~/.atelium/config.yaml` or `ATELIUM_*` environment variables.

```yaml
# ~/.atelium/config.yaml
api_url: http://localhost:8000
registry_url: http://localhost:8000/registry
nats_url: nats://localhost:4222
redis_url: redis://localhost:6379
postgres_dsn: postgresql://atelium:atelium@localhost:5432/atelium
langfuse_url: http://localhost:3000
default_output: table   # table | json | yaml
```

---

## Command Groups

```
atelium
  ├── agent       Agent manifest management
  ├── run         Execute pipelines
  ├── registry    Registry operations
  ├── eval        FTEP evaluation protocol (experiments)
  ├── benchmark   Routing and SRS benchmarks
  ├── pipeline    Inspect and manage running pipelines
  ├── hitl        Human-in-the-loop operations
  └── dev         Local development utilities
```

---

## `atelium agent`

### `atelium agent validate`

Validates a manifest file against the Agent Manifest v1 schema.

```
atelium agent validate MANIFEST_PATH [OPTIONS]

Arguments:
  MANIFEST_PATH    Path to .yaml manifest file

Options:
  --strict         Treat warnings as errors [default: False]
  --output FORMAT  Output format: table | json [default: table]
```

**Example:**

```bash
atelium agent validate manifests/contract-reviewer.yaml

✓ apiVersion         atelium/v1alpha1
✓ metadata.name      contract-reviewer (unique in registry)
✓ metadata.version   1.3.0 > 1.2.0 (previous)
✓ capabilities       4 entries, all valid
✓ task.success_criteria  3 criteria, all valid
✓ task.transition_guard  expression parsed OK
✓ saga               compensating_action present
✓ blast_radius       no forbidden systems in mcps
⚠ pii_masking: true but pii_fields not specified

1 warning. Manifest is valid (use --strict to fail on warnings).
```

---

### `atelium agent register`

Registers a manifest in the Atelium registry. Computes capability embedding and stores in Redis Stack + PostgreSQL.

```
atelium agent register MANIFEST_PATH [OPTIONS]

Arguments:
  MANIFEST_PATH    Path to .yaml manifest file

Options:
  --dry-run        Validate and preview registration without writing [default: False]
  --force          Allow re-registration of same version [default: False]
```

**Example:**

```bash
atelium agent register manifests/contract-reviewer.yaml

Registering contract-reviewer@1.3.0...
  ✓ Manifest validated
  ✓ Capability embedding computed (dim=768, model=nomic-embed-text)
  ✓ Stored in Redis Stack index: agent_capabilities
  ✓ Stored in PostgreSQL: agent_registry
  ✓ Previous version 1.2.0 marked as superseded

Agent registered: contract-reviewer@1.3.0
Registry URL: http://localhost:8000/registry/agents/contract-reviewer
```

---

### `atelium agent show`

Displays details of a registered agent.

```
atelium agent show AGENT_NAME [OPTIONS]

Arguments:
  AGENT_NAME    Agent name (optionally @version, e.g. contract-reviewer@1.2.0)

Options:
  --output FORMAT   table | json | yaml [default: table]
```

**Example:**

```bash
atelium agent show contract-reviewer

Name:     contract-reviewer
Version:  1.3.0
Owner:    legal-team@company.com
Status:   active
Tags:     legal, contracts, BR, compliance

Capabilities:
  • contract review and classification
  • jurisdiction analysis Brazil
  • LGPD compliance verification
  • legal risk identification

Task:
  Transition to:  legal-risk-agent
  Success criteria: 3 fields
  Self-healing:   retry_with_feedback (max 3 iterations)

MCPs:       jira (read:issues, write:comments), confluence (read:pages)
Knowledge:  legal-contracts-br (read), lgpd-compliance (read)

Stats (last 7d):
  Executions:  142
  Success rate: 91.5%
  Avg elapsed: 12.4s
  Avg tokens:  3,204
  HITL rate:   4.2%
```

---

### `atelium agent list`

Lists registered agents with filtering.

```
atelium agent list [OPTIONS]

Options:
  --tag TEXT          Filter by tag (repeatable)
  --owner TEXT        Filter by owner
  --status TEXT       active | deprecated | all [default: active]
  --search TEXT       Semantic search on capabilities
  --output FORMAT     table | json [default: table]
  --limit INT         Max results [default: 20]
```

**Example:**

```bash
atelium agent list --tag legal --search "contract analysis"

NAME                    VERSION   OWNER                    AFFINITY   STATUS
contract-reviewer       1.3.0     legal-team@company.com   0.94       active
legal-risk-agent        2.1.0     legal-team@company.com   0.87       active
clause-extractor        1.0.1     nlp-team@company.com     0.72       active
```

---

### `atelium agent deprecate`

Marks an agent version as deprecated (excluded from routing by default).

```
atelium agent deprecate AGENT_NAME [OPTIONS]

Options:
  --version TEXT   Specific version to deprecate (default: current)
  --reason TEXT    Deprecation reason stored in lineage
```

---

## `atelium run`

### `atelium run pipeline`

Executes a pipeline starting from a root agent manifest.

```
atelium run pipeline MANIFEST_PATH [OPTIONS]

Arguments:
  MANIFEST_PATH    Root agent manifest or pipeline definition file

Options:
  --input TEXT         Input payload as JSON string
  --input-file PATH    Input payload from file
  --saga-a BOOL        Enable/disable SAGA-A [default: True]
  --transition-guard BOOL  Enable/disable Transition Guard [default: True]
  --self-healing BOOL  Enable/disable self-healing loop [default: True]
  --inject-failure TEXT  Inject failure at position: position=N,type=TYPE
  --watch              Stream step events to terminal [default: False]
  --output FORMAT      summary | full | json [default: summary]
```

**Example:**

```bash
atelium run pipeline manifests/contract-reviewer.yaml \
  --input '{"document_text": "...", "document_type": "NDA"}' \
  --watch

Pipeline started: pipeline-7f3a2c1d
Root agent: contract-reviewer@1.3.0

[00:00] ● contract-reviewer      EXECUTING
[00:08] ✓ contract-reviewer      SUCCEEDED  (8.2s, 3,104 tokens)
         output.jurisdiction = BR
         output.risk_level   = MEDIUM
         output.confidence   = 0.91

[00:08] ● legal-risk-agent       EXECUTING  (routed via emergent, affinity=0.89)
[00:15] ✓ legal-risk-agent       SUCCEEDED  (7.1s, 2,891 tokens)

Pipeline SUCCEEDED in 15.3s
Steps: 2  |  Tokens: 5,995  |  Cost: $0.0000  |  HITL: 0
```

---

### `atelium run step`

Executes a single agent step (no pipeline chaining). Useful for testing individual agents.

```
atelium run step AGENT_NAME [OPTIONS]

Options:
  --input TEXT         Input payload as JSON string
  --input-file PATH    Input payload from file
  --iterations INT     Max self-healing iterations [default: from manifest]
  --output FORMAT      summary | full | json [default: summary]
```

---

## `atelium registry`

### `atelium registry seed`

Bulk-registers agents from a registry seed file. Used in experiments (E4: seed 47 agents).

```
atelium registry seed SEED_FILE [OPTIONS]

Arguments:
  SEED_FILE    YAML file containing list of agent manifests

Options:
  --parallel INT   Concurrent registrations [default: 4]
  --dry-run        Validate all manifests without registering
```

**Seed file format:**

```yaml
# examples/agent-registry-47.yaml
agents:
  - path: manifests/contract-reviewer.yaml
  - path: manifests/legal-risk-agent.yaml
  - path: manifests/clause-extractor.yaml
  # ... 44 more
```

---

### `atelium registry stats`

Shows registry statistics.

```bash
atelium registry stats

Registry Statistics
  Total agents:      47
  Active:            45
  Deprecated:        2
  Owners:            12 teams
  Capability index:  47 vectors (dim=768) in Redis Stack

Top agents by success rate (last 7d):
  sentiment-classifier   98.2%  (1,204 executions)
  contract-reviewer      91.5%  (142 executions)
  legal-risk-agent       89.3%  (98 executions)
```

---

### `atelium registry changelog`

Shows version history for an agent.

```bash
atelium registry changelog contract-reviewer

contract-reviewer — version history

1.3.0  2026-03-15  legal-team@company.com  [current]
  Added LGPD compliance capability
  Changed: confidence threshold 0.70 → 0.75

1.2.0  2026-02-01  legal-team@company.com  [superseded]
  Added self-healing strategy

1.0.0  2026-01-10  legal-team@company.com  [deprecated]
  Initial registration
```

---

## `atelium eval`

FTEP (Fault-Tolerance Evaluation Protocol) — runs the structured evaluation used in Experiment E1.

### `atelium eval ftep`

```
atelium eval ftep [OPTIONS]

Options:
  --framework TEXT     Framework to evaluate: langgraph | crewai | autogen
  --dimensions TEXT    Comma-separated FTEP dimensions: D1,D2,D3,D4,D5 or all
  --pipeline TEXT      Pipeline definition: canonical-4agent | custom
  --inject-failure TEXT  position=N or position=2,3,4
  --runs INT           Number of runs per configuration [default: 30]
  --seed INT           Random seed for reproducibility [default: 42]
  --output PATH        Results output file (.json)
```

**FTEP Dimensions:**

| ID | Dimension |
|---|---|
| D1 | Compensating action primitives |
| D2 | State persistence across failures |
| D3 | Partial failure isolation |
| D4 | Rollback / undo semantics |
| D5 | Human-in-the-loop integration |

**Example (Experiment E1):**

```bash
atelium eval ftep \
  --framework langgraph \
  --dimensions all \
  --pipeline canonical-4agent \
  --inject-failure position=2,3,4 \
  --runs 30 \
  --seed 42 \
  --output results/e1-langgraph.json

Running FTEP evaluation: langgraph / canonical-4agent
  30 runs × 3 failure positions × 5 dimensions = 450 evaluations

[████████████████████] 450/450

Results: results/e1-langgraph.json

FTEP Matrix — LangGraph
  D1 Compensating primitives:  ABSENT
  D2 State persistence:        PARTIAL
  D3 Partial failure isolation: ABSENT
  D4 Rollback semantics:       ABSENT
  D5 HITL integration:         PARTIAL

State consistency score:
  Failure at position 2:  0.41
  Failure at position 3:  0.38
  Failure at position 4:  0.61
  Mean:                   0.47 ± 0.12
```

---

### `atelium eval compare`

Generates comparative FTEP matrix from multiple result files.

```bash
atelium eval compare results/e1-*.json

FTEP Comparison Matrix

Framework   D1       D2       D3       D4       D5       Mean SCS
LangGraph   ABSENT   PARTIAL  ABSENT   ABSENT   PARTIAL  0.47
CrewAI      ABSENT   ABSENT   ABSENT   ABSENT   ABSENT   0.31
AutoGen     ABSENT   PARTIAL  PARTIAL  ABSENT   FULL     0.52
Atelium     FULL     FULL     FULL     FULL     FULL     0.94
```

---

## `atelium benchmark`

### `atelium benchmark routing`

Routing accuracy benchmark (Experiment E4): compares random, round-robin, emergent, and oracle strategies.

```
atelium benchmark routing [OPTIONS]

Options:
  --tasks PATH         JSON file with benchmark tasks [required]
  --methods TEXT       Comma-separated: random,round-robin,emergent,oracle
  --alpha FLOAT        Affinity weight α [default: 0.50]
  --beta FLOAT         Affinity weight β [default: 0.30]
  --gamma FLOAT        Affinity weight γ [default: 0.10]
  --delta FLOAT        Affinity weight δ [default: 0.10]
  --runs INT           Repetitions per task [default: 5]
  --seed INT           [default: 42]
  --output PATH        Results file (.json)
```

**Example (Experiment E4):**

```bash
atelium benchmark routing \
  --tasks benchmark/200-tasks.json \
  --methods random,round-robin,emergent,oracle \
  --runs 5 \
  --seed 42 \
  --output results/e4-routing.json

Routing Benchmark: 200 tasks × 4 methods × 5 runs = 4,000 evaluations
Registry: 47 agents

[████████████████████] 4000/4000

Method          Completion Rate   Avg Affinity   p-value (vs random)
random          0.51 ± 0.09       —              —
round-robin     0.54 ± 0.08       —              0.41
emergent        0.84 ± 0.05       0.81           < 0.001 ***
oracle          0.91 ± 0.03       —              —
```

---

### `atelium benchmark srs`

Step-Resident State necessity benchmark (Experiment E5): measures context completeness with agent-stateful vs. step-resident memory.

```
atelium benchmark srs [OPTIONS]

Options:
  --rerouting-events INT   Number of dynamic re-routing events to inject [default: 40]
  --memory-mode TEXT       agent-stateful | step-resident
  --runs INT               [default: 20]
  --seed INT               [default: 42]
  --output PATH            Results file (.json)
```

**Example (Experiment E5):**

```bash
# Baseline: agent-stateful memory
atelium benchmark srs \
  --rerouting-events 40 \
  --memory-mode agent-stateful \
  --runs 20 \
  --output results/e5-agent-stateful.json

# Treatment: step-resident state
atelium benchmark srs \
  --rerouting-events 40 \
  --memory-mode step-resident \
  --runs 20 \
  --output results/e5-step-resident.json

atelium benchmark srs --compare results/e5-*.json

SRS Necessity Benchmark

Memory Mode       Context Completeness   Lost Steps   p-value
agent-stateful    0.38 ± 0.07            23.4 / 40    —
step-resident     1.00 ± 0.00            0.0 / 40     < 0.001 ***

Conclusion: SRS is necessary for correct context under re-routing.
```

---

### `atelium benchmark saga`

SAGA-A effectiveness benchmark (Experiment E2): measures state consistency with and without SAGA-A.

```
atelium benchmark saga [OPTIONS]

Options:
  --manifest PATH      Pipeline manifest [required]
  --inject-failure TEXT  position=N
  --saga-a BOOL        Enable/disable SAGA-A
  --runs INT           [default: 50]
  --seed INT           [default: 42]
  --output PATH        Results file (.json)
```

**Example (Experiment E2):**

```bash
# Baseline
atelium benchmark saga \
  --manifest examples/contract-pipeline.yaml \
  --saga-a false --inject-failure position=3 \
  --runs 50 --output results/e2-no-saga.json

# Treatment
atelium benchmark saga \
  --manifest examples/contract-pipeline.yaml \
  --saga-a true --inject-failure position=3 \
  --runs 50 --output results/e2-with-saga.json

atelium benchmark saga --compare results/e2-*.json

SAGA-A Benchmark (failure at position 3)

Config        State Consistency   Detection Time   Compensated
without SAGA  0.34 ± 0.11         —                0 / 50
with SAGA-A   0.91 ± 0.04         1.2s ± 0.3s      47 / 50
```

---

## `atelium pipeline`

### `atelium pipeline list`

```bash
atelium pipeline list --status running

PIPELINE ID              ROOT AGENT          STATUS    STARTED       STEPS
pipeline-7f3a2c1d        contract-reviewer   running   2m ago        2/4
pipeline-3b1e9a08        sentiment-batch     running   45s ago       1/1
```

### `atelium pipeline inspect`

Shows full step tree for a pipeline.

```bash
atelium pipeline inspect pipeline-7f3a2c1d

Pipeline: pipeline-7f3a2c1d
Status:   running
Started:  2026-03-15T14:22:10Z

Step tree:
  ✓ contract-reviewer@1.3.0    SUCCEEDED   8.2s   iter=0
    └─ ● legal-risk-agent@2.1.0  EXECUTING   7s...
```

### `atelium pipeline replay`

Replays a pipeline from a specific step using archived state.

```bash
atelium pipeline replay pipeline-7f3a2c1d --from-step step-4a2b1c3d

Replaying from step: legal-risk-agent (step-4a2b1c3d)
Loaded snapshot from PostgreSQL archive
Starting execution...
```

### `atelium pipeline cancel`

```bash
atelium pipeline cancel pipeline-7f3a2c1d

Cancelling pipeline-7f3a2c1d...
Triggering SAGA-A compensation for 2 committed steps...
  ✓ Compensated: contract-reviewer (delete_review_draft)
  ✓ Compensated: legal-risk-agent (close_risk_assessment)
Pipeline cancelled and compensated.
```

---

## `atelium hitl`

### `atelium hitl list`

Lists pending HITL requests.

```bash
atelium hitl list

ID                    PIPELINE              AGENT               REASON             AGE
hitl-9f2a1b3c         pipeline-7f3a2c1d     contract-reviewer   low_confidence     5m
hitl-2d4e5f6a         pipeline-1a2b3c4d     contract-reviewer   dry_run_review     12m
```

### `atelium hitl inspect`

```bash
atelium hitl inspect hitl-9f2a1b3c

HITL Request: hitl-9f2a1b3c
Pipeline:     pipeline-7f3a2c1d
Agent:        contract-reviewer@1.3.0
Reason:       output.confidence = 0.48 < threshold 0.50
Iteration:    3 of 3 (self-healing exhausted)

Current output:
  jurisdiction: BR
  risk_level:   MEDIUM
  confidence:   0.48
  summary:      "Contract appears to be governed by Brazilian law..."

Options:
  [A] Approve output as-is and continue pipeline
  [E] Edit output fields and continue
  [R] Reject and abort pipeline
```

### `atelium hitl approve`

```bash
atelium hitl approve hitl-9f2a1b3c
# or with edited output:
atelium hitl approve hitl-9f2a1b3c \
  --set output.confidence=0.82 \
  --set output.risk_level=HIGH

HITL approved. Pipeline pipeline-7f3a2c1d resuming...
```

### `atelium hitl reject`

```bash
atelium hitl reject hitl-9f2a1b3c --reason "Incorrect jurisdiction classification"

HITL rejected. Triggering SAGA-A compensation...
  ✓ Compensated: contract-reviewer
Pipeline failed with reason: human_rejection
```

---

## `atelium dev`

Utilities for local development and testing.

### `atelium dev up`

Starts all local infrastructure via Docker Compose.

```bash
atelium dev up [OPTIONS]

Options:
  --profile TEXT   minimal | full [default: minimal]

# minimal: PostgreSQL + Redis + NATS + Ollama
# full:    + Langfuse + Grafana + Prometheus + Keycloak
```

```bash
atelium dev up --profile full

Starting Atelium local stack (full profile)...
  ✓ PostgreSQL    localhost:5432
  ✓ Redis Stack   localhost:6379
  ✓ NATS          localhost:4222
  ✓ Ollama        localhost:11434  (pulling nomic-embed-text...)
  ✓ Langfuse      http://localhost:3000
  ✓ Grafana       http://localhost:3001
  ✓ Prometheus    http://localhost:9090

All services up. Run `atelium dev status` to check health.
```

### `atelium dev down`

```bash
atelium dev down
# stops and removes containers, preserves volumes

atelium dev down --volumes
# also removes all data
```

### `atelium dev status`

```bash
atelium dev status

Service         Status    URL
PostgreSQL      ✓ up      localhost:5432
Redis Stack     ✓ up      localhost:6379
NATS            ✓ up      localhost:4222  (JetStream enabled)
Ollama          ✓ up      localhost:11434 (llama3:70b loaded)
Langfuse        ✓ up      http://localhost:3000
Grafana         ✓ up      http://localhost:3001
Prometheus      ✓ up      http://localhost:9090

Registry:       47 agents registered
Active pipelines: 0
```

### `atelium dev scaffold`

Generates a new agent manifest template.

```bash
atelium dev scaffold AGENT_NAME [OPTIONS]

Options:
  --template TEXT   minimal | full | pipeline [default: minimal]
  --output PATH     Output directory [default: ./manifests]
```

```bash
atelium dev scaffold my-new-agent --template full

Created: manifests/my-new-agent.yaml

Fill in the required fields:
  spec.capabilities   — describe what your agent does
  spec.task.success_criteria — define what "done" looks like
  spec.blast_radius   — declare which systems your agent may access

Then validate: atelium agent validate manifests/my-new-agent.yaml
```

### `atelium dev logs`

Streams runtime logs filtered by pipeline or agent.

```bash
atelium dev logs --pipeline pipeline-7f3a2c1d
atelium dev logs --agent contract-reviewer --follow
```

### `atelium dev mock-hitl`

Auto-approves all HITL requests. For use in automated experiment runs only.

```bash
atelium dev mock-hitl --strategy approve-all
# strategies: approve-all | reject-all | approve-if-confidence-gt-N
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Manifest validation error |
| 3 | Registry error (agent not found, version conflict) |
| 4 | Pipeline execution failed |
| 5 | Pipeline cancelled / compensated |
| 6 | HITL timeout |
| 7 | Infrastructure unreachable |

---

## Global Options

Available on every command:

```
--config PATH     Config file path [default: ~/.atelium/config.yaml]
--api-url TEXT    Override API URL
--output FORMAT   Override default output format
--no-color        Disable colored output
--quiet           Suppress all output except errors
--verbose         Verbose logging (shows HTTP requests, NATS events)
--version         Show CLI version and exit
```

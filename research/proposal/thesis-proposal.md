# Master's Dissertation Proposal

## Title

**Fault-Tolerant Agent Networks: A Layered Resilience Model for Multi-Agent LLM Systems**

---

## 1. Motivation

LLM-based agents execute real-world actions: they send emails, write to databases, create tickets, debit accounts, and publish messages. Unlike traditional code, these actions frequently **cannot be undone**.

Popular frameworks like LangGraph, CrewAI, OpenClaw, and Hermes Agent treat action execution as an atomic primitive — with no distinction between reversible and irreversible actions, no compensation mechanism on failure, and no declared success or transition criteria between agents.

The practical result is twofold: when an agent fails, the system is left in an **inconsistent state with no recovery mechanism**; when an agent produces invalid output but transitions anyway, the failure **propagates silently across the entire downstream network**.

Mature distributed systems solved analogous problems decades ago — TCP/IP with retry and acknowledgment, databases with transactional rollback, Kubernetes with liveness probes and restart policies. None of these principles have been systematically applied to LLM agent networks.

This work proposes that **fault tolerance in agent networks is a systems engineering problem, not a prompt engineering problem** — and that the same resilience principles established in distributed systems can be adapted to produce robust agent networks with minimal dependency on human intervention.

---

## 2. Central Thesis

> **LLM agent networks lack fault tolerance by design. The absence of declared success criteria, self-healing mechanisms, and compensation primitives forces excessive dependency on human intervention and produces irrecoverable inconsistent state. A layered resilience model — Transition Guard → Self-Healing → SAGA-A → HITL — can make agent networks as robust as mature distributed systems.**

---

## 3. Research Problem

**Main Question:**
> How can a layered resilience model — composed of Transition Guards, iterative self-healing, SAGA-A, and selective HITL — make LLM agent networks fault-tolerant, reducing state inconsistency and dependency on human intervention?

**Secondary Questions:**

1. Which categories of actions executed by agents are inherently irreversible, and how can they be classified?
2. Do current multi-agent frameworks offer fault-tolerance primitives? If not, what is the measurable cost of their absence?
3. Do declared success criteria combined with self-healing reduce the ambiguity surface that requires human judgment?
4. Does a layered resilience model produce measurably more robust processes than frameworks without these primitives?
5. In large-scale networks without pre-defined choreography, does probabilistic routing by capability affinity produce viable and auditable emergent composition?
6. What is the behavior of SAGA-A in N:1 topologies with partial failure, and how does the declared aggregation strategy (wait_all, quorum, best_effort) affect the scope of compensation?

---

## 4. Hypotheses

**H1:** Major multi-agent frameworks do not have native compensation or distributed state rollback primitives.

**H2:** It is possible to define an irreversibility taxonomy for agent actions with at least three distinct categories (reversible, compensable, irreversible).

**H3:** The absence of compensating actions produces measurable state inconsistency in multi-agent workflows under induced failure conditions.

**H4:** An extension of the SAGA pattern (SAGA-A) can reduce the state inconsistency rate in agentic workflows without significantly compromising throughput.

**H5:** The absence of declared transition criteria (Transition Guards) is a primary cause of failure propagation in agent networks — incomplete tasks transition to downstream agents that assume unsatisfied preconditions, corrupting the state of all subsequent agents.

**H6:** The explicit declaration of success criteria combined with self-healing loops reduces the need for Human-in-the-Loop (HITL) in direct proportion to criteria coverage — the more complete the task contract, the smaller the ambiguity surface requiring human judgment.

**H7:** In N:1 topologies, the declared aggregation strategy (wait_all, quorum, best_effort) determines the trade-off between output consistency and resilience to partial failures — and the absence of explicit declaration produces undefined behavior measurable as an inconsistency rate.

**H8:** Coupling memory to the step rather than the agent — making agents stateless — is a necessary condition for viable emergent routing: dynamically discovered agents can only process tasks coherently if the step carries all required context.

---

## 4.1 Layered Resilience Model (Central Contribution)

The proposed model operates on four progressive levels. Each level is only activated if the previous one failed to resolve the failure:

```
LEVEL 1 — Self-Healing (local, automatic)
  Agent detects invalid output against success_criteria
  Iterates with error feedback as additional context
  Resolves: technical failures and low ambiguity
  Analogous to: gradient descent, retry with backoff

LEVEL 2 — Transition Guard (boundary, automatic)
  Blocks transition if output does not satisfy transition_guard
  Triggers SAGA-A if max_iterations exhausted
  Resolves: prevents downstream propagation of invalid output
  Analogous to: TCP acknowledgment, Git conflict detection

LEVEL 3 — SAGA-A (compensation, automatic)
  Executes compensating_actions in reverse order
  Restores distributed state consistency
  Resolves: side effects already executed upstream
  Analogous to: transactional rollback in ACID databases

LEVEL 4 — HITL (arbitration, human)
  Triggered only for genuine domain ambiguity
  or actions marked irreversible with high impact
  Resolves: what no declared criterion can cover
  Analogous to: escalation to SRE specialist
```

**Emergent property:** The process does not stop on failure — it **degrades gracefully**, containing damage at the lowest possible level before involving a human.

| Comparison | Without the model | With the model |
|---|---|---|
| Technical failure | Immediate HITL | Self-healing resolves |
| Propagated invalid output | Corrupts downstream | Blocked at the guard |
| Inconsistent state | Irrecoverable | SAGA-A compensates |
| HITL | Quality checker | Ambiguity arbiter |

---

## 5. Irreversibility Taxonomy

| Category | Definition | Examples | Strategy |
|---|---|---|---|
| **Reversible** | Action can be fully undone | Saved draft, uncommitted DB record | Direct rollback |
| **Compensable** | Action cannot be undone but effect can be offset | Ticket created → close ticket; CRM written → delete record | Compensating action |
| **Irreversible** | Neither reversal nor compensation is possible | Email sent, Slack posted, payment executed | Dry-run gate + human approval before execution |

This taxonomy is an original contribution — it does not exist in the MAS or LLM agents literature.

---

## 6. Theoretical Foundation: Agent Networks as a Neural Network Analogy

### 6.1 The Structural Analogy

Artificial neural networks emerged from the chaining of simple units — individual neurons with limited computational capacity whose **intelligence emerges from composition**, not from the isolated element. Multi-agent systems follow the same principle: specialized, limited agents produce emergent behavior when chained.

The analogy, however, reveals a critical asymmetry:

> *Neural networks have a retroactive correction mechanism (backpropagation). Agent networks have no equivalent — every action executed in the real world is potentially irreversible.*

```
Neural network:  forward pass → measured error → backward pass → weight correction
Agent network:   forward pass → world action  → error → irrecoverable inconsistent state
```

SAGA-A, proposed in this work, is a primitive form of "backward pass" for agents — it does not correct the reasoning, but **undoes the real-world side effects**.

### 6.2 Chaining Topologies

The chaining topology determines the emergent properties of the system — and the failure patterns:

| Neural Topology | Agentic Topology | Property | Failure Pattern |
|---|---|---|---|
| Sequential (feedforward) | Linear pipeline A→B→C | Predictable, auditable | Failure propagates forward irreversibly |
| Parallel | Fan-out A→B, A→C | Throughput, redundancy | Divergent results without reconciliation |
| Recurrent | Feedback loop A→B→A | Memory, iteration | Infinite loops, error amplification |
| Residual (skip connection) | Conditional bypass | Node failure resilience | Analogous to Circuit Breaker pattern |

The **residual** topology is especially relevant: ResNet's skip connections — which allow the gradient to "skip" problematic layers — have a direct correspondence with the Circuit Breaker pattern in agents, where a failing agent can be bypassed without interrupting the pipeline.

### 6.3 Emergence and Composition

In deep neural networks, early layers detect simple patterns (edges, textures) and subsequent layers compose complex representations (faces, objects). The same principle of **hierarchical composition** appears in agent networks:

```
Layer 1 (specialized agents):
  Extractor → Classifier → Summarizer

Layer 2 (composition agents):
  Reviewer → Validator → Approver

Layer 3 (orchestration agents):
  Supervisor → Router → Notifier
```

The fundamental difference: in neural networks, composition is **differentiable and correctable**. In agent networks, each layer can produce **irreversible side effects** before an error in the next layer is detected.

This is the formal motivation for the central problem of this dissertation.

---

## 7. Methodology

### 7.1 Framework Analysis (Study 1)

**Objective:** Empirically verify H1.

**Method:**
- Static analysis of LangGraph, CrewAI, AutoGen source code
- Analysis protocol: presence of (a) compensating actions, (b) state rollback, (c) reversible/irreversible distinction, (d) dry-run mode
- Expected result: capability matrix per framework

**Artifact:** Comparative table publishable as part of the state-of-the-art review.

### 7.2 Induced Failure Experiments (Study 2)

**Objective:** Verify H3 — measure the cost of absent compensation.

**Setup:**
- Multi-agent workflow with 4 agents in sequence
- Failure injected at distinct positions (agents 2, 3, 4)
- Metrics: state inconsistency rate, detection time, manual recovery time

**Baseline:** frameworks without SAGA-A
**Treatment:** same workflow with SAGA-A implemented

### 7.3 SAGA-A Implementation (Artifact)

Extension of the SAGA pattern with three new primitives:

```
1. irreversibility_class: reversible | compensable | irreversible
2. compensating_action: declared in the agent manifest
3. dry_run_gate: mandatory simulated execution before irreversible actions
```

OSS reference implementation integrated into the Agent Manifest.

### 7.4 Validation (Study 3)

**Objective:** Verify H4 — SAGA-A reduces inconsistency without prohibitive cost.

**Method:** Controlled experiment comparing workflows with and without SAGA-A.

**Metrics:**
- State inconsistency rate after failure
- Additional latency introduced by compensating actions
- Failure scenario coverage (% of failures detected and compensated)

---

## 8. Original Contributions

1. **Layered Resilience Model** — composition of Transition Guard, Self-Healing, SAGA-A, and HITL as a fault-tolerance system for agent networks
2. **Irreversibility Taxonomy** — first formalization of agent action categories (reversible, compensable, irreversible)
3. **Transition Guard with Self-Healing** — declarative contract primitive with iterative correction loop before escalation
4. **SAGA-A** — extension of the SAGA pattern for agentic workflows with non-determinism, irreversible actions, and N:1 topologies
5. **Emergent Routing** — third composition mode beyond orchestration and choreography: probabilistic routing by capability affinity in large-scale networks
6. **Network Topologies (1:N, N:1)** — delegation and aggregation patterns with declared partial failure tolerance strategies
7. **Step-Coupled Memory** — separation of stateless agent and stateful step as a condition for emergent routing and native replay
8. **Empirical framework analysis** — evidence that current frameworks lack native fault tolerance
9. **Agent Manifest** — declarative OSS specification that unifies all proposed primitives

---

## 9. Dissertation Structure

```
Ch. 1 — Introduction
  Motivation, problem, thesis, contributions, structure

Ch. 2 — Theoretical Foundation
  2.1 LLM agents: definition, capabilities, limitations
  2.2 Fault tolerance in distributed systems: SAGA, retry, circuit breaker, idempotency
  2.3 Multi-Agent Systems: classical MAS vs. LLM agents
  2.4 Agent networks as neural network analogy: composition, emergence, and absence of backpropagation

Ch. 3 — Systematic Literature Review
  State of the art in multi-agent frameworks — fault-tolerance primitive analysis

Ch. 4 — Irreversibility Taxonomy (contribution 1)
  Formal definition of categories, classification criteria

Ch. 5 — Framework Analysis (contribution 2)
  Methodology, results, comparative matrix

Ch. 6 — SAGA-A: Extension for Agents (contribution 3)
  Formal specification, Agent Manifest, use cases

Ch. 7 — Atelium: Reference Platform (contribution 4)
  OSS implementation, architecture, experiment execution

Ch. 8 — Experiments and Results (contributions 5–9)
  Setup, execution, analysis, threats to validity

Ch. 9 — Discussion
  Implications, limitations, future work

Ch. 10 — Conclusion
```

---

## 10. Timeline

| Phase | Activity | Duration |
|---|---|---|
| 1 | Systematic literature review | 2 months |
| 2 | Framework analysis (Study 1) | 1 month |
| 3 | Irreversibility taxonomy | 1 month |
| 4 | SAGA-A specification + Agent Manifest | 2 months |
| 5 | OSS reference implementation | 2 months |
| 6 | Experiments (Studies 2 and 3) | 2 months |
| 7 | Writing, review, defense | 2 months |
| **Total** | | **~12 months** |

---

## 11. Publication Venues

**Primary targets:**
- ICSE 2027 — International Conference on Software Engineering
- FSE 2027 — Foundations of Software Engineering

**Alternatives:**
- ICSOC — Service-Oriented Computing
- Journal of Systems and Software (Elsevier)

**Intermediate paper (Ch. 5 standalone):**
- MSR — Mining Software Repositories (OSS framework analysis)

---

## 12. Initial References

- Garcia-Molina, H., & Salem, K. (1987). Sagas. *ACM SIGMOD Record*, 16(3), 249–259.
- Richardson, C. (2018). *Microservices Patterns*. Manning. Ch. 4.
- Yao, S. et al. (2022). ReAct: Synergizing Reasoning and Acting in Language Models. *arXiv:2210.03629*.
- Wooldridge, M., & Jennings, N. (1995). Intelligent agents: Theory and practice. *Knowledge Engineering Review*, 10(2).
- Chase, N. et al. (2024). Model Context Protocol Specification. Anthropic / Linux Foundation.
- OpenClaw Community (2025). OpenClaw Architecture Specification. GitHub.
- Nous Research (2026). Hermes Agent: Closed-Loop Learning for Agentic Workflows.
- Microsoft (2026). Agent 365: The Control Plane for AI Agents.
- Hevner, A. et al. (2004). Design Science in Information Systems Research. *MIS Quarterly*, 28(1).
- OWASP (2024). LLM Top 10 for Large Language Model Applications.
- Wohlin, C. et al. (2012). *Experimentation in Software Engineering*. Springer.

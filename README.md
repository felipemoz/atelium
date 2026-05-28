# Atelium — Thesis Research

**Working title:** Fault-Tolerant Agent Networks: A Layered Resilience Model for Multi-Agent LLM Systems

**Level:** Academic Master's Degree

**Field:** AI Engineering / Distributed Systems

---

## Problem

The proliferation of LLM agents in enterprise environments lacks standardized infrastructure for governance, discovery, composition, and distributed transactions. Frameworks like LangGraph and CrewAI solve the problem of building individual agents, but not the problem of operating a fleet of agents with consistency guarantees, permission controls, and auditability.

## Central Hypothesis

Established distributed systems patterns — specifically Service Registry, SAGA, Choreography/Orchestration, and Event Sourcing — can be formalized and adapted for LLM-based multi-agent systems, resulting in a reference architecture that is both implementable and empirically validatable.

## Central Thesis

> LLM agent networks lack fault tolerance by design. A layered resilience model — Transition Guard → Self-Healing → SAGA-A → HITL — combined with emergent routing and step-coupled memory, can make agent networks as robust as mature distributed systems.

## Hypotheses

| # | Hypothesis |
|---|---|
| H1 | Current frameworks lack native compensation or rollback primitives |
| H2 | Agent actions can be classified into: reversible, compensable, irreversible |
| H3 | Absence of compensating actions produces measurable state inconsistency |
| H4 | SAGA-A reduces inconsistency without significantly compromising throughput |
| H5 | Absence of Transition Guards is the primary cause of failure propagation in agent networks |
| H6 | Declared success criteria + self-healing reduce HITL proportionally |
| H7 | Aggregation strategy in N:1 topologies determines consistency vs. resilience trade-off |
| H8 | Stateless agents with Step-Coupled Memory are a necessary condition for Emergent Routing |

## Contributions

1. **Layered Resilience Model** — Transition Guard + Self-Healing + SAGA-A + HITL
2. **Irreversibility Taxonomy** — reversible / compensable / irreversible
3. **Transition Guard with Self-Healing** — declarative contract with iterative correction loop
4. **SAGA-A** — SAGA extended for non-determinism and N:1 topologies
5. **Emergent Routing** — third composition mode: probabilistic routing by capability affinity
6. **Network Topologies (1:N, N:1)** — delegation and aggregation with partial failure tolerance
7. **Step-Coupled Memory** — stateless agent, stateful step — necessary condition for emergent routing
8. **Empirical framework analysis** — comparative matrix of fault-tolerance primitives
9. **Agent Manifest** — declarative OSS specification unifying all proposed primitives

---

## Repository Structure

```
proposal/       Formal thesis proposal and dissertation chapters
patterns/       Architectural pattern catalog (11 patterns)
literature/     Systematic literature review
architecture/   Technical diagrams and specifications
experiments/    Experiment protocols and results
references/     BibTeX and bibliographic annotations
papers/         Academic paper drafts
```

---

## Current Landscape (May 2026)

| Solution | Type | Focus | Gap |
|---|---|---|---|
| Microsoft Agent 365 | Proprietary, $15/user/month | Enterprise control plane | Vendor lock-in, no OSS |
| LangGraph | OSS | Stateful agent DAG runtime | No registry or governance |
| CrewAI | OSS | Multi-agent collaboration | No fault-tolerance primitives |
| LangSmith | SaaS | Observability and traces | No catalog or permissions |
| N8N | OSS | Visual DAG workflow engine | No agent-native node |

**Identified gap:** No OSS solution delivers a complete control plane — registry, permissions, SAGA, shared RAG, and A2A choreography as a unified platform.

---

## Theoretical Connections

- **Microservices patterns** → adapted for agents (Fowler, Newman)
- **SAGA pattern** (Garcia-Molina & Salem, 1987) → transactions in agentic workflows
- **Event-driven architecture** → A2A choreography via MCP/ACP protocol
- **Service mesh** (Istio) → analogy for Agent Fabric
- **Backstage (Spotify)** → analogy for Agent Portal

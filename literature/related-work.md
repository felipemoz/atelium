# Related Work — Initial Map

## 1. Distributed Systems (Theoretical Foundation)

### SAGA Pattern
- **Garcia-Molina & Salem (1987)** — original SAGA paper for long-lived transactions
- **Richardson, C. (2018)** — Microservices Patterns (Ch. 4: Managing transactions with sagas) — modern adaptation
- **Relevance:** Direct foundation for SAGA-A (adaptation for agents)

### Event-Driven Architecture
- **Hohpe & Woolf (2003)** — Enterprise Integration Patterns — messaging pattern catalog
- **Kleppmann, M. (2017)** — Designing Data-Intensive Applications — event sourcing and CQRS
- **Relevance:** Foundation for A2A choreography via NATS

### Service Registry & Discovery
- **Zookeeper (Hunt et al., 2010)** — distributed coordination system
- **Consul (HashiCorp, 2014)** — service discovery and health checking
- **Backstage (Spotify/CNCF, 2020)** — developer portal and service catalog
- **Relevance:** Direct analogy for Agent Registry

---

## 2. Classical Multi-Agent Systems (MAS)

### Foundations
- **Wooldridge & Jennings (1995)** — "Intelligent agents: Theory and practice" — formal agent definition
- **Russell & Norvig (2020)** — AIMA Ch. 2 — rational agents and environments
- **FIPA Specifications (2002)** — inter-agent communication protocols (ACL, KQML)
- **Relevance:** Conceptual foundation, but classical MAS does not cover LLMs

### Gap with LLM Agents
- Classical MAS assumes deterministic, symbolic agent behavior
- LLM agents introduce: non-determinism, emergent reasoning, variable cost, unpredictable latency
- This work addresses that gap

---

## 3. LLM Agents & Frameworks (State of the Art)

### Agent Frameworks
- **ReAct (Yao et al., 2022)** — reasoning + acting in LLM agents
- **LangGraph (LangChain, 2024)** — stateful DAG for agents
- **CrewAI (2024)** — multi-agent collaboration
- **AutoGen (Microsoft, 2023)** — multi-agent conversation framework
- **OpenClaw (2025)** — autonomous agents with self-upgrade
- **Hermes Agent (Nous Research, 2026)** — closed-loop learning

### Observability
- **LangSmith (2024)** — tracing for LLM applications
- **Arize Phoenix (2024)** — observability for LLM and agents
- **OpenTelemetry for LLMs (2025)** — OTel extensions for LLM traces

---

## 4. AI Engineering & Governance

### AI Engineering (Emerging Field)
- **Sculley et al. (2015)** — "Hidden Technical Debt in Machine Learning Systems" — MLOps foundational paper
- **Amershi et al. (2019)** — "Software engineering for machine learning" (Microsoft)
- **Shankar et al. (2024)** — "Who Validates the Validators?" — quality assurance for LLM outputs

### Agent Governance
- **Microsoft Agent 365 (2026)** — proprietary control plane (comparison baseline)
- **OWASP LLM Top 10 (2024)** — vulnerabilities in LLM applications
- **NIST AI RMF (2023)** — AI risk management framework

---

## 5. Relevant Protocols

| Protocol | Creator | Focus | Status |
|---|---|---|---|
| MCP (Model Context Protocol) | Anthropic / Linux Fdn | Agent-to-tool | De facto standard (2026) |
| A2A (Agent-to-Agent) | Google | Inter-agent communication | Open, growing adoption |
| ACP (Agent Communication Protocol) | OpenClaw | Decentralized agents | Emerging |
| FIPA-ACL | FIPA (1997) | Classical MAS | Legacy, historical reference |

---

## 6. Identified Gaps in the Literature

| Gap | Nearest prior work | What is missing |
|---|---|---|
| SAGA for LLM agents | Richardson 2018 (microservices) | Adaptation for non-determinism and irreversibility |
| Agent registry with ACL | Consul/Backstage (services) | Agent-native with MCP scopes and RAG namespaces |
| Shared multi-agent RAG | Generic RAG surveys | Per-agent permissions, versioning, attribution |
| Choreography vs. orchestration in LLMs | AutoGen (conversation) | Empirical analysis with distributed systems metrics |
| Agent Manifest as contract | Kubernetes YAML (services) | Agent semantics: mcps, knowledge, a2a, saga |

---

## 7. Next Steps in the Review

- [ ] Systematic search in ACM DL: "multi-agent" AND "governance" (2022–2026)
- [ ] arXiv cs.SE search: "agentic" AND "distributed" (2024–2026)
- [ ] Map citations of ReAct and AutoGen to find work on composition
- [ ] Check ICSE 2025–2026 proceedings for AI Engineering papers
- [ ] Contact OpenClaw and Hermes authors for access to internal specs

# Literatura Relacionada — Mapa Inicial

## 1. Sistemas Distribuídos (base teórica)

### SAGA Pattern
- **Garcia-Molina & Salem (1987)** — paper original do padrão SAGA para long-lived transactions
- **Richardson, C. (2018)** — Microservices Patterns (Cap. 4: Managing transactions with sagas) — adaptação moderna do padrão
- **Relevância:** Base direta para SAGA-A (adaptação para agentes)

### Event-Driven Architecture
- **Hohpe & Woolf (2003)** — Enterprise Integration Patterns — catálogo de padrões de mensageria
- **Kleppmann, M. (2017)** — Designing Data-Intensive Applications — event sourcing e CQRS
- **Relevância:** Base para coreografia A2A via NATS/Kafka

### Service Registry & Discovery
- **Zookeeper (Hunt et al., 2010)** — sistema de coordenação distribuída
- **Consul (HashiCorp, 2014)** — service discovery e health checking
- **Backstage (Spotify/CNCF, 2020)** — developer portal e service catalog
- **Relevância:** Analogia direta para Agent Registry

---

## 2. Multi-Agent Systems (MAS) Clássico

### Fundamentos
- **Wooldridge & Jennings (1995)** — "Intelligent agents: Theory and practice" — definição formal de agente
- **Russell & Norvig (2020)** — AIMA Cap. 2 — agentes racionais e ambientes
- **FIPA Specifications (2002)** — protocolos de comunicação entre agentes (ACL, KQML)
- **Relevância:** Base conceitual, mas MAS clássico não cobre LLMs

### Gap com LLM Agents
- MAS clássico assume agentes com comportamento determinístico e simbólico
- Agentes LLM introduzem: não-determinismo, raciocínio emergente, custo variável, latência imprevisível
- Este trabalho endereça esse gap

---

## 3. LLM Agents & Frameworks (estado da arte)

### Frameworks de Agentes
- **ReAct (Yao et al., 2022)** — reasoning + acting em agentes LLM
- **LangGraph (LangChain, 2024)** — DAG stateful para agentes
- **CrewAI (2024)** — multi-agent collaboration
- **AutoGen (Microsoft, 2023)** — framework de conversação multi-agente
- **OpenClaw (2025)** — agentes autônomos com self-upgrade
- **Hermes Agent (Nous Research, 2026)** — closed-loop learning

### Observabilidade
- **LangSmith (2024)** — tracing para LLM applications
- **Arize Phoenix (2024)** — observabilidade para LLM e agentes
- **OpenTelemetry for LLMs (2025)** — extensões de OTel para LLM traces

---

## 4. AI Engineering & Governance

### AI Engineering (campo emergente)
- **Sculley et al. (2015)** — "Hidden Technical Debt in Machine Learning Systems" — paper fundacional de MLOps
- **Amershi et al. (2019)** — "Software engineering for machine learning" (Microsoft)
- **Shankar et al. (2024)** — "Who Validates the Validators?" — quality assurance para LLM outputs

### Agent Governance
- **Microsoft Agent 365 (2026)** — control plane proprietário (ponto de comparação)
- **OWASP LLM Top 10 (2024)** — vulnerabilidades em aplicações LLM
- **NIST AI RMF (2023)** — framework de gestão de riscos para IA

---

## 5. Protocolos Relevantes

| Protocolo | Criador | Foco | Status |
|---|---|---|---|
| MCP (Model Context Protocol) | Anthropic / Linux Fdn | Agent-to-tool | Padrão de fato (2026) |
| A2A (Agent-to-Agent) | Google | Inter-agent communication | Aberto, adoção crescente |
| ACP (Agent Communication Protocol) | OpenClaw | Decentralized agents | Emergente |
| FIPA-ACL | FIPA (1997) | MAS clássico | Legado, referência histórica |

---

## 6. Gaps Identificados na Literatura

| Gap | Último trabalho próximo | O que falta |
|---|---|---|
| SAGA para agentes LLM | Richardson 2018 (microserviços) | Adaptação para não-determinismo e irreversibilidade |
| Registry de agentes com ACL | Consul/Backstage (serviços) | Agent-native com MCP scopes e RAG namespaces |
| RAG compartilhado multi-agente | RAG surveys genéricos | Permissões por agente, versionamento, attribution |
| Choreography vs. orchestration em LLMs | AutoGen (conversação) | Análise empírica com métricas de sistemas distribuídos |
| Agent Manifest como contrato | Kubernetes YAML (serviços) | Semântica de agente: mcps, knowledge, a2a, saga |

---

## 7. Próximos Passos na Revisão

- [ ] Busca sistemática no ACM DL: "multi-agent" AND "governance" (2022-2026)
- [ ] Busca no arXiv cs.SE: "agentic" AND "distributed" (2024-2026)
- [ ] Mapear citações de ReAct e AutoGen para encontrar trabalhos sobre composição
- [ ] Verificar proceedings ICSE 2025-2026 para papers de AI Engineering
- [ ] Contatar autores de OpenClaw e Hermes para acesso a specs internas

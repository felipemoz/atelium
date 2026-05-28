# Atelium — Thesis Research

**Título provisório:** Distributed Systems Patterns for Multi-Agent AI Orchestration: A Registry-Based Governance Architecture

**Nível:** Mestrado Acadêmico

**Campo:** AI Engineering / Distributed Systems

---

## Problema

A proliferação de agentes LLM em ambientes corporativos carece de infraestrutura padronizada para governança, descoberta, composição e transações distribuídas. Frameworks como OpenClaw e Hermes resolvem a construção de agentes individuais, mas não o problema de operar uma frota de agentes com garantias de consistência, permissões e rastreabilidade.

## Hipótese Central

Padrões consolidados de sistemas distribuídos — especificamente Service Registry, SAGA, Choreography/Orchestration e Event Sourcing — podem ser formalizados e adaptados para sistemas multi-agente baseados em LLM, resultando em uma arquitetura de referência implementável e validável empiricamente.

## Tese Central

> Redes de agentes LLM carecem de tolerância a falhas por design. Um modelo de resiliência em camadas — Transition Guard → Self-Healing → SAGA-A → HITL — combinado com roteamento emergente e memória acoplada ao step, pode tornar redes de agentes tão robustas quanto sistemas distribuídos maduros.

## Hipóteses

| # | Hipótese |
|---|---|
| H1 | Frameworks atuais não possuem primitivas de compensação ou rollback |
| H2 | Ações de agentes classificam-se em: reversível, compensável, irreversível |
| H3 | Ausência de compensating actions produz inconsistência mensurável |
| H4 | SAGA-A reduz inconsistência sem comprometer throughput |
| H5 | Ausência de Transition Guards é causa primária de propagação de falha |
| H6 | Critérios declarados + self-healing reduzem HITL proporcionalmente |
| H7 | Estratégia de agregação em N:1 determina consistência vs. resiliência |
| H8 | Agentes stateless com Step-Coupled Memory são condição para Emergent Routing |

## Contribuições

1. **Modelo de Resiliência em Camadas** — Transition Guard + Self-Healing + SAGA-A + HITL
2. **Taxonomia de irreversibilidade** — reversível / compensável / irreversível
3. **Transition Guard com Self-Healing** — contrato declarativo com loop de correção
4. **SAGA-A** — SAGA estendido para não-determinismo e topologias N:1
5. **Emergent Routing** — terceiro modo de composição: roteamento probabilístico por afinidade
6. **Network Topologies (1:N, N:1)** — delegação e agregação com tolerância a falha parcial
7. **Step-Coupled Memory** — agente stateless, step stateful — condição para roteamento emergente
8. **Análise empírica de frameworks** — matriz comparativa de primitivas de tolerância a falhas
9. **Agent Manifest** — especificação declarativa OSS unificando todas as primitivas

---

## Estrutura do Repositório

```
proposal/       Proposta formal da tese
patterns/       Catálogo de padrões arquiteturais
literature/     Revisão sistemática de literatura
architecture/   Diagramas e especificações técnicas
experiments/    Protocolos e resultados de experimentos
references/     BibTeX e anotações bibliográficas
```

---

## Landscape Atual (maio/2026)

| Solução | Tipo | Foco | Gap |
|---|---|---|---|
| Microsoft Agent 365 | Proprietário, $15/user/mês | Control plane enterprise | Vendor lock-in, sem OSS |
| OpenClaw | OSS (345k stars) | Runtime de agentes autônomos | Sem registry ou governance |
| Hermes Agent | OSS (Nous Research) | Learning loop por workflow | Sem composição multi-agente |
| LangSmith | SaaS | Observabilidade e traces | Sem catálogo ou permissões |
| N8N | OSS | DAG visual (workflow engine) | Sem agent-native node |

**Gap identificado:** Nenhuma solução OSS entrega control plane completo — registry, permissões, SAGA, RAG compartilhado e coreografia A2A como plataforma unificada.

---

## Conexões Teóricas

- **Microservices patterns** → adaptados para agentes (Fowler, Newman)
- **SAGA pattern** (Garcia-Molina & Salem, 1987) → transações em workflows agenticos
- **Event-driven architecture** → coreografia A2A via protocolo MCP/ACP
- **Service mesh** (Istio) → analogia para Agent Fabric
- **Backstage (Spotify)** → analogia para Agent Portal

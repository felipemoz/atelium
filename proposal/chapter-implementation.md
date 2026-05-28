# Capítulo 6 — Atelium: Plataforma de Referência para Redes de Agentes Tolerantes a Falhas

## 6.1 Motivação

Os capítulos anteriores formalizaram os padrões arquiteturais, estabeleceram as hipóteses e descreveram os experimentos que as validam. Este capítulo descreve **Atelium** — a implementação de referência OSS que serve simultaneamente como:

1. **Artefato de validação** — plataforma onde os experimentos dos Estudos 1, 2 e 3 são executados
2. **Prova de viabilidade** — demonstra que os padrões propostos são implementáveis com tecnologia disponível
3. **Contribuição à comunidade** — plataforma reutilizável por pesquisadores e praticantes

Seguindo a metodologia Design Science Research [Hevner et al., 2004], o artefato não é apenas um subproduto da pesquisa — ele é uma contribuição em si, avaliada por critérios de utilidade, completude e generalidade.

---

## 6.2 Visão Geral da Plataforma

Atelium é um **Identity Platform (IdP) para agentes** — análogo ao que o Backstage faz para serviços de software, mas com primitivas nativas para as propriedades únicas de agentes LLM: não-determinismo, ações irreversíveis, roteamento dinâmico e estado distribuído.

```
┌─────────────────────────────────────────────────────────┐
│                    AI STAGE PLATFORM                     │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Agent Portal │  │ Registry API │  │  CLI (atelium)│  │
│  │ (catálogo,   │  │ (CRUD,       │  │  scaffold,    │  │
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

## 6.3 O Agente como Entidade de Primeira Classe

A diferença central entre Atelium e plataformas existentes (LangSmith, Microsoft Agent 365) é que o agente é uma **entidade com identidade própria**, não apenas um processo efêmero.

Cada agente registrado na plataforma tem:

| Propriedade | Descrição | Análogo em software tradicional |
|---|---|---|
| **Identidade** | UUID + nome + versão semântica | Container image tag |
| **Owner** | Time/pessoa responsável | CODEOWNERS |
| **Capabilities** | Vetor semântico de capacidades | API contract |
| **MCP Scopes** | Ferramentas autorizadas | IAM policy |
| **Knowledge ACL** | Namespaces de RAG acessíveis | Database permissions |
| **Task Contract** | Success criteria + transition guard | SLO definition |
| **SAGA Config** | Compensating actions por ação | Rollback script |
| **Blast Radius** | Sistemas máximos impactáveis | Network policy |
| **Lineage** | Histórico de versões e deploys | Git history |

---

## 6.4 Agent Manifest — Especificação Completa

O Agent Manifest é o contrato declarativo que todo agente registrado na plataforma deve fornecer. É o artefato central que conecta todos os padrões propostos.

```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: contract-reviewer
  owner: legal-team@company.com
  version: 1.3.0
  tags: [legal, contracts, BR, compliance]

spec:
  # --- Modelo LLM (apenas OSS) ---
  model:
    provider: ollama
    name: llama3:70b
    temperature: 0.1          # baixa para tarefas de classificação
    max_tokens: 4096

  # --- Capacidades (base do Emergent Routing) ---
  capabilities:
    - "contract review and classification"
    - "jurisdiction analysis Brazil"
    - "LGPD compliance verification"
    - "legal risk identification"
  accepts:
    input_types: [contract_document, legal_text]
    required_fields: [document_text, document_type]

  # --- Conectores MCP (princípio do menor privilégio) ---
  mcps:
    - name: jira
      version: "^2.1"
      scopes: [read:issues, write:comments]
    - name: confluence
      version: "^3.0"
      scopes: [read:pages]

  # --- Knowledge namespaces (RAG compartilhado) ---
  knowledge:
    namespaces:
      - name: legal-contracts-br
        access: read-only
      - name: lgpd-compliance
        access: read-only

  # --- Contrato de tarefa (Transition Guard) ---
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
        Sua resposta anterior não satisfez os critérios:
        {validation_errors}
        Tente novamente considerando: {success_criteria}

    transition_to: legal-risk-agent
    transition_guard: >
      output.jurisdiction != null
      AND output.confidence >= 0.75
      AND output.risk_level != null

  # --- SAGA-A (tolerância a falhas) ---
  saga:
    compensating_action: delete_review_draft
    irreversible_actions:
      - name: send_legal_notification
        requires: pre_confirmation
        dry_run: true
    snapshot_before: [write_to_crm, create_jira_ticket]

  # --- Topologia (1:N e N:1) ---
  topology:
    delegation:
      mode: route_best            # 1:1 por padrão
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

  # --- Observabilidade ---
  observability:
    traces: true
    cost_tracking: true
    pii_masking: true
    log_step_memory: true         # persiste step para replay
```

---

## 6.5 Como os Experimentos Usam a Plataforma

### Experimento E1 — Análise de Frameworks (Paper 1)

Atelium não é usado para executar LangGraph/CrewAI/AutoGen — ele fornece o **protocolo de avaliação FTEP** como ferramenta CLI:

```bash
atelium eval --framework langgraph --ftep-dimensions all \
             --pipeline canonical-4agent \
             --inject-failure position=2,3,4 \
             --runs 30 \
             --output results/e1-langgraph.json
```

O CLI executa cada framework no pipeline canônico, injeta falhas, mede consistência de estado e gera a matriz comparativa. Isso resolve o problema de inter-rater reliability: a avaliação é automatizada e reproduzível.

### Experimento E2 — Falha Induzida sem vs. com SAGA-A (Paper 1)

```bash
# Baseline: pipeline sem SAGA-A
atelium run --manifest examples/contract-pipeline.yaml \
            --saga-a disabled \
            --inject-failure position=3 \
            --runs 50

# Tratamento: pipeline com SAGA-A
atelium run --manifest examples/contract-pipeline.yaml \
            --saga-a enabled \
            --inject-failure position=3 \
            --runs 50
```

Métricas coletadas automaticamente: state consistency score, tempo de detecção, ações compensadas.

### Experimento E3 — Transition Guard com Self-Healing (Paper 1, H5+H6)

```bash
atelium run --manifest examples/contract-pipeline.yaml \
            --transition-guard disabled \
            --inject-incomplete-output agent=classifier \
            --runs 50

atelium run --manifest examples/contract-pipeline.yaml \
            --transition-guard enabled \
            --self-healing enabled \
            --inject-incomplete-output agent=classifier \
            --runs 50
```

Mede: taxa de propagação downstream de output inválido, número de HITL escalations, taxa de auto-resolução via self-healing.

### Experimento E4 — Emergent Routing (Paper 2)

```bash
# Popula o registry com 47 agentes especializados
atelium registry seed --agents examples/agent-registry-47.yaml

# Executa benchmark de routing
atelium benchmark routing \
  --tasks benchmark/200-tasks.json \
  --methods random,round-robin,emergent,oracle \
  --affinity-weights alpha=0.50,beta=0.30,gamma=0.10,delta=0.10 \
  --runs 5 \
  --output results/e4-routing.json
```

### Experimento E5 — SRS Necessity (Paper 2, Teorema 1)

```bash
# Injeta re-routing dinâmico (40 eventos)
atelium benchmark srs-necessity \
  --rerouting-events 40 \
  --memory-mode agent-stateful \
  --runs 20

atelium benchmark srs-necessity \
  --rerouting-events 40 \
  --memory-mode step-resident \
  --runs 20
```

Mede: context completeness após re-routing (esperado: 0.38 vs. 1.00).

---

## 6.6 Stack Técnico OSS

Todos os componentes respeitam o princípio OSS declarado no documento [OSS-PRINCIPLES.md]:

| Camada | Componente | Licença | Justificativa |
|---|---|---|---|
| Registry + Routing | Qdrant (HNSW) | Apache 2.0 | ANN sub-linear, OSS, self-hostável |
| Event Bus (A2A) | NATS JetStream | Apache 2.0 | Baixa latência, persistência, OSS |
| Step Store | PostgreSQL + pgvector | PostgreSQL License | Step log + embedding sem infra extra |
| LLM Runtime | Ollama + Llama 3 70B | MIT + Meta License | OSS, local, sem API key |
| Observability | Langfuse + OpenTelemetry | MIT + Apache 2.0 | Tracing nativo de LLM, OSS |
| Auth/Permissions | OpenFGA | Apache 2.0 | Controle relacional, OSS da Okta |
| Workflow (DAG) | N8N | Fair-code | Composição visual, self-hostável |
| API Gateway | FastAPI | MIT | Python nativo, rápido de iterar |

---

## 6.7 Arquitetura de Implantação

A plataforma pode ser implantada em três configurações para cobrir diferentes cenários de pesquisa e produção:

**Modo 1 — Local (laptop, experimentos)**
```
Docker Compose: Qdrant + NATS + PostgreSQL + Ollama + Langfuse
Tempo de setup: ~10 minutos
Requisitos: 16GB RAM, GPU opcional
```

**Modo 2 — Cluster (experimentos de escala)**
```
Kubernetes + Helm charts fornecidos
Registry: até 10k agentes testado
Step store: sharding automático via PostgreSQL
```

**Modo 3 — Produção (validação com praticantes)**
```
HA: Qdrant cluster, NATS cluster, PostgreSQL replication
Monitoring: Grafana + Prometheus + Langfuse
Auth: OpenFGA + Keycloak
```

---

## 6.8 Critérios de Avaliação do Artefato (DSR)

Seguindo Hevner et al. [2004], o artefato é avaliado em três dimensões:

| Critério | Métrica | Alvo |
|---|---|---|
| **Utilidade** | Taxa de adoção por praticantes (survey pós-experimento) | ≥ 70% considerariam usar em produção |
| **Completude** | Cobertura dos padrões implementados vs. propostos | 100% dos 11 padrões com implementação de referência |
| **Generalidade** | Funciona com LangGraph, CrewAI, AutoGen sem modificação | 3/3 frameworks integrados |
| **Eficiência** | Overhead de routing vs. chamada direta | ≤ 15ms p95 para registry query |
| **Reprodutibilidade** | Experimentos reproduzíveis por terceiros | Todos os 5 experimentos com seed fixo |

---

## 6.9 Roadmap de Desenvolvimento da Pesquisa

O desenvolvimento do artefato segue os marcos da dissertação:

```
Mês 1-2:   atelium CLI + Agent Manifest parser + Registry básico
Mês 3:     Transition Guard Engine + Self-Healing Loop
Mês 4:     SAGA-A Coordinator + Step-Resident State
Mês 5:     Emergent Router (Qdrant + affinity scoring)
Mês 6:     Topologias 1:N e N:1 + Merge Engine
Mês 7:     FTEP CLI (experimentos E1-E3)
Mês 8:     Benchmark de routing (experimentos E4-E5)
Mês 9-10:  Avaliação com praticantes + coleta de feedback
Mês 11-12: Refinamento, escrita, defesa
```

---

## 6.10 Relação com Trabalhos Concorrentes

| Plataforma | Tipo | Agent como entidade? | SAGA-A? | Emergent Routing? | OSS? |
|---|---|---|---|---|---|
| Microsoft Agent 365 | Proprietário | Parcial | Não | Não | Não |
| LangSmith | SaaS | Não (trace-only) | Não | Não | Não |
| SagaLLM | Arquitetura customizada | Não | Parcial | Não | Sim |
| ALAS | Domínio específico | Não | Parcial | Não | Sim |
| Agent Identity URI | Naming/discovery | Sim (naming) | Não | Não | Sim |
| **Atelium** | **Control plane OSS** | **Sim (completo)** | **Sim** | **Sim** | **Sim** |

O gap persiste: nenhuma plataforma existente trata o agente como entidade de primeira classe com identidade, governança, SAGA-A, Transition Guard, Emergent Routing e Step-Resident State integrados como sistema coerente.

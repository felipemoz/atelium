# Atelium — OSS Principles & Definitive Stack

## Regra Fundamental

> Toda tecnologia usada na implementação de referência e nos experimentos deve ser 100% open source e self-hostável.

Sistemas proprietários (Agent 365, LangSmith, GPT-4, Claude) podem ser citados e comparados na revisão de literatura, mas **nunca como dependência do artefato produzido**.

---

## Stack Definitivo

Decisões tomadas e fixadas. Alterações requerem justificativa explícita.

### Camada de Execução

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| Agent runtime | **LangGraph** | MIT | DAG stateful com checkpointing nativo — suporte direto a Transition Guard e Step-Resident State |
| LLM serving (local) | **Ollama** | MIT | Zero config para experimentos e laptop |
| LLM serving (produção) | **vLLM** | Apache 2.0 | OpenAI-compatible API, alta performance |

### Camada de Comunicação

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| Event bus A2A | **NATS JetStream** | Apache 2.0 | Baixa latência, persistência, streams e consumers nativos |
| API Gateway | **FastAPI** | MIT | Async Python, OpenAPI automático, mesmo ecossistema do runtime |
| CLI | **Typer** (Python) | MIT | Mesmo processo do runtime — sem serialização entre CLI e core |

### Camada de Estado

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| Step Store (quente) | **Redis** | BSD 3-Clause | Estado de steps em execução, TTL automático, pub/sub para notificações |
| Step Store (arquivo) | **PostgreSQL** | PostgreSQL License | Persistência durável, replay, auditoria |
| Registry vetorial | **Redis Stack** (RediSearch) | RSALv2 / SSPL | Vector similarity search para affinity scoring do Emergent Router |
| Registry metadados | **PostgreSQL** | PostgreSQL License | Ownership, versioning, lineage dos agentes |
| Knowledge / RAG | **pgvector** | PostgreSQL License | Namespaces de RAG sobre o Postgres existente — zero infra extra |
| Cache | **Redis** | BSD 3-Clause | Compartilhado com Step Store quente |

### Camada de Observabilidade

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| LLM tracing | **Langfuse** | MIT | Tracing nativo de LLM, OSS self-hostável |
| Instrumentação | **OpenTelemetry** | Apache 2.0 | Padrão de mercado, vendor-neutral |
| Métricas | **Prometheus** | Apache 2.0 | Pull-based, integra com Langfuse e NATS |
| Dashboards | **Grafana** | AGPL 3.0 | Self-hostável, data sources nativos |

### Camada de Segurança

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| Autorização relacional | **OpenFGA** | Apache 2.0 | Blast radius enforcement, MCP scopes, knowledge ACLs |
| Identity provider | **Keycloak** | Apache 2.0 | OIDC/OAuth2 para CLI, Portal e API |

### Modelos LLM (pesos abertos)

| Modelo | Licença | Uso |
|---|---|---|
| Llama 3 70B (Meta) | Llama 3 Community | Agente de propósito geral — padrão nos experimentos |
| Mistral 7B | Apache 2.0 | Agente leve, baixo custo |
| DeepSeek-R1 32B | MIT | Tarefas de raciocínio complexo |
| Qwen2 | Apache 2.0 | Multilingual |

### Infraestrutura

| Papel | Tecnologia | Licença | Decisão |
|---|---|---|---|
| Containers | **Docker Compose** | Apache 2.0 | Modo local/experimentos |
| Orquestração | **Kubernetes + Helm** | Apache 2.0 | Modo cluster e produção |

---

## Diagrama de Dependências

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
    ├── Redis (step store quente)              └── PostgreSQL (metadados)
    ├── PostgreSQL (step store arquivo)
    ├── pgvector (RAG namespaces)
    ├── OpenFGA (blast radius)
    └── Langfuse + OTel (observability)
```

---

## Critério de Avaliação para Novas Dependências

Antes de adicionar qualquer tecnologia ao projeto:

1. **Licença OSI-approved?** (MIT, Apache 2.0, BSD, GPL, MPL)
2. **Self-hostável sem restrições de uso?**
3. **Sem dependência de API key ou serviço externo obrigatório?**
4. **Código-fonte disponível e auditável?**

Se qualquer resposta for **não** → tecnologia não é aprovada.

> **Nota Redis Stack:** A licença RSALv2/SSPL restringe uso como serviço gerenciado, mas permite self-hosting sem restrição. Aprovado para uso no artefato.

---

## Nota sobre Comparação com Proprietários

O paper **pode e deve** comparar os resultados com sistemas proprietários (Agent 365, LangSmith, GPT-4o) como baseline de mercado na seção de discussão. Isso fortalece a relevância do trabalho sem criar dependência técnica.

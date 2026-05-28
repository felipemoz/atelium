# Catálogo de Padrões Arquiteturais para Sistemas Multi-Agente

> Status: rascunho inicial — cada padrão será expandido com contexto formal, forças, consequências e exemplos de implementação.

---

## Padrão 1: Agent Registry

**Categoria:** Infraestrutura / Descoberta

**Problema:**
Em uma organização com múltiplos agentes, nenhum mecanismo centralizado rastreia quais agentes existem, quem os criou, quais ferramentas acessam, e se estão saudáveis.

**Solução:**
Um registro central onde cada agente declara seu manifesto. O registry resolve dependências, verifica permissões e expõe um catálogo pesquisável.

**Analogia em sistemas distribuídos:** Consul, Backstage, Kubernetes API Server

**Componentes:**
- Agent Manifest (declaração)
- Registry API (CRUD de agentes)
- Health Check Endpoint por agente
- Diff de permissões em pull requests

**Forças:**
- Visibilidade de toda a frota
- Prevenção de duplicação ("já existe um agente que faz isso")
- Base para governança e auditoria

**Consequências:**
- Single point of truth (requer alta disponibilidade)
- Bootstrapping problem: agentes precisam ser registrados antes de rodar

---

## Padrão 2: SAGA-A (SAGA para Agentes)

**Categoria:** Transações Distribuídas

**Problema:**
Um workflow multi-agente executa ações no mundo real em sequência (grava CRM, envia email, cria ticket). Se um agente falha no meio do fluxo, o estado distribuído fica inconsistente.

**Solução:**
Cada agente declara uma `compensating_action` no manifesto. Um SAGA coordinator (choreography via eventos ou orchestration via LLM supervisor) dispara compensações em ordem inversa em caso de falha.

**Analogia:** SAGA pattern (Garcia-Molina & Salem, 1987) adaptado

**Extensões específicas para LLM agents (SAGA-A):**

| Extensão | Descrição |
|---|---|
| `irreversible: true` | Ação que não pode ser desfeita — exige `pre_confirmation` |
| `compensating_action` | Ação de reversão declarada no manifesto |
| `dry_run_gate` | Execução simulada obrigatória antes de ações de alto impacto |
| `idempotency_key` | Cache de execução por hash(input + tool_calls) para retries seguros |
| `cognitive_snapshot` | Snapshot do estado de memória/RAG antes da execução |

**Fluxo de rollback:**
```
[A] → [B] → [C: FALHA]
              ↓
        saga.rollback emitido
              ↓
        [B].compensating_action executada
              ↓
        [A].compensating_action executada
```

**Forças:**
- Consistência eventual em workflows multi-agente
- Sem necessidade de 2PC (incompatível com latência de LLMs)

**Consequências:**
- Ações irreversíveis criam "pontos de não-retorno" no workflow
- Compensações com LLMs podem produzir output diferente do esperado (non-determinism)

---

## Padrão 3: Connector Fabric (MCP Registry)

**Categoria:** Integração / Conectividade

**Problema:**
Cada agente conecta-se diretamente a ferramentas externas (Jira, GitHub, banco de dados) via código customizado. Sem padronização, cada integração é única, sem versionamento ou controle de escopo.

**Solução:**
Um registro de MCP Servers versionados, análogo ao npm. Agentes declaram dependências de conectores no manifesto com scopes explícitos. A plataforma resolve versões e injeta conexões autorizadas.

**Analogia:** npm/pip para conectores; Istio para controle de tráfego

**Estrutura:**
```yaml
mcps:
  - name: jira
    version: "^2.1"
    scopes: [read:issues, write:comments]
    # NÃO tem: delete:issues, admin:project
```

**Forças:**
- Princípio do menor privilégio por agente
- Auditoria de quem acessa o quê
- Breaking change detection entre versões de MCP

**Consequências:**
- Requer processo de review para novos scopes (pode criar atrito)
- MCP servers precisam ser mantidos e versionados

---

## Padrão 4: Knowledge Namespace

**Categoria:** Dados / RAG Compartilhado

**Problema:**
Cada agente mantém seu próprio índice vetorial. Resulta em duplicação de dados, inconsistência entre bases, e custo de ingestão multiplicado.

**Solução:**
Um Knowledge Fabric centralizado com namespaces por domínio. Agentes declaram quais namespaces podem ler. A plataforma garante isolamento e attribution de acesso.

**Analogia:** Database schemas com row-level security; IAM policies para S3 buckets

**Estrutura:**
```yaml
knowledge:
  namespaces:
    - name: legal-contracts
      access: read-only
    - name: compliance-br
      access: read-only
  # NÃO tem acesso a: financial-data, hr-records
```

**Forças:**
- Single source of truth para knowledge organizacional
- Custo de ingestão e embedding centralizado
- Attribution: qual agente leu qual chunk em qual momento

**Consequências:**
- Multi-tenancy de RAG é tecnicamente complexo (metadata filtering não escala linearmente)
- Requer namespace governance (quem pode criar, quem pode escrever)

---

## Padrão 5: Agent Choreography (A2A Event-Driven)

**Categoria:** Comunicação / Composição

**Problema:**
Em orquestração centralizada, um LLM supervisor conhece todos os agentes e decide cada passo. Isso cria acoplamento forte, latência adicional (round-trips LLM) e single point of failure.

**Solução:**
Agentes publicam eventos em um bus (NATS/Kafka). Outros agentes reagem a eventos de seu interesse. Nenhum agente central conhece o fluxo completo.

**Analogia:** Event-driven microservices; Choreography vs. Orchestration (Hohpe & Woolf)

**Quando usar choreography:**
- Workflows com etapas bem definidas e contratos estáveis
- Requisitos de baixa latência
- Alta resiliência (sem SPOF)

**Quando usar orchestration:**
- Workflows abertos onde o LLM precisa raciocinar sobre o próximo passo
- Workflows que mudam frequentemente
- Debugging mais fácil (trace linear)

**Métricas para escolha (base para Experimento E2):**

| Critério | Choreography | Orchestration |
|---|---|---|
| Latência | Menor | Maior (round-trips LLM) |
| Resiliência | Alta (sem SPOF) | Média (supervisor é SPOF) |
| Flexibilidade | Baixa (contrato fixo) | Alta (LLM decide) |
| Observabilidade | Difícil (causal tracing) | Fácil (trace linear) |
| Custo em tokens | Menor | Maior |

---

## Padrão 6: Blast Radius Boundary

**Categoria:** Segurança / Governança

**Problema:**
Um agente comprometido, mal configurado ou com prompt injection pode propagar danos por toda a infraestrutura se não houver isolamento.

**Solução:**
Cada agente opera dentro de um blast radius declarado — conjunto máximo de sistemas que pode afetar. A plataforma bloqueia ações fora desse escopo em runtime.

**Analogia:** Kubernetes RBAC + NetworkPolicy; AWS IAM least privilege

**Estrutura:**
```yaml
blast_radius:
  max_write_systems: [jira, slack-channel-legal]
  max_read_systems: [legal-contracts-rag, jira, confluence]
  forbidden: [production-db, billing-api, user-pii]
  human_approval_required: [send_external_email, approve_contract]
```

**Forças:**
- Contenção de danos em caso de falha ou ataque
- Requisito auditável para compliance (LGPD, SOC2)

**Consequências:**
- Requer plataforma de enforcement em runtime (não apenas declaração)
- Pode limitar agentes legítimos se blast radius for mal calibrado

---

## Padrão 7: Agent Manifest as Contract

**Categoria:** Governança / DevOps

**Problema:**
Não há padrão para declarar o que um agente é, o que pode fazer, e quais são suas dependências. Isso impede automação de deploy, review de permissões e descoberta.

**Solução:**
Um formato YAML padronizado (Agent Manifest) que serve como contrato entre o agente e a plataforma. Análogo ao Dockerfile para containers ou ao Chart.yaml para Helm.

**Especificação mínima:**
```yaml
apiVersion: atelium/v1alpha1
kind: Agent
metadata:
  name: string
  owner: string          # time responsável
  version: semver
spec:
  model: string          # llama3, mistral, qwen2 via Ollama ou vLLM (OSS only)
  mcps: []               # conectores com scopes
  knowledge: {}          # namespaces de RAG
  task: {}               # critérios de sucesso, falha e transição
  a2a: {}                # contratos de comunicação
  saga: {}               # compensating actions
  blast_radius: {}       # escopo máximo de impacto
  observability: {}      # telemetry settings
```

**Forças:**
- Base para todo o ciclo de vida: register → deploy → observe → retire
- Permite diff de permissões em PRs ("esse agente ganhou acesso a billing-api")
- Versionamento semântico com breaking change detection

---

## Padrão 8: Transition Guard

**Categoria:** Contratos / Composição

**Problema:**
Agentes transitam para o próximo nó da rede mesmo quando sua tarefa está incompleta ou seu output não satisfaz as pré-condições do agente downstream. A tarefa incompleta propaga silenciosamente, corrompendo o estado de todos os agentes subsequentes que assumiram pré-condições não satisfeitas.

**Analogia neural:** Um neurônio que não atingiu o limiar de ativação não deve propagar sinal. O Transition Guard é o **threshold** da rede de agentes.

**Solução:**
Cada agente declara explicitamente no manifesto: (a) o que constitui sucesso da sua tarefa, (b) o que constitui falha, e (c) a condição que deve ser verdadeira para transitar para o próximo agente. A plataforma bloqueia a transição se o guard não for satisfeito e aciona SAGA-A automaticamente.

**Especificação:**
```yaml
spec:
  task:
    description: "Classify contract by jurisdiction"

    success_criteria:
      - field: output.jurisdiction
        type: enum
        values: [BR, US, EU]
      - field: output.confidence
        type: float
        min: 0.85

    failure_criteria:
      - condition: "output.jurisdiction == null"
        action: compensate         # aciona SAGA-A upstream
      - condition: "output.confidence < 0.5"
        action: escalate_human     # pausa, aguarda revisão humana
      - condition: "elapsed > 30s"
        action: circuit_breaker    # não transita, não propaga

    transition_to: legal-agent
    transition_guard: "output.jurisdiction != null AND output.confidence >= 0.85"
```

**O que acontece quando o guard falha:**

```
[Classifier Agent] → avalia transition_guard → FALHA
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         compensate     escalate_human   circuit_breaker
         (SAGA-A)       (pausa humana)   (aborta silencioso
         reverte         aguarda input    com log de falha)
         upstream        antes de seguir
```

**Relação com SAGA-A:**
O Transition Guard é a **detecção de falha** — SAGA-A é a **resposta à falha**. Os dois padrões são complementares: sem Transition Guard, SAGA-A nunca é acionado porque a falha não é detectada antes da transição.

**Forças:**
- Falhas são detectadas na fronteira do agente, não propagadas downstream
- Contrato de interface explícito e auditável entre agentes
- Base para H5: torna testável a hipótese de que tarefas incompletas corrompem redes

**Consequências:**
- Requer que o output do agente seja estruturado o suficiente para avaliação do guard
- Agentes com output livre (texto puro) precisam de um parser de avaliação intermediário
- Pode introduzir latência se o guard exigir chamada LLM adicional para avaliação

---

## Mapa de Padrões

```
DESENVOLVIMENTO          RUNTIME               OPERAÇÃO
─────────────────────────────────────────────────────────
Agent Manifest      →   Agent Registry    →   Blast Radius
(contrato)              (descoberta)          (segurança)
      │                      │
      │               Connector Fabric      →   SAGA-A
      │               (ferramentas)             (transações)
      │                      │                     ▲
      │               Knowledge Namespace          │
      │               (dados)                      │
      │                                            │
      └──► Transition Guard ──────────────────────►┘
           (critérios de sucesso,      aciona SAGA-A
            falha e transição)         se guard falha
                    │
                    ▼
              Choreography
              (composição A2A)
```

---

## Padrão 9: Emergent Routing

**Categoria:** Composição / Descoberta

**Problema:**
Em redes com milhares de agentes, coreografia pré-definida é inviável — nenhum designer consegue mapear todas as rotas possíveis. Orquestração centralizada cria SPOF e não escala. É necessário um mecanismo pelo qual agentes descobrem autonomamente o próximo nó mais capaz, sem supervisão e sem DAG pré-definido.

**Analogia neural:** Mecanismo de atenção nos Transformers — cada token calcula afinidade (Q·K) com todos os outros e roteia para os mais relevantes, sem regra pré-definida.

**Solução:**
Após passar no Transition Guard, o agente consulta o Registry com seu output como query. O Registry retorna um ranking probabilístico de agentes com maior afinidade de capacidade. O agente roteia para o melhor candidato — ou para os K melhores em delegação 1:N.

```
Agente A conclui tarefa → output: {type: contract_classified, jurisdiction: BR}
        │
        ▼
Registry.route(output, context) → ranking:
  legal-agent-BR      score: 0.94
  compliance-agent    score: 0.81
  summarizer-agent    score: 0.67
        │
        ▼
Agente A roteia para legal-agent-BR  ← sem DAG, sem supervisor
```

**Como o Registry calcula afinidade:**
- Cada agente publica no manifesto suas `capabilities` como vetor semântico
- O output do agente emissor é embedado e comparado por similaridade
- Score combina: similaridade semântica + taxa histórica de sucesso + latência média + carga atual

**Manifesto do agente receptor:**
```yaml
spec:
  capabilities:
    - "contract review"
    - "jurisdiction analysis BR"
    - "legal compliance LGPD"
  accepts:
    input_types: [contract_classified, legal_document]
    required_fields: [jurisdiction, document_text]
```

**Três modos de roteamento:**

| Modo | Topologia | Descrição |
|---|---|---|
| `route_best` | 1:1 | Roteia para o agente com maior score |
| `route_top_k` | 1:N | Delega para os K melhores em paralelo |
| `route_quorum` | 1:N→N:1 | Delega para K, agrega quando quorum completa |

**Forças:**
- Escala para milhares de agentes sem coreografia manual
- Rotas se adaptam dinamicamente conforme agentes entram/saem do registry
- Especialização emergente: agentes melhores em uma tarefa são naturalmente preferidos

**Consequências:**
- Requer Registry com capacidade de busca vetorial (Qdrant/pgvector)
- Rotas não-determinísticas dificultam reprodução exata de workflows
- Auditoria precisa registrar qual rota foi escolhida e por quê (score log)

---

## Padrão 10: Network Topologies (1:N e N:1)

**Categoria:** Composição / Agregação

**Problema:**
Workflows reais requerem delegação paralela (1:N) e agregação de resultados (N:1). Sem declaração explícita da topologia e da estratégia de agregação, o comportamento em caso de falha parcial é indefinido — especialmente em N:1, onde um agente aguarda múltiplos upstream.

**Topologias válidas:**

```
1:1  Pipeline direto
     A ──► B

1:N  Fan-out (delegação paralela)
     A ──► B
       ──► C
       ──► D

N:1  Fan-in (agregação, join)
     B ──►
     C ──► E
     D ──►

N:N  EXCLUÍDO — sem semântica clara de agregação, produz caos
```

**Analogia neural:**
```
1:N  →  divergência entre camadas (uma camada alimenta várias)
N:1  →  pooling / agregação (várias camadas convergem em uma)
N:N  →  full attention — não é o modelo desta arquitetura
```

**O problema central do N:1: falha parcial**

```
             ┌──► agente B (concluiu) ──┐
agente A ────┤                          ├──► agente E (aguarda)
             ├──► agente C (concluiu) ──┤
             └──► agente D (FALHOU)  ───┘
```

Três estratégias de agregação — devem ser declaradas no manifesto do agente E:

| Estratégia | Comportamento | Quando usar |
|---|---|---|
| `wait_all` | Bloqueia até todos entregarem ou timeout | Output de E depende de todos os inputs |
| `quorum` | Segue se K de N entregarem | Tolerância a falha parcial aceitável |
| `best_effort` | Segue com o que chegou, marca os faltantes | Output de E é parcialmente válido |

**Manifesto do agente agregador (N:1):**
```yaml
spec:
  task:
    aggregation:
      mode: quorum            # wait_all | quorum | best_effort
      quorum_size: 2          # mínimo de N para prosseguir
      timeout: 60s
      on_timeout: best_effort # degradação graciosa após timeout
      on_partial_failure:
        action: compensate_completed  # SAGA-A nos agentes que já concluíram
        mark_incomplete: true         # registra quais inputs faltaram

    success_criteria:
      - field: output.aggregated_results
        type: array
        min_length: "{{ aggregation.quorum_size }}"
```

**SAGA-A em topologias N:1:**

Quando agente D falha após B e C já terem concluído:
- `wait_all` → compensa B e C, aciona SAGA-A completo
- `quorum` → segue sem D, registra falha parcial, não compensa B e C
- `best_effort` → segue sem D, output marcado como incompleto

**Manifesto do agente delegador (1:N):**
```yaml
spec:
  task:
    delegation:
      mode: route_top_k
      k: 3
      strategy: parallel      # parallel | sequential_fallback
      collect_via: fan_in     # referência ao agente agregador
      on_all_failed: compensate_self
```

**Forças:**
- Comportamento de falha parcial explícito e auditável
- Degradação graciosa configurável por workflow
- SAGA-A sabe exatamente o que compensar em cada topologia

**Consequências:**
- Quorum e best_effort produzem outputs potencialmente incompletos — downstream precisa tratar
- Timeout em wait_all pode se propagar como latência em cascata

---

## Mapa de Padrões (atualizado)

```
DESENVOLVIMENTO             RUNTIME                    OPERAÇÃO
──────────────────────────────────────────────────────────────────
Agent Manifest         →   Agent Registry         →   Blast Radius
(contrato)                 (descoberta +               (segurança)
      │                     embedding de caps)
      │                          │
      │                    Emergent Routing  ←────────────────┐
      │                    (1:1 probabilístico)               │
      │                          │                            │
      │                    ┌─────┴──────┐                     │
      │                   1:N          N:1                    │
      │                 (fan-out)    (fan-in/                  │
      │                              aggregation)             │
      │                    └─────┬──────┘                     │
      │                          │                            │
      │                  Connector Fabric    →   SAGA-A ──────┘
      │                  (ferramentas)           (compensa por
      │                          │                topologia)
      │                  Knowledge Namespace         ▲
      │                  (dados)                     │
      │                                              │
      └──► Transition Guard ────────────────────────►┘
           (success criteria +     aciona SAGA-A
            self-healing loop)     se guard falha
```

---

---

## Padrão 11: Step-Coupled Memory

**Categoria:** Estado / Memória

**Problema:**
Em redes com roteamento emergente e topologias dinâmicas, a memória acoplada ao agente cria dois problemas: agentes descobertos dinamicamente não têm contexto, e em topologias 1:N/N:1 o estado se fragmenta sem mecanismo de sincronização. Frameworks atuais confundem capacidade de processamento (agente) com estado (memória), forçando agentes stateful que não podem ser substituídos ou roteados livremente.

**Princípio:**
> **Agente = capacidade de processamento** (stateless, substituível, roteável)
> **Step = unidade de estado e memória** (stateful, imutável após conclusão)

**Solução:**
A memória é acoplada ao step, não ao agente. O step é o objeto que viaja pela rede — carrega task, input, memória acumulada e output. O agente recebe o step, processa, devolve o step enriquecido. O agente é apenas o processador; o step é o portador de estado.

```
Step = {
  id:        uuid
  task:      descrição da tarefa
  input:     dados de entrada
  memory:    [ output do step anterior, step anterior ao anterior, ... ]
  output:    resultado deste agente (preenchido após execução)
  metadata:  { agent, timestamp, score, branch_id }
}
```

**Comportamento por topologia:**

```
1:1 — memória cresce linearmente
  Step₀ → Agente A → Step₁{memory:[A]}
         → Agente B → Step₂{memory:[A,B]}

1:N — step clonado no ponto de fork
  Step₂{memory:[A,B]}
    → branch B: Step₂ᵦ{memory:[A,B], branch:B} → Agente C
    → branch C: Step₂꜀{memory:[A,B], branch:C} → Agente D
  Cada branch acumula independentemente a partir do mesmo snapshot

N:1 — steps mergeados no agregador
  Step₃ᵦ{memory:[A,B,C]}  ┐
  Step₃꜀{memory:[A,B,D]}  ├─► merge ─► Step₄{memory:[A,B,C,D,E]}
  Step₃_d{memory:[A,B,E]} ┘
```

**Manifesto:**
```yaml
spec:
  memory:
    scope: step                      # acoplada ao step, não ao agente
    append_output: true              # output é adicionado ao step.memory
    visible_history: last_3          # agente vê N steps anteriores, não tudo

    on_branch:
      strategy: clone                # cada branch recebe snapshot do step atual

    on_merge:
      strategy: union                # une todos os outputs dos branches
      conflict_resolution: voting    # voting | last_write_wins | manual
```

**O que isso resolve:**

| Problema | Solução |
|---|---|
| Agente descoberto dinamicamente não tem contexto | Recebe o step completo |
| 1:N: quanto de contexto cada branch recebe | Snapshot no ponto de fork |
| N:1: como agregar contextos divergentes | Merge policy declarada no agregador |
| SAGA-A: qual era o estado antes da ação | Step é imutável — snapshot nativo |
| Replay de workflow | Sequência de steps é o log completo |
| Context window do LLM | visible_history limita o que o agente recebe |

**Relação com Emergent Routing:**
Step-Coupled Memory é o que torna o Emergent Routing possível. Qualquer agente com a capacidade certa pode pegar qualquer step — porque o step carrega tudo que é necessário. O agente não precisa de contexto próprio.

**Analogia:**
- **Programação funcional** — função pura recebe estado, retorna novo estado sem efeitos colaterais
- **Event sourcing** — o log de steps é a fonte de verdade, o estado atual é derivado
- **Git commits** — cada commit é um snapshot imutável; branches divergem e mergeiam

**Forças:**
- Agentes são completamente stateless — substituíveis, escaláveis, roteáveis
- Replay e debugging triviais — sequência de steps é o log completo
- SAGA-A tem snapshot nativo para compensação — o step antes da ação é preservado
- Context window gerenciável — visible_history evita crescimento ilimitado

**Consequências:**
- Steps crescem em tamanho ao longo de workflows longos — visible_history é essencial
- Merge em N:1 com conflito real requer política explícita ou escalação humana
- Imutabilidade do step requer armazenamento — não pode ser só in-memory em workflows longos

---

## Mapa de Padrões (final)

```
DESENVOLVIMENTO             RUNTIME                       OPERAÇÃO
─────────────────────────────────────────────────────────────────────
Agent Manifest         →   Agent Registry            →   Blast Radius
(contrato)                 (descoberta +                  (segurança)
      │                     embedding de caps)
      │                          │
      │                    Emergent Routing
      │                    (roteamento probabilístico)
      │                          │
      │                   ┌──────┴──────┐
      │                  1:N           N:1
      │               (fan-out)    (fan-in / merge)
      │                   └──────┬──────┘
      │                          │
      │              Step-Coupled Memory ──────────────────────┐
      │              (estado viaja com o step)                 │
      │                          │                             │
      │                  Connector Fabric    →   SAGA-A ───────┘
      │                  (ferramentas MCP)       (compensa por
      │                          │                topologia +
      │                  Knowledge Namespace      snapshot do step)
      │                  (RAG compartilhado)          ▲
      │                                               │
      └──► Transition Guard + Self-Healing ──────────►┘
           (success criteria, iteração,    aciona SAGA-A
            loop de correção)              se guard esgota
                    │
                    ▼
              HITL (apenas ambiguidade genuína)
```

---

## Próximos Padrões a Documentar

- **Agent Versioning & Canary** — deploy gradual de nova versão de agente
- **Cognitive Snapshot** — checkpoint de raciocínio para debugging (derivado de Step-Coupled Memory)
- **Human-in-the-Loop Gate** — padrão para aprovação humana em ações críticas
- **Agent Circuit Breaker** — para de rotear para agente com alta taxa de falha

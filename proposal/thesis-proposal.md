# Proposta de Dissertação de Mestrado

## Título

**Fault-Tolerant Agent Networks: A Layered Resilience Model for Multi-Agent LLM Systems**

*Título alternativo em PT-BR:*
**Redes de Agentes Tolerantes a Falhas: Um Modelo de Resiliência em Camadas para Sistemas Multi-Agente**

---

## 1. Motivação

Agentes baseados em LLMs executam ações no mundo real: enviam emails, gravam em bancos de dados, criam tickets, debitam contas, publicam mensagens. Diferente de código tradicional, essas ações têm efeitos que frequentemente **não podem ser desfeitos**.

Frameworks populares como LangGraph, CrewAI, OpenClaw e Hermes Agent tratam a execução de ações como primitiva atômica — sem distinção entre ações reversíveis e irreversíveis, sem mecanismo de compensação em caso de falha, e sem critérios declarados de sucesso ou transição entre agentes.

O resultado prático é duplo: quando um agente falha, o sistema fica em **estado inconsistente sem mecanismo de recuperação**; quando um agente produz output inválido mas transita mesmo assim, a falha **propaga silenciosamente por toda a rede downstream**.

Sistemas distribuídos maduros resolveram problemas análogos há décadas — TCP/IP com retry e acknowledgment, bancos de dados com rollback transacional, Kubernetes com liveness probes e restart policies. Nenhum desses princípios foi sistematicamente aplicado a redes de agentes LLM.

Este trabalho propõe que **tolerância a falhas em redes de agentes é um problema de engenharia de sistemas, não de engenharia de prompts** — e que os mesmos princípios de resiliência estabelecidos em sistemas distribuídos podem ser adaptados para produzir redes de agentes robustas, com mínima dependência de intervenção humana.

---

## 2. Tese Central

> **Redes de agentes LLM carecem de tolerância a falhas por design. A ausência de critérios de sucesso declarados, mecanismos de self-healing e primitivas de compensação força dependência excessiva de intervenção humana e produz estado inconsistente irrecuperável. Um modelo de resiliência em camadas — Transition Guard → Self-Healing → SAGA-A → HITL — pode tornar redes de agentes tão robustas quanto sistemas distribuídos maduros.**

---

## 3. Problema de Pesquisa

**Questão Principal:**
> Como um modelo de resiliência em camadas — composto por Transition Guards, self-healing iterativo, SAGA-A e HITL seletivo — pode tornar redes de agentes LLM tolerantes a falhas, reduzindo inconsistência de estado e dependência de intervenção humana?

**Questões Secundárias:**

1. Quais categorias de ações executadas por agentes são irreversíveis por natureza, e como classificá-las?
2. Os frameworks multi-agente atuais oferecem primitivas de tolerância a falhas? Se não, qual é o custo mensurável dessa ausência?
3. Critérios de sucesso declarados combinados com self-healing reduzem a superfície de ambiguidade que requer julgamento humano?
4. Um modelo de resiliência em camadas produz processos mensuravelmente mais robustos do que frameworks sem essas primitivas?
5. Em redes de larga escala sem coreografia pré-definida, roteamento probabilístico por afinidade de capacidade produz composição emergente viável e auditável?
6. Qual é o comportamento de SAGA-A em topologias N:1 com falha parcial, e como a estratégia de agregação declarada (wait_all, quorum, best_effort) afeta a extensão da compensação?

---

## 4. Hipóteses

**H1:** Os principais frameworks multi-agente não possuem primitivas nativas de compensação ou rollback de estado distribuído.

**H2:** É possível definir uma taxonomia de irreversibilidade para ações de agentes com pelo menos três categorias distintas (reversível, compensável, irreversível).

**H3:** A ausência de compensating actions produz inconsistência de estado mensurável em workflows multi-agente sob condições de falha induzida.

**H4:** Uma extensão do padrão SAGA (SAGA-A) pode reduzir a taxa de inconsistência de estado em workflows agenticos sem comprometer throughput significativamente.

**H5:** A ausência de critérios de transição declarados (Transition Guards) é uma causa primária de propagação de falha em redes de agentes — tarefas incompletas transitam para agentes downstream que assumem pré-condições não satisfeitas, corrompendo o estado de toda a rede subsequente.

**H6:** A declaração explícita de critérios de sucesso combinada com loops de self-healing reduz a necessidade de Human-in-the-Loop (HITL) em proporção direta à cobertura dos critérios — quanto mais completo o contrato da tarefa, menor a superfície de ambiguidade que requer julgamento humano.

**H7:** Em topologias N:1, a estratégia de agregação declarada (wait_all, quorum, best_effort) determina o trade-off entre consistência do output e resiliência a falhas parciais — e a ausência de declaração explícita produz comportamento indefinido mensurável como taxa de inconsistência.

**H8:** Acoplar memória ao step em vez de ao agente — tornando agentes stateless — é condição necessária para roteamento emergente viável: agentes descobertos dinamicamente só podem processar tarefas de forma coerente se o step carregar todo o contexto necessário.

---

## 4.1 Modelo de Resiliência em Camadas (contribuição central)

O modelo proposto opera em quatro níveis progressivos. Cada nível só é acionado se o anterior não resolveu a falha:

```
NÍVEL 1 — Self-Healing (local, automático)
  Agente detecta output inválido contra success_criteria
  Itera com feedback do erro como contexto adicional
  Resolve: falhas técnicas e ambiguidade baixa
  Análogo a: gradient descent, retry com backoff

NÍVEL 2 — Transition Guard (fronteira, automático)
  Bloqueia transição se output não satisfaz transition_guard
  Aciona SAGA-A se max_iterations esgotado
  Resolve: impede propagação downstream de output inválido
  Análogo a: acknowledgment no TCP, conflict detection no Git

NÍVEL 3 — SAGA-A (compensação, automático)
  Executa compensating_actions em ordem inversa
  Restaura consistência do estado distribuído
  Resolve: efeitos colaterais já executados upstream
  Análogo a: rollback transacional em bancos ACID

NÍVEL 4 — HITL (arbitragem, humano)
  Acionado apenas para ambiguidade genuína de domínio
  ou ações marcadas como irreversíveis com alto impacto
  Resolve: o que nenhum critério declarado consegue cobrir
  Análogo a: escalação para especialista em SRE
```

**Propriedade emergente:** O processo não para em caso de falha — ele **degrada graciosamente**, contendo o dano no nível mais baixo possível antes de envolver o humano.

| Comparação | Sem o modelo | Com o modelo |
|---|---|---|
| Falha técnica | HITL imediato | Self-healing resolve |
| Output inválido propagado | Corrompe downstream | Bloqueado no guard |
| Estado inconsistente | Irrecuperável | SAGA-A compensa |
| HITL | Verificador de qualidade | Árbitro de ambiguidade |

---

## 5. Taxonomia de Irreversibilidade (rascunho)

| Categoria | Definição | Exemplos | Estratégia |
|---|---|---|---|
| **Reversível** | Ação pode ser desfeita com fidelidade total | Rascunho salvo, registro em DB sem commit | Rollback direto |
| **Compensável** | Ação não pode ser desfeita, mas pode ser compensada semanticamente | Ticket criado → fechar ticket; CRM gravado → deletar registro | Compensating action |
| **Irreversível** | Nem reversão nem compensação são possíveis | Email enviado, Slack postado, pagamento executado | Dry-run gate + aprovação humana antes |

Esta taxonomia é uma contribuição original — não existe na literatura de MAS ou LLM agents.

---

## 6. Fundamentação Teórica: Redes de Agentes como Analogia a Redes Neurais

### 6.1 A Analogia Estrutural

Redes neurais artificiais emergiram do encadeamento de unidades simples — neurônios individuais com capacidade computacional limitada cuja **inteligência surge da composição**, não do elemento isolado. Sistemas multi-agente seguem o mesmo princípio: agentes especializados e limitados produzem comportamento emergente quando encadeados.

A analogia, porém, revela uma assimetria crítica:

> *Redes neurais possuem mecanismo de correção retroativa (backpropagation). Redes de agentes não possuem equivalente — cada ação executada no mundo real é potencialmente irreversível.*

```
Rede neural:     forward pass → erro mensurado → backward pass → correção dos pesos
Rede de agentes: forward pass → ação no mundo → erro → estado inconsistente irrecuperável
```

SAGA-A, proposto neste trabalho, é uma forma primitiva de "backward pass" para agentes — não corrige o raciocínio, mas **desfaz os efeitos colaterais no mundo real**.

### 6.2 Topologias de Encadeamento

A topologia do encadeamento determina as propriedades emergentes do sistema — e os padrões de falha:

| Topologia Neural | Topologia Agentica | Propriedade | Padrão de Falha |
|---|---|---|---|
| Sequencial (feedforward) | Pipeline linear A→B→C | Previsível, auditável | Falha propaga para frente irreversivelmente |
| Paralela | Fan-out A→B, A→C | Throughput, redundância | Resultados divergentes sem reconciliação |
| Recorrente | Loop com feedback A→B→A | Memória, iteração | Loops infinitos, amplificação de erro |
| Residual (skip connection) | Bypass condicional | Resiliência a falha de nó | Análogo ao Circuit Breaker pattern |

A topologia **residual** é especialmente relevante: as skip connections do ResNet — que permitem que o gradiente "pule" camadas problemáticas — têm correspondência direta com o padrão Circuit Breaker em agentes, onde um agente com falha pode ser contornado sem interromper o pipeline.

### 6.3 Emergência e Composição

Em redes neurais profundas, camadas iniciais detectam padrões simples (bordas, texturas) e camadas subsequentes compõem representações complexas (rostos, objetos). O mesmo princípio de **composição hierárquica** aparece em redes de agentes:

```
Camada 1 (agentes especializados):
  Extractor → Classifier → Summarizer

Camada 2 (agentes de composição):
  Reviewer → Validator → Approver

Camada 3 (agentes de orquestração):
  Supervisor → Router → Notifier
```

A diferença fundamental: em redes neurais, a composição é **diferenciável e corrigível**. Em redes de agentes, cada camada pode produzir **efeitos colaterais irreversíveis** antes que o erro na camada seguinte seja detectado.

Esta é a motivação formal para o problema central desta dissertação.

---

## 7. Metodologia

### 7.1 Análise de Frameworks (Estudo 1)

**Objetivo:** Verificar H1 empiricamente.

**Método:**
- Análise estática do código-fonte de LangGraph, CrewAI, OpenClaw, Hermes Agent
- Protocolo de análise: presença de (a) compensating actions, (b) rollback de estado, (c) distinção reversível/irreversível, (d) dry-run mode
- Resultado esperado: matriz de capacidades por framework

**Artefato:** Tabela comparativa publicável como parte da revisão do estado da arte.

### 7.2 Experimentos de Falha Induzida (Estudo 2)

**Objetivo:** Verificar H3 — medir custo da ausência de compensação.

**Setup:**
- Workflow multi-agente com 4 agentes em sequência
- Falha injetada em posições distintas (agente 2, 3, 4)
- Métricas: taxa de inconsistência de estado, tempo de detecção, tempo de recuperação manual

**Baseline:** frameworks sem SAGA-A
**Tratamento:** mesmo workflow com SAGA-A implementado

### 7.3 Implementação de SAGA-A (Artefato)

Extensão do padrão SAGA com três primitivas novas:

```
1. irreversibility_class: reversible | compensable | irreversible
2. compensating_action: declarado no manifesto do agente
3. dry_run_gate: execução simulada obrigatória antes de ações irreversíveis
```

Implementação de referência OSS integrada ao Agent Manifest.

### 7.4 Validação (Estudo 3)

**Objetivo:** Verificar H4 — SAGA-A reduz inconsistência sem custo proibitivo.

**Método:** Experimento controlado comparando workflows com e sem SAGA-A.

**Métricas:**
- Taxa de inconsistência de estado após falha
- Latência adicional introduzida por compensating actions
- Cobertura de cenários de falha (% de falhas detectadas e compensadas)

---

## 7. Contribuições Originais

1. **Modelo de Resiliência em Camadas** — composição de Transition Guard, Self-Healing, SAGA-A e HITL como sistema de tolerância a falhas para redes de agentes
2. **Taxonomia de irreversibilidade** — primeira formalização das categorias de ações de agentes (reversível, compensável, irreversível)
3. **Transition Guard com Self-Healing** — primitiva de contrato declarativo com loop de correção iterativa antes de escalar
4. **SAGA-A** — extensão do padrão SAGA para workflows agenticos com não-determinismo, ações irreversíveis e topologias N:1
5. **Emergent Routing** — terceiro modo de composição além de orquestração e coreografia: roteamento probabilístico por afinidade de capacidade em redes de larga escala
6. **Network Topologies (1:N, N:1)** — padrões de delegação e agregação com estratégias declaradas de tolerância a falha parcial
7. **Step-Coupled Memory** — separação entre agente stateless e step stateful como condição para roteamento emergente e replay nativo
8. **Análise empírica de frameworks** — evidência de que frameworks atuais carecem de tolerância a falhas nativa
9. **Agent Manifest** — especificação declarativa OSS que unifica todas as primitivas propostas

---

## 8. Estrutura da Dissertação

```
Cap. 1 — Introdução
  Motivação, problema, tese, contribuições, estrutura

Cap. 2 — Fundamentação Teórica
  2.1 Agentes LLM: definição, capacidades, limitações
  2.2 Tolerância a falhas em sistemas distribuídos: SAGA, retry, circuit breaker, idempotência
  2.3 Multi-Agent Systems: MAS clássico vs. LLM agents
  2.4 Redes de agentes como analogia a redes neurais: composição, emergência e ausência de backpropagation

Cap. 3 — Revisão Sistemática de Literatura
  Estado da arte em frameworks multi-agente — análise de primitivas de tolerância a falhas

Cap. 4 — Taxonomia de Irreversibilidade (contribuição 1)
  Definição formal das categorias, critérios de classificação

Cap. 5 — Análise de Frameworks (contribuição 2)
  Metodologia, resultados, matriz comparativa

Cap. 6 — SAGA-A: Extensão para Agentes (contribuição 3)
  Especificação formal, Agent Manifest, casos de uso

Cap. 7 — Experimentos e Resultados (contribuições 4-5)
  Setup, execução, análise, ameaças à validade

Cap. 8 — Discussão
  Implicações, limitações, trabalhos futuros

Cap. 9 — Conclusão
```

---

## 9. Cronograma

| Fase | Atividade | Duração |
|---|---|---|
| 1 | Revisão sistemática de literatura | 2 meses |
| 2 | Análise de frameworks (Estudo 1) | 1 mês |
| 3 | Taxonomia de irreversibilidade | 1 mês |
| 4 | Especificação SAGA-A + Agent Manifest | 2 meses |
| 5 | Implementação OSS de referência | 2 meses |
| 6 | Experimentos (Estudos 2 e 3) | 2 meses |
| 7 | Escrita, revisão, defesa | 2 meses |
| **Total** | | **~12 meses** |

---

## 10. Venues de Publicação

**Alvo principal:**
- ICSE 2027 — International Conference on Software Engineering
- FSE 2027 — Foundations of Software Engineering

**Alternativos:**
- ICSOC — Service-Oriented Computing
- Journal of Systems and Software (Elsevier)

**Paper intermediário (cap. 5 isolado):**
- MSR — Mining Software Repositories (análise de frameworks OSS)

---

## 11. Referências Iniciais

- Garcia-Molina, H., & Salem, K. (1987). Sagas. *ACM SIGMOD Record*, 16(3), 249–259.
- Richardson, C. (2018). *Microservices Patterns*. Manning. Cap. 4.
- Yao, S. et al. (2022). ReAct: Synergizing Reasoning and Acting in Language Models. *arXiv:2210.03629*.
- Wooldridge, M., & Jennings, N. (1995). Intelligent agents: Theory and practice. *Knowledge Engineering Review*, 10(2).
- Chase, N. et al. (2024). Model Context Protocol Specification. Anthropic / Linux Foundation.
- OpenClaw Community (2025). OpenClaw Architecture Specification. GitHub.
- Nous Research (2026). Hermes Agent: Closed-Loop Learning for Agentic Workflows.
- Microsoft (2026). Agent 365: The Control Plane for AI Agents.
- Hevner, A. et al. (2004). Design Science in Information Systems Research. *MIS Quarterly*, 28(1).
- OWASP (2024). LLM Top 10 for Large Language Model Applications.

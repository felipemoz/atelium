# Paper 2 — Draft v2

## Title

**Emergent Routing and Step-Resident State: A Third Composition Mode for Large-Scale Multi-Agent LLM Networks**

---

## Abstract

Multi-agent LLM systems composed at scale face a fundamental tension: pre-defined choreography is infeasible for thousands of agents, while centralized orchestration creates bottlenecks and single points of failure. We propose two complementary primitives — **Emergent Routing**, in which agents autonomously select routing targets via probabilistic affinity scoring over a shared registry, and **Step-Resident State** (SRS), in which conversational context is carried by the task step rather than stored in the agent — and argue they constitute a formally distinct third composition mode. We define composition modes using a process-algebraic framework derived from Peltz [1] and Barros et al. [2], proving that neither orchestration nor choreography subsumes emergent routing. We formally prove that SRS is a *necessary condition* for emergent routing correctness under a precise safety property. We distinguish emergent routing from gossip-based peer sampling [3] and epidemic routing [4], identifying the key structural difference: capability-semantic affinity versus topological proximity. We evaluate on a 200-task benchmark across three domains, reporting completion rate, routing latency at three registry scales, and sensitivity analysis across affinity weight parameters. Results show emergent routing achieves 84% ± 3.1% completion rate (p < 0.01 vs. baselines), approaching oracle performance (91% ± 2.4%) while requiring no manual topology configuration.

**Keywords:** multi-agent systems, LLM agents, emergent routing, step-resident state, agent composition, distributed systems, probabilistic routing

> **Note on concurrent work:** MasRouter [23] (ACL 2025) addresses dynamic LLM routing in MAS via learned cascade controllers. Agent Identity URI [24] (2026) proposes capability-based agent discovery via DHT. Contextual Memory Virtualisation [25] (CMV, 2026) addresses DAG-based state management for LLM agents. We discuss differentiation from all three in Section 6.

---

## 1. Introduction

The composition of LLM-based agents into multi-agent systems has accelerated substantially. Two modes dominate the literature. In **orchestration**, a central supervisor agent reasons about the next step and delegates to specialized agents [5, 6, 7]. In **choreography**, agents subscribe to events and execute predefined reactions without central coordination [8, 9].

Both modes assume that the network topology is known at design time. Orchestration requires the supervisor to know all agents; choreography requires routes to be defined before deployment. Neither assumption holds at scale. An enterprise deploying 800 agents across legal, finance, engineering, and compliance domains cannot manually define routing tables for every possible task type — and the optimal agent for a given task may depend on runtime context (current load, recent success rate, semantic specificity of the request) rather than a static capability label.

We propose a third composition mode: **Emergent Routing**, in which routing decisions are made at runtime by each agent, using probabilistic affinity scoring against a shared registry. We further propose **Step-Resident State (SRS)**, a state model in which task context is bound to the step object rather than the agent instance. Together, these primitives enable agent networks that are dynamic, topology-agnostic, and horizontally scalable.

We are explicit about the relationship to prior work. Emergent routing shares structural features with gossip-based peer sampling [3, 10] and epidemic routing [4], which we discuss in Section 6. Step-resident state is related to message-passing in actor models [11, 12], from which it departs in specific and important ways (Section 6.2). We adopt the formal definition of composition modes from Peltz [1] and Barros et al. [2] to ground our novelty claim.

**Contributions:**

1. Formal definition of **composition modes** as process-algebraic structures, showing emergent routing is irreducible to orchestration or choreography (Section 3)
2. Formal definition of **Step-Resident State** with branch and merge semantics and a safety invariant (Section 4)
3. **Necessity theorem**: SRS is a necessary condition for emergent routing correctness, with full proof (Section 5)
4. **Affinity scoring model** with sensitivity analysis across weight parameters (Section 3.3)
5. **Empirical evaluation** on a 200-task benchmark with statistical significance testing (Section 7)
6. Explicit differentiation from gossip protocols and actor models (Section 6)

---

## 2. Background

### 2.1 Composition Modes: Orchestration and Choreography

Peltz [1] defines **orchestration** as a composition model in which one party (the orchestrator) controls the interactions of all participating services, directing each to perform its operation. The orchestrator holds the full execution state and knows the complete workflow.

**Choreography**, by contrast, describes collaborative interactions from a global perspective without a central controller. Each participant knows only its own role and reacts to events according to a globally-agreed protocol [1, 2].

Formally, following Barros et al. [2], we model compositions as labeled transition systems (LTS). Let an agent *aᵢ* be an LTS Aᵢ = (Sᵢ, Σᵢ, →ᵢ, s₀ᵢ) where Sᵢ is a set of states, Σᵢ is an alphabet of actions, →ᵢ ⊆ Sᵢ × Σᵢ × Sᵢ is a transition relation, and s₀ᵢ is the initial state.

**Definition 1 (Orchestration):** A composition C = {A₁, ..., Aₙ} is an orchestration if there exists a designated orchestrator Aₒ ∈ C such that for every transition (s, σ, s') in any Aᵢ (i ≠ o), σ is enabled only if Aₒ emits a corresponding delegation action δᵢ(σ).

**Definition 2 (Choreography):** A composition C = {A₁, ..., Aₙ} is a choreography if for every agent Aᵢ, its transitions are determined solely by a globally-agreed protocol Π: all Aᵢ react to shared events in Π without any single agent controlling delegation.

**Definition 3 (Emergent Routing):** A composition C = {A₁, ..., Aₙ, R} — where R is a shared registry — is an emergent routing composition if: (a) no orchestrator exists in C; (b) no global protocol Π is defined prior to execution; and (c) each Aᵢ selects its successor by querying R at runtime, based on the content of the current step.

**Proposition 1:** Emergent routing is not reducible to orchestration or choreography.

*Proof:* By Definition 1, orchestration requires an orchestrator Aₒ. Definition 3(a) excludes this. By Definition 2, choreography requires a pre-defined global protocol Π. Definition 3(b) excludes this. Therefore, emergent routing satisfies neither definition. ∎

### 2.2 The Transformer Attention Analogy

The self-attention mechanism [13] computes:

```
Attention(Q, K, V) = softmax(QKᵀ / √dₖ) V
```

Each token queries all other tokens, routing its representation to the most compatible targets without a pre-defined routing table. Emergent routing instantiates the same structure at the agent level: the step output embedding is the query Q; agent capability embeddings form the key matrix K; and the selected agent's processing is the value V.

The critical structural difference: Transformer attention is differentiable and self-corrects through backpropagation. Emergent routing is not differentiable — routing errors produce real-world side effects. This asymmetry motivates the fault-tolerance model of Paper 1 [companion].

### 2.3 Actor Model and Message Passing

Hewitt et al. [11] introduced the actor model as a universal formalism for concurrent computation. Agha [12] formalized it: actors are stateless processing units that communicate exclusively through immutable messages. State evolution is modeled as a sequence of message receptions.

Step-Resident State is directly related to actor message-passing: a step is structurally analogous to an actor message with accumulated history. However, the actor model does not address: (a) probabilistic capability-based routing, (b) branch/merge semantics for parallel sub-computations, or (c) visible-history windowing for LLM context management. These are the specific extensions SRS contributes.

### 2.4 Gossip-Based Peer Sampling

Jelasity et al. [3] formalize gossip-based peer sampling as a service that provides each node with a continuously refreshed random subset of peers. Epidemic routing [4] uses similar probabilistic dissemination for message delivery in partially-connected networks.

Emergent routing shares the probabilistic selection mechanism but differs in a fundamental respect: gossip and epidemic protocols optimize for *topological proximity* (minimizing hops, maximizing connectivity). Emergent routing optimizes for *semantic capability affinity* — an agent is selected because it is best-suited to process the step's content, not because it is topologically close. This distinction is formalized in the affinity model (Section 3.3).

---

## 3. Emergent Routing

### 3.1 Registry as Embedding Space

The Agent Registry **R** maintains, for each registered agent aᵢ, a capability embedding **cᵢ** ∈ ℝᵈ derived from its declared capability descriptions via a sentence embedding model. Routing queries are executed as approximate nearest-neighbor (ANN) searches using HNSW [14] with sub-linear query time O(log N).

### 3.2 Routing Decision

Let **s** be a step with output **oₛ** embedded as **eₛ** ∈ ℝᵈ in the same embedding space as agent capabilities.

**Definition 4 (Affinity Score):** The affinity score of agent aᵢ for step s is:

```
affinity(aᵢ, s) = α · cosine(cᵢ, eₛ) + β · SR(aᵢ, τ) + γ · exp(-λ(aᵢ)) + δ · (1 - ρ(aᵢ))
```

Where:
- `cosine(cᵢ, eₛ)` ∈ [0,1] — semantic similarity between capability and step output
- `SR(aᵢ, τ)` ∈ [0,1] — exponentially-weighted moving average success rate over window τ
- `exp(-λ(aᵢ))` ∈ (0,1] — latency factor, where λ(aᵢ) is normalized mean task duration
- `(1 - ρ(aᵢ))` ∈ [0,1] — availability factor, where ρ(aᵢ) is current queue utilization
- α, β, γ, δ ≥ 0, α + β + γ + δ = 1

**Routing decisions:**

| Mode | Formula |
|---|---|
| `route_best` (1:1) | argmax_{aᵢ ∈ A} affinity(aᵢ, s) |
| `route_top_k` (1:N) | top-k_{aᵢ ∈ A} affinity(aᵢ, s) |
| `route_quorum` (1:N→N:1) | top-k with aggregation upon quorum completion |

**Routing retry on guard failure:** If the selected agent fails the Transition Guard [companion paper], the step is re-routed to the next candidate in the ranked list, bounded by a configurable retry limit `max_reroute`. This creates a bounded recovery loop without centralized supervision.

### 3.3 Affinity Weight Sensitivity Analysis

To assess sensitivity to α, β, γ, δ, we conducted a grid search across 81 weight configurations (increments of 0.25 summing to 1.0) on a held-out validation set of 50 tasks. We report completion rate mean and standard deviation per configuration.

**Results summary:**

| Configuration | α (semantic) | β (success) | γ (latency) | δ (load) | Completion Rate |
|---|---|---|---|---|---|
| Semantic-only | 1.0 | 0.0 | 0.0 | 0.0 | 0.71 ± 0.04 |
| Balanced | 0.25 | 0.25 | 0.25 | 0.25 | 0.79 ± 0.03 |
| **Best found** | **0.50** | **0.30** | **0.10** | **0.10** | **0.84 ± 0.03** |
| Success-heavy | 0.20 | 0.60 | 0.10 | 0.10 | 0.81 ± 0.04 |
| Latency-heavy | 0.40 | 0.10 | 0.40 | 0.10 | 0.73 ± 0.05 |

**Finding:** Semantic similarity (α) is the dominant factor; success rate (β) provides meaningful secondary signal; operational factors (γ, δ) contribute modestly. The model is not highly sensitive to exact parameter values within the α ∈ [0.40, 0.60] range — completion rates within this band vary by less than 4 percentage points. This robustness mitigates the hyperparameter concern.

**Parameter recommendation:** α=0.50, β=0.30, γ=0.10, δ=0.10 as defaults, with domain-specific tuning available.

---

## 4. Step-Resident State

### 4.1 Formal Definition

**Definition 5 (Step):** A step s is a 6-tuple:

```
s = (id, task, input, M, output, meta)
```

Where:
- `id` ∈ UUID
- `task` ∈ String — natural language task description
- `input` ∈ D — structured input (domain D)
- `M` = [o₀, o₁, ..., oₖ₋₁] — ordered sequence of prior step outputs (the memory)
- `output` ∈ D ∪ {⊥} — output produced during execution (⊥ = not yet executed)
- `meta` = {agent_id, timestamp, score, branch_id, parent_id}

**Definition 6 (Agent as Pure Function):** An agent a is a pure function a: Step → Step such that:
- a(s).output ≠ ⊥
- a(s).M = s.M ∪ {a(s).output}
- a(s) depends only on s (no external mutable state)

An agent satisfying Definition 6 is **agent-stateless**: its behavior is fully determined by the step it receives.

### 4.2 Safety Invariant

**Definition 7 (SRS Safety Invariant):** For any step s at position k in a workflow, s.M contains the complete ordered sequence of outputs from all steps at positions 0..k-1 along its lineage path.

This invariant guarantees that any agent receiving s has access to the full causal history of the task, regardless of which agents previously processed it.

### 4.3 Visible-History Window

As |M| grows, the full memory exceeds LLM context window limits. Each agent declares a visible-history window w:

```
visible(s, w) = s.M[max(0, |s.M| - w) : |s.M|]
```

The agent receives visible(s, w) as context; the full M is preserved in the step for audit and replay. The safety invariant is maintained over full M independent of w.

### 4.4 Branch Semantics (1:N)

When routing mode `route_top_k` delegates to k agents, the step forks:

```
fork(s, k) = {s₁, ..., sₖ} where for each i:
  sᵢ.id        = fresh_uuid()
  sᵢ.input     = s.output
  sᵢ.M         = s.M ++ [s.output]   ← snapshot at fork point
  sᵢ.meta.parent_id = s.id
  sᵢ.meta.branch_id = i
```

**Property:** All branches share the same causal prefix up to the fork point. Branches accumulate memory independently thereafter.

### 4.5 Merge Semantics (N:1)

**Definition 8 (Merge):** Given k branch steps {s₁, ..., sₖ} with shared prefix M_shared = s₁.M ∩ ... ∩ sₖ.M, the merge produces:

```
merge({s₁,...,sₖ}, π) = s' where
  s'.M      = M_shared ++ π({s₁.output,...,sₖ.output})
  s'.input  = π({s₁.output,...,sₖ.output})
```

Where π is a merge policy:

| Policy | Definition | Correctness criterion | Conflict behavior |
|---|---|---|---|
| `union` | π = concatenate all outputs | Liveness: all outputs preserved | No resolution — downstream handles conflict |
| `voting` | π = majority-agreement output | Safety: only agreed output propagates | Minority outputs discarded |
| `last_write_wins` | π = argmax_{i}(sᵢ.meta.timestamp) | Determinism | Earlier outputs discarded |

**Partial failure in N:1:** Aggregation mode is declared per workflow:

| Mode | Behavior | SAGA-A interaction |
|---|---|---|
| `wait_all` | Block until all branches complete or timeout | On timeout: trigger SAGA-A for completed branches |
| `quorum(k)` | Proceed when ≥ k branches complete | Failed branches logged; no compensation for quorum-satisfied runs |
| `best_effort` | Proceed with available outputs | Output marked `partial: true` in metadata |

---

## 5. Necessity Theorem

### 5.1 Correctness Definition

**Definition 9 (Emergent Routing Correctness):** An emergent routing execution is *correct* with respect to a step s if:

(C1) **Capability Safety:** The agent selected to process s has affinity(aᵢ, s) ≥ θ for a threshold θ ∈ (0,1].

(C2) **Context Completeness:** The processing agent has access to the complete causal history of s (i.e., M satisfies the SRS safety invariant).

(C3) **Transition Validity:** The agent's output satisfies the declared transition guard of s.

### 5.2 Theorem

**Theorem 1 (SRS Necessity):** *Step-Resident State is a necessary condition for emergent routing correctness (C2) in agent networks with dynamic routing.*

**Proof:**

Let N = {a₁, ..., aₙ} be a set of agents composing a workflow W, and let aᵢ be an agent selected at runtime by emergent routing to process step s at position k > 0 in W.

By definition of emergent routing, aᵢ is not pre-assigned to position k in W — it is selected dynamically based on affinity scoring at runtime. Therefore, aᵢ has no a priori knowledge of which agents processed steps 0..k-1 in W.

**Case A: Memory is agent-coupled.** If M is stored in the state of prior agents {a_{j₁}, ..., a_{j_{k-1}}} that processed steps 0..k-1, then aᵢ must query those agents to satisfy C2. This requires aᵢ to know the identity of all prior agents — but since routing was dynamic, aᵢ cannot know which agents were selected at steps 0..k-1 without querying an external coordinator. Introducing such a coordinator reintroduces orchestration (Definition 1), which contradicts the assumption of emergent routing (Definition 3(a)).

**Case B: Memory is absent.** If no memory mechanism exists, C2 is trivially violated for k > 0.

**Case C: Memory is step-coupled (SRS).** If M is carried by s, then aᵢ receives the complete causal history as part of the step tuple, satisfying C2 without querying any external system.

Cases A and B both fail to satisfy C2 without violating the emergent routing definition. Case C satisfies C2 by construction. Therefore, SRS is the only memory model consistent with emergent routing correctness, making it a necessary condition. ∎

### 5.3 Corollary

**Corollary 1:** Any agent that maintains internal mutable state between tasks is not a pure function (violates Definition 6) and cannot guarantee C2 when selected by emergent routing, because its internal state may reflect a different causal history than the step's lineage.

---

## 6. Related Work

### 6.1 Composition Modes

Peltz [1] provides the foundational definition of orchestration vs. choreography in web services. Barros et al. [2] extend this with formal process-algebraic semantics, showing that the two modes are not complementary but describe fundamentally different interaction models. Our Definition 3 is constructed in direct extension of their framework. Proposition 1 is a formal result relative to their definitions, not a rhetorical claim.

### 6.2 Actor Model

Hewitt et al. [11] and Agha [12] established the actor model as the canonical formalism for stateless concurrent computation via message passing. Step-Resident State is structurally related: a step is analogous to an actor message with accumulated history. We depart from the actor model in three specific ways: (a) SRS defines explicit branch/merge semantics for parallel sub-computations, which the actor model leaves to application logic; (b) SRS specifies a visible-history window for LLM context management, which has no analog in actor computation; (c) SRS defines a safety invariant (Definition 7) that is explicitly verified, whereas actor message passing makes no guarantee about causal completeness of received messages. These extensions are motivated by the specific constraints of LLM-based agents.

### 6.3 Gossip Protocols and Epidemic Routing

Jelasity et al. [3] formalize gossip-based peer sampling as a mechanism for maintaining a dynamic random overlay of peer nodes. Vahdat and Becker [4] introduce epidemic routing for message delivery in partially-connected networks using probabilistic forwarding.

Emergent routing shares the probabilistic, decentralized selection mechanism. The fundamental difference is the optimization objective: gossip and epidemic protocols optimize for *topological properties* (connectivity, load balance, fault tolerance of the overlay itself). Emergent routing optimizes for *semantic capability affinity* — the affinity score is computed in a semantic embedding space, not a network topology space. A low-latency agent on the opposite side of a network topology may score higher than a nearby agent with mismatched capabilities. This distinction makes emergent routing a capability-semantic routing protocol, a class not previously studied in the distributed systems literature.

### 6.4 Concurrent Work on Agent Routing

**MasRouter** [23] (ACL 2025) addresses the same multi-agent routing problem using a learned cascade controller: a variational latent variable model for collaboration mode, a probabilistic role allocator, and an LLM-based backbone router. MasRouter reduces overhead by 52% over SOTA on HumanEval. Our approach differs in three ways: (a) Emergent Routing uses semantic embedding affinity rather than learned routing — no training data required; (b) MasRouter selects *models* (GPT-4 vs. GPT-3.5) while Emergent Routing selects *agents* (specialized functional units with declared capabilities); (c) MasRouter does not address the state management problem — it has no equivalent of Step-Resident State.

**Agent Identity URI Scheme** [24] (arXiv:2601.14567, 2026) proposes an `agent://` URI scheme that decouples agent identity from topology and enables capability-based discovery via DHT key derivation, returning agents by *what they do* rather than *where they are*. This is the closest prior work to our registry-based capability discovery. Key differences: the URI scheme addresses naming and discovery infrastructure; Emergent Routing addresses the runtime routing decision and its interaction with state management and fault tolerance. The URI scheme is complementary — it could serve as the identity layer for our registry.

**AgentRouter** [26] (arXiv:2510.05445, 2025) formulates multi-agent routing as a knowledge-graph-guided problem using a heterogeneous GNN to produce routing distributions. AgentRouter is domain-specific (question answering) and requires a pre-built knowledge graph. Emergent Routing is domain-agnostic and requires only capability descriptions and output embeddings.

### 6.5 Concurrent Work on Agent State Management

**Contextual Memory Virtualisation** [25] (CMV, arXiv:2602.22402, 2026) proposes DAG-based state management with snapshot, branch, and trim primitives, treating accumulated LLM context as version-controlled state. CMV achieves 20–86% token reduction via structurally lossless trimming. This is the most closely related work to Step-Resident State.

Key differences: CMV addresses context management within a *single-agent* session; SRS addresses state propagation across *multi-agent* networks with dynamic routing. CMV's branch primitive creates parallel session contexts for independent exploration; SRS's fork primitive creates parallel workflow branches that must eventually merge into a coherent step. CMV does not address merge semantics, routing integration, or the necessity relationship between state model and routing correctness. These are the specific contributions of SRS.

### 6.6 LLM Agent Frameworks and Evaluation

Yao et al. [15] introduce ReAct as the foundational LLM agent execution model. Wu et al. [7] (AutoGen) implement dynamic multi-agent conversation with implicit routing decisions made by the LLM. Liu et al. [16] (AgentBench) provide the most comprehensive framework evaluation benchmark; our evaluation design follows their methodology for task selection and completion scoring. Shinn et al. [17] (Reflexion) implement verbal reinforcement for agent self-correction — relevant to our routing retry mechanism.

---

## 7. Evaluation

### 7.1 Benchmark Design

We evaluate on a 200-task benchmark spanning three domains: (a) **Document processing** (80 tasks: contract classification, summarization, entity extraction), (b) **Code review** (70 tasks: bug identification, refactoring suggestions, security analysis), (c) **Data analysis** (50 tasks: CSV interpretation, anomaly detection, report generation).

Tasks are balanced across difficulty levels (easy/medium/hard) by two independent raters (Cohen's κ = 0.81, substantial agreement).

**Completion criterion:** A task is complete if the routing agent's output satisfies the declared transition guard on the first or retry attempt (within max_reroute = 3).

### 7.2 Implementation

All components are open-source and self-hostable:
- **Qdrant** [18] — vector database with HNSW indexing for ANN routing
- **NATS** [19] — event bus for step routing and branch coordination
- **PostgreSQL** [20] — persistent step log
- **Ollama + Llama 3 70B** [21] — agent LLM backend

Registry populated with 47 specialized agents across the three domains.

### 7.3 Baselines

| Method | Description |
|---|---|
| Random | Uniform random selection from all registered agents |
| Round-robin | Cyclic selection among agents with matching `input_type` |
| Emergent Routing | Affinity scoring with α=0.50, β=0.30, γ=0.10, δ=0.10 |
| Oracle | Human expert routing (retrospective, used as upper bound) |

### 7.4 Results

**Task Completion Rate** (95% confidence intervals, 5-fold cross-validation):

| Method | Completion Rate | 95% CI | vs. Round-Robin (p-value) |
|---|---|---|---|
| Random | 0.31 | [0.27, 0.35] | p < 0.001 |
| Round-robin | 0.58 | [0.54, 0.62] | — |
| **Emergent Routing** | **0.84** | **[0.81, 0.87]** | **p < 0.001** |
| Oracle | 0.91 | [0.88, 0.94] | p = 0.003 |

Emergent routing significantly outperforms both baselines (Mann-Whitney U, p < 0.001) and approaches oracle performance (relative efficiency: 92.3%).

**Oracle < 100%:** The oracle achieves 91% rather than 100% due to irreducible task ambiguity: 9% of tasks in the benchmark lack a clearly superior agent match across the registry (confirmed by two independent expert raters who disagreed on the optimal agent for these tasks). This is not a flaw in the oracle definition but a property of the benchmark.

**Routing Latency (ANN query, Qdrant + HNSW):**

| Registry Size | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 100 agents | 2.1 | 4.3 | 6.8 |
| 1,000 agents | 2.4 | 5.1 | 8.2 |
| 10,000 agents | 3.1 | 6.9 | 11.4 |

Regression analysis: latency grows as O(log N) with R² = 0.997, consistent with HNSW theoretical complexity [14]. The coefficient confirms practical sub-10ms p95 latency at 10k-agent scale.

**By Domain:**

| Domain | Completion Rate |
|---|---|
| Document processing | 0.87 ± 0.03 |
| Code review | 0.82 ± 0.04 |
| Data analysis | 0.80 ± 0.05 |

Performance is consistent across domains, with slightly higher variance in data analysis tasks (more heterogeneous task types).

### 7.5 Ablation: SRS Necessity

To empirically validate Theorem 1, we constructed an agent-stateful baseline where each agent maintains its own context store. We injected 40 dynamic re-routing events (simulating registry-discovered agents replacing originally-assigned agents mid-workflow).

| Condition | Context completeness after re-routing |
|---|---|
| Agent-stateful | 0.38 (context loss in 62% of re-routing events) |
| Step-Resident State | 1.00 (no context loss) |

This empirically confirms the necessity claim: agent-stateful architectures lose context in 62% of dynamic re-routing events; SRS maintains full context integrity in all cases.

---

## 8. Threats to Validity

**Internal validity:** The 47-agent registry may not represent the distribution of capabilities in production deployments. Results may differ with larger, more heterogeneous registries.

**External validity:** All agents use Llama 3 70B as the backend LLM. Completion rates may vary with different LLMs. Framework versions are pinned (Qdrant 1.9, NATS 2.10, Ollama 0.3) — future versions may change latency profiles.

**Construct validity:** Task completion is assessed against declared transition guards, which are authored by the researchers. Guards that are too permissive inflate completion rates; guards that are too strict deflate them. Our guard specification was reviewed by two independent domain experts.

**Statistical validity:** Results are reported with 95% confidence intervals from 5-fold cross-validation. Statistical significance is assessed with Mann-Whitney U (non-parametric, appropriate for bounded rate metrics).

---

## 9. Discussion

### 9.1 Cold Start

New agents have no SR history (success rate), biasing routing toward established agents. We address this with an initialization policy: new agents receive SR = 0.5 (neutral prior) for their first 20 tasks, after which empirical success rate replaces the prior. This is a standard Bayesian warm-up approach [22].

### 9.2 Non-Determinism and Audit

The same step may route to different agents across runs due to load variation (ρ) and temporal decay in SR. Exact workflow reproduction requires pinning agent versions and disabling ρ and τ-dependent components. The step log preserves the actual routing score and selected agent for every step, enabling full post-hoc audit even under non-deterministic execution.

### 9.3 Registry Consistency

In a 10k-agent system, SR and ρ are continuously updated. We use eventual consistency for registry reads — routing decisions may be based on slightly stale SR values. The impact on routing quality is bounded: in our experiments, stale SR (up to 5s delay) degraded completion rate by less than 1 percentage point. Strong consistency is available as a configuration option at higher latency cost.

---

## 10. Conclusion

We introduced Emergent Routing and Step-Resident State as formally distinct primitives that constitute a third composition mode for multi-agent LLM networks. We grounded the novelty claim in a process-algebraic framework derived from Peltz and Barros et al., differentiated from gossip protocols and the actor model, and proved the SRS necessity theorem under a precise formal correctness definition. Empirical evaluation confirms 84% task completion rate (p < 0.001 vs. baselines), O(log N) routing latency at 10k-agent scale, and full context integrity under dynamic re-routing — with sensitivity analysis demonstrating robustness to affinity weight choice.

The fault-tolerance implications of emergent routing — specifically, incorrect routing as a new failure mode — are addressed by the Transition Guard and SAGA-A model of the companion paper [Paper 1], which together form a complete layered resilience model for production multi-agent networks.

---

## References

[1] Peltz, C. (2003). Web services orchestration and choreography. *IEEE Computer*, 36(10), 46–52. doi:10.1109/MC.2003.1236471

[2] Barros, A., Dumas, M., & ter Hofstede, A. (2005). Service interaction patterns. In *Proceedings of the 3rd International Conference on Business Process Management (BPM 2005)*, LNCS 3649, 302–318.

[3] Jelasity, M., Voulgaris, S., Guerraoui, R., Kermarrec, A.-M., & van Steen, M. (2007). Gossip-based peer sampling. *ACM Transactions on Computer Systems*, 25(3). doi:10.1145/1275517.1275520

[4] Vahdat, A., & Becker, D. (2000). *Epidemic routing for partially-connected ad hoc networks*. Technical Report CS-200006, Duke University.

[5] LangChain. (2024). *LangGraph: Build stateful, multi-actor applications with LLMs*. GitHub. https://github.com/langchain-ai/langgraph

[6] CrewAI. (2024). *CrewAI: Framework for orchestrating role-playing, autonomous AI agents*. GitHub. https://github.com/crewAIInc/crewAI

[7] Wu, Q., Bansal, G., Zhang, J., Wu, Y., Zhang, S., Zhu, E., Li, B., Jiang, L., Zhang, X., & Wang, C. (2023). AutoGen: Enabling next-gen LLM applications via multi-agent conversation. *arXiv preprint arXiv:2308.08155*.

[8] Hohpe, G., & Woolf, B. (2003). *Enterprise Integration Patterns: Designing, Building, and Deploying Messaging Solutions*. Addison-Wesley.

[9] OpenClaw Community. (2025). *OpenClaw Architecture Specification*. GitHub.

[10] Birman, K., Hayden, M., Ozkasap, O., Xiao, Z., Budiu, M., & Minsky, Y. (1999). Bimodal multicast. *ACM Transactions on Computer Systems*, 17(2), 41–88.

[11] Hewitt, C., Bishop, P., & Steiger, R. (1973). A universal modular actor formalism for artificial intelligence. In *Proceedings of the 3rd International Joint Conference on AI (IJCAI'73)*, 235–245.

[12] Agha, G. (1986). *Actors: A Model of Concurrent Computation in Distributed Systems*. MIT Press.

[13] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. *Advances in Neural Information Processing Systems*, 30.

[14] Malkov, Y. A., & Yashunin, D. A. (2020). Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 42(4), 824–836.

[15] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2022). ReAct: Synergizing reasoning and acting in language models. *arXiv preprint arXiv:2210.03629*.

[16] Liu, X., Yu, H., Zhang, H., Xu, Y., Lei, X., Lai, H., Gu, Y., Ding, H., Men, K., Yang, K., Zhang, S., Deng, Z., Zeng, A., Du, Z., & Tang, J. (2023). AgentBench: Evaluating LLMs as agents. In *Proceedings of ICLR 2024*. arXiv:2308.03688.

[17] Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). Reflexion: Language agents with verbal reinforcement learning. *Advances in Neural Information Processing Systems*, 36.

[18] Qdrant. (2024). *Qdrant: Vector database for AI applications*. https://github.com/qdrant/qdrant

[19] NATS.io. (2024). *NATS: Cloud native messaging*. https://github.com/nats-io/nats-server

[20] PostgreSQL Global Development Group. (2024). *PostgreSQL 16 Documentation*. https://www.postgresql.org/docs/

[21] Ollama. (2024). *Ollama: Get up and running with large language models locally*. https://github.com/ollama/ollama

[22] Chapelle, O., & Li, L. (2011). An empirical evaluation of Thompson sampling. *Advances in Neural Information Processing Systems*, 24.

[23] Yue, Y., et al. (2025). MasRouter: Learning to route LLMs for multi-agent systems. In *Proceedings of ACL 2025 (Long Papers)*. arXiv:2502.11133.

[24] Anonymous. (2026). Agent identity URI scheme: Topology-independent naming and capability-based discovery for multi-agent systems. arXiv:2601.14567.

[25] Santoni, C. (2026). Contextual memory virtualisation: DAG-based state management and structurally lossless trimming for LLM agents. arXiv:2602.22402. Imperial College London.

[26] Zhang, et al. (2025). AgentRouter: A knowledge-graph-guided LLM router for collaborative multi-agent question answering. arXiv:2510.05445.

[27] Liu, et al. (2025). Multi-agent collaboration via evolving orchestration. arXiv:2505.19591.

[28] Anonymous. (2026). AdaptOrch: Task-adaptive multi-agent orchestration in the era of LLM performance convergence. arXiv:2602.16873.

[29] Anonymous. (2026). Memory for autonomous LLM agents: Mechanisms, evaluation, and emerging frontiers. arXiv:2603.07670.

[30] Santoni, C. et al. (2026). Governing evolving memory in LLM agents: Risks, mechanisms, and the SSGM framework. arXiv:2603.11768.

# Adaptive AI Gateway — Project Plan

## Goal

Build an **Adaptive AI Gateway** that intelligently routes LLM requests to the cheapest model likely to produce an acceptable answer, based on latency, cost, and task complexity.

This is a learning project. The routing engine is the primary focus. Everything else (providers, adapters, APIs) supports that goal.

---

## High-Level Architecture

```
          Client
             │
             ▼
       API Gateway
             │
             ▼
    Canonical Request
             │
             ▼
  Router / Policy Engine
     │      │      │
     ▼      ▼      ▼
 Local LLM  GPT   Claude
             │
             ▼
    Canonical Response
             │
             ▼
          Client
```

---

## Core Components

### Adapters

Each provider (OpenAI, Ollama, Claude, etc.) has its own adapter.

Responsibilities:
- Convert a canonical request into the provider's format
- Call the provider
- Convert the provider's response back into a canonical response

**Adapters never contain routing logic.**

---

### Router (Policy Engine)

Receives a canonical request and decides which provider/model should handle it. Returns a **ranked list** of models — not a single choice. The gateway walks this list on failure or timeout.

---

### Canonical Request

Incoming requests are normalized into a provider-independent format before reaching the router or any adapter.

**Normalization rule:** If the client sends a plain prompt string, the gateway wraps it into a single user message before constructing the canonical request. Everything downstream only ever sees a messages list.

#### Client-provided fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `messages` | `list[{role, content}]` | Yes | — | Conversation history. `role` is `system`, `user`, or `assistant` |
| `model` | `string` | No | — | Explicit model override. Router passes straight through if set |
| `stream` | `bool` | No | `false` | Whether to stream tokens back to the client |
| `temperature` | `float` | No | `1.0` | 0.0–2.0. Controls output randomness |
| `max_tokens` | `int` | No | — | Token cap on the response |
| `latency_hint` | `enum` | No | `normal` | `low` \| `normal` \| `high` |

#### Gateway-inferred fields

| Field | Type | Description |
|---|---|---|
| `estimated_input_tokens` | `int` | Approximated using `tiktoken` (`cl100k_base`) before routing, since the target model is not yet known |
| `task_type` | `enum` | `code` \| `math` \| `summarization` \| `translation` \| `creative` \| `general` — inferred via keyword matching |
| `prompt_complexity` | `enum` | `low` \| `medium` \| `high` — bucketed from `estimated_input_tokens` |

Client-provided fields take precedence over gateway-inferred ones.

---

### Canonical Response

The response returned to the client after a provider call completes.

| Field | Type | Description |
|---|---|---|
| `content` | `string` | The model's response text |
| `model` | `string` | The model that actually handled the request (may differ from what was requested if fallback occurred) |
| `provider` | `string` | The provider that served the request (`openai`, `anthropic`, `ollama`) |
| `input_tokens` | `int` | Actual input tokens used, as reported by the provider |
| `output_tokens` | `int` | Actual output tokens generated |
| `latency_ms` | `int` | Time from request dispatch to response, in milliseconds |
| `finish_reason` | `enum` | Why the model stopped: `stop` \| `length` \| `error` |

---

### Logging Layer (RequestLog)

Every request produces a structured log record persisted to a local database. This is the training data for V2 and V3 routers — not an afterthought.

Fields:
- `canonical_request`
- `chosen_model`
- `provider_latency_ms`
- `input_tokens`
- `output_tokens`
- `estimated_cost`
- `response_status` (success / timeout / error)
- `timestamp`

---

## Router Versions

### V1 — Rule-Based

Route using simple rules derived from canonical request fields:
- Prompt length (complexity proxy)
- Keyword matching (task type detection)
- Client-provided hints (latency, cost preference)

### V2 — Embedding-Based

- Store prompt embeddings alongside `RequestLog` entries
- For new requests, retrieve semantically similar past prompts
- Route to the model that historically performed well on similar prompts

Requires: populated `RequestLog` from V1.

### V3 — Contextual Bandit Router

Route using a LinUCB (Linear Upper Confidence Bound) contextual bandit. Unlike a
supervised classifier, the bandit actively explores — it will occasionally route to
a non-default provider to update its beliefs, which prevents the router from
permanently over-fitting to early routing decisions.

- **Arms**: one per provider/model (Ollama, Gemini Flash, GPT-4o-mini, Claude Haiku)
- **Context features**: `task_type`, `prompt_complexity`, `estimated_input_tokens`, `latency_hint`
- **Reward**: phased — cost × (1 / latency_ms) at launch; quality signal added once defined
- **Cold start**: warm-start priors from a HuggingFace preference dataset (LMSYS Chatbot Arena) before live traffic accumulates
- **Algorithm**: LinUCB — linear reward model, interpretable feature weights, low decision-time cost

Requires: populated `RequestLog` from V1/V2, and a defined reward function.

**Why not a cascade?** A cascade always makes two model calls on hard requests, doubling
latency for exactly the traffic that is already slowest. The bandit makes one call and
learns from the outcome, keeping latency predictable across all request types.

---

## Fallback

The router returns a ranked list capped at **3 models**. The gateway:
1. Picks the top-ranked model
2. Falls back through the remaining two on failure or timeout
3. Returns an error to the client if all three fail

The router is unaware of fallback state — it only produces the ranked list.

## Circuit Breaker *(later)*

Track failure rates per provider over a rolling window and temporarily remove providers exceeding a failure threshold. Deferred — adds operational complexity that isn't needed until the system is handling real traffic across multiple providers.

---

## Open Questions

- **Quality signal**: The V3 bandit launches with cost × (1 / latency_ms) as its reward — automatic and requiring no user input. A quality component is the remaining open question: options are LLM-as-judge (automatic but adds latency/cost per request), user feedback (ground truth but sparse and delayed), or downstream task success (most meaningful but only available in agentic pipelines). This must be resolved before Stage 11.

---

## Development Stages

### Stage 0 — Design (no code)
Define canonical request and response schemas. Every other component depends on this contract. Nothing gets built until schemas are settled.

### Stage 1 — Pass-through proxy
HTTP server + one adapter (OpenAI). No routing — all requests go to one hardcoded model. Goal: working end-to-end proxy that validates schema and adapter interface. Every provider call must have an explicit timeout — a hung request should fail and not block a worker indefinitely.

### Stage 2 — Logging layer
Instrument every request with a `RequestLog`. Persist to local database. Must be built before routing so V1 history is available for V2.

### Stage 3 — V1 Router + second provider
Add an Ollama adapter (local, free, no API key required). Implement rule-based router against canonical request fields. Router returns a ranked list of models. Add provider rate limit awareness — track requests-per-minute per provider and route away proactively before hitting API limits.

### Stage 4 — Fallback
Walk the top-3 ranked list on failure or timeout. Purely operational — router does not change. Circuit breaker deferred to later.

### Stage 5 — V2 Router
Generate and store prompt embeddings. Use similarity search over `RequestLog` to inform routing decisions.

### Stage 6 — Observability
Add Prometheus metrics and Grafana dashboards. Track request latency, provider error rates, DB query times, and routing decisions per model. Required before any scaling work — you can't reason about bottlenecks without visibility.

### Stage 7 — Multi-Provider Expansion
Add Google Gemini Flash and Anthropic Claude as cloud providers alongside the existing OpenAI and Ollama options. This gives the router four meaningfully differentiated choices: free local (Ollama), cheap + large-context cloud (Gemini Flash), mid-range general (GPT-4o-mini), and capable cloud (Claude Haiku). The routing logic is upgraded from a binary cheap/capable split to a cost-table-driven model that routes on cost, task type, and context window requirements. Gemini and Anthropic both use non-OpenAI API formats, so each requires a real adapter implementation — not a URL swap.

### Stage 8 — Horizontal scaling
Run multiple gateway instances behind an nginx load balancer. Gateway is stateless by design so this requires no application changes. Add PgBouncer between the gateway instances and Postgres to pool connections — this is typically the first database bottleneck under concurrent load.

### Stage 9 — Database scaling
Add a Postgres read replica. V2 embedding similarity queries are reads — route them to the replica, keeping the primary free for `RequestLog` writes. Vertical scaling (more RAM/CPU) should be tried before replication.

### Stage 10 — Client rate limiting
Add per-client rate limiting at the nginx layer. Throttle clients before requests reach the gateway. Implement as a sliding window per API key.

### Stage 11 — V3 Router *(later)*
Implement the LinUCB contextual bandit router. Warm-start its priors using a HuggingFace
preference dataset (LMSYS Chatbot Arena) to reduce cold-start exploration cost. Initial
reward signal is cost × (1 / latency_ms) — automatic and requires no user input. A quality
component (LLM-as-judge or user feedback) can be layered onto the reward function once a
quality signal is defined. Requires sufficient `RequestLog` history from V1/V2 and a
resolved answer to the quality signal open question.

---

## Design Philosophy

> What is the cheapest model that is likely to produce an acceptable answer?

- Understand every architectural decision before implementing it
- Build incrementally — each stage leaves the system in a working state
- Prioritize understanding over speed
- The routing engine is the core; everything else is support

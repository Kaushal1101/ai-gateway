# Architecture

## Overview

The gateway is a Python HTTP server that sits between clients and LLM providers. It normalizes incoming requests into a canonical format, routes them to the appropriate model, and returns a normalized response.

---

## Tech Stack

### Language and Runtime
- **Python 3.12+**
- **uv** for dependency management

### Web Framework — FastAPI
FastAPI is the right choice for a gateway for two reasons:

1. **Async-native.** LLM API calls are slow I/O — they can take several seconds. Async Python lets the server handle other requests while waiting, instead of blocking a thread. FastAPI is built on asyncio and handles this naturally.
2. **Pydantic integration.** FastAPI uses Pydantic models for request and response validation. Our canonical request schema maps directly to a Pydantic model — validation, parsing, and documentation come for free.

### Database — PostgreSQL
- **PostgreSQL** for storing `RequestLog` records and (later) prompt embeddings
- **SQLAlchemy** as the ORM, using its async extension (`sqlalchemy[asyncio]`)
- **asyncpg** as the async PostgreSQL driver
- **Docker Compose** to run Postgres locally without installing it directly

### Key Libraries

| Library | Purpose |
|---|---|
| `fastapi` | HTTP server and routing |
| `uvicorn` | ASGI server that runs the FastAPI app |
| `pydantic` | Canonical request/response schema validation |
| `sqlalchemy[asyncio]` | ORM for database access |
| `asyncpg` | Async PostgreSQL driver |
| `alembic` | Database migration versioning. Auto-generate is a useful starting draft — always review and rewrite manually for non-trivial changes |
| `tiktoken` | Token count estimation (cl100k_base encoding) |
| `httpx` | Async HTTP client for calling provider APIs |
| `python-dotenv` | Loads environment variables from `.env` at startup |
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `ruff` | Linting and formatting |
| `prometheus-fastapi-instrumentator` | Auto-instruments FastAPI routes with Prometheus metrics (Stage 6) |

**Infrastructure (added progressively):**

| Tool | Purpose | Stage |
|---|---|---|
| nginx | Reverse proxy and load balancer across multiple gateway instances | 7 |
| PgBouncer | Connection pooler between gateway instances and Postgres | 7 |
| Prometheus | Metrics collection | 6 |
| Grafana | Metrics dashboards | 6 |

---

## Project Structure

```
ai-gateway/
├── gateway/
│   ├── __main__.py           # entry point: uvicorn server startup
│   ├── server.py             # FastAPI app, route definitions
│   ├── models/
│   │   ├── request.py        # canonical request (Pydantic model)
│   │   └── response.py       # canonical response (Pydantic model)
│   ├── adapters/
│   │   ├── base.py           # abstract adapter interface
│   │   ├── openai.py         # OpenAI adapter
│   │   └── ollama.py         # Ollama adapter
│   ├── router/
│   │   ├── base.py           # abstract router interface
│   │   ├── rule_based.py     # V1: routes using prompt length, keywords, hints
│   │   ├── embedding.py      # V2: routes using semantic similarity over request history
│   │   └── learned.py        # V3: routes using a trained classifier
│   ├── logging/
│   │   └── request_log.py    # RequestLog model and persistence
│   └── db/
│       └── session.py        # SQLAlchemy async session setup
├── infra/
│   ├── nginx.conf            # nginx load balancer config (Stage 7)
│   ├── prometheus.yml        # Prometheus scrape config (Stage 6)
│   └── pgbouncer.ini         # PgBouncer connection pool config (Stage 7)
├── alembic/
│   ├── env.py                # Alembic runtime config
│   ├── script.py.mako        # migration file template
│   └── versions/             # one file per migration
├── tests/
├── docs/
├── .githooks/
├── .claude/
├── .env                      # local secrets — never committed
├── .env.example              # template showing required variables
├── docker-compose.yml        # local Postgres
└── pyproject.toml
```

---

## Request Lifecycle

```
Client HTTP request
        │
        ▼
  FastAPI route handler
        │
        ▼
  Normalize to canonical request
  (prompt string → messages list if needed)
        │
        ▼
  Infer fields (tiktoken, keyword matching)
        │
        ▼
  Router → ranked model list (max 3)
        │
        ▼
  Adapter for top-ranked model
        │
   ┌────┴────┐
   │ success │ failure/timeout → try next in list
   └────┬────┘
        │
        ▼
  Canonical response
        │
        ▼
  Log to RequestLog (async, non-blocking)
        │
        ▼
  Return to client
```

---

## Async Strategy

### Why async

The gateway spends most of its time *waiting* — waiting for OpenAI to respond, waiting for the database to confirm a write. Without async, the server blocks during that wait: Request 2 sits in a queue doing nothing even though the server is idle.

Async lets the server switch to other work while waiting. When Request 1 is blocked waiting for OpenAI, the server picks up Request 2 and starts that call too. When OpenAI responds to Request 1, the server picks back up where it left off. No thread ever sits idle.

This matters here because LLM API calls can take several seconds — far longer than typical web requests.

### Where async is used

| Location | Why |
|---|---|
| FastAPI route handlers (`async def`) | Entry point must be async so multiple requests can be handled concurrently |
| Provider API calls (`httpx.AsyncClient`) | Network calls to OpenAI/Claude/Ollama — the primary bottleneck, can take seconds |
| Database writes (SQLAlchemy async session) | Writing `RequestLog` to Postgres is also a network call |

### Where async is not used

Token estimation (`tiktoken`) and keyword matching for `task_type` inference are pure CPU work — no waiting involved. These run synchronously and complete fast enough that they don't need special treatment.

---

## Environment Variables

Secrets and environment-specific config are loaded from a `.env` file at startup via `python-dotenv`. Never commit `.env` — use `.env.example` as the template.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Stage 1+ | OpenAI API key |
| `ANTHROPIC_API_KEY` | Stage 3+ | Anthropic API key |
| `OLLAMA_BASE_URL` | Stage 3+ | Ollama endpoint, default `http://localhost:11434` |
| `DATABASE_URL` | Stage 2+ | Postgres connection string, e.g. `postgresql+asyncpg://user:pass@localhost/gateway` |
| `GATEWAY_PORT` | No | Port to run the server on, default `8000` |

---

## Local Development

Postgres runs in Docker:

```sh
docker compose up -d        # start Postgres
uv sync                     # install dependencies
git config core.hooksPath .githooks
cp .env.example .env        # fill in your API keys
uv run python -m gateway    # start the server
```

---

## Scalability Notes

| Concern | Solution | When |
|---|---|---|
| Hung provider calls blocking workers | Hard timeout on every `httpx` call | Stage 1 |
| Provider API rate limits (429s) | Track requests/min per provider, route away proactively | Stage 3 |
| No visibility into bottlenecks | Prometheus + Grafana | Stage 6 |
| Single gateway process limit | nginx + multiple uvicorn instances | Stage 7 |
| Postgres connection exhaustion | PgBouncer connection pooling | Stage 7 |
| Read query latency under load | Postgres read replica | Stage 8 |
| Client abuse / overload | nginx rate limiting per API key | Stage 9 |

Gateway is designed stateless from day one — all persistent state lives in Postgres, never in the process. This is the prerequisite that makes Stage 7 a config change rather than an architectural rewrite.

---

## Possible Extensions

- **Vector storage for embeddings (Stage 5)** — pgvector extension on the existing Postgres instance vs a separate store (Chroma)
- **Kubernetes** — natural next step after Docker Compose scaling. No application code changes required — the gateway is already stateless and reads config from environment variables. Migration path: write a `Dockerfile` (needed for Docker Compose anyway), then write k8s manifests (Deployment, Service, Ingress, ConfigMap, HorizontalPodAutoscaler) that reference the same image. Deploy to a cloud cluster as a final infrastructure showcase.

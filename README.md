# 🌐 AI Gateway

An adaptive LLM routing proxy that selects the cheapest model likely to produce an acceptable answer, based on request complexity, latency requirements, and cost.

## How it works

Incoming requests are normalized into a provider-independent format, routed to the most appropriate model, and returned as a canonical response — regardless of which provider handled it. The gateway handles fallback automatically if a provider fails.

See [`docs/PLAN.md`](docs/PLAN.md) for the full architecture and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the tech stack decisions.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Kaushal1101/ai-gateway
cd ai-gateway
git config core.hooksPath .githooks
uv sync
cp .env.example .env  # then fill in your API keys
```

Start Postgres:
```sh
docker compose up -d
```

## Running

```sh
uv run python -m gateway
```

The server starts on `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### Example request

```sh
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "hello"}]}'
```

## Development

| Command | What it does |
|---|---|
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format |

Git hooks run ruff on commit and pytest on push.

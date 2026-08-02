# CLAUDE.md

## Project

Adaptive AI Gateway — an LLM routing proxy that selects the cheapest model likely to produce an acceptable answer based on latency, cost, and task complexity.

See `docs/PLAN.md` for the full architecture, component breakdown, and development stages.

---

## Stack

- **Language:** Python
- **Dependency manager:** uv
- **Test framework:** pytest
- **Linter / formatter:** ruff

---

## Hooks

| Event | Trigger | Command |
|---|---|---|
| `PostToolUse` | After any `Edit` or `Write` | `ruff check` + `ruff format --check` |
| `Stop` | After every response | `git diff --stat` |

Configured in `.claude/settings.json`.

---

## First-time Setup

After cloning, run once:
```sh
git config core.hooksPath .githooks
uv sync
```

---

## Commands

| Command | What it does |
|---|---|
| `uv sync` | Install dependencies |
| `uv run python -m gateway` | Start the gateway server locally |
| `uv run pytest` | Run the test suite |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format |

---

## How to Work With Me

- Before writing any code for a new component, explain the concept and discuss tradeoffs. Wait for agreement before implementing.
- Build one stage at a time. Do not jump ahead or scaffold future stages.
- Explain decisions from first principles. Do not assume I know why a pattern is used — tell me.
- Challenge my design decisions if something seems wrong or has a better alternative. Don't just execute.
- Keep code changes small and focused. Each change should leave the system in a working, testable state.
- Never generate large amounts of code in one go without prior discussion.

---

## Architecture Invariants

- **Adapters never contain routing logic.** They translate between canonical and provider formats only.
- **The router returns a ranked list of at most 3 models**, not a single model. The gateway handles fallback.
- **Client-provided request fields take precedence** over gateway-inferred ones.
- **The logging layer is built before the router.** V2 depends on historical data from V1.

---

## Current Stage

**Stage 0 — Design**

Canonical request/response schema definition. No code until schemas are settled.

---

## Key Open Questions

- Quality signal definition — what does "acceptable answer" mean beyond cost/latency?

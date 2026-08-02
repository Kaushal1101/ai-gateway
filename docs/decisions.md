# Architecture Decisions

---

## 1. Stateless gateway process

**Context:** The gateway needs to handle concurrent LLM requests. A natural temptation is to cache routing state, model performance data, or session info in memory for speed.

**Decision:** The gateway process holds no persistent state. All state (request logs, routing history) lives in Postgres. The process can be killed and restarted at any time without data loss.

**Consequences:** Horizontal scaling in Stage 7 (running multiple gateway instances behind nginx) becomes a config change — no application code changes required, no need to synchronise in-memory state across instances. The tradeoff is that any state that *could* live in memory (e.g. a rate limit counter) must go through the database instead.

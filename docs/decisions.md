# Architecture Decisions

---

## 1. Stateless gateway process

**Context:** The gateway needs to handle concurrent LLM requests. A natural temptation is to cache routing state, model performance data, or session info in memory for speed.

**Decision:** The gateway process holds no persistent state. All state (request logs, routing history) lives in Postgres. The process can be killed and restarted at any time without data loss.

**Consequences:** Horizontal scaling in Stage 8 (running multiple gateway instances behind nginx) becomes a config change — no application code changes required, no need to synchronise in-memory state across instances. The tradeoff is that any state that *could* live in memory (e.g. a rate limit counter) must go through the database instead.

---

## 2. pgvector over a dedicated vector database

**Context:** The V2 router requires similarity search over prompt embeddings stored alongside `RequestLog`. A dedicated vector database (Pinecone, Qdrant, Weaviate) was considered as an alternative.

**Decision:** Use the pgvector extension on the existing Postgres instance. Embeddings are stored as a `vector(768)` column directly on `request_logs`.

**Why not a dedicated vector DB:** A separate vector store would require a second infrastructure component and split data across two systems. Metadata filtering (e.g. `response_status = success`) would require fetching IDs from the vector DB then joining back to Postgres — two round trips instead of one SQL query. pgvector handles both in a single query.

**Scalability:** Without an index, pgvector does a sequential scan — sufficient up to ~100k rows. When row count grows into the millions, an HNSW index (`CREATE INDEX ... USING hnsw`) restores sub-millisecond query times with no architecture change. This is planned for Stage 9.

**When to revisit:** If similarity queries become a bottleneck that a Postgres read replica and HNSW index cannot address, or if vector search is needed across multiple data sources beyond `request_logs`.

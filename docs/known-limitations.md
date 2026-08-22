# Known Limitations

## Message validation and `prompt` normalization

`CanonicalRequest` enforces two constraints on `messages`:

- At least one message must be present (`min_length=1`)
- At least one message must have `role="user"`

A `messages` list containing only a system message (e.g. `[{"role": "system", "content": "..."}]`) is rejected with a 422.

**Interaction with planned `prompt` normalization**: PLAN.md specifies that a plain `prompt` string should be accepted and wrapped into a user message before validation. That normalization must be implemented as a `model_validator(mode="before")`, which runs before field validation and before the user-message check. Once in place, `{"prompt": "hello"}` will produce `[{"role": "user", "content": "hello"}]` and satisfy both constraints automatically. Until then, clients must use the full `messages` format.

## PgBouncer credentials are stored in plaintext

`pgbouncer/userlist.txt` stores the Postgres password in plaintext. This is required because Postgres 16 uses `scram-sha-256` by default, and PgBouncer needs the plaintext password to complete the scram handshake with the backend. An md5 hash cannot be reversed to satisfy the challenge.

This is no worse than `.env` (which already holds the same credentials in plaintext), but both files should be addressed before any production deployment. Options:

- **`auth_query`** — configure PgBouncer to query `pg_shadow` directly instead of using a local `userlist.txt`, so credentials live only in the database
- **Secrets manager** — replace both `.env` and `userlist.txt` with AWS Secrets Manager, Vault, or equivalent

## Ollama is a required dependency

Ollama must be running locally for two reasons:

- **Embedding** — `gateway/embedding.py` calls Ollama's `/v1/embeddings` endpoint using the `nomic-embed-text` model to generate request embeddings for similarity search and logging. If Ollama is unreachable, embedding fails silently (degrading to no similarity routing), but adds up to 10 seconds of timeout latency per request.
- **Model routing** — Ollama (`llama3.2:3b`) is one of the four routable models. Requests routed to it (e.g. `latency_hint=low`) will fail and fall back to a cloud provider if Ollama is not running, adding up to 5 seconds of connect timeout latency.

Ollama is the only provider that does not require an API key but does require a local process. The gateway does not validate Ollama availability at startup.

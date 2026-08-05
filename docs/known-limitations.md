# Known Limitations

## Message validation and `prompt` normalization

`CanonicalRequest` enforces two constraints on `messages`:

- At least one message must be present (`min_length=1`)
- At least one message must have `role="user"`

A `messages` list containing only a system message (e.g. `[{"role": "system", "content": "..."}]`) is rejected with a 422.

**Interaction with planned `prompt` normalization**: PLAN.md specifies that a plain `prompt` string should be accepted and wrapped into a user message before validation. That normalization must be implemented as a `model_validator(mode="before")`, which runs before field validation and before the user-message check. Once in place, `{"prompt": "hello"}` will produce `[{"role": "user", "content": "hello"}]` and satisfy both constraints automatically. Until then, clients must use the full `messages` format.

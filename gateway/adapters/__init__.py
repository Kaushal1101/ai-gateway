# This file is the public interface of the adapters package.
# External code calls adapters.dispatch() and never imports individual adapter
# modules directly — openai.py and ollama.py are internal implementation details.
from gateway.adapters import claude, gemini, ollama, openai
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse
from gateway.router import CLAUDE_MODEL, GEMINI_MODEL, OLLAMA_MODEL, OPENAI_MODEL

# Maps model identifiers (as returned by the router) to their adapter functions.
# Adding a new provider means adding an entry here and creating the adapter module.
_REGISTRY: dict[str, object] = {
    OPENAI_MODEL: openai.complete,
    OLLAMA_MODEL: ollama.complete,
    GEMINI_MODEL: gemini.complete,
    CLAUDE_MODEL: claude.complete,
}


async def dispatch(model: str, request: CanonicalRequest) -> CanonicalResponse:
    adapter = _REGISTRY.get(model)
    if adapter is None:
        raise ValueError(f"No adapter registered for model: {model!r}")
    return await adapter(request)  # type: ignore[operator]

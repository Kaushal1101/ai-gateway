# This file is the public interface of the adapters package.
# External code calls adapters.dispatch() and never imports individual adapter
# modules directly — openai.py and ollama.py are internal implementation details.
from gateway.adapters import ollama, openai
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse

# Maps model identifiers (as returned by the router) to their adapter functions.
# Adding a new provider means adding an entry here and creating the adapter module.
_REGISTRY: dict[str, object] = {
    "gpt-4o-mini": openai.complete,
    "llama3.2:3b": ollama.complete,
}


async def dispatch(model: str, request: CanonicalRequest) -> CanonicalResponse:
    adapter = _REGISTRY.get(model)
    if adapter is None:
        raise ValueError(f"No adapter registered for model: {model!r}")
    return await adapter(request)  # type: ignore[operator]

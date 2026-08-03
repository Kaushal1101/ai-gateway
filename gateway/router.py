from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    PromptComplexity,
    TaskType,
)

OPENAI_MODEL = "gpt-4o-mini"
OLLAMA_MODEL = "llama3.2:3b"

_KNOWN_MODELS = {OPENAI_MODEL, OLLAMA_MODEL}

_OPENAI_FIRST = [OPENAI_MODEL, OLLAMA_MODEL]
_OLLAMA_FIRST = [OLLAMA_MODEL, OPENAI_MODEL]

_TASK_TYPE_PREFERS_OPENAI = {TaskType.code, TaskType.math}


def _rank_v2(similar: list[tuple[str, float]]) -> list[str]:
    return [model for model, _ in similar]


def rank(
    request: CanonicalRequest, similar: list[tuple[str, float]] | None = None
) -> list[str]:
    # Client override — bypass routing entirely
    if request.model:
        if request.model not in _KNOWN_MODELS:
            raise ValueError(f"Unknown model: {request.model!r}")
        return [request.model]

    # Latency-sensitive: always prefer fast local model regardless of task
    if request.latency_hint == LatencyHint.low:
        return _OLLAMA_FIRST

    # V2: use historical similarity when available
    if similar:
        return _rank_v2(similar)

    # V1: precision tasks and high complexity prefer the more capable model
    if request.task_type in _TASK_TYPE_PREFERS_OPENAI:
        return _OPENAI_FIRST
    if request.prompt_complexity == PromptComplexity.high:
        return _OPENAI_FIRST

    # Default: prefer cheap local model
    return _OLLAMA_FIRST

from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    PromptComplexity,
    TaskType,
)

_OPENAI_MODEL = "gpt-4o-mini"
_OLLAMA_MODEL = "llama3.2:3b"

_KNOWN_MODELS = {_OPENAI_MODEL, _OLLAMA_MODEL}

_OPENAI_FIRST = [_OPENAI_MODEL, _OLLAMA_MODEL]
_OLLAMA_FIRST = [_OLLAMA_MODEL, _OPENAI_MODEL]

_TASK_TYPE_PREFERS_OPENAI = {TaskType.code, TaskType.math}


def rank(request: CanonicalRequest) -> list[str]:
    # Client override — bypass routing entirely
    if request.model:
        if request.model not in _KNOWN_MODELS:
            raise ValueError(f"Unknown model: {request.model!r}")
        return [request.model]

    # Latency-sensitive: always prefer fast local model regardless of task
    if request.latency_hint == LatencyHint.low:
        return _OLLAMA_FIRST

    # Precision tasks and high complexity: prefer the more capable model
    if request.task_type in _TASK_TYPE_PREFERS_OPENAI:
        return _OPENAI_FIRST
    if request.prompt_complexity == PromptComplexity.high:
        return _OPENAI_FIRST

    # Default: prefer cheap local model
    return _OLLAMA_FIRST

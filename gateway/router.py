from collections.abc import Callable

from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    PromptComplexity,
    TaskType,
)

OPENAI_MODEL = "gpt-4o-mini"
OLLAMA_MODEL = "llama3.2:3b"
GEMINI_MODEL = "gemini-2.0-flash"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_KNOWN_MODELS = {OPENAI_MODEL, OLLAMA_MODEL, GEMINI_MODEL, CLAUDE_MODEL}

MODEL_PROVIDER = {
    OPENAI_MODEL: "openai",
    OLLAMA_MODEL: "ollama",
    GEMINI_MODEL: "google",
    CLAUDE_MODEL: "anthropic",
}

# USD per million input tokens — used to rank models when no stronger signal applies.
# Output costs are not used for routing (unknown until after the call).
INPUT_COST_PER_MTOK: dict[str, float] = {
    OLLAMA_MODEL: 0.0,
    GEMINI_MODEL: 0.075,
    OPENAI_MODEL: 0.15,
    CLAUDE_MODEL: 0.80,
}

# Ranked lists — ordered by preference for each routing case.
# Each list has exactly 3 models; the 4th is excluded as unsuitable for that case.
_LATENCY_SENSITIVE = [
    OLLAMA_MODEL,
    GEMINI_MODEL,
    OPENAI_MODEL,
]  # Claude excluded: slowest, costliest
_SUMMARIZATION = [
    GEMINI_MODEL,
    OPENAI_MODEL,
    CLAUDE_MODEL,
]  # Ollama excluded: 3B too small for long docs
_PRECISION = [
    CLAUDE_MODEL,
    OPENAI_MODEL,
    GEMINI_MODEL,
]  # Ollama excluded: 3B insufficient for code/math
_CREATIVE = [
    OPENAI_MODEL,
    CLAUDE_MODEL,
    GEMINI_MODEL,
]  # Ollama excluded: 3B quality ceiling too low
_DEFAULT = [
    GEMINI_MODEL,
    OPENAI_MODEL,
    OLLAMA_MODEL,
]  # Claude excluded: too costly for general tasks

# Priority rule table — first matching rule wins.
# V1 rules only; V2 similarity is applied after these in rank().
_RULES: list[tuple[Callable[[CanonicalRequest], bool], list[str]]] = [
    (lambda r: r.latency_hint == LatencyHint.low, _LATENCY_SENSITIVE),
    (
        lambda r: (
            r.task_type == TaskType.summarization
            or (r.estimated_input_tokens or 0) > 4000
        ),
        _SUMMARIZATION,
    ),
    (lambda r: r.task_type in {TaskType.code, TaskType.math}, _PRECISION),
    (lambda r: r.task_type in {TaskType.translation, TaskType.creative}, _CREATIVE),
    (lambda r: r.prompt_complexity == PromptComplexity.high, _PRECISION),
]


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

    # V1 rules — explicit signals take precedence over historical similarity
    for condition, ranked in _RULES:
        if condition(request):
            return ranked

    # V2 — use historical similarity when no V1 rule matched
    if similar:
        return _rank_v2(similar)

    return _DEFAULT

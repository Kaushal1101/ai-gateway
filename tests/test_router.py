import pytest

from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    Message,
    PromptComplexity,
    TaskType,
)
from gateway.router import CLAUDE_MODEL, GEMINI_MODEL, OLLAMA_MODEL, OPENAI_MODEL, rank


def _make_request(**kwargs) -> CanonicalRequest:
    return CanonicalRequest(messages=[Message(role="user", content="hello")], **kwargs)


def test_rank_model_override_bypasses_router():
    request = _make_request(model=OPENAI_MODEL)
    assert rank(request) == [OPENAI_MODEL]


def test_rank_unknown_model_raises():
    request = _make_request(model="gpt-99-ultra")
    with pytest.raises(ValueError, match="Unknown model"):
        rank(request)


def test_rank_latency_low_prefers_ollama():
    request = _make_request(latency_hint=LatencyHint.low)
    assert rank(request)[0] == OLLAMA_MODEL


def test_rank_latency_low_overrides_code_task():
    request = _make_request(latency_hint=LatencyHint.low, task_type=TaskType.code)
    assert rank(request)[0] == OLLAMA_MODEL


@pytest.mark.parametrize(
    "task_type,expected",
    [
        (TaskType.code, CLAUDE_MODEL),
        (TaskType.math, CLAUDE_MODEL),
        (TaskType.summarization, GEMINI_MODEL),
        (TaskType.translation, OPENAI_MODEL),
        (TaskType.creative, OPENAI_MODEL),
    ],
)
def test_rank_task_type_routing(task_type, expected):
    request = _make_request(task_type=task_type)
    assert rank(request)[0] == expected


def test_rank_high_complexity_prefers_claude():
    request = _make_request(prompt_complexity=PromptComplexity.high)
    assert rank(request)[0] == CLAUDE_MODEL


def test_rank_default_prefers_gemini():
    request = _make_request()
    assert rank(request)[0] == GEMINI_MODEL


def test_rank_always_returns_multiple_models():
    request = _make_request()
    assert len(rank(request)) > 1


# --- V2 routing (similarity-based) ---


def test_rank_v2_uses_similar_when_provided():
    request = _make_request()
    similar = [(OPENAI_MODEL, 0.97)]
    assert rank(request, similar) == [OPENAI_MODEL]


def test_rank_v2_returns_all_similar_models_in_order():
    request = _make_request()
    similar = [(OPENAI_MODEL, 0.97), (OLLAMA_MODEL, 0.93)]
    assert rank(request, similar) == [OPENAI_MODEL, OLLAMA_MODEL]


def test_rank_latency_hint_takes_precedence_over_v2():
    # latency_hint is client-provided, so it overrides gateway-inferred similarity
    request = _make_request(latency_hint=LatencyHint.low)
    similar = [(OPENAI_MODEL, 0.97)]
    assert rank(request, similar)[0] == OLLAMA_MODEL


def test_rank_v2_falls_back_to_default_when_similar_empty():
    request = _make_request()
    assert rank(request, similar=[])[0] == GEMINI_MODEL


def test_rank_v2_falls_back_to_default_when_similar_none():
    request = _make_request()
    assert rank(request, similar=None)[0] == GEMINI_MODEL


def test_rank_v1_task_type_takes_precedence_over_v2():
    # V1 signals are explicit client intent — they override historical similarity
    request = _make_request(task_type=TaskType.code)
    similar = [(OLLAMA_MODEL, 0.97)]
    assert rank(request, similar)[0] == CLAUDE_MODEL

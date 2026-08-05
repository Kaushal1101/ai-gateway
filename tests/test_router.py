import pytest

from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    Message,
    PromptComplexity,
    TaskType,
)
from gateway.router import (
    CLAUDE_MODEL,
    GEMINI_MODEL,
    OLLAMA_MODEL,
    OPENAI_MODEL,
    rank_v1,
    rank_v2,
)


def _make_request(**kwargs) -> CanonicalRequest:
    return CanonicalRequest(messages=[Message(role="user", content="hello")], **kwargs)


def test_rank_model_override_bypasses_router():
    request = _make_request(model=OPENAI_MODEL)
    assert rank_v1(request) == [OPENAI_MODEL]


def test_rank_unknown_model_raises():
    request = _make_request(model="gpt-99-ultra")
    with pytest.raises(ValueError, match="Unknown model"):
        rank_v1(request)


def test_rank_latency_low_prefers_ollama():
    request = _make_request(latency_hint=LatencyHint.low)
    assert rank_v1(request)[0] == OLLAMA_MODEL


def test_rank_latency_low_overrides_code_task():
    request = _make_request(latency_hint=LatencyHint.low, task_type=TaskType.code)
    assert rank_v1(request)[0] == OLLAMA_MODEL


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
    assert rank_v1(request)[0] == expected


def test_rank_high_complexity_prefers_claude():
    request = _make_request(prompt_complexity=PromptComplexity.high)
    assert rank_v1(request)[0] == CLAUDE_MODEL


def test_rank_v1_returns_none_for_default_request():
    request = _make_request()
    assert rank_v1(request) is None


# --- V2 routing (similarity-based) ---


def test_rank_v2_uses_similar_when_provided():
    similar = [(OPENAI_MODEL, 0.97)]
    assert rank_v2(similar) == [OPENAI_MODEL]


def test_rank_v2_returns_all_similar_models_in_order():
    similar = [(OPENAI_MODEL, 0.97), (OLLAMA_MODEL, 0.93)]
    assert rank_v2(similar) == [OPENAI_MODEL, OLLAMA_MODEL]


def test_rank_v2_falls_back_to_default_when_similar_empty():
    assert rank_v2([])[0] == GEMINI_MODEL


def test_rank_v2_falls_back_to_default_when_similar_none():
    assert rank_v2(None)[0] == GEMINI_MODEL


def test_rank_v2_always_returns_multiple_models():
    assert len(rank_v2([])) > 1


def test_rank_v2_filters_stale_model_names():
    similar = [("gpt-99-deprecated", 0.97), (OPENAI_MODEL, 0.93)]
    assert rank_v2(similar) == [OPENAI_MODEL]


def test_rank_v1_takes_precedence_when_task_type_set():
    # V1 fires for code — caller never reaches rank_v2
    request = _make_request(task_type=TaskType.code)
    assert rank_v1(request)[0] == CLAUDE_MODEL


def test_rank_v1_takes_precedence_when_latency_hint_low():
    request = _make_request(latency_hint=LatencyHint.low)
    assert rank_v1(request)[0] == OLLAMA_MODEL

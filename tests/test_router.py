import pytest

from gateway.models.request import (
    CanonicalRequest,
    LatencyHint,
    Message,
    PromptComplexity,
    TaskType,
)
from gateway.router import OLLAMA_MODEL, OPENAI_MODEL, rank


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
        (TaskType.code, OPENAI_MODEL),
        (TaskType.math, OPENAI_MODEL),
        (TaskType.summarization, OLLAMA_MODEL),
        (TaskType.translation, OLLAMA_MODEL),
        (TaskType.creative, OLLAMA_MODEL),
    ],
)
def test_rank_task_type_routing(task_type, expected):
    request = _make_request(task_type=task_type)
    assert rank(request)[0] == expected


def test_rank_high_complexity_prefers_openai():
    request = _make_request(prompt_complexity=PromptComplexity.high)
    assert rank(request)[0] == OPENAI_MODEL


def test_rank_default_prefers_ollama():
    request = _make_request()
    assert rank(request)[0] == OLLAMA_MODEL


def test_rank_always_returns_multiple_models():
    request = _make_request()
    assert len(rank(request)) > 1

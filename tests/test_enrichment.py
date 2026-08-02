from gateway.enrichment import enrich
from gateway.models.request import (
    CanonicalRequest,
    Message,
    PromptComplexity,
    TaskType,
)


def _make_request(content: str, **kwargs) -> CanonicalRequest:
    return CanonicalRequest(messages=[Message(role="user", content=content)], **kwargs)


def test_enrich_populates_token_estimate():
    request = _make_request("hello world")
    enriched = enrich(request)
    assert enriched.estimated_input_tokens is not None
    assert enriched.estimated_input_tokens > 0


def test_enrich_populates_task_type():
    request = _make_request("write a Python function")
    enriched = enrich(request)
    assert enriched.task_type == TaskType.code


def test_enrich_populates_complexity():
    request = _make_request("hello")
    enriched = enrich(request)
    assert enriched.prompt_complexity == PromptComplexity.low


def test_enrich_respects_client_task_type():
    request = _make_request("write a Python function", task_type=TaskType.creative)
    enriched = enrich(request)
    assert enriched.task_type == TaskType.creative


def test_enrich_respects_client_token_estimate():
    request = _make_request("hello", estimated_input_tokens=999)
    enriched = enrich(request)
    assert enriched.estimated_input_tokens == 999


def test_enrich_respects_client_complexity():
    request = _make_request("hello", prompt_complexity=PromptComplexity.high)
    enriched = enrich(request)
    assert enriched.prompt_complexity == PromptComplexity.high


def test_task_type_code_keyword():
    enriched = enrich(_make_request("debug this function"))
    assert enriched.task_type == TaskType.code


def test_task_type_math_keyword():
    enriched = enrich(_make_request("solve this equation"))
    assert enriched.task_type == TaskType.math


def test_task_type_summarization_keyword():
    enriched = enrich(_make_request("summarize this article"))
    assert enriched.task_type == TaskType.summarization


def test_task_type_translation_keyword():
    enriched = enrich(_make_request("translate this into french"))
    assert enriched.task_type == TaskType.translation


def test_task_type_general_fallback():
    enriched = enrich(_make_request("what is the meaning of life?"))
    assert enriched.task_type == TaskType.general


def test_task_type_frequency_wins_over_position():
    # "translate" → translation (1 hit), "python function debug" → code (3 hits)
    # code wins despite translation appearing first in _TASK_KEYWORDS
    enriched = enrich(_make_request("translate this python function and debug it"))
    assert enriched.task_type == TaskType.code


def test_complexity_low_boundary():
    enriched = enrich(_make_request("hello"))
    assert enriched.prompt_complexity == PromptComplexity.low


def test_complexity_high_boundary():
    # needs > 2000 tokens to hit high bucket
    long_text = "explain this concept in detail " * 450
    enriched = enrich(_make_request(long_text))
    assert enriched.prompt_complexity == PromptComplexity.high

import pytest
from pydantic import ValidationError

from gateway.models.request import CanonicalRequest, LatencyHint
from gateway.models.response import CanonicalResponse, FinishReason


def test_canonical_request_defaults():
    req = CanonicalRequest(messages=[{"role": "user", "content": "hello"}])
    assert req.temperature == 1.0
    assert req.stream is False
    assert req.latency_hint == LatencyHint.normal
    assert req.model is None
    assert req.max_tokens is None


def test_canonical_request_invalid_role():
    with pytest.raises(ValidationError):
        CanonicalRequest(messages=[{"role": "invalid", "content": "hello"}])


def test_canonical_request_temperature_out_of_range():
    with pytest.raises(ValidationError):
        CanonicalRequest(
            messages=[{"role": "user", "content": "hello"}], temperature=3.0
        )


def test_canonical_request_max_tokens_must_be_positive():
    with pytest.raises(ValidationError):
        CanonicalRequest(messages=[{"role": "user", "content": "hello"}], max_tokens=0)


def test_canonical_response_valid():
    resp = CanonicalResponse(
        content="hello",
        model="gpt-4o-mini",
        provider="openai",
        input_tokens=10,
        output_tokens=5,
        latency_ms=100,
        finish_reason=FinishReason.stop,
    )
    assert resp.finish_reason == FinishReason.stop
    assert resp.provider == "openai"

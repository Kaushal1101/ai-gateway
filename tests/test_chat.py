from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.main import app
from gateway.models.response import CanonicalResponse, FinishReason

client = TestClient(app)

_STUB_RESPONSE = CanonicalResponse(
    content="Hello",
    model="gpt-4o-mini",
    provider="openai",
    input_tokens=10,
    output_tokens=5,
    latency_ms=100,
    finish_reason=FinishReason.stop,
)


def test_chat_returns_canonical_response():
    with patch(
        "gateway.adapters.openai.complete", new=AsyncMock(return_value=_STUB_RESPONSE)
    ):
        response = client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello"
    assert data["model"] == "gpt-4o-mini"
    assert data["provider"] == "openai"
    assert data["input_tokens"] == 10
    assert data["finish_reason"] == "stop"


def test_chat_invalid_role_returns_422():
    response = client.post(
        "/chat", json={"messages": [{"role": "invalid", "content": "hello"}]}
    )
    assert response.status_code == 422


def test_chat_missing_messages_returns_422():
    response = client.post("/chat", json={})
    assert response.status_code == 422

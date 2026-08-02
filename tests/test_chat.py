from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.main import app
from gateway.models.response import CanonicalResponse, FinishReason
from gateway.router import OLLAMA_MODEL

client = TestClient(app)

_STUB_RESPONSE = CanonicalResponse(
    content="Hello",
    model=OLLAMA_MODEL,
    provider="ollama",
    input_tokens=10,
    output_tokens=5,
    latency_ms=100,
    finish_reason=FinishReason.stop,
)


def _mock_session():
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session)


def test_chat_returns_canonical_response():
    with (
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(return_value=_STUB_RESPONSE),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        response = client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello"
    assert data["model"] == OLLAMA_MODEL
    assert data["provider"] == "ollama"
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


def test_chat_log_written_on_success():
    mock_session = _mock_session()
    with (
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(return_value=_STUB_RESPONSE),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=mock_session),
    ):
        client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

    session_instance = mock_session.return_value.__aenter__.return_value
    session_instance.add.assert_called_once()
    log = session_instance.add.call_args[0][0]
    assert log.response_status.value == "success"
    assert log.chosen_model == OLLAMA_MODEL
    assert log.input_tokens == 10


def test_chat_log_written_on_error():
    mock_session = _mock_session()
    error_client = TestClient(app, raise_server_exceptions=False)
    with (
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(side_effect=Exception("provider failure")),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=mock_session),
    ):
        response = error_client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert response.status_code == 500
    session_instance = mock_session.return_value.__aenter__.return_value
    session_instance.add.assert_called_once()
    log = session_instance.add.call_args[0][0]
    assert log.response_status.value == "error"
    assert log.chosen_model == OLLAMA_MODEL  # model is known even on error
    assert log.input_tokens is None

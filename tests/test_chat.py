from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.main import app
from gateway.models.response import CanonicalResponse, FinishReason
from gateway.router import OLLAMA_MODEL, OPENAI_MODEL

client = TestClient(app)

_STUB_OLLAMA = CanonicalResponse(
    content="Hello",
    model=OLLAMA_MODEL,
    provider="ollama",
    input_tokens=10,
    output_tokens=5,
    latency_ms=100,
    finish_reason=FinishReason.stop,
)

_STUB_OPENAI = CanonicalResponse(
    content="Hello from OpenAI",
    model=OPENAI_MODEL,
    provider="openai",
    input_tokens=10,
    output_tokens=5,
    latency_ms=200,
    finish_reason=FinishReason.stop,
)


@pytest.fixture(autouse=True)
def _mock_embedding_and_similarity():
    with (
        patch("gateway.embedding.embed", new=AsyncMock(return_value=[0.0] * 768)),
        patch("gateway.similarity.find_similar", new=AsyncMock(return_value=[])),
    ):
        yield


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
            new=AsyncMock(return_value=_STUB_OLLAMA),
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
            new=AsyncMock(return_value=_STUB_OLLAMA),
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
    assert log.fallback_count == 0


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
    assert log.chosen_model == OLLAMA_MODEL
    assert log.input_tokens is None
    assert log.fallback_count == 2  # both ranked models tried and failed


def test_chat_fallback_succeeds_on_second_model():
    dispatch_mock = AsyncMock(side_effect=[Exception("ollama down"), _STUB_OPENAI])
    with (
        patch("gateway.adapters.dispatch", new=dispatch_mock),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        response = client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == OPENAI_MODEL
    assert data["provider"] == "openai"
    assert dispatch_mock.call_count == 2


def test_chat_all_models_fail_returns_500():
    dispatch_mock = AsyncMock(side_effect=Exception("all providers down"))
    error_client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("gateway.adapters.dispatch", new=dispatch_mock),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        response = error_client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert response.status_code == 500
    assert dispatch_mock.call_count == 2  # all ranked models were tried


def test_chat_fallback_count_logged_on_fallback():
    mock_session = _mock_session()
    with (
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(side_effect=[Exception("ollama down"), _STUB_OPENAI]),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=mock_session),
    ):
        client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

    session_instance = mock_session.return_value.__aenter__.return_value
    log = session_instance.add.call_args[0][0]
    assert log.response_status.value == "success"
    assert log.chosen_model == OPENAI_MODEL
    assert log.fallback_count == 1


# --- Metrics instrumentation tests ---


def _patch_metrics():
    return (
        patch("gateway.metrics.REQUEST_LATENCY"),
        patch("gateway.metrics.MODEL_CHOSEN"),
        patch("gateway.metrics.PROVIDER_ERRORS"),
        patch("gateway.metrics.REQUEST_FALLBACKS"),
    )


def test_metrics_recorded_on_success():
    p_latency, p_model, p_errors, p_fallbacks = _patch_metrics()
    with (
        p_latency as m_latency,
        p_model as m_model,
        p_errors as m_errors,
        p_fallbacks as m_fallbacks,
        patch("gateway.adapters.dispatch", new=AsyncMock(return_value=_STUB_OLLAMA)),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

    m_fallbacks.observe.assert_called_once_with(0)
    m_model.labels.assert_called_once_with(model=OLLAMA_MODEL, routing_version="v1")
    m_model.labels.return_value.inc.assert_called_once()
    m_latency.observe.assert_called_once()
    m_errors.labels.assert_not_called()


def test_metrics_recorded_on_fallback():
    p_latency, p_model, p_errors, p_fallbacks = _patch_metrics()
    with (
        p_latency as m_latency,
        p_model as m_model,
        p_errors as m_errors,
        p_fallbacks as m_fallbacks,
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(side_effect=[Exception("ollama down"), _STUB_OPENAI]),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

    m_errors.labels.assert_called_once_with(provider="ollama")
    m_errors.labels.return_value.inc.assert_called_once()
    m_fallbacks.observe.assert_called_once_with(1)
    m_model.labels.assert_called_once_with(model=OPENAI_MODEL, routing_version="v1")
    m_latency.observe.assert_called_once()


def test_metrics_recorded_on_all_models_fail():
    p_latency, p_model, p_errors, p_fallbacks = _patch_metrics()
    error_client = TestClient(app, raise_server_exceptions=False)
    with (
        p_latency as m_latency,
        p_model as m_model,
        p_errors as m_errors,
        p_fallbacks as m_fallbacks,
        patch(
            "gateway.adapters.dispatch",
            new=AsyncMock(side_effect=Exception("all down")),
        ),
        patch("gateway.routes.chat.AsyncSessionLocal", new=_mock_session()),
    ):
        error_client.post(
            "/chat", json={"messages": [{"role": "user", "content": "hello"}]}
        )

    assert m_errors.labels.call_count == 2
    m_fallbacks.observe.assert_called_once_with(2)
    m_latency.observe.assert_called_once()
    m_model.labels.assert_not_called()

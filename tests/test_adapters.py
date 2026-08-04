from unittest.mock import AsyncMock, MagicMock, patch

from gateway.adapters.claude import _build_messages
from gateway.adapters.claude import complete as claude_complete
from gateway.adapters.gemini import _build_contents
from gateway.adapters.gemini import complete as gemini_complete
from gateway.models.request import CanonicalRequest, Message
from gateway.models.response import FinishReason


def _make_request(**kwargs) -> CanonicalRequest:
    return CanonicalRequest(messages=[Message(role="user", content="hello")], **kwargs)


def _mock_http_client(json_data: dict) -> MagicMock:
    """Async context manager mock whose .post() returns a response with the given JSON."""  # noqa: E501
    response = MagicMock()
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    return client


_GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {"parts": [{"text": "Hello there"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    "modelVersion": "gemini-2.0-flash",
}

_CLAUDE_RESPONSE = {
    "content": [{"type": "text", "text": "Hello there"}],
    "model": "claude-haiku-4-5-20251001",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 5},
}


# --- Gemini: _build_contents ---


def test_gemini_build_contents_user_message():
    contents, system = _build_contents(_make_request())
    assert contents == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert system is None


def test_gemini_build_contents_extracts_system_message():
    request = CanonicalRequest(
        messages=[
            Message(role="system", content="Be concise"),
            Message(role="user", content="hello"),
        ]
    )
    contents, system = _build_contents(request)
    assert system == {"parts": [{"text": "Be concise"}]}
    assert len(contents) == 1
    assert contents[0]["role"] == "user"


def test_gemini_build_contents_maps_assistant_to_model():
    request = CanonicalRequest(
        messages=[
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
    )
    contents, _ = _build_contents(request)
    assert contents[1]["role"] == "model"


# --- Gemini: complete ---


async def test_gemini_complete_parses_response():
    mock_client = _mock_http_client(_GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await gemini_complete(_make_request())

    assert result.content == "Hello there"
    assert result.model == "gemini-2.0-flash"
    assert result.provider == "google"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.finish_reason == FinishReason.stop
    assert result.latency_ms >= 0


async def test_gemini_complete_sends_contents_not_messages():
    mock_client = _mock_http_client(_GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await gemini_complete(_make_request())

    payload = mock_client.post.call_args.kwargs["json"]
    assert "contents" in payload
    assert "messages" not in payload
    assert payload["contents"][0]["parts"][0]["text"] == "hello"


async def test_gemini_complete_sends_system_instruction():
    request = CanonicalRequest(
        messages=[
            Message(role="system", content="Be concise"),
            Message(role="user", content="hello"),
        ]
    )
    mock_client = _mock_http_client(_GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await gemini_complete(request)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["systemInstruction"] == {"parts": [{"text": "Be concise"}]}
    assert all("system" not in m["role"] for m in payload["contents"])


# --- Claude: _build_messages ---


def test_claude_build_messages_user_message():
    messages, system = _build_messages(_make_request())
    assert messages == [{"role": "user", "content": "hello"}]
    assert system is None


def test_claude_build_messages_extracts_system():
    request = CanonicalRequest(
        messages=[
            Message(role="system", content="Be concise"),
            Message(role="user", content="hello"),
        ]
    )
    messages, system = _build_messages(request)
    assert system == "Be concise"
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


# --- Claude: complete ---


async def test_claude_complete_parses_response():
    mock_client = _mock_http_client(_CLAUDE_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await claude_complete(_make_request())

    assert result.content == "Hello there"
    assert result.model == "claude-haiku-4-5-20251001"
    assert result.provider == "anthropic"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.finish_reason == FinishReason.stop
    assert result.latency_ms >= 0


async def test_claude_complete_sends_required_headers():
    mock_client = _mock_http_client(_CLAUDE_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await claude_complete(_make_request())

    headers = mock_client.post.call_args.kwargs["headers"]
    assert "x-api-key" in headers
    assert headers["anthropic-version"] == "2023-06-01"


async def test_claude_complete_always_sends_max_tokens():
    mock_client = _mock_http_client(_CLAUDE_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await claude_complete(_make_request())  # no max_tokens set

    payload = mock_client.post.call_args.kwargs["json"]
    assert "max_tokens" in payload


async def test_claude_complete_sends_system_as_top_level_string():
    request = CanonicalRequest(
        messages=[
            Message(role="system", content="Be concise"),
            Message(role="user", content="hello"),
        ]
    )
    mock_client = _mock_http_client(_CLAUDE_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await claude_complete(request)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["system"] == "Be concise"
    assert all(m["role"] != "system" for m in payload["messages"])

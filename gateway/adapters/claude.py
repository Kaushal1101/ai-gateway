import os
import time

import httpx

from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse, FinishReason

_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_CONNECT_TIMEOUT = float(os.getenv("GATEWAY_CONNECT_TIMEOUT", "5.0"))
_READ_TIMEOUT = 30.0
_TIMEOUT = httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT)

_FINISH_REASON_MAP = {
    "end_turn": FinishReason.stop,
    "max_tokens": FinishReason.length,
}


def _build_messages(request: CanonicalRequest) -> tuple[list[dict], str | None]:
    """Split messages into Anthropic's messages array and optional system string."""
    system = None
    messages = []
    for m in request.messages:
        if m.role == "system":
            system = m.content
        else:
            messages.append({"role": m.role, "content": m.content})
    return messages, system


async def complete(request: CanonicalRequest) -> CanonicalResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    messages, system = _build_messages(request)

    # Request shape:
    # {
    #   "model": "claude-haiku-4-5-20251001",
    #   "system": "You are a helpful assistant",  # optional
    #   "messages": [
    #     {"role": "user",      "content": "hello"},
    #     {"role": "assistant", "content": "hi there"}
    #   ],
    #   "max_tokens": 1024,
    #   "temperature": 1.0
    # }
    payload: dict = {
        "model": request.model or _DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": request.max_tokens or 1024,
        "temperature": request.temperature,
    }
    if system:
        payload["system"] = system

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _API_URL, json=payload, headers=headers, timeout=_TIMEOUT
        )
        response.raise_for_status()
    latency_ms = int((time.monotonic() - start) * 1000)

    # Response shape:
    # {
    #   "content": [{"type": "text", "text": "..."}],
    #   "model": "claude-haiku-4-5-20251001",
    #   "stop_reason": "end_turn",
    #   "usage": {"input_tokens": 10, "output_tokens": 5}
    # }
    data = response.json()
    usage = data["usage"]

    return CanonicalResponse(
        content=data["content"][0]["text"],
        model=data["model"],
        provider="anthropic",
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        latency_ms=latency_ms,
        # data.get("stop_reason", "end_turn"): read stop_reason from the response,
        # defaulting to "end_turn" if Anthropic omits the field.
        # _FINISH_REASON_MAP.get(..., FinishReason.stop): translate to our canonical
        # enum, defaulting to stop if Anthropic adds a new reason we haven't mapped.
        finish_reason=_FINISH_REASON_MAP.get(
            data.get("stop_reason", "end_turn"), FinishReason.stop
        ),
    )

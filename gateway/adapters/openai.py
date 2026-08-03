import os
import time

import httpx

from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse, FinishReason

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_CONNECT_TIMEOUT = float(os.getenv("GATEWAY_CONNECT_TIMEOUT", "5.0"))
_READ_TIMEOUT = 30.0
_TIMEOUT = httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT)

_FINISH_REASON_MAP = {
    "stop": FinishReason.stop,
    "length": FinishReason.length,
}


async def complete(request: CanonicalRequest) -> CanonicalResponse:
    api_key = os.getenv("OPENAI_API_KEY")

    payload: dict = {
        "model": request.model or _DEFAULT_MODEL,
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
    }

    # Don't send max_tokens if it's not set (not even null)
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
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
    #   "model": "gpt-4o-mini",
    #   "choices": [{"message": {"role": "assistant", "content": "..."},
    #               "finish_reason": "stop"}],
    #   "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    # }
    data = response.json()
    choice = data["choices"][0]
    usage = data["usage"]

    return CanonicalResponse(
        content=choice["message"]["content"],
        model=data["model"],
        provider="openai",
        input_tokens=usage["prompt_tokens"],
        output_tokens=usage["completion_tokens"],
        latency_ms=latency_ms,
        finish_reason=_FINISH_REASON_MAP.get(
            choice["finish_reason"], FinishReason.stop
        ),
    )

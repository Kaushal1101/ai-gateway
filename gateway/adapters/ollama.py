import os
import time

import httpx

from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse, FinishReason

_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_API_URL = f"{_BASE_URL}/v1/chat/completions"
_DEFAULT_MODEL = "llama3.2:3b"

_FINISH_REASON_MAP = {
    "stop": FinishReason.stop,
    "length": FinishReason.length,
}


async def complete(request: CanonicalRequest) -> CanonicalResponse:
    payload: dict = {
        "model": request.model or _DEFAULT_MODEL,
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
    }

    # Don't send max_tokens if it's not set (not even null)
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens

    headers = {
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _API_URL, json=payload, headers=headers, timeout=60.0
        )
        response.raise_for_status()
    latency_ms = int((time.monotonic() - start) * 1000)

    # Response shape:
    # {
    #   "model": "llama3.2:3b",
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
        provider="ollama",
        input_tokens=usage["prompt_tokens"],
        output_tokens=usage["completion_tokens"],
        latency_ms=latency_ms,
        finish_reason=_FINISH_REASON_MAP.get(
            choice["finish_reason"], FinishReason.stop
        ),
    )

import os
import time

import httpx

from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse, FinishReason

_DEFAULT_MODEL = "gemini-2.0-flash"
_BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_DEFAULT_MODEL}:generateContent"
_CONNECT_TIMEOUT = float(os.getenv("GATEWAY_CONNECT_TIMEOUT", "5.0"))
_READ_TIMEOUT = 30.0
_TIMEOUT = httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT)

_FINISH_REASON_MAP = {
    "STOP": FinishReason.stop,
    "MAX_TOKENS": FinishReason.length,
}


def _build_contents(request: CanonicalRequest) -> tuple[list[dict], dict | None]:
    """Split messages into Gemini's contents array and optional systemInstruction."""
    system = None
    contents = []
    for m in request.messages:
        if m.role == "system":
            system = {"parts": [{"text": m.content}]}
        else:
            role = "model" if m.role == "assistant" else m.role
            contents.append({"role": role, "parts": [{"text": m.content}]})
    return contents, system


async def complete(request: CanonicalRequest) -> CanonicalResponse:
    api_key = os.getenv("GEMINI_API_KEY", "")
    url = f"{_BASE_URL}?key={api_key}"

    contents, system_instruction = _build_contents(request)

    generation_config: dict = {"temperature": request.temperature}
    if request.max_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_tokens

    # Request shape:
    # {
    #   "systemInstruction": {"parts": [{"text": "..."}]},  # optional
    #   "contents": [
    #     {"role": "user",  "parts": [{"text": "..."}]},
    #     {"role": "model", "parts": [{"text": "..."}]}
    #   ],
    #   "generationConfig": {"temperature": 1.0, "maxOutputTokens": 1000}
    # }
    payload: dict = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=_TIMEOUT)
        response.raise_for_status()
    latency_ms = int((time.monotonic() - start) * 1000)

    # Response shape:
    # {
    #   "candidates": [{"content": {"parts": [{"text": "..."}]},
    #                   "finishReason": "STOP"}],
    #   "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    #   "modelVersion": "gemini-2.0-flash"
    # }
    data = response.json()
    candidate = data["candidates"][0]
    usage = data["usageMetadata"]

    return CanonicalResponse(
        content=candidate["content"]["parts"][0]["text"],
        model=data.get("modelVersion", _DEFAULT_MODEL),
        provider="google",
        input_tokens=usage["promptTokenCount"],
        output_tokens=usage["candidatesTokenCount"],
        latency_ms=latency_ms,
        finish_reason=_FINISH_REASON_MAP.get(
            candidate.get("finishReason", "STOP"), FinishReason.stop
        ),
    )

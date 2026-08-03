import os

import httpx

from gateway.models.request import CanonicalRequest

_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_API_URL = f"{_BASE_URL}/v1/embeddings"
_MODEL = "nomic-embed-text"
_CONNECT_TIMEOUT = float(os.getenv("GATEWAY_CONNECT_TIMEOUT", "5.0"))
_READ_TIMEOUT = 10.0
_TIMEOUT = httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT)


async def embed(request: CanonicalRequest) -> list[float]:
    text = "\n".join(m.content for m in request.messages)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _API_URL,
            json={"model": _MODEL, "input": text},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    # {"data": [{"embedding": [...], "index": 0, "object": "embedding"}], ...}
    return response.json()["data"][0]["embedding"]

from fastapi import APIRouter

from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse, FinishReason

router = APIRouter()


@router.post("/chat", response_model=CanonicalResponse)
async def chat(request: CanonicalRequest) -> CanonicalResponse:
    return CanonicalResponse(
        content="stub response",
        model="stub",
        provider="stub",
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        finish_reason=FinishReason.stop,
    )

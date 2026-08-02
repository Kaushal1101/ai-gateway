from fastapi import APIRouter

from gateway.adapters import openai
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse

router = APIRouter()


@router.post("/chat", response_model=CanonicalResponse)
async def chat(request: CanonicalRequest) -> CanonicalResponse:

    response = await openai.complete(request)

    # OpenAI returns Canonical response, so we can just return it
    return response

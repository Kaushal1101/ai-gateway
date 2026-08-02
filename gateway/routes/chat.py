from fastapi import APIRouter

from gateway import adapters, enrichment, router
from gateway.db import AsyncSessionLocal
from gateway.models.log import RequestLog, ResponseStatus
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse

app_router = APIRouter()


@app_router.post("/chat", response_model=CanonicalResponse)
async def chat(request: CanonicalRequest) -> CanonicalResponse:
    enriched = enrichment.enrich(request)
    ranked = router.rank(enriched)
    model = ranked[0]

    try:
        response = await adapters.dispatch(model, enriched)
        log = RequestLog(
            chosen_model=response.model,
            provider=response.provider,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_latency_ms=response.latency_ms,
            response_status=ResponseStatus.success,
            canonical_request=enriched.model_dump(),
        )
    except Exception:
        log = RequestLog(
            chosen_model=model,
            provider=None,
            input_tokens=None,
            output_tokens=None,
            provider_latency_ms=None,
            response_status=ResponseStatus.error,
            canonical_request=enriched.model_dump(),
        )
        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()
        raise

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    return response

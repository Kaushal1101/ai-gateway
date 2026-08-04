import time

from fastapi import APIRouter

from gateway import adapters, embedding, enrichment, metrics, router, similarity
from gateway.db import AsyncSessionLocal
from gateway.models.log import RequestLog, ResponseStatus
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse

app_router = APIRouter()


@app_router.post("/chat", response_model=CanonicalResponse)
async def chat(request: CanonicalRequest) -> CanonicalResponse:
    start = time.monotonic()
    enriched = enrichment.enrich(request)

    try:
        vec = await embedding.embed(enriched)
    except Exception:
        vec = None

    similar = await similarity.find_similar(vec)
    ranked = router.rank(enriched, similar)

    last_exc = None
    fallback_count = 0
    for model in ranked:
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
                fallback_count=fallback_count,
                embedding=vec,
            )

            # Prometheus model and route tracking
            metrics.MODEL_CHOSEN.labels(
                model=response.model, routing_version="v2" if similar else "v1"
            ).inc()

            # Prometheus latency tracking
            duration_ms = (time.monotonic() - start) * 1000
            metrics.REQUEST_LATENCY.observe(duration_ms)

            break
        except Exception as e:
            fallback_count += 1
            last_exc = e

    else:
        log = RequestLog(
            chosen_model=ranked[0],
            provider=None,
            input_tokens=None,
            output_tokens=None,
            provider_latency_ms=None,
            response_status=ResponseStatus.error,
            canonical_request=enriched.model_dump(),
            fallback_count=fallback_count,
            embedding=None,
        )
        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()

        # Prometheus latency tracking
        duration_ms = (time.monotonic() - start) * 1000
        metrics.REQUEST_LATENCY.observe(duration_ms)

        raise last_exc

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    return response

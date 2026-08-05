import time

from fastapi import APIRouter, HTTPException

from gateway import adapters, embedding, enrichment, metrics, router, similarity
from gateway.db import AsyncSessionLocal
from gateway.models.log import RequestLog, ResponseStatus
from gateway.models.request import CanonicalRequest
from gateway.models.response import CanonicalResponse
from gateway.router import MODEL_PROVIDER

app_router = APIRouter()


@app_router.post("/chat", response_model=CanonicalResponse)
async def chat(request: CanonicalRequest) -> CanonicalResponse:
    if request.stream:
        raise HTTPException(status_code=501, detail="Streaming is not yet supported.")

    start = time.monotonic()
    enriched = enrichment.enrich(request)

    try:
        vec = await embedding.embed(enriched)
    except Exception:
        vec = None

    try:
        ranked = router.rank_v1(enriched)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if ranked is None:
        try:
            similar = await similarity.find_similar(vec)
        except Exception:
            similar = []  # DB failure — rank_v2 will fall back to _DEFAULT
        ranked = router.rank_v2(similar)
        routing_version = "v2" if similar else "v1"
    else:
        routing_version = "v1"

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

            # Prometheus fallback count tracking
            metrics.REQUEST_FALLBACKS.observe(fallback_count)

            # Prometheus model and route tracking
            metrics.MODEL_CHOSEN.labels(
                model=response.model, routing_version=routing_version
            ).inc()

            # Prometheus latency tracking
            duration_ms = (time.monotonic() - start) * 1000
            metrics.REQUEST_LATENCY.observe(duration_ms)

            break
        except Exception as e:
            fallback_count += 1
            last_exc = e

            # Prometheus provider error tracking
            provider = MODEL_PROVIDER.get(model, model)
            metrics.PROVIDER_ERRORS.labels(provider=provider).inc()

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
        # Prometheus metrics observed before DB write to match success path boundary
        metrics.REQUEST_FALLBACKS.observe(fallback_count)
        duration_ms = (time.monotonic() - start) * 1000
        metrics.REQUEST_LATENCY.observe(duration_ms)

        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()

        raise last_exc

    # Best-effort logging — a DB failure here must not fail the client response.
    # Downside: missing log rows mean V2 routing loses data points for those requests.
    # TODO: replace with BackgroundTasks or an outbox pattern for durability.
    try:
        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()
    except Exception:
        pass

    return response

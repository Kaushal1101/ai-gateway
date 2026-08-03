import os

from sqlalchemy import select

from gateway.db import AsyncSessionLocal
from gateway.models.log import RequestLog, ResponseStatus

_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.9"))
_TOP_K = 3


async def find_similar(vec: list[float] | None) -> list[tuple[str, float]]:
    if vec is None:
        return []

    # 0 = identical, 2 = opposite
    distance = RequestLog.embedding.cosine_distance(vec)
    # similarity >= 0.9
    above_threshold = distance <= 1 - _SIMILARITY_THRESHOLD
    stmt = (
        # convert distance to similarity score (0–1)
        select(RequestLog.chosen_model, (1 - distance).label("similarity"))
        # skip rows without embeddings
        .where(RequestLog.embedding.is_not(None))
        # quality signal: only learn from successes
        .where(RequestLog.response_status == ResponseStatus.success)
        # discard loosely related history
        .where(above_threshold)
        # closest match first
        .order_by(distance)
        # top 3 results
        .limit(_TOP_K)
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return [(row.chosen_model, float(row.similarity)) for row in result]

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from gateway.db import Base


class ResponseStatus(str, enum.Enum):
    success = "success"
    error = "error"


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    chosen_model: Mapped[str]
    provider: Mapped[str]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    provider_latency_ms: Mapped[int]
    response_status: Mapped[ResponseStatus] = mapped_column(
        SAEnum(ResponseStatus, name="response_status")
    )
    canonical_request: Mapped[dict[str, Any]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

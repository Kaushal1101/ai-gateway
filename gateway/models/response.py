from enum import Enum

from pydantic import BaseModel


class FinishReason(str, Enum):
    stop = "stop"
    length = "length"
    error = "error"


class CanonicalResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    finish_reason: FinishReason

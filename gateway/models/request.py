from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class LatencyHint(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class TaskType(str, Enum):
    code = "code"
    math = "math"
    summarization = "summarization"
    translation = "translation"
    creative = "creative"
    general = "general"


class PromptComplexity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class CanonicalRequest(BaseModel):
    # Client-provided
    messages: list[Message]
    model: str | None = None
    stream: bool = False
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    latency_hint: LatencyHint = LatencyHint.normal

    # Gateway-inferred (populated after parsing, before routing)
    estimated_input_tokens: int | None = None
    task_type: TaskType | None = None
    prompt_complexity: PromptComplexity | None = None

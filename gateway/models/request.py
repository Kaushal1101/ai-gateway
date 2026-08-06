from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    messages: list[Message] = Field(min_length=1)
    model: str | None = None
    stream: bool = False
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    latency_hint: LatencyHint = LatencyHint.normal

    # Gateway-inferred (populated after parsing, before routing)
    estimated_input_tokens: int | None = None
    task_type: TaskType | None = None
    prompt_complexity: PromptComplexity | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_prompt(cls, data: dict) -> dict:
        if "prompt" in data and "messages" not in data:
            data["messages"] = [{"role": "user", "content": data.pop("prompt")}]
        return data

    @model_validator(mode="after")
    def _validate_messages(self) -> "CanonicalRequest":
        if not any(m.role == "user" for m in self.messages):
            raise ValueError("At least one user message is required.")
        if sum(1 for m in self.messages if m.role == "system") > 1:
            raise ValueError("At most one system message is allowed.")
        return self

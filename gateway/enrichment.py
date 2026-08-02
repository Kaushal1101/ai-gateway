import tiktoken

from gateway.models.request import CanonicalRequest, PromptComplexity, TaskType

_ENCODING = tiktoken.get_encoding("cl100k_base")

# Priority order: first match wins (top = highest priority)
_TASK_KEYWORDS: list[tuple[TaskType, set[str]]] = [
    (
        TaskType.code,
        {
            "function",
            "class",
            "debug",
            "bug",
            "error",
            "implement",
            "python",
            "javascript",
            "typescript",
            "sql",
            "api",
            "refactor",
            "compile",
            "syntax",
        },
    ),
    (
        TaskType.math,
        {
            "calculate",
            "equation",
            "solve",
            "integral",
            "derivative",
            "proof",
            "formula",
            "compute",
            "sum",
            "percentage",
        },
    ),
    (
        TaskType.summarization,
        {"summarize", "summary", "tldr", "condense", "shorten", "brief", "overview"},
    ),
    (TaskType.translation, {"translate", "french", "spanish", "japanese", "german"}),
    (
        TaskType.creative,
        {"poem", "song", "creative", "imagine", "fiction", "narrative", "character"},
    ),
]


def _estimate_tokens(request: CanonicalRequest) -> int:
    return sum(len(_ENCODING.encode(m.content)) for m in request.messages)


_COMPLEXITY_MEDIUM_THRESHOLD = 500
_COMPLEXITY_HIGH_THRESHOLD = 2000


def _bucket_complexity(tokens: int) -> PromptComplexity:
    if tokens < _COMPLEXITY_MEDIUM_THRESHOLD:
        return PromptComplexity.low
    if tokens < _COMPLEXITY_HIGH_THRESHOLD:
        return PromptComplexity.medium
    return PromptComplexity.high


def _infer_task_type(request: CanonicalRequest) -> TaskType:
    words = " ".join(m.content for m in request.messages).lower().split()
    word_set = set(words)

    best_type = TaskType.general
    best_count = 0

    for task_type, keywords in _TASK_KEYWORDS:
        count = len(word_set & keywords)
        if count > best_count:
            best_count = count
            best_type = task_type

    return best_type


def enrich(request: CanonicalRequest) -> CanonicalRequest:
    tokens = _estimate_tokens(request)
    task_type = _infer_task_type(request)
    complexity = _bucket_complexity(tokens)

    return request.model_copy(
        update={
            "estimated_input_tokens": request.estimated_input_tokens or tokens,
            "task_type": request.task_type or task_type,
            "prompt_complexity": request.prompt_complexity or complexity,
        }
    )

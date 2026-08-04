from prometheus_client import Counter, Histogram

# Buckets cover fast local responses through slow cloud responses (ms)
REQUEST_LATENCY = Histogram(
    "gateway_request_latency_ms",
    "End-to-end request latency in milliseconds",
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000, 20000, 30000],
)

# Labeled by model and routing version to distinguish V1 vs V2 routing outcomes
MODEL_CHOSEN = Counter(
    "gateway_model_chosen_total",
    "Number of successful requests routed to each model",
    ["model", "routing_version"],
)

# Labeled by provider so a single counter covers all providers
PROVIDER_ERRORS = Counter(
    "gateway_provider_errors_total",
    "Number of failed dispatch calls per provider",
    ["provider"],
)

# Distribution of fallback depth per request (0 = first model succeeded)
REQUEST_FALLBACKS = Histogram(
    "gateway_request_fallback_count",
    "Number of fallbacks per request",
    buckets=[0, 1, 2],
)

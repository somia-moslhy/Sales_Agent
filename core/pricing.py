"""
Model pricing (per-million-token) — single source of truth for cost calculations.

Stored as an in-code dictionary rather than fetched from MongoDB to avoid
extra database calls or added latency on every message, especially during
experimentation and when switching between models/providers (currently Gemini;
Groq or others may be added later via an LLM router).

Prices are documented and verified against Google's official docs
(ai.google.dev/gemini-api/docs/pricing) and multiple independent sources
as of June 2026. Update this file only if official Google prices change
or if you add a new model/provider.

The key used is (provider, model_name) — the same values returned by
`pydantic-ai` as `ModelResponse.provider_name` and `ModelResponse.model_name`.
"""

# (provider, model_name) -> {"input": $/1M tokens, "output": $/1M tokens}
PRICING_TABLE = {
    ("google", "gemini-2.5-flash"): {
        "input": 0.30,   # $/1M input tokens
        "output": 2.50,  # $/1M output tokens
    },
    ("google", "gemini-embedding-001"): {
        "input": 0.15,   # $/1M input tokens
        "output": 0.0,   # Embeddings have no output tokens (they return vectors, not text)
    },
}

# Fallback default rate used when a model is not registered in the table.
# Prevents crashes and ensures a warning/estimated flag is logged instead
# of silently computing a zero cost, which can be more misleading than
# a clear estimated value.
_FALLBACK_RATE = {"input": 0.50, "output": 2.00}


def calculate_cost(provider: str, model_name: str, input_tokens: int, output_tokens: int) -> dict:
    """
   Calculate the cost for a single model call (chat or embedding) without any
    external API or database lookups — pure arithmetic based on the
    `PRICING_TABLE` above.

    Returns a dict containing: `input_cost`, `output_cost`, `total_cost` (all
    in USD), and `is_estimated=True` when the model is not listed in the
    pricing table (fallback rates are used in that case).
    """
    key = (provider, model_name)
    rate = PRICING_TABLE.get(key)
    is_estimated = rate is None
    if rate is None:
        rate = _FALLBACK_RATE

    input_cost = (input_tokens / 1_000_000) * rate["input"]
    output_cost = (output_tokens / 1_000_000) * rate["output"]

    return {
        "input_cost": round(input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(input_cost + output_cost, 8),
        "is_estimated": is_estimated,
    }

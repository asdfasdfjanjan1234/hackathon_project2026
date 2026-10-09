"""Known AI models and how we get their energy numbers.

Local models are "measured": real watts from this machine.

Cloud models run in the provider's data center, so their energy is never on the
user's bill. It is "estimated" from token counts: list price per token stands in
for compute (the only public number that exists for every model and token type),
scaled so that a typical query on the reference model matches a published figure.
These numbers rank models; they don't measure them.
"""

LOCAL_MODELS = {
    "llama3:70b": {"avg_watts": 280, "smaller_alternative": "llama3:8b"},
    "llama3:8b": {"avg_watts": 75, "smaller_alternative": None},
    "sdxl-turbo": {"avg_watts": 220, "smaller_alternative": None},
}

# USD per 1M tokens, list prices as of Sep 25, 2026 (PROJECT_PLAN.md §3.3).
CLOUD_MODELS = {
    "claude-fable-5-1": {"name": "Fable 5.1", "provider": "Anthropic", "input": 10.0, "output": 50.0},
    "claude-opus-5-5": {"name": "Opus 5.5", "provider": "Anthropic", "input": 4.0, "output": 20.0},
    "claude-opus-5": {"name": "Opus 5", "provider": "Anthropic", "input": 5.0, "output": 25.0},
    "claude-sonnet-5-5": {"name": "Sonnet 5.5", "provider": "Anthropic", "input": 2.0, "output": 10.0},
    "claude-haiku-4-5": {"name": "Haiku 4.5", "provider": "Anthropic", "input": 1.0, "output": 5.0},
}
# Anthropic prices cache reads and writes relative to the input price.
CACHE_READ = 0.1
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.0

RELATIVE_TO = "claude-sonnet-5-5"  # energy per output token is shown relative to this model

# Published reference figure. Epoch AI estimated ≈0.3 Wh for a typical GPT-4o query
# (Feb 2025), assuming about 500 output tokens. Sonnet 5.5 is in GPT-4o's price class.
REFERENCE = {
    "wh_per_query": 0.3,
    "model": RELATIVE_TO,
    "output_tokens": 500,
    "source": "Epoch AI (Feb 2025): ≈0.3 Wh per typical GPT-4o query of ~500 output tokens",
}


def cloud_model(model_id):
    """Catalog entry for a model id, matching dated ids like claude-haiku-4-5-20251001."""
    if not model_id:
        return None
    if model_id in CLOUD_MODELS:
        return CLOUD_MODELS[model_id]
    matches = [k for k in CLOUD_MODELS if model_id.startswith(k + "-")]
    return CLOUD_MODELS[max(matches, key=len)] if matches else None


def list_cost(model_id, tokens):
    """USD at list price for tokens = {input, output, cache_read, cache_write_5m, cache_write_1h}."""
    m = cloud_model(model_id)
    if not m:
        return None
    per_input = m["input"] / 1e6
    return (tokens.get("input", 0) * per_input
            + tokens.get("output", 0) * m["output"] / 1e6
            + tokens.get("cache_read", 0) * per_input * CACHE_READ
            + tokens.get("cache_write_5m", 0) * per_input * CACHE_WRITE_5M
            + tokens.get("cache_write_1h", 0) * per_input * CACHE_WRITE_1H)


def wh_per_dollar():
    ref = CLOUD_MODELS[REFERENCE["model"]]
    return REFERENCE["wh_per_query"] / (REFERENCE["output_tokens"] * ref["output"] / 1e6)


def datacenter_wh(model_id, tokens):
    """Estimated data-center Wh for these tokens, or None for a model without a known price."""
    cost = list_cost(model_id, tokens)
    return None if cost is None else cost * wh_per_dollar()


def relative_energy(model_id):
    """Energy per output token relative to Sonnet 5.5 (2.0 means twice as much)."""
    m = cloud_model(model_id)
    return None if not m else m["output"] / CLOUD_MODELS[RELATIVE_TO]["output"]

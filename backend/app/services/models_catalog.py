"""Known AI models and how we get their energy numbers.

Local models are "measured" at the device: real watts from this machine, split per model
by each model's share of CPU and GPU use (attribution.py).

Cloud models run in the provider's data center, so their energy is never on the
user's bill. It is "estimated" from token counts: list price per token stands in
for compute (the only public number that exists for every model and token type),
scaled so that a typical query on the reference model matches a published figure.
These numbers rank models; they don't measure them.

For local models, energy per generated token follows model size: generating a token
reads every weight once, so a model half the size in bytes (fewer parameters, or fewer
bits per weight) needs about half the energy per token on the same hardware.
"""

import re

# Well-known local models, used when a device's runtimes don't say more about a model.
# Devices list their own models from Ollama and LM Studio (local_models.installed_local_models).
LOCAL_MODELS = {
    "llama3:70b": {"avg_watts": 280, "smaller_alternative": "llama3:8b", "family": "llama",
                   "params_b": 70, "quantization": "Q4_0"},
    "llama3:8b": {"avg_watts": 75, "smaller_alternative": None, "family": "llama",
                  "params_b": 8, "quantization": "Q8_0"},
    "sdxl-turbo": {"avg_watts": 220, "smaller_alternative": None, "family": "sdxl",
                   "params_b": None, "quantization": None},  # image model: no GGUF quantization
}

# Average bits per weight of common GGUF / MLX quantizations (llama.cpp figures).
QUANT_BITS = {
    "f32": 32, "fp32": 32, "f16": 16, "fp16": 16, "bf16": 16,
    "q8_0": 8.5, "q6_k": 6.6, "q5_k_m": 5.7, "q5_k_s": 5.5, "q5_0": 5.5, "q5_1": 6.0,
    "q4_k_m": 4.8, "q4_k_s": 4.6, "q4_0": 4.5, "q4_1": 5.0, "iq4_xs": 4.3, "iq4_nl": 4.5,
    "q3_k_m": 3.9, "q3_k_s": 3.5, "q3_k_l": 4.3, "q2_k": 2.6,
    "8bit": 8.5, "6bit": 6.5, "4bit": 4.5, "3bit": 3.5,
}
RECOMMENDED_QUANT = "Q4_K_M"  # the usual default: close to full quality at about 4.8 bits per weight


def quant_bits(quantization):
    """Bits per weight for a quantization name like "Q4_K_M", "F16" or "mlx-4bit"; None if unknown."""
    if not quantization:
        return None
    q = quantization.lower().replace("-", "_")
    if q in QUANT_BITS:
        return QUANT_BITS[q]
    for key in sorted(QUANT_BITS, key=len, reverse=True):
        if q.endswith(key) or q.startswith(key):
            return QUANT_BITS[key]
    m = re.match(r"i?q(\d)", q)
    return {2: 2.6, 3: 3.9, 4: 4.8, 5: 5.7, 6: 6.6, 8: 8.5}.get(int(m.group(1))) if m else None


def parse_params_b(text):
    """Billions of parameters from "8.0B", "llama3:70b", "qwen2.5-7b-instruct" or "mixtral:8x7b"."""
    if not text:
        return None
    t = str(text).lower()
    m = re.search(r"(\d+)x(\d+(?:\.\d+)?)b(?![a-z])", t)
    if m:
        return float(m.group(1)) * float(m.group(2))
    m = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*b(?![a-z])", t)
    return float(m.group(1)) if m else None


def local_name(model_label):
    """"Ollama · llama3:8b" → "llama3:8b"; sample-data names have no app prefix."""
    return model_label.split(" · ", 1)[1] if " · " in model_label else model_label


def model_bytes(info):
    """Size of a local model's weights in bytes, from its file size or parameters × bits."""
    if info.get("size_bytes"):
        return info["size_bytes"]
    bits = quant_bits(info.get("quantization"))
    if info.get("params_b") and bits:
        return info["params_b"] * 1e9 * bits / 8
    return None

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


# A date suffix on a catalog id: claude-haiku-4-5-20251001, or claude-haiku-4-5@20251001 on Vertex.
DATED = re.compile(r"[-@]\d{8}$")

# A Claude model that isn't in the catalog (newer, older, or named another way, like
# "claude-sonnet-4.5" or "us.anthropic.claude-opus-4-1-v1:0") is priced like the
# catalog's model of the same family, and marked approximate.
FAMILIES = {"fable": "claude-fable-5-1", "opus": "claude-opus-5-5",
            "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-4-5"}
FAMILY = re.compile(r"(?<![a-z])(" + "|".join(FAMILIES) + r")(?![a-z])")

# Who makes a model, from its id, for models with no catalog entry.
PROVIDERS = [
    ("Anthropic", re.compile(r"claude")),
    ("OpenAI", re.compile(r"(^|[/.])(gpt|o\d|codex|chatgpt)")),
    ("Google", re.compile(r"gemini|gemma")),
    ("Meta", re.compile(r"llama")),
    ("Mistral", re.compile(r"mistral|mixtral|codestral|devstral")),
    ("DeepSeek", re.compile(r"deepseek")),
    ("xAI", re.compile(r"grok")),
    ("Alibaba", re.compile(r"qwen")),
]


def cloud_model(model_id):
    """Catalog entry for a model id, with "approximate" set when only its family is known.

    Dated ids match their model exactly. Only a date suffix is ignored, so a new version
    like claude-opus-5-6 isn't mistaken for claude-opus-5.
    """
    if not model_id:
        return None
    key = DATED.sub("", model_id)
    if key in CLOUD_MODELS:
        return {**CLOUD_MODELS[key], "approximate": False}
    lowered = model_id.lower()
    family = FAMILY.search(lowered) if "claude" in lowered else None
    return {**CLOUD_MODELS[FAMILIES[family.group(1)]], "approximate": True} if family else None


def provider_of(model_id):
    lowered = (model_id or "").lower()
    return next((name for name, pattern in PROVIDERS if pattern.search(lowered)), None)


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

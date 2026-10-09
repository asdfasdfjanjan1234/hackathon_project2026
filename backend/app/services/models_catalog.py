"""Known AI models and how we get their energy numbers.

`source` is "measured" for local models (real watts from this machine) and
"estimated" for cloud models (token counts × published energy estimates).
"""

MODELS = {
    "llama3:70b": {"kind": "local", "source": "measured", "avg_watts": 280, "smaller_alternative": "llama3:8b"},
    "llama3:8b": {"kind": "local", "source": "measured", "avg_watts": 75, "smaller_alternative": None},
    "sdxl-turbo": {"kind": "local", "source": "measured", "avg_watts": 220, "smaller_alternative": None},
    # Cloud: Wh per 1,000 tokens. Placeholder value; replace with a cited estimate.
    "claude (cloud)": {"kind": "cloud", "source": "estimated", "wh_per_1k_tokens": 0.3, "smaller_alternative": None},
}

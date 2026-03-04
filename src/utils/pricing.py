from __future__ import annotations

import os
import re
from typing import Tuple

from models.extraction import TokenUsage


# Standard default pricing (USD per 1M tokens), overridable via env vars.
_DEFAULT_INPUT_PER_1M = 2.5
_DEFAULT_OUTPUT_PER_1M = 10.0


def _model_env_key(model_name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", (model_name or "").strip().upper()).strip("_")


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def resolve_token_prices_per_1m(model_name: str) -> Tuple[float, float]:
    key = _model_env_key(model_name)
    in_default = _float_env("OPENAI_PRICE_INPUT_PER_1M", _DEFAULT_INPUT_PER_1M)
    out_default = _float_env("OPENAI_PRICE_OUTPUT_PER_1M", _DEFAULT_OUTPUT_PER_1M)
    input_rate = _float_env(f"OPENAI_PRICE_{key}_INPUT_PER_1M", in_default)
    output_rate = _float_env(f"OPENAI_PRICE_{key}_OUTPUT_PER_1M", out_default)
    return input_rate, output_rate


def estimate_price_usd(model_name: str, usage: TokenUsage | None) -> float | None:
    if usage is None:
        return None
    input_rate, output_rate = resolve_token_prices_per_1m(model_name)
    prompt_cost = (max(usage.prompt_tokens, 0) / 1_000_000.0) * input_rate
    completion_cost = (max(usage.completion_tokens, 0) / 1_000_000.0) * output_rate
    return round(prompt_cost + completion_cost, 8)

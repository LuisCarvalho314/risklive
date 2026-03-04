from __future__ import annotations

from models.extraction import TokenUsage
from utils.pricing import estimate_price_usd, resolve_token_prices_per_1m


def test_resolve_token_prices_per_1m_defaults():
    assert resolve_token_prices_per_1m("openai_chat") == (2.5, 10.0)
    assert resolve_token_prices_per_1m("gpt4") == (2.5, 10.0)
    assert resolve_token_prices_per_1m("gpt-4o") == (2.5, 10.0)


def test_resolve_token_prices_per_1m_model_override(monkeypatch):
    monkeypatch.setenv("OPENAI_PRICE_INPUT_PER_1M", "2")
    monkeypatch.setenv("OPENAI_PRICE_OUTPUT_PER_1M", "8")
    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_INPUT_PER_1M", "3")
    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_OUTPUT_PER_1M", "12")

    input_rate, output_rate = resolve_token_prices_per_1m("gpt-4o")
    assert input_rate == 3
    assert output_rate == 12


def test_estimate_price_usd_none_usage():
    assert estimate_price_usd("gpt-4o", None) is None


def test_estimate_price_usd_uses_prompt_and_completion(monkeypatch):
    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_INPUT_PER_1M", "1")
    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_OUTPUT_PER_1M", "2")
    usage = TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300)
    assert estimate_price_usd("gpt-4o", usage) == 0.0005

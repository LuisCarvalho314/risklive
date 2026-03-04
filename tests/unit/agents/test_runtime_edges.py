"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from types import SimpleNamespace

from agents import registry as agent_registry
from agents.extraction import agent as extraction_agent
from models.extraction import ExtractionResult


def test_extract_record_usage_mapping(monkeypatch):
    class DummyRun:
        def __init__(self):
            self.output = ExtractionResult(short_summary="x")
            self.response = SimpleNamespace(usage=SimpleNamespace(input_tokens=1, response_tokens=2, total_tokens=3))

    class DummyAgent:
        def run_sync(self, prompt):
            return DummyRun()

    monkeypatch.setattr(extraction_agent, "build_extraction_agent", lambda *args, **kwargs: DummyAgent())
    monkeypatch.setattr(extraction_agent, "load_prompts", lambda: {"EXTRACTION_PROMPT": "P"})
    record = extraction_agent.extract_record("text")
    assert record.metrics is not None
    assert record.metrics.token_usage is not None
    assert record.metrics.token_usage.total_tokens == 3
    assert record.metrics.price_usd is not None
    assert record.metrics.price_usd > 0


def test_extract_record_usage_pricing_env_override(monkeypatch):
    class DummyRun:
        def __init__(self):
            self.output = ExtractionResult(short_summary="x")
            self.response = SimpleNamespace(usage=SimpleNamespace(input_tokens=10, response_tokens=20, total_tokens=30))

    class DummyAgent:
        def run_sync(self, prompt):
            return DummyRun()

    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_INPUT_PER_1M", "1")
    monkeypatch.setenv("OPENAI_PRICE_GPT_4O_OUTPUT_PER_1M", "2")
    monkeypatch.setattr(extraction_agent, "build_extraction_agent", lambda *args, **kwargs: DummyAgent())
    monkeypatch.setattr(extraction_agent, "load_prompts", lambda: {"EXTRACTION_PROMPT": "P"})

    record = extraction_agent.extract_record("text", model_name="gpt-4o")
    assert record.metrics is not None
    # 10*1 + 20*2 token-dollar-units per 1M tokens => 0.00005
    assert record.metrics.price_usd == 0.00005


def test_registry_reset_all(monkeypatch):
    called = {"extract": False, "report": False}
    monkeypatch.setattr(agent_registry, "reset_extraction_agent", lambda: called.__setitem__("extract", True))
    monkeypatch.setattr(agent_registry, "reset_report_agent", lambda: called.__setitem__("report", True))
    agent_registry.reset_all_agents()
    assert called["extract"] and called["report"]

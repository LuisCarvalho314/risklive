"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from agents.extraction import agent as extraction_agent
from agents.report import agent as report_agent
from models.extraction import ExtractionResult
from models.report import ReportEntry


def test_extraction_agent_uses_prompt(monkeypatch, dummy_agent_factory):
    output = ExtractionResult(short_summary="s")
    dummy = dummy_agent_factory(output)

    def _fake_build_agent(_model_name="gpt-4o"):
        return dummy

    monkeypatch.setattr(extraction_agent, "build_extraction_agent", _fake_build_agent)
    monkeypatch.setattr(extraction_agent, "load_prompts", lambda: {"EXTRACTION_PROMPT": "PROMPT"})

    result = extraction_agent.extract("TEXT")
    assert result.short_summary == "s"
    assert "PROMPT" in dummy.last_prompt


def test_report_agent_uses_prompt(monkeypatch, dummy_agent_factory):
    output = ReportEntry(keyword="k", input_prompt="p", response="r")
    dummy = dummy_agent_factory(output)

    def _fake_build_agent(_model_name="gpt-4o"):
        return dummy

    monkeypatch.setattr(report_agent, "build_report_agent", _fake_build_agent)
    monkeypatch.setattr(report_agent, "load_prompts", lambda: {"REPORT_PROMPT": "RP"})

    result = report_agent.generate_report_section("TEXT")
    assert result.keyword == "k"
    assert "RP" in dummy.last_prompt

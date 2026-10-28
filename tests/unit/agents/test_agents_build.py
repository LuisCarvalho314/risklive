"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import pytest

from agents.extraction import agent as extraction_agent
from agents.report import agent as report_agent


@pytest.fixture(autouse=True)
def isolated_agent_caches(monkeypatch):
    # Construction must not reuse cached agents or leave dummy agents behind.
    monkeypatch.setattr(extraction_agent, "_EXTRACTION_AGENT", None)
    monkeypatch.setattr(report_agent, "_REPORT_AGENT", None)


def test_build_extraction_agent(monkeypatch):
    class DummyAgent:
        def __init__(self, model, instructions=None, output_type=None):
            self.model = model
            self.instructions = instructions
            self.output_type = output_type

    monkeypatch.setattr(extraction_agent, "Agent", DummyAgent)
    monkeypatch.setattr(extraction_agent, "build_model", lambda name: "model")

    agent = extraction_agent.build_extraction_agent("gpt-4o")
    assert agent.model == "model"


def test_build_report_agent(monkeypatch):
    class DummyAgent:
        def __init__(self, model, instructions=None, output_type=None):
            self.model = model
            self.instructions = instructions
            self.output_type = output_type

    monkeypatch.setattr(report_agent, "Agent", DummyAgent)
    monkeypatch.setattr(report_agent, "build_model", lambda name: "model")

    agent = report_agent.build_report_agent("gpt-4o")
    assert agent.model == "model"

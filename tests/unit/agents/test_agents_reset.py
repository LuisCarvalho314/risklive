from __future__ import annotations

from agents.extraction import agent as extraction_agent
from agents.report import agent as report_agent


def test_agent_reset_paths():
    extraction_agent._EXTRACTION_AGENT = object()
    extraction_agent.reset_extraction_agent()
    assert extraction_agent._EXTRACTION_AGENT is None

    report_agent._REPORT_AGENT = object()
    report_agent.reset_report_agent()
    assert report_agent._REPORT_AGENT is None

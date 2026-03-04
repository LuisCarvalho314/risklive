"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from utils import llm_rate_limit


def test_rate_limit_sleep_branches(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_MIN_INTERVAL_SEC", "0")
    llm_rate_limit._LAST_CALL_TS = 0.0
    llm_rate_limit.rate_limit_sleep()
    monkeypatch.setenv("AZURE_OPENAI_MIN_INTERVAL_SEC", "0.01")
    monkeypatch.setattr(llm_rate_limit.time, "time", lambda: 100.0)
    monkeypatch.setattr(llm_rate_limit.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(llm_rate_limit.time, "sleep", lambda *_args: None)
    llm_rate_limit._LAST_CALL_TS = 99.999
    llm_rate_limit.rate_limit_sleep()

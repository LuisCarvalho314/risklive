from __future__ import annotations

from config import get_config, load_prompts


def test_get_config_reads_file():
    cfg = get_config()
    assert cfg.categories == ["CatA"]
    assert cfg.queries == ["QueryA"]
    assert cfg.trending == ["TrendA"]


def test_load_prompts():
    prompts = load_prompts()
    assert prompts["EXTRACTION_PROMPT"] == "EXTRACTION_PROMPT"
    assert prompts["REPORT_PROMPT"] == "REPORT_PROMPT"


def test_get_settings_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    from config import settings as settings_module
    settings_module._settings = None
    import os
    assert os.getenv("OPENAI_API_KEY") == "key"
    settings = settings_module.get_settings()
    assert settings.openai_api_key == "key"

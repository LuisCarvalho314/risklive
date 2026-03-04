"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters import llm as llm_adapter
from models.errors import ConfigError, ExternalServiceError


def test_llm_build_model_config_error(monkeypatch):
    monkeypatch.setattr(llm_adapter, "get_settings", lambda: SimpleNamespace(azure_openai_config=SimpleNamespace(api_base="", api_key=SimpleNamespace(get_secret_value=lambda: ""), api_version="")))
    with pytest.raises(ConfigError):
        llm_adapter.build_model("gpt-4o")


def test_llm_build_model_external_service_error(monkeypatch):
    cfg = SimpleNamespace(
        api_base="https://example.openai.azure.com",
        api_key=SimpleNamespace(get_secret_value=lambda: "k"),
        api_version="2024-10-21",
    )
    monkeypatch.setattr(llm_adapter, "get_settings", lambda: SimpleNamespace(azure_openai_config=cfg))
    monkeypatch.setattr(llm_adapter, "AzureProvider", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(ExternalServiceError):
        llm_adapter.build_model("gpt-4o")

"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import runpy
from types import SimpleNamespace

import pytest

from adapters import valyu as valyu_adapter
from models.errors import ExternalServiceError


def test_valyu_client_init_and_search_exception(monkeypatch):
    monkeypatch.setattr(
        valyu_adapter,
        "get_valyu_config",
        lambda: SimpleNamespace(
            api_key=SimpleNamespace(get_secret_value=lambda: "key"),
            runtime=SimpleNamespace(excluded_sources=[], max_num_results=1),
        ),
    )
    monkeypatch.setattr(valyu_adapter, "Valyu", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(ExternalServiceError):
        valyu_adapter.fetch_news(["q"])

    class DummyValyu:
        def __init__(self, _api_key):
            pass

        def search(self, *args, **kwargs):
            raise RuntimeError("search-fail")

    monkeypatch.setattr(valyu_adapter, "Valyu", DummyValyu)
    with pytest.raises(ExternalServiceError):
        valyu_adapter.fetch_news(["q"])


def test_valyu_empty_api_key_branch(monkeypatch):
    monkeypatch.setattr(
        valyu_adapter,
        "get_valyu_config",
        lambda: SimpleNamespace(
            api_key=SimpleNamespace(get_secret_value=lambda: ""),
            runtime=SimpleNamespace(excluded_sources=[], max_num_results=1),
        ),
    )
    with pytest.raises(Exception):
        valyu_adapter.fetch_news(["q"])


def test_llm_module_main_block(monkeypatch):
    monkeypatch.setenv("VALYU_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.openai.azure.com")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_VERSION", "2024-10-21")
    runpy.run_module("adapters.llm", run_name="__main__")

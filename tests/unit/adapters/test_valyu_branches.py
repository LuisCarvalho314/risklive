"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from adapters import valyu as valyu_adapter
from models.errors import ConfigError


def test_valyu_no_key(monkeypatch):
    from config import settings as settings_module

    settings_module._settings = None
    monkeypatch.delenv("VALYU_API_KEY", raising=False)

    try:
        valyu_adapter.fetch_news(["q"], hours=1)
    except ConfigError as exc:
        assert exc.code == "config_error"
    else:
        raise AssertionError("Expected ConfigError when VALYU_API_KEY is missing")


def test_valyu_empty_query(monkeypatch):
    class DummyValyu:
        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, *args, **kwargs):
            raise AssertionError("should not be called")

    monkeypatch.setenv("VALYU_API_KEY", "key")
    from config import settings as settings_module

    settings_module._settings = None
    monkeypatch.setattr(valyu_adapter, "Valyu", DummyValyu)

    articles = valyu_adapter.fetch_news([""], hours=1)
    assert articles == []


def test_valyu_unsuccessful(monkeypatch):
    class DummyResponse:
        success = False
        results = []

    class DummyValyu:
        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, *args, **kwargs):
            return DummyResponse()

    monkeypatch.setenv("VALYU_API_KEY", "key")
    from config import settings as settings_module

    settings_module._settings = None
    monkeypatch.setattr(valyu_adapter, "Valyu", DummyValyu)

    articles = valyu_adapter.fetch_news(["q"], hours=1)
    assert articles == []

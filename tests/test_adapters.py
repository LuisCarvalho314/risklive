from __future__ import annotations

from types import SimpleNamespace

from adapters import llm as llm_adapter
from adapters import valyu as valyu_adapter
from models.article import ArticleSource


def test_build_model_uses_env(monkeypatch):
    class DummyProvider:
        def __init__(self, azure_endpoint, api_key, api_version):
            self.azure_endpoint = azure_endpoint
            self.api_key = api_key
            self.api_version = api_version

    class DummyModel:
        def __init__(self, model_name, provider=None):
            self.model_name = model_name
            self.provider = provider

    monkeypatch.setattr(llm_adapter, "AzureProvider", DummyProvider)
    monkeypatch.setattr(llm_adapter, "OpenAIChatModel", DummyModel)
    monkeypatch.setenv("OPENAI_API_BASE", "base")
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_API_VERSION", "v")
    from config import settings as settings_module
    settings_module._settings = None

    model = llm_adapter.build_model("gpt-4o")
    assert model.model_name == "gpt-4o"
    assert model.provider.api_key == "key"


def test_valyu_fetch_news(monkeypatch):
    class DummyResult:
        def __init__(self, title, url):
            self._data = {"title": title, "url": url, "description": "d"}

        def model_dump(self):
            return dict(self._data)

    class DummyResponse:
        def __init__(self):
            self.success = True
            self.results = [DummyResult("t", "https://example.com")]

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
    assert articles
    assert articles[0].source == ArticleSource.valyu

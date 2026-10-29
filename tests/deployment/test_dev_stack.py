"""Static resolved deployment and lifecycle checks; never starts containers."""
import pytest


def test_provider_guards_precede_construction(monkeypatch):
    from adapters import llm, valyu
    monkeypatch.setenv('RISKLIVE_EXTERNAL_APIS_ENABLED', 'false')
    def forbidden(*args, **kwargs):
        pytest.fail('Provider constructed while offline')
    monkeypatch.setattr(llm, 'AzureProvider', forbidden)
    monkeypatch.setattr(valyu, 'Valyu', forbidden)
    from models.errors import ConfigError
    with pytest.raises(ConfigError, match='External APIs disabled'):
        llm.build_model()
    with pytest.raises(ConfigError, match='External APIs disabled'):
        valyu.fetch_news(['fixture'])


def test_existing_model_cannot_bypass_offline(monkeypatch):
    import asyncio
    from adapters.llm import OpenAIChatModel
    from models.errors import ConfigError
    monkeypatch.setenv('RISKLIVE_EXTERNAL_APIS_ENABLED', 'false')
    with pytest.raises(ConfigError, match='External APIs disabled'):
        asyncio.run(OpenAIChatModel.request(object(), [], None, None))


def test_development_registration_forbidden_even_live(monkeypatch):
    from app.scheduler_jobs import register_jobs
    monkeypatch.setenv('RISKLIVE_ENVIRONMENT', 'development')
    monkeypatch.setenv('RISKLIVE_EXTERNAL_APIS_ENABLED', 'true')
    with pytest.raises(RuntimeError, match='forbidden'):
        register_jobs(None)


def test_stream_guard_precedes_network(monkeypatch):
    import asyncio
    from adapters.llm import OpenAIChatModel
    from models.errors import ConfigError
    monkeypatch.setenv('RISKLIVE_EXTERNAL_APIS_ENABLED', 'false')
    async def stream():
        async with OpenAIChatModel.request_stream(object(), [], None, None):
            pytest.fail('Stream opened offline')
    with pytest.raises(ConfigError, match='External APIs disabled'):
        asyncio.run(stream())


def test_live_request_audits_usage_without_payload(monkeypatch, caplog):
    import asyncio
    import logging
    from types import SimpleNamespace
    from adapters.llm import OpenAIChatModel, BaseOpenAIChatModel
    monkeypatch.setenv('RISKLIVE_EXTERNAL_APIS_ENABLED', 'true')
    async def request(*args, **kwargs):
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=3, output_tokens=2))
    monkeypatch.setattr(BaseOpenAIChatModel, 'request', request)
    with caplog.at_level(logging.INFO):
        asyncio.run(OpenAIChatModel.request(OpenAIChatModel.__new__(OpenAIChatModel), ['private prompt'], None, None))
    assert 'provider=azure_openai operation=chat request_count=1' in caplog.text
    assert 'input_tokens=3 output_tokens=2' in caplog.text
    assert 'private prompt' not in caplog.text

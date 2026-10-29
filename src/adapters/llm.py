"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from adapters.external_policy import require_external_api, audit_request

from pydantic_ai.models.openai import OpenAIChatModel as BaseOpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider

from config.settings import get_settings
from models.errors import ConfigError, ExternalServiceError
from utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIChatModel(BaseOpenAIChatModel):
    async def request(self, *args, **kwargs):
        require_external_api("azure_openai", "chat")
        audit_request("azure_openai", "chat")
        response = await super().request(*args, **kwargs)
        # Separate completion record; request count was already recorded above.
        usage = response.usage
        logger.info("provider_usage provider=azure_openai operation=chat input_tokens=%s output_tokens=%s",
                    usage.input_tokens, usage.output_tokens)
        return response

    @asynccontextmanager
    async def request_stream(self, *args, **kwargs):
        require_external_api("azure_openai", "chat_stream")
        audit_request("azure_openai", "chat_stream")
        async with super().request_stream(*args, **kwargs) as response:
            yield response
            usage = response.usage()
            logger.info("provider_usage provider=azure_openai operation=chat_stream input_tokens=%s output_tokens=%s",
                        usage.input_tokens, usage.output_tokens)


def build_model(model_name: str = "gpt-4o") -> OpenAIChatModel:
    require_external_api("azure_openai", "build_model")
    started = time.perf_counter()
    model_config = get_settings().azure_openai_config
    azure_endpoint = model_config.api_base
    api_key = model_config.api_key.get_secret_value()
    api_version = model_config.api_version
    if not azure_endpoint or not api_key or not api_version:
        raise ConfigError("Missing Azure OpenAI configuration")
    try:
        provider = AzureProvider(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version
        )
        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(
            "llm_model_init_succeeded",
            extra={
                "event": "llm_model_init_succeeded",
                "component": "adapters.llm",
                "operation": "build_model",
                "stage": "extract",
                "stage_status": "succeeded",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "status": "ok",
            },
        )
        return model
    except Exception as exc:
        logger.error(
            "llm_model_init_failed",
            extra={
                "event": "llm_model_init_failed",
                "component": "adapters.llm",
                "operation": "build_model",
                "stage": "extract",
                "stage_status": "failed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error_code": exc.__class__.__name__,
            },
        )
        raise ExternalServiceError(
            "Unable to initialize LLM provider",
            details={"exception": exc.__class__.__name__},
            retryable=False,
        ) from exc

if __name__ == "__main__":
    print("Starting Azure model creation")
    model_config = get_settings().azure_openai_config
    print(model_config.api_base)
    print(model_config.api_version)
    model = build_model()
    print(f"Model {model} created successfully")

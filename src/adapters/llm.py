from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider

from config.settings import get_settings


def build_model(model_name: str = "gpt-4o") -> OpenAIChatModel:
    model_config = get_settings().azure_openai_config
    azure_endpoint = model_config.api_base
    api_key = model_config.api_key.get_secret_value()
    api_version = model_config.api_version
    provider = AzureProvider(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version
    )
    return OpenAIChatModel(model_name, provider=provider)

if __name__ == "__main__":
    print("Starting Azure model creation")
    model_config = get_settings().azure_openai_config
    print(model_config.openai_api_base)
    print(model_config.openai_api_key)
    print(model_config.openai_api_version)
    model = build_model()
    print(f"Model {model} created successfully")

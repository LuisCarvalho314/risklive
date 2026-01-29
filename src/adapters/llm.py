from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider

from config.settings import get_settings


def build_model(model_name: str = "gpt-4o") -> OpenAIChatModel:
    settings = get_settings()
    azure_endpoint = settings.openai_api_base
    api_key = settings.openai_api_key
    api_version = settings.openai_api_version
    provider = AzureProvider(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version
    )
    return OpenAIChatModel(model_name, provider=provider)

if __name__ == "__main__":
    print("Starting Azure model creation")
    settings = get_settings()
    print(settings.openai_api_base)
    print(settings.openai_api_key)
    print(settings.openai_api_version)
    model = build_model()
    print(f"Model {model} created successfully")

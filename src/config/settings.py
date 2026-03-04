"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import os

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr, Field

ROOT_DIR = Path(__file__).resolve().parents[2]

class ValyuConfig(BaseModel):
    api_key: SecretStr
    runtime: ValyuRuntimeConfig

class ValyuRuntimeConfig(BaseModel):
    excluded_sources: Optional[List[str]]
    max_num_results: int


class AzureOpenAIConfig(BaseModel):
    api_type: str = "azure"
    api_base: str
    api_key: SecretStr
    api_version: str

class RiskLiveConfig(BaseModel):
    categories: List[str] = []
    queries: List[str] = []
    trending: List[str] = []
    prompt_paths: Dict[str, str] = {}
    interval: int = 15
    save_dir: Dict[str, str] = {}
    cleanup_days_to_keep: int = 3

    valyu: ValyuRuntimeConfig = Field(default_factory=ValyuRuntimeConfig)


@dataclass(frozen=True)
class Settings:
    valyu_config: ValyuConfig
    azure_openai_config: AzureOpenAIConfig


def load_config(path: Path | None = None) -> RiskLiveConfig:
    default_path = ROOT_DIR / "config" / "config.yml"
    config_path = path or default_path

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    loaded_yaml = yaml.safe_load(config_path.read_text()) or {}

    valyu_block = loaded_yaml.get("VALYU", {})

    normalized = {
        "categories": loaded_yaml.get("CATEGORIES", []),
        "queries": loaded_yaml.get("QUERIES", []),
        "trending": loaded_yaml.get("TRENDING", []),
        "excluded_sources": loaded_yaml.get("EXCLUDED_SOURCES", []),
        "prompt_paths": loaded_yaml.get("PROMPT_PATHS", {}),
        "interval": loaded_yaml.get("INTERVAL", 15),
        "save_dir": loaded_yaml.get("SAVE_DIR", {}),
        "cleanup_days_to_keep": loaded_yaml.get("CLEANUP_DAYS_TO_KEEP", 3),
        "valyu": {
            "excluded_sources": valyu_block.get("VALYU_EXCLUDED_SOURCES", []),
            "max_num_results": valyu_block.get("VALYU_MAX_NUM_RESULTS", 50),
        }
    }
    return RiskLiveConfig(**normalized)


_settings: Settings | None = None
_config: RiskLiveConfig | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        load_dotenv(ROOT_DIR / ".env")
        _settings = Settings(
            valyu_config=get_valyu_config(),
            azure_openai_config=get_azure_openai_config(),
        )
    return _settings


def _load_environment_variables() -> None:
    load_dotenv(ROOT_DIR / ".env")

def _require_environment_variable(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable {name} is required.")
    return value

def get_valyu_config() -> ValyuConfig:
    _load_environment_variables()

    risklive_config = get_config()

    valyu_api_key = SecretStr(_require_environment_variable("VALYU_API_KEY"))
    return ValyuConfig(api_key=valyu_api_key, runtime=risklive_config.valyu)

def get_azure_openai_config() -> AzureOpenAIConfig:
    _load_environment_variables()

    # Prefer "OPENAI_*" but allow Azure fallbacks for compatibility.
    api_type = os.getenv("OPENAI_API_TYPE") or os.getenv(
        "AZURE_OPENAI_API_TYPE") or "azure"
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv(
        "AZURE_OPENAI_ENDPOINT")
    api_key = SecretStr(os.getenv("OPENAI_API_KEY") or os.getenv(
        "AZURE_OPENAI_API_KEY"))
    api_version = os.getenv("OPENAI_API_VERSION") or os.getenv(
        "AZURE_OPENAI_API_VERSION")

    return AzureOpenAIConfig(
        api_type=api_type,
        api_base=api_base,
        api_key=api_key,
        api_version=api_version,
    )


def get_config() -> RiskLiveConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config

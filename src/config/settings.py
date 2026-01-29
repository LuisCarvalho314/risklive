from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import os

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]


class RiskLiveConfig(BaseModel):
    categories: List[str] = []
    queries: List[str] = []
    trending: List[str] = []
    excluded_sources: List[str] = []
    prompt_paths: Dict[str, str] = {}
    interval: int = 15
    save_dir: Dict[str, str] = {}
    cleanup_days_to_keep: int = 3


@dataclass(frozen=True)
class Settings:
    openai_api_type: str = "azure"
    openai_api_base: str | None = None
    openai_api_key: str | None = None
    openai_api_version: str | None = None
    valyu_api_key: str | None = None


def load_config(path: Path | None = None) -> RiskLiveConfig:
    default_path = ROOT_DIR / "config" / "config.yml"
    config_path = path or default_path
    data = yaml.safe_load(config_path.read_text()) or {}
    normalized = {
        "categories": data.get("CATEGORIES", []),
        "queries": data.get("QUERIES", []),
        "trending": data.get("TRENDING", []),
        "excluded_sources": data.get("EXCLUDED_SOURCES", []),
        "prompt_paths": data.get("PROMPT_PATHS", {}),
        "interval": data.get("INTERVAL", 15),
        "save_dir": data.get("SAVE_DIR", {}),
        "cleanup_days_to_keep": data.get("CLEANUP_DAYS_TO_KEEP", 3),
    }
    return RiskLiveConfig(**normalized)


_settings: Settings | None = None
_config: RiskLiveConfig | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        load_dotenv(ROOT_DIR / ".env")
        _settings = Settings(
            # Prefer OpenAI envs but allow Azure fallbacks for compatibility.
            openai_api_type=os.getenv("OPENAI_API_TYPE") or os.getenv("AZURE_OPENAI_API_TYPE", "azure"),
            openai_api_base=os.getenv("OPENAI_API_BASE") or os.getenv("AZURE_OPENAI_ENDPOINT"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"),
            openai_api_version=os.getenv("OPENAI_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION"),
            valyu_api_key=os.getenv("VALYU_API_KEY"),
        )
    return _settings


def get_config() -> RiskLiveConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config

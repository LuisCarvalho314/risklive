from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import settings as settings_module


def _write_config(root: Path) -> None:
    cfg_dir = root / "config"
    prompts_dir = root / "prompts"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "info_extraction.txt").write_text("EXTRACTION_PROMPT")
    (prompts_dir / "report_prompt.txt").write_text("REPORT_PROMPT")

    cfg = """CATEGORIES:
  - CatA
QUERIES:
  - QueryA
TRENDING:
  - TrendA
EXCLUDED_SOURCES:
  - example.com
PROMPT_PATHS:
  EXTRACTION_PROMPT: 'prompts/info_extraction.txt'
  REPORT_PROMPT: 'prompts/report_prompt.txt'
INTERVAL: 15
SAVE_DIR:
  CSV_DATA_DIR: 'results/data/'
  CSV_DATA_BACKUP_DIR: 'results/backup_data/'
  TOPIC_MODEL_DIR: 'results/models/'
  TOPIC_MODEL_IMAGE_DIR: 'results/images/'
CLEANUP_DAYS_TO_KEEP: 3
"""
    (cfg_dir / "config.yml").write_text(cfg)


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch, tmp_path):
    # Reset module globals and redirect ROOT_DIR for isolated tests.
    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._settings = None
    settings_module._config = None
    _write_config(tmp_path)
    yield


class DummyRunResult:
    def __init__(self, output):
        self.output = output


class DummyAgent:
    def __init__(self, output):
        self._output = output
        self.last_prompt = None

    def run_sync(self, prompt):
        self.last_prompt = prompt
        return DummyRunResult(self._output)


@pytest.fixture
def dummy_agent_factory():
    def _factory(output):
        return DummyAgent(output)

    return _factory

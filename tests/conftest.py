"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tests.fixtures.runtime_guard import install

install()
from tests.fixtures.offline_models import install as install_offline_models

install_offline_models()

from config import settings as settings_module


def _write_config(root: Path) -> None:
    cfg_dir = root / "config"
    prompts_dir = root / "prompts"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "info_extraction.txt").write_text("EXTRACTION_PROMPT")
    (prompts_dir / "report_prompt.txt").write_text("REPORT_PROMPT")
    (prompts_dir / "report_merge_prompt.txt").write_text("REPORT_MERGE_PROMPT")

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
  REPORT_MERGE_PROMPT: 'prompts/report_merge_prompt.txt'
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
    monkeypatch.setenv("VALYU_API_KEY", "test-valyu-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.openai.azure.com")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_API_VERSION", "2024-10-21")
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


@pytest.fixture(autouse=True)
def forbid_background_threads(monkeypatch):
    import threading

    def forbidden(*args, **kwargs):
        from tests.fixtures.runtime_guard import VIOLATIONS
        VIOLATIONS.append("background thread start")
        pytest.fail("Test runtime guard: background thread start")

    monkeypatch.setattr(threading.Thread, "start", forbidden)


@pytest.fixture(autouse=True)
def frozen_archive_clock(request, monkeypatch):
    if not ({"integration", "regression"} & {m.name for m in request.node.iter_markers()}):
        return
    from datetime import datetime, timezone
    from services import dashboard_export

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 1, 15, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(dashboard_export, "datetime", FixedDatetime)


def pytest_sessionfinish(session, exitstatus):
    from tests.fixtures.runtime_guard import VIOLATIONS
    if VIOLATIONS:
        session.exitstatus = 1
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("!", "Runtime guard violations: " + "; ".join(VIOLATIONS))

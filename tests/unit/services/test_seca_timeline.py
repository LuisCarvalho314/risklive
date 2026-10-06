"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services import seca_timeline


def _write_llm_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Title",
        "URL",
        "Description",
        "Timestamp",
        "ShortSummary",
        "API_Timestamp",
        "Query",
        "NewsCategory",
        "AlertFlag",
        "Relevance",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(day, url=None, **extra):
    return {
        "Title": "Fixture risk",
        "URL": url or f"https://fixture/{day}",
        "Timestamp": f"{day}T12:00:00Z",
        "Relevance": "Yes",
        **extra,
    }


@pytest.fixture
def fake_cli(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(seca_timeline, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(seca_timeline, "_resolve_seca_command", lambda _: ["realtime-seca-cli"])
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] is None
        if command[1] == "from-csv":
            with Path(command[2]).open() as handle:
                rows = list(csv.DictReader(handle))
            index = int(command[command.index("--batch-index") + 1])
            Path(command[3]).write_text(json.dumps({"batch_index": index, "sources": [
                {"source_id": f"row_{i}", "batch_index": index, "tokens": ["risk"], "metadata": row}
                for i, row in enumerate(rows)
            ]}))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        assert command[1] == "update", "Production must never run baseline after bootstrap"
        config = json.loads(Path(command[command.index("--config") + 1]).read_text())
        assert config["memory_mode"] == "SlidingWindow"
        batch = json.loads(Path(command[2]).read_text())
        previous = json.loads(Path(command[command.index("--state-in") + 1]).read_text()) if "--state-in" in command else None
        if previous:
            assert previous["last_processed_batch_index"] + 1 == batch["batch_index"]
        retained = ((previous or {}).get("state", {}).get("processed_batches", []) + [batch])[-config["max_batches_in_memory"]:]
        sources = [source for b in retained for source in b["sources"]]
        state = {"schema_version": 3, "last_processed_batch_index": batch["batch_index"],
            "config": config, "state": {"processed_batches": retained, "model_identity": (previous or {}).get("state", {}).get("model_identity", "one-model")}}
        tree = {"hkts": [], "nodes": [], "word_legend": [], "logically_removed_hkts": [],
            "source_legend": [{"internal_source_id": i, "external_source_id": src["source_id"]} for i, src in enumerate(sources)]}
        Path(command[command.index("--state-out") + 1]).write_text(json.dumps(state))
        Path(command[command.index("--dump-tree-verbose") + 1]).write_text(json.dumps(tree))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"batch_index": batch["batch_index"], "sources_processed": len(batch["sources"]), "notes": []}), stderr="")
    monkeypatch.setattr(seca_timeline.subprocess, "run", run)
    return calls


def _manifest(root, days=30):
    directory = root / f"results/web/newsmap/seca-light-{days}d"
    return directory, json.loads((directory / "timeline_manifest.json").read_text())


def _state(root):
    import sqlite3
    with sqlite3.connect(root / "runtime/seca/stream.sqlite3") as db:
        return json.loads(db.execute("SELECT state FROM model").fetchone()[0])


def test_second_run_loads_persisted_model_and_keeps_historical_snapshot(fake_cli, tmp_path):
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    _write_llm_csv(source, [_row("2026-10-01")])
    assert seca_timeline.run_seca_light_timeline(batch_id="batch-one")
    directory, first_manifest = _manifest(tmp_path)
    first_tree = (directory / first_manifest["files"][0]).read_bytes()
    _write_llm_csv(source, [_row("2026-10-01"), _row("2026-10-02")])
    assert seca_timeline.run_seca_light_timeline(batch_id="batch-two")
    updates = [c for c in fake_cli if c[1] == "update"]
    assert "--state-in" not in updates[0]
    assert "--state-in" in updates[1]
    assert _state(tmp_path)["last_processed_batch_index"] == 1
    assert (directory / first_manifest["files"][0]).read_bytes() == first_tree
    for days in (30, 7, 3):
        assert _manifest(tmp_path, days)[1]["batch_ids"] == ["batch-one", "batch-two"]


def test_batch_id_retry_is_idempotent(fake_cli, tmp_path):
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", [_row("2026-10-01")])
    seca_timeline.run_seca_light_timeline(batch_id="same")
    before = _state(tmp_path)
    fake_cli.clear()
    assert seca_timeline.run_seca_light_timeline(batch_id="same")
    assert not fake_cli
    assert _state(tmp_path) == before


def test_duplicate_article_is_not_reingested_after_source_window_expires(fake_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("RISKLIVE_SECA_GAMMA_BATCHES", "1")
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    _write_llm_csv(source, [_row("2026-10-01", "https://same"), _row("2026-10-02", "https://same")])
    seca_timeline.run_seca_light_timeline(batch_id="one")
    for n in range(2, 6):
        assert seca_timeline.run_seca_light_timeline(batch_id=str(n))
    assert _state(tmp_path)["state"]["processed_batches"][0]["sources"] == []
    assert len([c for c in fake_cli if c[1] == "from-csv"]) == 1


def test_gamma_three_bounds_active_batches_and_preserves_history(fake_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("RISKLIVE_SECA_GAMMA_BATCHES", "3")
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    for n in range(1, 13):
        _write_llm_csv(source, [_row("2026-10-01", f"https://article/{n}")])
        assert seca_timeline.run_seca_light_timeline(batch_id=f"batch-{n}")
        assert len(_state(tmp_path)["state"]["processed_batches"]) <= 3
        if n == 4:
            assert _state(tmp_path)["state"]["processed_batches"][0]["batch_index"] == 1
    assert len(_manifest(tmp_path)[1]["files"]) == 12


def test_empty_run_preserves_model_and_commits_empty_batch(fake_cli, tmp_path):
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    _write_llm_csv(source, [_row("2026-10-01")])
    seca_timeline.run_seca_light_timeline(batch_id="one")
    _write_llm_csv(source, [])
    assert seca_timeline.run_seca_light_timeline(batch_id="empty")
    assert _state(tmp_path)["state"]["model_identity"] == "one-model"
    assert _state(tmp_path)["state"]["processed_batches"][-1]["sources"] == []


def test_empty_bootstrap_waits_for_sources(fake_cli, tmp_path):
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", [])
    assert seca_timeline.run_seca_light_timeline() is None
    assert not fake_cli


@pytest.mark.parametrize("failure", ["from-csv", "update", "timeout", "missing", "invalid"])
def test_failed_processing_preserves_model_history_and_ingestion_receipts(fake_cli, tmp_path, monkeypatch, failure):
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    _write_llm_csv(source, [_row("2026-10-01")])
    seca_timeline.run_seca_light_timeline(batch_id="one")
    before = _state(tmp_path)
    directory, _ = _manifest(tmp_path)
    files = {p.name: p.read_bytes() for p in directory.iterdir()}
    original = seca_timeline.subprocess.run
    def fail(command, **kwargs):
        if failure == "timeout": raise subprocess.TimeoutExpired(command, 1)
        if command[1] == failure: return subprocess.CompletedProcess(command, 2, stdout="", stderr="failure")
        if failure == "missing" and command[1] == "update": return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        result = original(command, **kwargs)
        if failure == "invalid" and command[1] == "update": Path(command[command.index("--state-out") + 1]).write_text("broken json")
        return result
    monkeypatch.setattr(seca_timeline.subprocess, "run", fail)
    _write_llm_csv(source, [_row("2026-10-02")])
    assert seca_timeline.run_seca_light_timeline(batch_id="two") is None
    assert _state(tmp_path) == before
    assert files == {p.name: p.read_bytes() for p in directory.iterdir()}
    monkeypatch.setattr(seca_timeline.subprocess, "run", original)
    assert seca_timeline.run_seca_light_timeline(batch_id="two")
    assert _state(tmp_path)["last_processed_batch_index"] == 1


def test_committed_model_recovers_after_output_publication_failure(fake_cli, tmp_path, monkeypatch):
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", [_row("2026-10-01")])
    original = seca_timeline._publish_stream_views
    monkeypatch.setattr(seca_timeline, "_publish_stream_views", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    assert seca_timeline.run_seca_light_timeline(batch_id="one") is None
    assert _state(tmp_path)["last_processed_batch_index"] == 0
    fake_cli.clear()
    monkeypatch.setattr(seca_timeline, "_publish_stream_views", original)
    assert seca_timeline.run_seca_light_timeline(batch_id="one")
    assert not fake_cli


def test_calendar_window_edges_and_utc_conversion():
    latest = datetime(2026, 10, 6, 22, tzinfo=UTC)
    assert seca_timeline._window_start(latest, days=3) == datetime(2026, 10, 4, tzinfo=UTC)
    assert seca_timeline._parse_timestamp("2026-10-06T01:00:00+02:00").date().isoformat() == "2026-10-05"


def test_publish_rollback(tmp_path, monkeypatch):
    output = tmp_path / "published"
    output.mkdir()
    (output / "original").write_text("preserve")
    staged = tmp_path / "work/output"
    staged.mkdir(parents=True)
    rename = Path.rename

    def fail_staged(self, target):
        if self == staged:
            raise OSError("publish failure")
        return rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_staged)
    with pytest.raises(OSError):
        seca_timeline._publish_timeline(staged, output)
    assert (output / "original").read_text() == "preserve"


def test_explicit_cli_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLIVE_SECA_CLI", "/custom/bin/seca")
    monkeypatch.setattr(
        seca_timeline.shutil,
        "which",
        lambda name: (_ for _ in ()).throw(
            AssertionError("PATH lookup after override")
        ),
    )
    assert seca_timeline._resolve_seca_command(tmp_path) == ["/custom/bin/seca"]
    assert seca_timeline._seca_working_directory(["/custom/bin/seca"], None) is None


def test_installed_cli_wins_without_source_or_cargo_lookup(monkeypatch, tmp_path):
    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    looked_up = []

    def which(name):
        looked_up.append(name)
        assert name == "realtime-seca-cli", (
            "Cargo must not be considered for installed CLI"
        )
        return "/usr/local/bin/realtime-seca-cli"

    monkeypatch.setattr(seca_timeline.shutil, "which", which)
    assert seca_timeline._resolve_seca_command(None) == [
        "/usr/local/bin/realtime-seca-cli"
    ]
    # Installed CLI also takes precedence over a source binary.
    release = tmp_path / "target" / "release" / "realtime-seca-cli"
    release.parent.mkdir(parents=True)
    release.write_text("source binary placeholder")
    assert seca_timeline._resolve_seca_command(tmp_path) == [
        "/usr/local/bin/realtime-seca-cli"
    ]
    assert looked_up == ["realtime-seca-cli", "realtime-seca-cli"]


def test_source_release_then_debug_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    monkeypatch.setattr(seca_timeline.shutil, "which", lambda name: None)
    debug = tmp_path / "target" / "debug" / "realtime-seca-cli"
    debug.parent.mkdir(parents=True)
    debug.write_text("debug binary placeholder")
    assert seca_timeline._resolve_seca_command(tmp_path) == [str(debug)]
    release = tmp_path / "target" / "release" / "realtime-seca-cli"
    release.parent.mkdir(parents=True)
    release.write_text("release binary placeholder")
    assert seca_timeline._resolve_seca_command(tmp_path) == [str(release)]
    assert seca_timeline._seca_working_directory([str(release)], tmp_path) is None


def test_cargo_fallback_requires_source_workspace(monkeypatch, tmp_path):
    import pytest

    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    monkeypatch.setattr(
        seca_timeline.shutil,
        "which",
        lambda name: "/usr/bin/cargo" if name == "cargo" else None,
    )
    with pytest.raises(FileNotFoundError, match="realtime-seca-cli not found"):
        seca_timeline._resolve_seca_command(None)
    with pytest.raises(FileNotFoundError):
        seca_timeline._resolve_seca_command(tmp_path)
    (tmp_path / "Cargo.toml").write_text("[workspace]\n")
    command = seca_timeline._resolve_seca_command(tmp_path)
    assert command == ["cargo", "run", "-p", "realtime-seca-cli", "--"]
    assert seca_timeline._seca_working_directory(command, tmp_path) == tmp_path


def test_missing_cli_controlled_failure_without_source(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    monkeypatch.setattr(seca_timeline, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(seca_timeline.shutil, "which", lambda name: None)
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", [])
    monkeypatch.setattr(
        seca_timeline.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Unexpected subprocess")
        ),
    )
    caplog.set_level(logging.INFO)
    assert seca_timeline.run_seca_light_timeline() is None
    assert any(
        getattr(r, "error_code", "") == "seca_stream_failed" for r in caplog.records
    )


def test_source_identity_cannot_resolve_to_unrelated_historical_row(tmp_path):
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps(
            {
                "sources": [
                    {"source_id": "row_000001", "metadata": {"URL": "https://current"}},
                    {"source_id": "row_000002", "metadata": None},
                ]
            }
        )
    )
    assert seca_timeline._identify_sources(batch, variant_name="3d", batch_index=0) == 2
    sources = json.loads(batch.read_text())["sources"]
    assert sources[0]["source_id"] == "https://current"
    assert sources[1]["source_id"].startswith("article:")


def test_overlapping_generation_is_skipped(fake_cli, tmp_path, monkeypatch):
    def locked(*args):
        raise BlockingIOError("already running")

    monkeypatch.setattr(seca_timeline.fcntl, "flock", locked)
    assert seca_timeline.run_seca_light_timeline() is None
    assert not fake_cli

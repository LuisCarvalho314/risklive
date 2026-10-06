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
    monkeypatch.setattr(
        seca_timeline, "_resolve_seca_command", lambda _: ["realtime-seca-cli"]
    )

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] is None
        if command[1] == "from-csv":
            with Path(command[2]).open() as handle:
                rows = list(csv.DictReader(handle))
            Path(command[3]).write_text(
                json.dumps(
                    {
                        "sources": [
                            {"source_id": f"row_{index:06}", "metadata": row}
                            for index, row in enumerate(rows, 1)
                        ]
                    }
                )
            )
        elif command[1] == "baseline":
            sources = json.loads(Path(command[2]).read_text())["sources"]
            rows = [source["metadata"] for source in sources]
            assert all(
                source["source_id"] == row["URL"] for source, row in zip(sources, rows)
            )
            config = json.loads(
                Path(command[command.index("--config") + 1]).read_text()
            )
            assert (
                config["hkt_builder"][
                    "minimum_number_of_sources_to_create_branch_for_node"
                ]
                == 10
            )
            Path(command[command.index("--dump-tree-verbose") + 1]).write_text(
                json.dumps(
                    {
                        "hkts": [],
                        "nodes": [],
                        "source_legend": rows,
                        "word_legend": [],
                        "logically_removed_hkts": [],
                    }
                )
            )
        else:
            pytest.fail(f"Unexpected stateful CLI operation: {command}")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(seca_timeline.subprocess, "run", run)
    return calls


def _manifest(root, days):
    directory = root / f"results/web/newsmap/seca-light-{days}d"
    return directory, json.loads((directory / "timeline_manifest.json").read_text())


def test_filters_history_before_construction_all_windows(fake_cli, tmp_path):
    current = [
        _row("2026-10-03"),
        _row("2026-10-01"),
        _row("2026-09-27"),
        _row("2026-09-04"),
    ]
    history = [
        _row("2020-01-01"),
        _row("2026-09-03"),
        _row("2026-09-26"),
        _row("2026-09-30"),
    ]
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", current)
    _write_llm_csv(
        tmp_path / "results/backup_data/news_data_with_llm_info.csv", history + current
    )
    assert seca_timeline.run_seca_light_timeline() is not None
    expected = {30: 6, 7: 4, 3: 2}
    for days, count in expected.items():
        directory, manifest = _manifest(tmp_path, days)
        assert manifest["sources_total"] == count
        assert manifest["total_batches"] <= days
        cutoff = seca_timeline._window_start(
            datetime(2026, 10, 3, tzinfo=UTC), days=days
        )
        for filename in manifest["files"]:
            tree = json.loads((directory / filename).read_text())
            assert all(
                seca_timeline._row_timestamp(row) >= cutoff
                for row in tree["source_legend"]
            )
    assert all(command[1] in {"from-csv", "baseline"} for command in fake_cli)


@pytest.mark.parametrize("days", [3, 7, 30])
def test_calendar_window_edges_and_utc_conversion(days):
    latest = datetime(2026, 10, 3, 12, tzinfo=UTC)
    cutoff = seca_timeline._window_start(latest, days=days)
    rows = [
        {"Timestamp": latest.isoformat()},
        {"Timestamp": cutoff.isoformat()},
        {"Timestamp": (cutoff - seca_timeline.timedelta(microseconds=1)).isoformat()},
        {"Timestamp": "invalid", "API_Timestamp": cutoff.isoformat()},
        {"Timestamp": ""},
    ]
    assert seca_timeline._rolling_window_rows(rows, days=days) == [
        rows[0],
        rows[1],
        rows[3],
    ]
    assert seca_timeline._parse_timestamp("2026-10-04T00:30:00+02:00").day == 3
    assert seca_timeline._parse_timestamp("2026-10-03T12:00:00").tzinfo == UTC
    with pytest.raises(ValueError):
        seca_timeline._window_start(latest, days=0)


def test_repeated_generation_expires_history_and_replaces_stale_files(
    fake_cli, tmp_path
):
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    old = [_row("2026-10-01"), _row("2026-10-03")]
    _write_llm_csv(source, old)
    seca_timeline.run_seca_light_timeline()
    directory, _ = _manifest(tmp_path, 3)
    (directory / "tree_batch_9999.json").write_text("stale historical tree")
    _write_llm_csv(source, old + [_row("2026-12-01")])
    seca_timeline.run_seca_light_timeline()
    for days in (30, 7, 3):
        directory, manifest = _manifest(tmp_path, days)
        assert manifest["sources_total"] == 1
        assert manifest["days"] == ["2026-12-01"]
        assert sorted(p.name for p in directory.glob("tree*.json")) == manifest["files"]
        before = {p.name: p.read_bytes() for p in directory.glob("*.json")}
        seca_timeline.run_seca_light_timeline()
        assert before == {p.name: p.read_bytes() for p in directory.glob("*.json")}


def test_deduplicates_repeated_article_across_fetch_timestamps(fake_cli, tmp_path):
    _write_llm_csv(
        tmp_path / "results/data/news_data_with_llm_info.csv",
        [_row("2026-10-03", "https://same"), _row("2026-10-02", "https://same")],
    )
    seca_timeline.run_seca_light_timeline()
    assert _manifest(tmp_path, 30)[1]["sources_total"] == 1


def test_empty_generation_removes_stale_timeline(fake_cli, tmp_path):
    source = tmp_path / "results/data/news_data_with_llm_info.csv"
    _write_llm_csv(source, [_row("2026-10-03")])
    seca_timeline.run_seca_light_timeline()
    fake_cli.clear()
    _write_llm_csv(source, [{"Relevance": "Yes", "Timestamp": "bad"}])
    assert seca_timeline.run_seca_light_timeline() is not None
    assert not fake_cli
    for days in (30, 7, 3):
        directory, manifest = _manifest(tmp_path, days)
        assert manifest["files"] == []
        assert not list(directory.glob("tree*.json"))


@pytest.mark.parametrize("failure", ["from-csv", "baseline", "timeout", "missing"])
def test_failed_generation_preserves_previous_output(
    fake_cli, tmp_path, monkeypatch, failure, caplog
):
    _write_llm_csv(
        tmp_path / "results/data/news_data_with_llm_info.csv", [_row("2026-10-03")]
    )
    seca_timeline.run_seca_light_timeline()
    directory, _ = _manifest(tmp_path, 30)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    real_fake = seca_timeline.subprocess.run

    def fail(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if command[1] == failure:
            return subprocess.CompletedProcess(
                command, 2, stdout="", stderr="fixture failure"
            )
        if failure == "missing" and command[1] == "baseline":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return real_fake(command, **kwargs)

    monkeypatch.setattr(seca_timeline.subprocess, "run", fail)
    caplog.set_level(logging.INFO)
    assert seca_timeline.run_seca_light_timeline(timeout_seconds=1) is None
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
    assert any(getattr(r, "stage_status", "") == "failed" for r in caplog.records)


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
        getattr(r, "error_code", "") == "seca_cli_missing" for r in caplog.records
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
    assert sources[1]["source_id"] == "seca-3d-0:row_000002"


def test_deduplication_preserves_latest_source_anchor(fake_cli, tmp_path):
    _write_llm_csv(
        tmp_path / "results/data/news_data_with_llm_info.csv",
        [_row("2026-10-01", "https://same")],
    )
    _write_llm_csv(
        tmp_path / "results/backup_data/news_data_with_llm_info.csv",
        [_row("2026-10-03", "https://same")],
    )
    seca_timeline.run_seca_light_timeline()
    assert _manifest(tmp_path, 3)[1]["days"] == ["2026-10-03"]


def test_overlapping_generation_is_skipped(fake_cli, tmp_path, monkeypatch):
    def locked(*args):
        raise BlockingIOError("already running")

    monkeypatch.setattr(seca_timeline.fcntl, "flock", locked)
    assert seca_timeline.run_seca_light_timeline() is None
    assert not fake_cli

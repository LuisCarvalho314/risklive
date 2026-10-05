"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import csv
import logging
import subprocess

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


def test_run_seca_light_timeline_generates_30d_and_7d(monkeypatch, tmp_path, caplog):
    root = tmp_path
    seca_root = root / "experimental" / "RealtimeSECA"
    thirty_out_dir = root / "results" / "web" / "newsmap" / "seca-light-30d"
    thirty_manifest = thirty_out_dir / "timeline_manifest.json"
    seven_out_dir = root / "results" / "web" / "newsmap" / "seca-light-7d"
    seven_manifest = seven_out_dir / "timeline_manifest.json"
    three_out_dir = root / "results" / "web" / "newsmap" / "seca-light-3d"
    three_manifest = three_out_dir / "timeline_manifest.json"
    data_csv = root / "results" / "data" / "news_data_with_llm_info.csv"
    backup_csv = root / "results" / "backup_data" / "news_data_with_llm_info.csv"
    seca_root.mkdir(parents=True)

    _write_llm_csv(
        data_csv,
        [
            {
                "Title": "Recent 1",
                "URL": "https://example.com/r1",
                "Description": "Desc A",
                "Timestamp": "2026-02-27T00:00:00Z",
                "ShortSummary": "summary A",
                "API_Timestamp": "2026-02-27T00:01:00Z",
                "Query": "q1",
                "NewsCategory": "cybersecurity",
                "AlertFlag": "Red",
                "Relevance": "Yes",
            },
            {
                "Title": "Recent 2",
                "URL": "https://example.com/r2",
                "Description": "Desc B",
                "Timestamp": "2026-02-23T01:00:00Z",
                "ShortSummary": "summary B",
                "API_Timestamp": "2026-02-23T01:01:00Z",
                "Query": "q2",
                "NewsCategory": "miscellaneous",
                "AlertFlag": "Green",
                "Relevance": "Yes",
            },
            {
                "Title": "Non-relevant",
                "URL": "https://example.com/nr",
                "Description": "Desc C",
                "Timestamp": "2026-02-27T01:00:00Z",
                "ShortSummary": "summary C",
                "API_Timestamp": "2026-02-27T01:01:00Z",
                "Query": "q3",
                "NewsCategory": "miscellaneous",
                "AlertFlag": "Green",
                "Relevance": "No",
            },
        ],
    )
    _write_llm_csv(
        backup_csv,
        [
            {
                "Title": "Old but relevant",
                "URL": "https://example.com/old",
                "Description": "Desc old",
                "Timestamp": "2026-02-10T00:00:00Z",
                "ShortSummary": "summary old",
                "API_Timestamp": "2026-02-10T00:01:00Z",
                "Query": "q4",
                "NewsCategory": "supplychain",
                "AlertFlag": "Yellow",
                "Relevance": "Yes",
            }
        ],
    )

    calls = []
    monkeypatch.setattr(seca_timeline, "_project_root", lambda: root)
    monkeypatch.setattr(seca_timeline, "_resolve_seca_command", lambda _root: ["realtime-seca-cli"])

    def _run(*args, **kwargs):
        cmd = args[0]
        calls.append(cmd)
        if "timeline-many" in cmd and "seca-light-7d" in " ".join(cmd):
            seven_out_dir.mkdir(parents=True, exist_ok=True)
            seven_manifest.write_text('{"total_batches":1,"files":["tree_batch_0000.json"]}')
        if "timeline-many" in cmd and "seca-light-3d" in " ".join(cmd):
            three_out_dir.mkdir(parents=True, exist_ok=True)
            three_manifest.write_text('{"total_batches":1,"files":["tree_batch_0000.json"]}')
        if "timeline-many" in cmd and "seca-light-7d" not in " ".join(cmd) and "seca-light-3d" not in " ".join(cmd):
            thirty_out_dir.mkdir(parents=True, exist_ok=True)
            thirty_manifest.write_text('{"total_batches":2,"files":["tree_batch_0000.json","tree_batch_0001.json"]}')
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(seca_timeline.subprocess, "run", _run)
    caplog.set_level(logging.INFO)

    out = seca_timeline.run_seca_light_timeline()

    assert out == thirty_manifest
    assert len(calls) == 9
    assert "from-csv" in calls[0]
    assert "from-csv" in calls[1]
    assert "from-csv" in calls[2]
    assert "timeline-many" in calls[3]
    assert "from-csv" in calls[4]
    assert "from-csv" in calls[5]
    assert "timeline-many" in calls[6]
    assert "from-csv" in calls[7]
    assert "timeline-many" in calls[8]

    thirty_csv = root / "runtime" / "seca" / "relevant_news_data_30d.csv"
    seven_csv = root / "runtime" / "seca" / "relevant_news_data_7d.csv"
    assert thirty_csv.exists()
    assert seven_csv.exists()

    with thirty_csv.open("r", encoding="utf-8", newline="") as handle:
        thirty_rows = list(csv.DictReader(handle))
    with seven_csv.open("r", encoding="utf-8", newline="") as handle:
        seven_rows = list(csv.DictReader(handle))

    assert len(thirty_rows) == 3
    assert len(seven_rows) == 2
    assert {row["URL"] for row in seven_rows} == {"https://example.com/r1", "https://example.com/r2"}
    assert [part for part in calls[3] if "relevant_news_data_30d_" in part and part.endswith("_batch.json")] == [
        str(root / "runtime" / "seca" / "relevant_news_data_30d_2026-02-10_batch.json"),
        str(root / "runtime" / "seca" / "relevant_news_data_30d_2026-02-23_batch.json"),
        str(root / "runtime" / "seca" / "relevant_news_data_30d_2026-02-27_batch.json"),
    ]
    assert [part for part in calls[6] if "relevant_news_data_7d_" in part and part.endswith("_batch.json")] == [
        str(root / "runtime" / "seca" / "relevant_news_data_7d_2026-02-23_batch.json"),
        str(root / "runtime" / "seca" / "relevant_news_data_7d_2026-02-27_batch.json"),
    ]
    assert [part for part in calls[8] if "relevant_news_data_3d_" in part and part.endswith("_batch.json")] == [
        str(root / "runtime" / "seca" / "relevant_news_data_3d_2026-02-27_batch.json"),
    ]

    stage_end_ops = [
        (getattr(r, "operation", ""), getattr(r, "stage_status", ""))
        for r in caplog.records
        if getattr(r, "event", "") == "pipeline_stage_end"
    ]
    assert ("timeline_30d", "succeeded") in stage_end_ops
    assert ("timeline_7d", "succeeded") in stage_end_ops


def test_run_seca_light_timeline_skips_when_windows_empty(monkeypatch, tmp_path, caplog):
    root = tmp_path
    seca_root = root / "experimental" / "RealtimeSECA"
    data_csv = root / "results" / "data" / "news_data_with_llm_info.csv"
    seca_root.mkdir(parents=True)

    _write_llm_csv(
        data_csv,
        [
            {
                "Title": "No timestamp row",
                "URL": "https://example.com/notime",
                "Description": "Desc",
                "Timestamp": "",
                "ShortSummary": "",
                "API_Timestamp": "",
                "Query": "q",
                "NewsCategory": "",
                "AlertFlag": "Green",
                "Relevance": "Yes",
            }
        ],
    )

    monkeypatch.setattr(seca_timeline, "_project_root", lambda: root)
    monkeypatch.setattr(seca_timeline, "_resolve_seca_command", lambda _root: ["realtime-seca-cli"])

    calls = []

    def _run(*args, **kwargs):
        cmd = args[0]
        calls.append(cmd)
        if "timeline" in cmd:
            out_dir = root / "results" / "web" / "newsmap" / "seca-light-30d"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "timeline_manifest.json").write_text('{"total_batches":1,"files":["tree_batch_0000.json"]}')
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(seca_timeline.subprocess, "run", _run)
    caplog.set_level(logging.INFO)

    out = seca_timeline.run_seca_light_timeline()

    assert out is None
    assert len(calls) == 0
    stage_end_ops = [
        (getattr(r, "operation", ""), getattr(r, "stage_status", ""), getattr(r, "skip_reason", ""))
        for r in caplog.records
        if getattr(r, "event", "") == "pipeline_stage_end"
    ]
    assert ("timeline_30d", "skipped", "no_relevant_rows_30d") in stage_end_ops
    assert ("timeline_7d", "skipped", "no_relevant_rows_7d") in stage_end_ops


def test_run_seca_light_timeline_nonzero_exit(monkeypatch, tmp_path, caplog):
    root = tmp_path
    seca_root = root / "experimental" / "RealtimeSECA"
    data_csv = root / "results" / "data" / "news_data_with_llm_info.csv"
    seca_root.mkdir(parents=True)
    _write_llm_csv(
        data_csv,
        [
            {
                "Title": "A",
                "URL": "https://example.com/a",
                "Description": "Desc A",
                "Timestamp": "2026-02-27T00:00:00Z",
                "ShortSummary": "summary A",
                "API_Timestamp": "2026-02-27T00:01:00Z",
                "Query": "q1",
                "NewsCategory": "cybersecurity",
                "AlertFlag": "Red",
                "Relevance": "Yes",
            }
        ],
    )

    monkeypatch.setattr(seca_timeline, "_project_root", lambda: root)
    monkeypatch.setattr(seca_timeline, "_resolve_seca_command", lambda _root: ["realtime-seca-cli"])
    calls = {"count": 0}

    def _run(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=args[0], returncode=2, stdout="", stderr="cli failure")

    monkeypatch.setattr(seca_timeline.subprocess, "run", _run)
    caplog.set_level(logging.INFO)

    out = seca_timeline.run_seca_light_timeline()

    assert out is None
    end_logs = [r for r in caplog.records if getattr(r, "event", "") == "pipeline_stage_end"]
    assert any(getattr(r, "error_code", "") == "seca_timeline_failed" for r in end_logs)


def test_run_seca_light_timeline_timeout(monkeypatch, tmp_path, caplog):
    root = tmp_path
    seca_root = root / "experimental" / "RealtimeSECA"
    data_csv = root / "results" / "data" / "news_data_with_llm_info.csv"
    seca_root.mkdir(parents=True)
    _write_llm_csv(
        data_csv,
        [
            {
                "Title": "A",
                "URL": "https://example.com/a",
                "Description": "Desc A",
                "Timestamp": "2026-02-27T00:00:00Z",
                "ShortSummary": "summary A",
                "API_Timestamp": "2026-02-27T00:01:00Z",
                "Query": "q1",
                "NewsCategory": "cybersecurity",
                "AlertFlag": "Red",
                "Relevance": "Yes",
            }
        ],
    )

    monkeypatch.setattr(seca_timeline, "_project_root", lambda: root)
    monkeypatch.setattr(seca_timeline, "_resolve_seca_command", lambda _root: ["realtime-seca-cli"])

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(seca_timeline.subprocess, "run", _timeout)
    caplog.set_level(logging.INFO)

    out = seca_timeline.run_seca_light_timeline(timeout_seconds=1)

    assert out is None
    end_logs = [r for r in caplog.records if getattr(r, "event", "") == "pipeline_stage_end"]
    assert any(getattr(r, "error_code", "") == "seca_timeout" for r in end_logs)


def test_explicit_cli_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLIVE_SECA_CLI", "/custom/bin/seca")
    monkeypatch.setattr(seca_timeline.shutil, "which", lambda name: (_ for _ in ()).throw(AssertionError("PATH lookup after override")))
    assert seca_timeline._resolve_seca_command(tmp_path) == ["/custom/bin/seca"]
    assert seca_timeline._seca_working_directory(["/custom/bin/seca"], None) is None


def test_installed_cli_wins_without_source_or_cargo_lookup(monkeypatch, tmp_path):
    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    looked_up = []

    def which(name):
        looked_up.append(name)
        assert name == "realtime-seca-cli", "Cargo must not be considered for installed CLI"
        return "/usr/local/bin/realtime-seca-cli"

    monkeypatch.setattr(seca_timeline.shutil, "which", which)
    assert seca_timeline._resolve_seca_command(None) == ["/usr/local/bin/realtime-seca-cli"]
    # Installed CLI also takes precedence over a source binary.
    release = tmp_path / "target" / "release" / "realtime-seca-cli"
    release.parent.mkdir(parents=True)
    release.write_text("source binary placeholder")
    assert seca_timeline._resolve_seca_command(tmp_path) == ["/usr/local/bin/realtime-seca-cli"]
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
    monkeypatch.setattr(seca_timeline.shutil, "which", lambda name: "/usr/bin/cargo" if name == "cargo" else None)
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
    monkeypatch.setattr(seca_timeline.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected subprocess")))
    caplog.set_level(logging.INFO)
    assert seca_timeline.run_seca_light_timeline() is None
    assert any(getattr(r, "error_code", "") == "seca_cli_missing" for r in caplog.records)


def test_packaged_cli_runs_all_variants_without_source_or_cargo(monkeypatch, tmp_path):
    import json

    monkeypatch.delenv("RISKLIVE_SECA_CLI", raising=False)
    monkeypatch.setattr(seca_timeline, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(seca_timeline.shutil, "which", lambda name: "/usr/local/bin/realtime-seca-cli" if name == "realtime-seca-cli" else None)
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", [{
        "Title": "Fixture risk", "URL": "https://fixture.example/one",
        "Timestamp": "2026-01-15T12:00:00Z", "Relevance": "Yes"
    }])
    calls = []

    def run(command, **kwargs):
        assert command[0] == "/usr/local/bin/realtime-seca-cli"
        assert kwargs["cwd"] is None
        assert "cargo" not in command
        calls.append(command)
        if command[1] == "timeline-many":
            out = tmp_path / command[command.index("--out-dir") + 1]
            out.mkdir(parents=True)
            (out / "timeline_manifest.json").write_text(json.dumps({"total_batches": 1, "files": ["tree_batch_0000.json"]}))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(seca_timeline.subprocess, "run", run)
    assert seca_timeline.run_seca_light_timeline() == tmp_path / "results/web/newsmap/seca-light-30d/timeline_manifest.json"
    assert len(calls) == 6
    assert not (tmp_path / "experimental").exists()
    for window in ("30d", "7d", "3d"):
        manifest = json.loads((tmp_path / f"results/web/newsmap/seca-light-{window}/timeline_manifest.json").read_text())
        assert manifest["days"] == ["2026-01-15"]

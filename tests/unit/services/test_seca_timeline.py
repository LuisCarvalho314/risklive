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
        if "timeline" in cmd and "seca-light-7d" in " ".join(cmd):
            seven_out_dir.mkdir(parents=True, exist_ok=True)
            seven_manifest.write_text('{"total_batches":1,"files":["tree_batch_0000.json"]}')
        if "timeline" in cmd and "seca-light-7d" not in " ".join(cmd):
            thirty_out_dir.mkdir(parents=True, exist_ok=True)
            thirty_manifest.write_text('{"total_batches":2,"files":["tree_batch_0000.json","tree_batch_0001.json"]}')
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(seca_timeline.subprocess, "run", _run)
    caplog.set_level(logging.INFO)

    out = seca_timeline.run_seca_light_timeline()

    assert out == thirty_manifest
    assert len(calls) == 4
    assert "from-csv" in calls[0]
    assert "timeline" in calls[1]
    assert "from-csv" in calls[2]
    assert "timeline" in calls[3]

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

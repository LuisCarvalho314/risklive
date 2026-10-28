"""Offline contract tests: real Rust CLI and converter, isolated runtime only."""
import csv
import json
import os
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

from services import seca_v2 as v2

pytestmark = pytest.mark.skipif("tests.fixtures.runtime_guard" in sys.modules,
                                reason="Run separately with --confcutdir=tests/integration; suite guard forbids Rust subprocesses")

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "tests/fixtures/archive/news_data_with_llm_info.csv"


@pytest.fixture
def binaries(monkeypatch):
    directory = ROOT / ".worktrees/seca-v2-build/experimental/target/debug"
    cli = os.getenv("RISKLIVE_SECA_V2_CLI") or shutil.which("seca-v2-cli") or directory / "seca-v2-cli"
    converter = os.getenv("RISKLIVE_SECA_CLI") or shutil.which("realtime-seca-cli") or directory / "realtime-seca-cli"
    if not Path(cli).is_file() or not Path(converter).is_file():
        pytest.fail("Real Rust binaries required: set RISKLIVE_SECA_V2_CLI and RISKLIVE_SECA_CLI")
    monkeypatch.setenv("RISKLIVE_SECA_V2_CLI", str(cli))
    return [str(converter)]


def row(day, identity=None, **extra):
    return {"Title": "Nuclear reactor nuclear safety", "URL": identity or f"https://test/{day}",
            "Timestamp": f"2026-10-{day:02}T12:00:00Z", "Relevance": "Yes", **extra}


def write(path, rows):
    fields = sorted(set().union(*(r.keys() for r in rows))) if rows else list(row(1))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def receipts(root):
    with sqlite3.connect(root / "runtime/seca/v2/ledger.sqlite3") as db:
        return db.execute("SELECT sequence, day, input, status FROM batches ORDER BY sequence").fetchall()


def state(root):
    return (root / "runtime/seca/v2/state.json").read_bytes()


def invoke(root, csv_path, binaries, day=3, **kwargs):
    return v2.run(root=root, paths=[csv_path], converter=binaries,
                  utc_date=date(2026, 10, day), **kwargs)


def test_conversion_and_stable_identity(tmp_path, binaries):
    rows = [row(1), row(1, URL="", Title="Alpha reactor"), row(1, URL="", Title="Beta reactor")]
    first = v2.convert_articles(rows, tmp_path, converter=binaries)
    assert first == v2.convert_articles(list(reversed(rows)), tmp_path, converter=binaries)
    assert len({s["id"] for s in first}) == 3
    assert all(s["words"] == sorted(set(s["words"])) for s in first)
    assert next(s for s in first if s["id"].startswith("https:"))["words"] == ["nuclear", "reactor", "safety"]


def test_real_archive_restart_and_continue(tmp_path, binaries):
    rows = v2.collect_articles([ARCHIVE])
    assert rows
    end = max(v2._row_timestamp(r).date() for r in rows)
    result = v2.run(root=tmp_path, paths=[ARCHIVE], converter=binaries, bootstrap=True, utc_date=end)
    assert result["batch"] == 2
    assert [r[1] for r in receipts(tmp_path)] == [(end - v2.timedelta(days=n)).isoformat() for n in (2, 1, 0)]
    before = state(tmp_path)
    assert v2.run(root=tmp_path, paths=[ARCHIVE], converter=binaries, utc_date=end) == result
    assert state(tmp_path) == before
    result = v2.run(root=tmp_path, paths=[ARCHIVE], converter=binaries, utc_date=end + v2.timedelta(days=1))
    assert result["batch"] == 3
    assert v2.run(root=tmp_path, show=True) == result
    assert not (tmp_path / "runtime/seca/stream.sqlite3").exists()


def test_daily_empty_late_and_persistent_dedup(tmp_path, binaries):
    source = tmp_path / "articles.csv"
    write(source, [row(1), row(3), row(1), row(2, Relevance="No"), row(1, "https://old", Timestamp="2026-09-01")])
    invoke(tmp_path, source, binaries, bootstrap=True)
    batches = receipts(tmp_path)
    assert [len(json.loads(b[2])["sources"]) for b in batches] == [1, 0, 1]
    write(source, [row(1), row(3), row(2, "https://late")])
    invoke(tmp_path, source, binaries)  # same date cannot ingest late arrival
    assert len(receipts(tmp_path)) == 3
    invoke(tmp_path, source, binaries, day=6)
    batches = receipts(tmp_path)
    assert [json.loads(b[2])["sources"] for b in batches[3:]] == [[{"id": "https://late", "words": ["nuclear", "reactor", "safety"]}], [], []]
    assert json.loads(state(tmp_path))["model"]["retained"] == {"https://late": {"batch": 3, "words": ["nuclear", "reactor", "safety"]}}
    invoke(tmp_path, source, binaries, day=7)
    assert json.loads(state(tmp_path))["model"]["retained"] == {}
    assert json.loads(receipts(tmp_path)[-1][2])["sources"] == []


@pytest.mark.parametrize("point", ["before", "after", "commit", "bad-output"])
@pytest.mark.parametrize("crash_sequence", [0, 1, 3])
def test_crash_recovery_matches_uninterrupted(tmp_path, binaries, monkeypatch, point, crash_sequence):
    source = tmp_path / "articles.csv"
    write(source, [row(1), row(2), row(3), row(4)])
    baseline, crashed = tmp_path / "baseline", tmp_path / "crashed"
    expected = invoke(baseline, source, binaries, bootstrap=True)
    target = 4 if crash_sequence == 3 else 3
    if crash_sequence == 3:
        invoke(crashed, source, binaries, bootstrap=True)
        expected = invoke(baseline, source, binaries, day=4)
    original_cli, original_commit = v2._cli, v2._commit
    def crash(command, args, **kwargs):
        if args[0] == "update" and json.loads(Path(args[2]).read_text())["batch"] == crash_sequence:
            if point == "before":
                raise OSError("crash before Rust")
            output = original_cli(command, args, **kwargs)
            if point == "bad-output":
                return "{}"
            raise OSError("crash after Rust replacement")
        return original_cli(command, args, **kwargs)
    def fail_commit(*args):
        if args[1]["sequence"] == crash_sequence:
            raise OSError("crash before SQLite commit")
        return original_commit(*args)
    if point == "commit":
        monkeypatch.setattr(v2, "_commit", fail_commit)
    else:
        monkeypatch.setattr(v2, "_cli", crash)
    with pytest.raises((OSError, ValueError)):
        invoke(crashed, source, binaries, day=target, bootstrap=True)
    assert receipts(crashed)[-1][3] == "pending"
    monkeypatch.setattr(v2, "_cli", original_cli)
    monkeypatch.setattr(v2, "_commit", original_commit)
    assert invoke(crashed, source, binaries, day=target, bootstrap=True) == expected
    assert state(crashed) == state(baseline)
    assert receipts(crashed) == receipts(baseline)
    assert invoke(crashed, source, binaries, day=4) == invoke(baseline, source, binaries, day=4)
    assert state(crashed) == state(baseline)


@pytest.mark.parametrize("damage", ["input", "hash", "sequence", "evidence", "missing", "orphan", "source-ledger", "config"])
def test_fail_closed(tmp_path, binaries, damage):
    source = tmp_path / "articles.csv"
    write(source, [row(1), row(3)])
    invoke(tmp_path, source, binaries, bootstrap=True)
    directory = tmp_path / "runtime/seca/v2"
    if damage in ("input", "hash", "sequence", "orphan", "source-ledger"):
        with sqlite3.connect(directory / "ledger.sqlite3") as db:
            sql = {"input": "UPDATE batches SET input='{}' WHERE sequence=2",
                   "hash": "UPDATE batches SET state_hash='bad' WHERE sequence=2",
                   "sequence": "UPDATE batches SET sequence=9 WHERE sequence=2",
                   "orphan": "DELETE FROM sources; DELETE FROM batches",
                   "source-ledger": "DELETE FROM sources"}[damage]
            db.executescript(sql)
    elif damage == "missing":
        (directory / "state.json").unlink()
    else:
        payload = json.loads(state(tmp_path))
        if damage == "evidence":
            payload["model"]["retained"] = {}
        else:
            payload["model"]["config"]["alpha"] = 0.8
        (directory / "state.json").write_text(json.dumps(payload))
    with pytest.raises((ValueError, RuntimeError)):
        invoke(tmp_path, source, binaries, day=4)


@pytest.mark.parametrize("value", [2, -1, float("nan"), True])
def test_invalid_configuration(tmp_path, binaries, value):
    config = json.loads(v2.CONFIG.read_text())
    config["alpha"] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="configuration"):
        v2.run(root=tmp_path, bootstrap=True, config_path=path)
    assert not (tmp_path / "runtime/seca/v2/state.json").exists()


def test_missing_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("RISKLIVE_SECA_V2_CLI", str(tmp_path / "missing-cli"))
    source = tmp_path / "articles.csv"
    write(source, [row(3)])
    # Empty first bootstrap day reaches the actual executable without a converter.
    with pytest.raises(FileNotFoundError):
        invoke(tmp_path, source, ["unused"], bootstrap=True)


def test_show_last_finalizes_pending_without_reapplying(tmp_path, binaries, monkeypatch):
    source = tmp_path / "articles.csv"
    write(source, [row(3)])
    original = v2._commit
    monkeypatch.setattr(v2, "_commit", lambda *args: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        invoke(tmp_path, source, binaries, bootstrap=True)
    before = state(tmp_path)
    monkeypatch.setattr(v2, "_commit", original)
    cli = v2._cli
    commands = []
    def tracked(command, args, **kwargs):
        commands.append(args[0])
        return cli(command, args, **kwargs)
    monkeypatch.setattr(v2, "_cli", tracked)
    report = v2.run(root=tmp_path, show=True)
    assert report["batch"] == 0
    assert commands == ["show-last"]
    assert state(tmp_path) == before
    assert receipts(tmp_path)[0][3] == "committed"


def test_pending_wrong_input_fails_closed(tmp_path, binaries, monkeypatch):
    source = tmp_path / "articles.csv"
    write(source, [row(1)])
    original = v2._commit
    monkeypatch.setattr(v2, "_commit", lambda *args: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        invoke(tmp_path, source, binaries, bootstrap=True)
    with sqlite3.connect(tmp_path / "runtime/seca/v2/ledger.sqlite3") as db:
        prepared = v2._json({"batch": 0, "sources": []})
        db.execute("UPDATE batches SET input=?, input_hash=?", (prepared, v2._hash(prepared.encode())))
    monkeypatch.setattr(v2, "_commit", original)
    with pytest.raises(ValueError, match="evidence"):
        v2.run(root=tmp_path, show=True)
    assert receipts(tmp_path)[0][3] == "pending"


def test_exclusive_lock(tmp_path, binaries):
    directory = tmp_path / "runtime/seca/v2"
    directory.mkdir(parents=True)
    with (directory / "update.lock").open("a") as lock:
        v2.fcntl.flock(lock, v2.fcntl.LOCK_EX | v2.fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            v2.run(root=tmp_path, show=True)


def test_cli_offline_commands(tmp_path, binaries, monkeypatch, capsys):
    source = tmp_path / "articles.csv"
    write(source, [row(3)])
    monkeypatch.setenv("RISKLIVE_SECA_CLI", binaries[0])
    for command, day, expected in [("bootstrap", 3, 2), ("update", 4, 3), ("show-last", 4, 3)]:
        monkeypatch.setattr(sys, "argv", ["seca_v2", command, "--root", str(tmp_path),
                                         "--csv", str(source), "--date", f"2026-10-{day:02}"])
        v2.main()
        assert json.loads(capsys.readouterr().out)["batch"] == expected


def test_native_artifact_metrics_and_publication_recovery(tmp_path, binaries, monkeypatch):
    source = tmp_path / "articles.csv"
    write(source, [row(1), row(1), row(3)])
    stats = {}
    result = invoke(tmp_path, source, binaries, bootstrap=True, stats=stats)
    directory = tmp_path / "runtime/seca/v2"
    assert json.loads((directory / "latest.json").read_text()) == result
    assert json.loads((directory / "reports/2026-10-03/batch-2.json").read_text()) == result
    assert stats["input_rows"] == 3
    assert stats["deduped_rows"] == 1
    assert stats["output_rows"] == 2
    assert stats["state_bytes"] == len(state(tmp_path))
    assert stats["total_adapter_ms"] > 0
    assert stats["peak_rss_kib"] > 0
    assert set(p.name for p in tmp_path.iterdir()) == {"articles.csv", "runtime"}
    original = v2._publish_report
    monkeypatch.setattr(v2, "_publish_report", lambda *args: (_ for _ in ()).throw(OSError("publish failed")))
    with pytest.raises(OSError):
        invoke(tmp_path, source, binaries, day=4)
    before = state(tmp_path)
    assert receipts(tmp_path)[-1][3] == "committed"
    monkeypatch.setattr(v2, "_publish_report", original)
    assert invoke(tmp_path, source, binaries, day=4)["batch"] == 3
    assert state(tmp_path) == before
    assert json.loads((directory / "latest.json").read_text())["batch"] == 3

"""Offline SECALight V2 bridge. Rust owns the model; SQLite owns ingestion receipts."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import resource
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from services.seca_timeline import (
    _llm_input_paths, _project_root, _resolve_seca_command, _row_key,
    _row_timestamp, _seca_working_directory, _write_relevant_csv,
)

from utils.logging import get_logger, log_context, log_artifact_written, pipeline_stage

logger = get_logger(__name__)

CONFIG = Path(__file__).resolve().parents[2] / "config/seca_v2.json"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _state_hash(state: Path) -> str | None:
    return _hash(state.read_bytes()) if state.exists() else None


def _cli(command, args, *, cwd=None, timeout=600):
    started = time.perf_counter()
    try:
        result = subprocess.run([*command, *map(str, args)], cwd=cwd, capture_output=True,
                                text=True, timeout=timeout, check=False)
    finally:
        if args[0] == "update":
            logger.info("seca_v2_update", extra={"event": "seca_v2_update",
                        "component": "services.seca_v2", "operation": "update",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
    if result.returncode:
        raise RuntimeError(f"SECA {args[0]}: {result.stderr[-1000:]}")
    return result.stdout


def _load_config(path):
    value = json.loads(path.read_text())
    if (set(value) != {"alpha", "beta", "error_limits", "minimum_branch_sources", "window"}
            or not isinstance(value["error_limits"], dict)
            or set(value["error_limits"]) != {"alpha", "beta", "importance"}):
        raise ValueError("invalid V2 configuration schema")
    probabilities = [value["alpha"], value["beta"], *value["error_limits"].values()]
    if (any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities)
            or type(value["minimum_branch_sources"]) is not int or value["minimum_branch_sources"] < 1
            or (value["window"] is not None and (type(value["window"]) is not int or value["window"] < 1))):
        raise ValueError("invalid V2 configuration values")
    return _json(value)


def _command():
    executable = os.getenv("RISKLIVE_SECA_V2_CLI") or shutil.which("seca-v2-cli")
    if not executable:
        raise FileNotFoundError("seca-v2-cli not found; set RISKLIVE_SECA_V2_CLI")
    return [executable]


def collect_articles(paths: list[Path], *, stats=None) -> list[dict[str, str]]:
    """Read enriched CSVs without V1's rolling cutoff; newest duplicate wins."""
    selected = {}
    considered = relevant = 0
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                considered += 1
                stamp = _row_timestamp(row)
                if (row.get("Relevance") or "").strip().lower() != "yes" or stamp is None:
                    continue
                relevant += 1
                row = {key: (value or "").strip() for key, value in row.items() if key}
                key = _row_key(row)
                previous = selected.get(key)
                if previous is None or (stamp, _json(row)) > (_row_timestamp(previous), _json(previous)):
                    selected[key] = row
    if stats is not None:
        stats.update(input_rows=considered, relevant_rows=relevant, deduped_rows=relevant - len(selected))
    return [selected[key] for key in sorted(selected)]


def convert_articles(rows, directory: Path, *, converter=None, cwd=None):
    """Reuse from-csv's text/stop-word semantics, then make tokens a word set."""
    if not rows:
        return []
    normalized = []
    for row in rows:
        identity = (row.get("URL") or "").strip() or "article:" + _hash(_row_key(row).encode())
        # Stable fallback travels through converter metadata, even if it skips rows.
        normalized.append({**row, "URL": identity})
    fields = {"Title", "URL", "Description", "Timestamp", "ShortSummary",
              "API_Timestamp", "Query", "NewsCategory", "AlertFlag", "Relevance"}
    csv_path, batch_path = directory / "sources.csv", directory / "converted.json"
    _write_relevant_csv(csv_path, [{k: v for k, v in row.items() if k in fields} for row in normalized])
    _cli(converter, ["from-csv", csv_path, batch_path], cwd=cwd)
    converted = json.loads(batch_path.read_text())["sources"]
    sources = [{"id": source["metadata"]["URL"], "words": sorted(set(source["tokens"]))}
               for source in converted]
    if len({s["id"] for s in sources}) != len(sources):
        raise ValueError("duplicate converted source identity")
    return sorted(sources, key=lambda source: source["id"])


def _open_ledger(directory):
    db = sqlite3.connect(directory / "ledger.sqlite3", timeout=30)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS batches (
            sequence INTEGER PRIMARY KEY, day TEXT NOT NULL UNIQUE,
            input TEXT NOT NULL, input_hash TEXT NOT NULL, config TEXT NOT NULL,
            previous_hash TEXT, state_hash TEXT, result_hash TEXT,
            status TEXT NOT NULL CHECK(status IN ('pending','committed')));
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, sequence INTEGER NOT NULL REFERENCES batches(sequence));
    """)
    db.row_factory = sqlite3.Row
    return db


def _report(command, state):
    report = json.loads(_cli(command, ["show-last", "--state", state]))
    if (report.get("schema_version") != 1 or type(report.get("batch")) is not int
            or report.get("next_batch") != report["batch"] + 1
            or type(report.get("retained_source_count")) is not int
            or not isinstance(report.get("decisions"), list)):
        raise ValueError("invalid V2 report")
    def tree(hkt):
        if not isinstance(hkt, dict) or not isinstance(hkt.get("nodes"), list):
            raise ValueError("invalid recursive HKT")
        for node in hkt["nodes"]:
            if not all(isinstance(node.get(k), list) for k in ("words", "sources")):
                raise ValueError("invalid HKT node")
            if node.get("child") is not None:
                tree(node["child"])
    tree(report.get("root"))
    for decision in report["decisions"]:
        if (not isinstance(decision.get("path"), list)
                or type(decision.get("reconstructed")) is not bool
                or set(decision.get("errors", {})) != {"alpha", "beta", "importance"}):
            raise ValueError("invalid reconstruction decision")
    return report


def _verify_evidence(db, state, sequence, config):
    """Check exact retained input, including empty batches, without owning a model."""
    payload = json.loads(state.read_text())
    model = payload["model"]
    if (payload["engine"] != "realtime-seca-v2" or payload["version"] != 1
            or model["config"] != json.loads(config) or model["next_batch"] != sequence + 1
            or payload["last_result"]["batch"] != sequence):
        raise ValueError("state identity/configuration mismatch")
    expected = {}
    for receipt in db.execute("SELECT sequence, input FROM batches WHERE sequence<=? ORDER BY sequence", (sequence,)):
        for source in json.loads(receipt["input"])["sources"]:
            expected[source["id"]] = {"batch": receipt["sequence"], "words": source["words"]}
    window = model["config"]["window"]
    if window is not None:
        expected = {k: v for k, v in expected.items() if v["batch"] >= sequence + 1 - window}
    if model["retained"] != expected:
        raise ValueError("state evidence does not match prepared inputs")


def _commit(db, receipt, state, report):
    _verify_evidence(db, state, receipt["sequence"], receipt["config"])
    with db:
        db.execute("UPDATE batches SET status='committed', state_hash=?, result_hash=? WHERE sequence=?",
                   (_state_hash(state), _hash(_json(report).encode()), receipt["sequence"]))
        db.executemany("INSERT INTO sources VALUES (?,?)", [(s["id"], receipt["sequence"])
                       for s in json.loads(receipt["input"])["sources"]])


def _same_update(output, report):
    # serde_json's persisted f64 readback can differ from update stdout by 1 ULP.
    # Identity, tree and decisions stay exact; only metric readback gets 2 ULPs.
    if not isinstance(output, dict) or not isinstance(output.get("decisions"), list):
        return False
    if {**output, "decisions": report["decisions"]} != report:
        return False
    decisions = output.get("decisions", [])
    if len(decisions) != len(report["decisions"]):
        return False
    for emitted, persisted in zip(decisions, report["decisions"]):
        if {**emitted, "errors": persisted["errors"]} != persisted:
            return False
        errors = emitted.get("errors", {})
        if set(errors) != set(persisted["errors"]):
            return False
        for key, value in errors.items():
            stored = persisted["errors"][key]
            if (type(value) not in (float, int) or not math.isfinite(value)
                    or abs(value - stored) > 2 * max(math.ulp(value), math.ulp(stored))):
                return False
    return True


def _apply(db, receipt, command, state, directory):
    # Files are disposable; the ledger's immutable exact bytes are authoritative input.
    with tempfile.TemporaryDirectory(dir=directory, prefix="batch-") as temporary:
        work = Path(temporary)
        batch, config = work / "batch.json", work / "config.json"
        batch.write_text(receipt["input"], encoding="utf-8")
        config.write_text(receipt["config"], encoding="utf-8")
        with log_context(batch_index=receipt["sequence"], batch_date=receipt["day"]):
            output = json.loads(_cli(command, ["update", "--batch", batch, "--config", config, "--state", state]))
    report = _report(command, state)
    if not _same_update(output, report) or report["batch"] != receipt["sequence"]:
        raise ValueError("update output disagrees with authoritative state")
    _commit(db, receipt, state, report)
    return report


def _recover(db, command, state, directory, config):
    receipts = db.execute("SELECT * FROM batches ORDER BY sequence").fetchall()
    previous_day, previous_hash = None, None
    seen = set()
    for index, receipt in enumerate(receipts):
        batch = json.loads(receipt["input"])
        day = date.fromisoformat(receipt["day"])
        if (receipt["sequence"] != index or batch.get("batch") != index
                or _hash(receipt["input"].encode()) != receipt["input_hash"]
                or receipt["config"] != config or receipt["previous_hash"] != previous_hash
                or (previous_day is not None and day != previous_day + timedelta(days=1))
                or (receipt["status"] == "pending" and index != len(receipts) - 1)):
            raise ValueError("inconsistent V2 receipts")
        sources = batch.get("sources")
        if not isinstance(sources, list) or sources != sorted(sources, key=lambda s: s["id"]):
            raise ValueError("invalid ordered batch input")
        for source in sources:
            if (set(source) != {"id", "words"} or not isinstance(source["id"], str)
                    or not source["id"].strip() or source["id"] in seen
                    or not isinstance(source["words"], list)
                    or any(not isinstance(w, str) or not w.strip() for w in source["words"])
                    or source["words"] != sorted(set(source["words"]))):
                raise ValueError("invalid source input identity or words")
            seen.add(source["id"])
        if receipt["status"] == "committed" and not all(receipt[k] for k in ("state_hash", "result_hash")):
            raise ValueError("incomplete committed receipt")
        if receipt["status"] == "pending" and (receipt["state_hash"] or receipt["result_hash"]):
            raise ValueError("inconsistent pending receipt")
        previous_day, previous_hash = day, receipt["state_hash"]
    recorded = {s["id"]: r["sequence"] for r in receipts if r["status"] == "committed"
                for s in json.loads(r["input"])["sources"]}
    if recorded != dict(db.execute("SELECT id, sequence FROM sources")):
        raise ValueError("inconsistent source ledger")
    if not receipts:
        if state.exists():
            raise ValueError("state exists without receipts")
        return None
    last = receipts[-1]
    current_hash = _state_hash(state)
    if last["status"] == "committed":
        if current_hash != last["state_hash"]:
            raise ValueError("committed state missing or changed")
        report = _report(command, state)
        if report["batch"] != last["sequence"] or _hash(_json(report).encode()) != last["result_hash"]:
            raise ValueError("committed result mismatch")
        _verify_evidence(db, state, last["sequence"], config)
        return report
    if current_hash == last["previous_hash"]:
        return _apply(db, last, command, state, directory)
    if current_hash is None:
        raise ValueError("pending state missing")
    report = _report(command, state)
    if report["batch"] != last["sequence"]:
        raise ValueError("pending state sequence mismatch")
    _commit(db, last, state, report)
    return report


def _publish_report(directory, day, report):
    # Keep the CLI payload unchanged. The dated filename supplies UTC context.
    reports = directory / "reports" / day
    reports.mkdir(parents=True, exist_ok=True)
    output = reports / f"batch-{report['batch']}.json"
    payload = _json(report)
    for target in (output, directory / "latest.json"):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    log_artifact_written(logger, stage="seca_v2", operation="shadow_update",
                         component="services.seca_v2", artifact_path=output,
                         artifact_type="seca_v2_native_report")


def run_shadow():
    """Optional nonblocking post-pipeline experiment; initialization is explicit."""
    if os.getenv("RISKLIVE_SECA_V2_ENABLED", "false").strip().lower() != "true":
        return None
    try:
        with pipeline_stage(logger, stage="seca_v2", component="services.seca_v2",
                            operation="shadow_update"):
            return run()
    except Exception:
        logger.exception("seca_v2_non_blocking_error", extra={
            "event": "seca_v2_non_blocking_error", "component": "services.seca_v2",
            "operation": "shadow_update", "stage": "seca_v2", "stage_status": "failed"})
        return None


def run(*, root: Path | None = None, paths: list[Path] | None = None,
        utc_date: date | None = None, bootstrap=False, show=False,
        config_path: Path = CONFIG, converter=None, converter_cwd=None, stats=None):
    """Bootstrap three days or advance through a UTC date. Sole writer of V2 state."""
    root = root or _project_root()
    stats = stats if stats is not None else {}
    started = time.perf_counter()
    directory = root / "runtime/seca/v2"
    directory.mkdir(parents=True, exist_ok=True)
    state = directory / "state.json"
    config = _load_config(config_path)
    command = _command()
    with (directory / "update.lock").open("a") as lock, closing(_open_ledger(directory)) as db:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial_count = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        report = _recover(db, command, state, directory, config)
        def finish():
            if report is not None:
                receipt = db.execute("SELECT day FROM batches WHERE sequence=?", (report["batch"],)).fetchone()
                _publish_report(directory, receipt["day"], report)
                stats.update(batch_date=receipt["day"], batch_index=report["batch"],
                             retained_source_count=report["retained_source_count"],
                             reconstruction_decisions=len(report["decisions"]),
                             reconstructed=sum(d["reconstructed"] for d in report["decisions"]),
                             state_bytes=state.stat().st_size)
            stats.update(output_rows=db.execute("SELECT COUNT(*) FROM sources").fetchone()[0] - initial_count,
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         total_adapter_ms=round((time.perf_counter() - started) * 1000, 3))
            with log_context(**stats):
                logger.info("seca_v2_complete", extra={"event": "seca_v2_complete",
                            "component": "services.seca_v2", "operation": "shadow_update"})
            return report
        if show:
            return finish()
        rows = collect_articles(paths if paths is not None else [p for p in _llm_input_paths(root) if p.exists()], stats=stats)
        stats["already_ingested_sources"] = sum(bool(db.execute("SELECT 1 FROM sources WHERE id=?", (
            (row.get("URL") or "").strip() or "article:" + _hash(_row_key(row).encode()),)).fetchone()) for row in rows)
        last = db.execute("SELECT sequence, day, state_hash FROM batches ORDER BY sequence DESC LIMIT 1").fetchone()
        if last is None:
            if not bootstrap:
                raise ValueError("initialize with bootstrap first")
            if not rows:
                raise ValueError("bootstrap requires archived relevant articles")
            target = utc_date or max(_row_timestamp(row).date() for row in rows)
            first = target - timedelta(days=2)
        else:
            target = utc_date or datetime.now(UTC).date()
            first = date.fromisoformat(last["day"]) + timedelta(days=1)
        if first > target:
            return finish()
        origin = date.fromisoformat(db.execute("SELECT day FROM batches ORDER BY sequence LIMIT 1").fetchone()[0]) if last else first
        day = first
        while day <= target:
            selected = [row for row in rows if _row_timestamp(row).date() <= day
                        and (day > origin + timedelta(days=2) or _row_timestamp(row).date() >= origin)
                        and not db.execute("SELECT 1 FROM sources WHERE id=?", (
                            (row.get("URL") or "").strip() or "article:" + _hash(_row_key(row).encode()),)).fetchone()]
            if selected and converter is None:
                seca_root = next((p for p in (root / "experimental/RealtimeSECA", root / "experimental") if p.is_dir()), None)
                converter = _resolve_seca_command(seca_root)
                converter_cwd = _seca_working_directory(converter, seca_root)
            with tempfile.TemporaryDirectory(dir=directory, prefix="convert-") as temporary:
                sources = convert_articles(selected, Path(temporary), converter=converter, cwd=converter_cwd)
            sequence = last["sequence"] + 1 if last else 0
            prepared = _json({"batch": sequence, "sources": sources})
            with db:
                db.execute("INSERT INTO batches (sequence,day,input,input_hash,config,previous_hash,status) VALUES (?,?,?,?,?,?,'pending')",
                           (sequence, day.isoformat(), prepared, _hash(prepared.encode()), config, last["state_hash"] if last else None))
            receipt = db.execute("SELECT * FROM batches WHERE sequence=?", (sequence,)).fetchone()
            report = _apply(db, receipt, command, state, directory)
            last = db.execute("SELECT * FROM batches WHERE sequence=?", (sequence,)).fetchone()
            day += timedelta(days=1)
        return finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "update", "show-last"])
    parser.add_argument("--date", type=date.fromisoformat, help="inclusive logical UTC date")
    parser.add_argument("--csv", type=Path, action="append", help="archived enriched CSV (repeatable)")
    parser.add_argument("--root", type=Path, default=_project_root())
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    print(_json(run(root=args.root.resolve(), paths=args.csv, utc_date=args.date,
                    bootstrap=args.command == "bootstrap", show=args.command == "show-last", config_path=args.config)))


if __name__ == "__main__":
    main()

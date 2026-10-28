"""Explicit offline archive validation. Uses real Rust; writes only a NEW /tmp root."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import resource
import sys
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from services import seca_v2 as v2
from utils.logging import JsonFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, action="append", required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_relative_to(Path("/tmp")) or root.exists():
        parser.error("--root must be a new, nonexistent directory under /tmp")
    root.mkdir(parents=True)
    handler = logging.FileHandler(root / "events.jsonl")
    handler.setFormatter(JsonFormatter())
    v2.logger.addHandler(handler)
    v2.logger.setLevel(logging.INFO)
    rows = v2.collect_articles(args.csv)
    latest = max(v2._row_timestamp(row).date() for row in rows)
    anchor = latest - timedelta(days=5)
    results = []

    def run(label, day, **kwargs):
        stats = {}
        result = v2.run(root=root, paths=args.csv, utc_date=day, stats=stats, **kwargs)
        stats.update(scenario=label, decisions=result["decisions"])
        results.append(stats)
        return result

    state = root / "runtime/seca/v2/state.json"
    run("three_day_bootstrap", anchor, bootstrap=True)
    run("consecutive_update", anchor + timedelta(days=1))
    result = run("missed_date_catchup", anchor + timedelta(days=3))
    committed = state.read_bytes()
    assert run("repeated_invocation", anchor + timedelta(days=3)) == result
    assert state.read_bytes() == committed
    # Each call closes SQLite; every scientific update runs in a fresh Rust process.
    assert run("restart_show_last", anchor + timedelta(days=3), show=True) == result
    assert state.read_bytes() == committed

    command = os.environ.get("RISKLIVE_SECA_V2_CLI")
    os.environ["RISKLIVE_SECA_V2_CLI"] = str(root / "missing-cli")
    try:
        run("missing_cli", latest - timedelta(days=1))
        raise AssertionError("missing executable unexpectedly succeeded")
    except FileNotFoundError:
        pass
    finally:
        if command is None:
            os.environ.pop("RISKLIVE_SECA_V2_CLI", None)
        else:
            os.environ["RISKLIVE_SECA_V2_CLI"] = command
    assert state.read_bytes() == committed
    config = json.loads(v2.CONFIG.read_text())
    config["alpha"] = 0.6
    config_path = root / "mismatched-config.json"
    config_path.write_text(json.dumps(config))
    try:
        run("configuration_mismatch", latest - timedelta(days=1), config_path=config_path)
        raise AssertionError("mismatched configuration unexpectedly succeeded")
    except ValueError:
        pass
    assert state.read_bytes() == committed

    original = v2._cli
    def interrupted(command, arguments, **kwargs):
        result = original(command, arguments, **kwargs)
        if arguments[0] == "update":
            raise OSError("injected crash after Rust state replacement")
        return result
    v2._cli = interrupted
    try:
        run("partial_execution", latest - timedelta(days=1))
        raise AssertionError("injected crash did not occur")
    except OSError:
        pass
    finally:
        v2._cli = original
    run("show_last_recovery", latest - timedelta(days=1), show=True)
    run("continue_after_recovery", latest)
    handler.flush()
    updates = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()
               if json.loads(line).get("event") == "seca_v2_update"]
    summary = {"archive_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.csv},
               "source_rows": sum(1 for _ in rows), "latest_archive_date": str(latest),
               "scenarios": results, "updates": updates,
               "peak_python_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "peak_child_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               "state_bytes": state.stat().st_size,
               "checks": ["three_day_bootstrap", "consecutive_updates", "missed_date", "repeat",
                          "restart", "missing_cli", "configuration_mismatch", "partial_execution", "show_last_recovery"]}
    (root / "measurements.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"measurement_file": str(root / "measurements.json"),
                      "checks": summary["checks"], "state_bytes": summary["state_bytes"]}))


if __name__ == "__main__":
    main()

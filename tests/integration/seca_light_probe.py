"""Offline end-to-end probe. Run directly; all state/output is isolated in /tmp.

Uses the exact production Rust update command through the core's example binary.
By default CSV tokenization is replaced by a fixture adapter for offline use.
Pass --production-converter with the full CLI to test its real converter in CI.
Never runs fetch/LLM/scheduler.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from services import seca_timeline


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Pass the built CLI or core example/update binary")
    binary = Path(sys.argv[1]).resolve()
    if not binary.is_file():
        raise SystemExit("Pass the built realtime-seca-core example/update binary")
    with tempfile.TemporaryDirectory(prefix="seca-light-probe-") as temporary:
        root = Path(temporary)
        wrapper = root / "cli"
        wrapper.write_text("#!/usr/bin/env python3\n" + '''import csv,json,os,sys
from pathlib import Path
if PRODUCTION_CONVERTER or sys.argv[1] != 'from-csv':
    os.execv(BINARY, [BINARY, *sys.argv[1:]])
index = int(sys.argv[sys.argv.index('--batch-index') + 1])
with Path(sys.argv[2]).open() as handle:
    rows = list(csv.DictReader(handle))
sources = [{'source_id': f'row_{i}', 'batch_index': index,
    'tokens': row['Title'].split(), 'text': None, 'metadata': row,
    'timestamp_unix_ms': None} for i,row in enumerate(rows)]
Path(sys.argv[3]).write_text(json.dumps({'batch_index': index, 'sources': sources}))
'''.replace("BINARY", repr(str(binary))).replace("PRODUCTION_CONVERTER", repr("--production-converter" in sys.argv[2:])))
        wrapper.chmod(0o755)
        seca_timeline._project_root = lambda: root
        seca_timeline._resolve_seca_command = lambda _: [str(wrapper)]
        os.environ["RISKLIVE_SECA_GAMMA_BATCHES"] = "3"
        os.environ["RISKLIVE_SECA_ARCHIVE_BATCHES"] = "1"
        source = root / "results/data/news_data_with_llm_info.csv"
        source.parent.mkdir(parents=True)
        historical = None
        for n in range(1, 9):
            with source.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Title", "URL", "Timestamp", "Relevance"])
                writer.writeheader()
                writer.writerow({"Title": "nuclear energy", "URL": f"https://fixture/{n}", "Timestamp": "2026-10-06T12:00:00Z", "Relevance": "Yes"})
            manifest = seca_timeline.run_seca_light_timeline(batch_id=f"probe-{n}")
            assert manifest, f"batch {n} failed"
            with sqlite3.connect(root / "runtime/seca/stream.sqlite3") as db:
                state = json.loads(db.execute("SELECT state FROM model").fetchone()[0])
                assert state["last_processed_batch_index"] == n - 1
                assert len(state["state"]["processed_batches"]) <= 3
                assert len(state["state"]["baseline_source_legend"]) == min(n, 3)
                if historical is None:
                    historical = db.execute("SELECT tree FROM batches WHERE sequence=0").fetchone()[0]
                assert db.execute("SELECT tree FROM batches WHERE sequence=0").fetchone()[0] == historical
                assert db.execute("SELECT COUNT(*) FROM batches").fetchone()[0] == n
                assert db.execute("SELECT COUNT(*) FROM batches WHERE input_batch IS NOT NULL").fetchone()[0] == n
                report = json.loads(db.execute("SELECT report FROM batches ORDER BY sequence DESC LIMIT 1").fetchone()[0])
                assert not report["reconstruction_triggered"]
                if n > 3:
                    assert report["sources_forgotten"] == 1
            for days in (30, 7, 3):
                view = root / f"results/web/newsmap/seca-light-{days}d"
                data = json.loads((view / "timeline_manifest.json").read_text())
                assert len(data["files"]) == n
                assert json.loads((view / data["files"][0]).read_text()) == json.loads(historical)
        # Replay archived normalized batches through fresh Rust processes.
        replay = root / "replay"
        replay.mkdir()
        with sqlite3.connect(root / "runtime/seca/stream.sqlite3") as db:
            archived = db.execute("SELECT input_batch, config FROM batches ORDER BY sequence").fetchall()
            committed = json.loads(db.execute("SELECT state FROM model").fetchone()[0])
        for index, (batch_json, config_json) in enumerate(archived):
            (replay / "batch.json").write_text(batch_json)
            (replay / "config.json").write_text(config_json)
            args = [str(binary), "update", str(replay / "batch.json"), "--config", str(replay / "config.json"),
                    "--state-out", str(replay / "state.json"), "--dump-tree-verbose", str(replay / "tree.json")]
            if index:
                args.extend(["--state-in", str(replay / "state.json")])
            subprocess.run(args, capture_output=True, text=True, check=True)
        assert json.loads((replay / "state.json").read_text()) == committed
        # A new process is used for each CLI call, including this idempotent retry.
        assert seca_timeline.run_seca_light_timeline(batch_id="probe-8")
        print("PASS: 8 process boundaries, one evolving model, gamma=3, historical views, identical deterministic replay, idempotent retry")


if __name__ == "__main__":
    main()

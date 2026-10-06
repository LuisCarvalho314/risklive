"""Run directly with the built production CLI; writes only an isolated /tmp root."""
import csv
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from services import seca_timeline

def _database(root):
    return sqlite3.connect(root / "runtime/seca/stream.sqlite3")
def _manifest(root, days):
    directory = root / f"results/web/newsmap/seca-light-{days}d"
    return directory, json.loads((directory / "timeline_manifest.json").read_text())
def _row(day, url, **extra):
    return {"Title": "Nuclear reactor energy", "URL": url, "Timestamp": day+"T12:00:00Z", "Relevance": "Yes", **extra}
def _write_llm_csv(path, rows):
    path.parent.mkdir(parents=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def probe(tmp_path, binary):
    """Real Rust update -> SQLite report -> same variant/sequence JSON."""
    if not binary.is_file():
        raise RuntimeError("Build the SECA CLI first")
    os.environ["RISKLIVE_SECA_CLI"] = str(binary)
    rows = [_row(f"2026-09-{day:02}", url=f"https://fixture/{day}/{n}",
                 ShortSummary=("Nuclear reactor energy safety radiation regulation" if day % 2 else
                               "Nuclear reactor energy market electricity investment"))
            for day in range(1, 9) for n in range(day)]
    _write_llm_csv(tmp_path / "results/data/news_data_with_llm_info.csv", rows)
    assert seca_timeline._run_seca_light_timeline(root=tmp_path, timeout_seconds=60, batch_id="real-bootstrap")
    with _database(tmp_path) as db:
        for variant, count in [("3d", 3), ("7d", 7), ("30d", 8)]:
            directory, manifest = _manifest(tmp_path, int(variant[:-1]))
            history = db.execute("SELECT sequence, tree, report FROM batches WHERE variant=? ORDER BY sequence", (variant,)).fetchall()
            assert len(history) == count
            diagnostics = []
            for sequence, tree_text, report_text in history:
                tree, report = json.loads(tree_text), json.loads(report_text)
                published = json.loads((directory / f"tree_batch_{sequence:04}.json").read_text())
                assert published["diagnostics_schema_version"] == 2
                assert published["update_context"] == {"variant": variant, "sequence": sequence, "batch_index": sequence}
                assert published["decision_diagnostics"] == report["decision_diagnostics"]
                assert published["display_diagnostics"] == report["display_diagnostics"]
                assert {d["hkt_id"] for d in report["display_diagnostics"]} == {h["hkt_id"] for h in tree["hkts"]}
                assert published["nodes"] == tree["nodes"]
                if sequence == 0:
                    assert report["decision_diagnostics"] == []  # Baseline is not a trigger update.
                else:
                    assert report["decision_diagnostics"]
                    d = report["decision_diagnostics"][0]
                    assert d["scoped_source_count"] == report["sources_processed"]
                    assert 0 <= d["mapped_source_count"] <= d["scoped_source_count"]
                    assert isinstance(d["should_reconstruct"], bool)
                    for name in ("paper_alpha_error", "paper_beta_error", "paper_word_importance_error"):
                        assert name in d
                    diagnostics.append(d["scoped_source_count"])
            assert len(set(diagnostics)) == count - 1
            assert manifest["variant"] == variant

if __name__ == "__main__":
    binary = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="seca-diagnostics-") as temporary:
        probe(Path(temporary), binary)
        import runpy
        sys.argv = ["verify_seca_diagnostics.py", temporary]
        runpy.run_path(str(ROOT / "scripts/verify_seca_diagnostics.py"), run_name="__main__")
    print("PASS: real Rust diagnostics -> SQLite -> historical publication, 3d/7d/30d")

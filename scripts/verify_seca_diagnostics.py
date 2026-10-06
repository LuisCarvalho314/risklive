"""Read-only verification of a three-model diagnostics replay. Usage: script ROOT."""
import json
from pathlib import Path
import sqlite3
import re
import sys

root = Path(sys.argv[1]).resolve()
with sqlite3.connect(f"file:{root}/runtime/seca/stream.sqlite3?mode=ro", uri=True) as db:
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert {r[0] for r in db.execute("SELECT variant FROM models")} == {"3d", "7d", "30d"}
    for variant in ("3d", "7d", "30d"):
        rows = db.execute("SELECT sequence, logical_timestamp, tree, report FROM batches WHERE variant=? ORDER BY sequence", (variant,)).fetchall()
        assert rows and [r[0] for r in rows] == list(range(len(rows)))
        state = json.loads(db.execute("SELECT state FROM models WHERE variant=?", (variant,)).fetchone()[0])
        assert state["last_processed_batch_index"] == rows[-1][0]
        directory = root / "results/web/newsmap" / f"seca-light-{variant}"
        manifest = json.loads((directory / "timeline_manifest.json").read_text())
        assert manifest["variant"] == variant
        published = {}
        by_sequence = {row[0]: row for row in rows}
        for filename in manifest["files"]:
            match = re.fullmatch(r"tree_batch_([0-9]+)\.json", filename)
            assert match, filename
            sequence = int(match[1])
            assert sequence in by_sequence and sequence not in published
            published[sequence] = filename
        assert manifest["days"] == [by_sequence[seq][1][:10] for seq in published]
        joined = 0
        # Validate every stored snapshot. Publication may expose only the current
        # horizon while older history remains in SQLite; never zip unrelated rows.
        for sequence, _, tree_text, report_text in rows:
            tree, report = json.loads(tree_text), json.loads(report_text)
            if sequence in published:
                output = json.loads((directory / published[sequence]).read_text())
                assert output["diagnostics_schema_version"] == 2
                assert output["update_context"] == {"variant": variant, "sequence": sequence, "batch_index": sequence}
                assert output["decision_diagnostics"] == report["decision_diagnostics"]
                assert output["display_diagnostics"] == report["display_diagnostics"]
                for key, value in tree.items():
                    assert output[key] == value
            if sequence == 0:
                assert report["decision_diagnostics"] == []
            elif report.get("sources_processed", 0) > 0:
                assert report["decision_diagnostics"], (variant, sequence)
            ids = {h["hkt_id"] for h in tree["hkts"]}
            display = report["display_diagnostics"]
            assert len(display) == len(ids)
            assert {d["hkt_id"] for d in display} == ids
            coverage = {label: sum(d.get(field) is not None for d in display)
                        for label, field in [("alpha", "paper_alpha_error"), ("beta", "paper_beta_error"),
                                             ("WI", "paper_word_importance_error")]}
            print(f"{variant} sequence={sequence} HKTs={len(ids)} decision={len(report['decision_diagnostics'])} "
                  f"display={len(display)} available={coverage}")
            if sequence and ids and min(coverage.values()) / len(ids) < 0.25:
                print("WARNING: low evaluable display coverage; inspect unavailable_reason", file=sys.stderr)
            for d in display:
                for field in ("paper_alpha_error", "paper_beta_error", "paper_word_importance_error"):
                    value = d.get(field)
                    assert value is None or isinstance(value, (int, float)) and 0 <= value <= 1
                if sequence == 0:
                    assert d["paper_alpha_error"] is None
                    assert d["unavailable_reason"] == "baseline_no_comparison"
            for d in report["decision_diagnostics"]:
                assert 0 <= d["mapped_source_count"] <= d["scoped_source_count"]
                assert isinstance(d["should_reconstruct"], bool)
                for field in ("paper_alpha_error", "paper_beta_error", "paper_word_importance_error"):
                    assert field in d
                if d["output_hkt_id"] is not None:
                    assert d["output_hkt_id"] in ids
                    joined += 1
        print(variant, "historical batches:", len(rows), "joined evaluated scopes:", joined)

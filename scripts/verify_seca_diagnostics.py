"""Read-only verification of a three-model diagnostics replay. Usage: script ROOT."""
import json
from pathlib import Path
import sqlite3
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
        assert manifest["days"] == [r[1][:10] for r in rows]
        assert len(manifest["files"]) == len(rows)
        joined = 0
        for filename, (sequence, _, tree_text, report_text) in zip(manifest["files"], rows):
            tree, report = json.loads(tree_text), json.loads(report_text)
            output = json.loads((directory / filename).read_text())
            assert output["diagnostics_schema_version"] == 1
            assert output["update_context"] == {"variant": variant, "sequence": sequence, "batch_index": sequence}
            assert output["hkt_diagnostics"] == report["hkt_diagnostics"]
            for key, value in tree.items():
                assert output[key] == value
            if sequence == 0:
                assert report["hkt_diagnostics"] == []
            else:
                assert report["hkt_diagnostics"], (variant, sequence)
            ids = {h["hkt_id"] for h in tree["hkts"]}
            for d in report["hkt_diagnostics"]:
                assert 0 <= d["mapped_source_count"] <= d["scoped_source_count"]
                assert isinstance(d["should_reconstruct"], bool)
                for field in ("paper_alpha_error", "paper_beta_error", "paper_word_importance_error"):
                    assert field in d
                if d["output_hkt_id"] is not None:
                    assert d["output_hkt_id"] in ids
                    joined += 1
        print(variant, "historical batches:", len(rows), "joined evaluated scopes:", joined)

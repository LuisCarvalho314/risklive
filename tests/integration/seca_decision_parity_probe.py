"""Compare pre-feature and new CLIs on identical isolated historical updates.

Usage: python seca_decision_parity_probe.py OLD_CLI NEW_CLI
Writes only a disposable /tmp directory; no production or network access.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def probe(old_cli: Path, new_cli: Path, root: Path):
    checks = reconstructions = 0
    for gamma in (3, 7, 30):
        config = json.loads((ROOT / "experimental/seca_light_config.json").read_text())
        config["max_batches_in_memory"] = gamma
        # Force visible real reconstruction in this provenance comparison.
        for field in ("alpha_option1_threshold", "beta_option1_threshold", "word_importance_option1_threshold"):
            config["seca_thresholds"][field] = 0.0
        config_path = root / f"config-{gamma}.json"
        config_path.write_text(json.dumps(config))
        for name in ("old", "new"):
            (root / f"{name}-{gamma}").mkdir()
        for sequence in range(8):
            phase = ("reactor", "market", "solar")[sequence % 3]
            sources = [{"source_id": f"s-{sequence}-{i}", "batch_index": sequence,
                        "tokens": ["energy", phase, "investment" if i % 2 else "safety"]}
                       for i in range(12 + sequence)]
            batch = root / f"batch-{gamma}-{sequence}.json"
            batch.write_text(json.dumps({"batch_index": sequence, "sources": sources}))
            outputs = []
            for name, binary in (("old", old_cli), ("new", new_cli)):
                directory = root / f"{name}-{gamma}"
                state, tree = directory / "state.json", directory / "tree.json"
                args = [str(binary), "update", str(batch), "--config", str(config_path),
                        "--state-out", str(state), "--dump-tree-verbose", str(tree)]
                if sequence:
                    args.extend(["--state-in", str(state)])
                report = json.loads(subprocess.check_output(args, text=True, timeout=120))
                outputs.append((report, json.loads(state.read_text()), json.loads(tree.read_text())))
            old, new = outputs
            normalized = dict(new[0])
            display = normalized.pop("display_diagnostics")
            normalized["hkt_diagnostics"] = normalized.pop("decision_diagnostics")
            assert old[0] == normalized, (gamma, sequence, "decision/report changed")
            assert old[1] == new[1], (gamma, sequence, "full persisted engine changed")
            assert old[2] == new[2], (gamma, sequence, "final tree/reconstruction IDs changed")
            assert {d["hkt_id"] for d in display} == {h["hkt_id"] for h in new[2]["hkts"]}
            reconstructions += int(new[0]["reconstruction_triggered"])
            checks += 1
    assert reconstructions > 0
    print(f"PASS: {checks} pre-feature/new updates across 3d/7d/30d, {reconstructions} reconstructions; "
          "identical decisions, reports, topology, IDs and complete persisted engine state")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: seca_decision_parity_probe.py OLD_CLI NEW_CLI")
    old_cli = Path(sys.argv[1]).resolve()
    new_cli = Path(sys.argv[2]).resolve()
    if not old_cli.is_file() or not new_cli.is_file():
        raise SystemExit("OLD_CLI and NEW_CLI must both exist")
    with tempfile.TemporaryDirectory(prefix="seca-decision-parity-") as temporary:
        probe(old_cli, new_cli, Path(temporary))

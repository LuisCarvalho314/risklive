# SECA experimental sizing contract

Trigger diagnostics previously stopped at `HktTriggerDecisionInternal`: the recursive plan kept text notes, `BatchProcessingResult` discarded the structured decision, and the verbose tree had no metrics. SQLite already stored each update report, but timeline publication emitted only its structural tree. The loader therefore always selected proxies. The timeline's existing `weightModeOverride="value"` was correct.

The optional/default-empty Rust `BatchProcessingResult.hkt_diagnostics` now records actual evaluated **HKT scopes**, not node errors. Each record includes scoped incoming source count, unique incoming source count mapped to non-refuge nodes (refuge-only sources excluded), trigger decision/reasons, policy, placeholder diagnostics and selected paper diagnostics. Production `update` enforces PaperDiagnosticScaffold and Option1 for all three equations; the paper fields are authoritative. Plain error fields remain exported for inspection but are never frontend substitutes. No equations changed.

`hkt_id` is the evaluated state0 ID. `output_hkt_id` identifies that same scope in the post-update tree: unchanged HKT or explicitly mapped rebuilt subtree root. Removed scopes/full-rebuild IDs are null. New child HKTs, unvisited scopes, empty updates and baseline initialization have no independent trigger diagnostics. They remain unavailable; diagnostics are not invented for them. This is a report contract change; standalone verbose dumps remain structural. The CLI already serializes this result to stdout.

SQLite schema 2 remains unchanged: the report stays paired with the tree by `(variant, sequence)`. Publication adds `diagnostics_schema_version: 1`, `update_context: {variant, sequence, batch_index}`, and `hkt_diagnostics` to each JSON. Legacy missing reports produce an empty array. No latest-report lookup, cross-model join, migration or log parsing occurs.

| Selector | Raw score |
|---|---|
| Mapped Sources | Unique incoming sources mapped to non-refuge nodes of the evaluated HKT |
| Alpha Error | Selected Option1 `paper_alpha_error` |
| Beta Error | Selected Option1 `paper_beta_error` |
| Word-Importance Error | Selected Option1 `paper_word_importance_error` |
| Combined Error | `sqrt(mean(error²))` over available real paper errors; missing terms omitted, all missing means unavailable |
| Triggered | Actual `should_reconstruct`: true → 4, false → 1; independent of source count |
| Composite | Existing explicit legacy heuristic: rounded recency-weighted source mass × sqrt(word mass) × HKT significance × lexical/refuge proxy × window weight, minimum 1 |

For each sibling HKT group, High → Large uses `1e-9 + score`. High → Small uses `1e-9 + maxScore + minScore - score`, with extrema among sibling HKT groups. Both preserve ordering without quantization. Each HKT owns one group budget shared among its member nodes in proportion to `max(1, node source count)`. Child HKT groups partition their parent's budget conditionally by the same rule. Thus an ancestor's mass is not added once per descendant. The root budget is 1; only leaves contribute to D3 `.sum`. The experimental preweighted marker bypasses focus's log1p, emphasis scaling and minimum group weight. Hierarchy preservation bypasses production normalization; palette application preserves values and metadata. Production NewsMap behavior remains unchanged.

If any displayed HKT lacks the selected score, the whole snapshot uses equal HKT group budgets and visibly reports `Diagnostic unavailable (available/total HKT scopes); equal scope weighting.` It never selects Composite implicitly. Composite remains usable for legacy snapshots. Metadata exposes `seca_actual`, `legacy_proxy` or `unavailable` for the selected metric, alongside evaluated/output IDs, policy and reasons. Single-HKT siblings divide the same scope score by node source mass; they do not pretend to have independent alpha/beta errors.

## Validation

Run from the RiskLive checkout:

```bash
cargo test --manifest-path experimental/Cargo.toml --workspace
cargo build --manifest-path experimental/Cargo.toml -p realtime-seca-cli
.venv/bin/python -m pytest --no-cov tests/unit/services/test_seca_timeline.py
.venv/bin/python tests/integration/seca_diagnostics_probe.py experimental/target/debug/realtime-seca-cli
(cd web && npm test && npm run typecheck && npm run build)
```

The standalone probe uses the real production CSV converter and Rust CLI, writes only a disposable `/tmp` workspace, replays changing daily inputs across independent 3d/7d/30d models, and compares every published diagnostic to its own historical SQLite report. It runs outside pytest because that suite deliberately forbids subprocesses. Geometry tests use `buildWeightedTree` and actual D3 rectangles to prove selector differentiation, direction inversion, small/zero errors, trigger classes, legacy status and descendant budget conservation. Loader tests read different historical diagnostics from each variant's files.

## Production correction — commands only, not executed

Rebootstrap is required for the existing pre-fix history. Final persisted engine state retains only bounded recent batches and does not store historical trigger decisions; recalculating from that state is not equivalent. Historical replay of archived original input/config could recover them, but the cleanest supported correction is chronological bootstrap from existing enriched article CSVs into a new database. Baseline and genuinely unevaluated scopes still display unavailable.

Use the usual production compose exports, corrected immutable app/web images (including the updated Rust gitlink/binary), and a quiet processing period. The following builds and verifies in a separate replay root before replacing only the SECA database and three output directories. It preserves originals, CSVs, legacy outputs and unrelated runtime files. No fetching, inference, network, deployment build or scheduler runs during replay. All commands below are for an operator; Codex has not executed them.

```bash
set -euo pipefail
: "${APP_IMAGE:?Corrected immutable app image required}"
: "${WEB_IMAGE:?Corrected immutable web image required}"
test "$RISKLIVE_DATA_DIR" = /opt/risklive/data
export SECA_DIAGNOSTICS_BACKUP="/opt/risklive/backups/seca-diagnostics-$(date -u +%Y%m%dT%H%M%SZ)"
export SECA_DIAGNOSTICS_REPLAY="$SECA_DIAGNOSTICS_BACKUP/replay"
docker compose -f deployment/compose/docker-compose.prod.yml stop scheduler app web
sudo mkdir -p "$SECA_DIAGNOSTICS_REPLAY/results/data" "$SECA_DIAGNOSTICS_REPLAY/results/backup_data" "$SECA_DIAGNOSTICS_REPLAY/runtime" "$SECA_DIAGNOSTICS_BACKUP/output"
sudo cp -a "$RISKLIVE_DATA_DIR/runtime/seca" "$SECA_DIAGNOSTICS_BACKUP/runtime-seca"
for folder in data backup_data; do
  if test -f "$RISKLIVE_DATA_DIR/results/$folder/news_data_with_llm_info.csv"; then
    sudo cp -a "$RISKLIVE_DATA_DIR/results/$folder/news_data_with_llm_info.csv" "$SECA_DIAGNOSTICS_REPLAY/results/$folder/"
    sudo sha256sum "$RISKLIVE_DATA_DIR/results/$folder/news_data_with_llm_info.csv" "$SECA_DIAGNOSTICS_REPLAY/results/$folder/news_data_with_llm_info.csv"
  fi
done
for variant in 3d 7d 30d; do
  sudo cp -a "$RISKLIVE_DATA_DIR/results/web/newsmap/seca-light-$variant" "$SECA_DIAGNOSTICS_BACKUP/output/"
done
# The app image runs as UID/GID 10001. Only the isolated replay copy is changed.
sudo chown -R 10001:10001 "$SECA_DIAGNOSTICS_REPLAY"
docker run --rm --pull never --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev \
  --mount "type=bind,src=$SECA_DIAGNOSTICS_REPLAY/results,dst=/app/results" \
  --mount "type=bind,src=$SECA_DIAGNOSTICS_REPLAY/runtime,dst=/app/runtime" \
  "$APP_IMAGE" python -c 'from services.seca_timeline import run_seca_light_timeline; assert run_seca_light_timeline(timeout_seconds=3600, batch_id="diagnostics-rebootstrap-v1") is not None'
# Verifier is read-only and checks every historical report/tree pairing.
docker run --rm -i --pull never --network none --read-only \
  --mount "type=bind,src=$SECA_DIAGNOSTICS_REPLAY,dst=/data,readonly" \
  "$APP_IMAGE" python - /data < scripts/verify_seca_diagnostics.py
# Review replay outputs before this replacement step. Prepare whole directories
# on the production filesystem; retain original live directories for rollback.
for variant in 3d 7d 30d; do
  sudo cp -a "$SECA_DIAGNOSTICS_REPLAY/results/web/newsmap/seca-light-$variant" "$RISKLIVE_DATA_DIR/results/web/newsmap/.seca-diagnostics-$variant"
  sudo chown -R --reference="$RISKLIVE_DATA_DIR/results/web/newsmap/seca-light-$variant" "$RISKLIVE_DATA_DIR/results/web/newsmap/.seca-diagnostics-$variant"
done
sudo cp -a "$SECA_DIAGNOSTICS_REPLAY/runtime/seca/stream.sqlite3" "$RISKLIVE_DATA_DIR/runtime/seca/.stream-diagnostics.sqlite3"
sudo chown --reference="$RISKLIVE_DATA_DIR/runtime/seca/stream.sqlite3" "$RISKLIVE_DATA_DIR/runtime/seca/.stream-diagnostics.sqlite3"
sudo mv "$RISKLIVE_DATA_DIR/runtime/seca/stream.sqlite3" "$SECA_DIAGNOSTICS_BACKUP/pre-diagnostics-stream.sqlite3"
for suffix in -wal -shm -journal; do
  if test -f "$RISKLIVE_DATA_DIR/runtime/seca/stream.sqlite3$suffix"; then
    sudo mv "$RISKLIVE_DATA_DIR/runtime/seca/stream.sqlite3$suffix" "$SECA_DIAGNOSTICS_BACKUP/"
  fi
done
sudo mv "$RISKLIVE_DATA_DIR/runtime/seca/.stream-diagnostics.sqlite3" "$RISKLIVE_DATA_DIR/runtime/seca/stream.sqlite3"
for variant in 3d 7d 30d; do
  sudo mv "$RISKLIVE_DATA_DIR/results/web/newsmap/seca-light-$variant" "$SECA_DIAGNOSTICS_BACKUP/pre-diagnostics-$variant"
  sudo mv "$RISKLIVE_DATA_DIR/results/web/newsmap/.seca-diagnostics-$variant" "$RISKLIVE_DATA_DIR/results/web/newsmap/seca-light-$variant"
done
docker run --rm -i --pull never --network none --read-only \
  --mount "type=bind,src=$RISKLIVE_DATA_DIR,dst=/data,readonly" \
  "$APP_IMAGE" python - /data < scripts/verify_seca_diagnostics.py
# Start corrected app/web only after verification. Resume scheduler separately
# when operationally intended; do not run deploy.sh or fetch/LLM for this replay.
docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps --no-build --pull never --wait app web
```

If replay fails, leave production data unchanged and retry the isolated run with the same batch ID. If replacement verification fails, leave writers/readers stopped, move aside the replacement database/directories and restore `runtime-seca` and the three `output/seca-light-*` backups with their original ownership, using matching previous app/web images. Do not copy over unrelated runtime directories or article CSVs. The source window anchors to the newest copied relevant article; preserve the input-copy checksums to identify the exact replay.

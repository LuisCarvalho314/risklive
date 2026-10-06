# Independent persistent SECA-Light models

## Investigation and root cause

Before persistence, commit `98d8709` selected separate 30/7/3 UTC calendar-day source windows anchored to the latest relevant observation. `_run_timeline_variant` grouped each window by UTC day and built fresh CA baselines for successive cumulative prefixes. The variants shared builder/threshold configuration but had distinct input and trees. The frontend selects separate directories and reads parallel `files`/`days` arrays; it does not require a shared model.

Commit `6192a33` incorrectly replaced this distinction with one singleton state, one ingestion ledger and one bootstrap batch, then filtered that model's history into three presentation windows. It also assigned processing time to bootstrap snapshots. Similar output shapes did not imply identical models.

## Corrected lifecycle

SQLite `runtime/seca/stream.sqlite3` uses `PRAGMA user_version=2`. `models` stores separate Rust snapshots keyed by `variant` (`30d`, `7d`, `3d`). `batches` has primary key `(variant, sequence)` and unique `(variant, batch_id)`; it stores logical and processed timestamps, tree, report, optional normalized input and config. `ingested` has primary key `(variant, source_key)`. `invocations` records completion of a whole service call. Schema 1 is explicitly rejected unchanged; its state is never reinterpreted.

On an empty database, each variant selects its own original UTC calendar-day source window, groups nonempty source days chronologically, initializes on the first day's batch and passes the resulting Rust state to each subsequent day's update. All variants and historical batches commit together. The final state for each becomes its online state. Historical IDs are `bootstrap-v2-<variant>-<YYYY-MM-DD>`. Snapshot logical timestamps are midnight UTC on the source day; processed timestamps record actual processing time. Live logical timestamps are invocation time.

On subsequent calls, each model selects unseen articles in its own source window and evolves from its own saved state, including successful empty batches. A receipt in one variant cannot suppress another. Receipts outlive engine forgetting. Retrying an explicit completed invocation ID republishes without updating any model. Calling again under a new ID performs a normal online update, not another bootstrap. Publication failures leave committed history recoverable.

Production schedules fetching once daily at 06:20 Europe/London (`src/app/schedules.json`). Prior configurations used shared builder thresholds; baseline generation did not apply gamma as a retention rule. Rust SlidingWindow gamma retains the latest committed **batches**, pruning source memory after updates while retaining learned topology until reconstruction. Defaults now explicitly map `3d=3`, `7d=7`, `30d=30` in `config/seca_timeline.json`. `RISKLIVE_SECA_GAMMA_BATCHES_<3|7|30>D` overrides an individual model; the existing `RISKLIVE_SECA_GAMMA_BATCHES` remains an explicit all-model override. Values must be positive. Manual/empty calls also consume batches; missing historical days do not. Therefore gamma is not an exact calendar-age bound. Source discovery retains the existing calendar window semantics, including late arrivals within each window. Changing persisted configuration requires explicit replay.

All model/history/receipt updates share one SQLite transaction with synchronous FULL and the existing cross-process flock. CLI state files remain temporary and use Rust's fsync/atomic replacement. Failed tokenization or update rolls back all model writes and consumes no invocation ID. SQLite history remains complete; each output directory serves a calendar-bounded timeline of **its own model** with historical dates. Files/manifests preserve frontend fields and filenames; manifest `variant` identifies the model. Directory publication remains individually atomic and recoverable, not a three-directory filesystem transaction. Existing legacy output preservation remains in place.

## Paper mapping and interpretation

Reference: Al Sulaimani and Starkey, *Real-Time Event Detection Using Self-Evolving Contextual Analysis (SECA) Approach*, IEEE Access (2023), DOI [10.1109/ACCESS.2023.3331219](https://doi.org/10.1109/ACCESS.2023.3331219). Sections V–VII and the real-world configuration were reviewed in the [author-uploaded full text](https://www.researchgate.net/publication/375503068_Real-Time_Event_Detection_Using_Self-Evolving_Contextual_Analysis_SECA_Approach).

For scoped source sets, let `df(w)` count distinct sources containing a word, `N(node)` be the node's source membership, and `W0` the HKT's old vocabulary:

- Strength is `df(w) / max(df(v))` in the HKT scope. The alpha condition is strength >= alpha.
- Eligibility is `|sources(w) intersect N(node)| / |N(node)|`. The beta condition is eligibility >= beta.
- Alpha-Error is the mean over old words of `max(0, alpha - strength1(w))` (equation 6).
- Beta-Error is the mean over old words of `max(0, beta - eligibility1(w))` (equation 9).
- Word importance normalizes document frequency over old and newly eligible vocabulary. Word-Importance-Error is `1 - sum(importance1(w), w in W0)` (equation 12).

Production selects Option1 for all three measures. Options2/3 remain legacy diagnostics and are not the paper's active rule. Threshold comparisons use full precision and strict `>`; only log rendering rounds values. Builder alpha/beta must match update alpha/beta.

Traversal starts at Seed-HKT with the new batch. Child scopes inherit sources adopted by their parent node. Sources may belong to multiple nodes; unmatched sources enter refuge. A threshold crossing replaces that HKT and its descendants, stopping further descent there. Otherwise its existing structure is retained and children are inspected. Reconstruction uses retained source batches plus the current batch, excluding words already adopted along the ancestor path.

SECA-Light prunes source data **after** this update. The paper's phrase “before theta-gamma” has an inclusive-boundary ambiguity relative to “up to gamma batches”; we retain exactly the latest gamma successfully committed batches, as requested. The real-world paper uses gamma=3 with minute batches; RiskLive uses separate gamma defaults of 3/7/30 batches rather than minutes or days.

Forgetting alone does not erase learned topology. Zero-support nodes may remain until their container is reconstructed. Selective replacement can shrink a subtree, so the tree does not only grow. The paper does not establish a strict bound on tree size; gamma bounds retained batches, not nodes, sources per batch, vocabulary, or audit history. Empty scopes have no new evidence and do not trigger a rebuild. This is an explicit engineering interpretation of an undefined empty denominator.

## Validation and compatibility

Local results: **27 focused Python tests passed**, the eight-call real Rust probe passed, the offline Rust core suite passed, and 20 frontend loader/ops compatibility tests passed. Full production-converter CLI/container builds were not rerun locally; the existing CI gate remains required before deployment.

The focused Python suite covers independent state/history, 30 historical daily updates versus 7 versus 3, logical timestamps, model-specific receipts, live continuation, independent gamma forgetting, idempotent retry, late third-model bootstrap rollback, schema-1 rejection, processing failures and publication recovery. The real Rust probe launches separate engine processes across eight calls, checks all three restored states and receipt ledgers, and proves archived replay equals persisted continuation. Existing Rust core tests additionally cover restart equivalence, scoped reconstruction and forgetting. No Rust implementation or gitlink change is required.

SQLite schema 1 requires the explicit migration below. CSVs, backup articles, legacy outputs and frontend contracts remain intact. Historic static baselines cannot initialize resumable states. Output size guards still apply. Archive history grows separately from bounded active engine memory; `RISKLIVE_SECA_ARCHIVE_BATCHES=1` retains normalized inputs for reproducible replay.

## Operator migration — do not run automatically

Deploy/build the tested corrected version first, without starting its scheduler. Run the commands below from the production repository with its usual compose environment (`COMPOSE_PROJECT_NAME`, `APP_IMAGE`, `WEB_IMAGE`, `APP_ENV_FILE`, `WEB_ENV_FILE`, `RISKLIVE_DATA_DIR`) already exported. `APP_IMAGE` must be the corrected immutable image. These commands pause app/manual processing and web reads too, giving a quiet CSV/SQLite backup point. No fetch/LLM pipeline is invoked.

```bash
set -euo pipefail
: "${APP_IMAGE:?Set corrected versioned image}"
test "$RISKLIVE_DATA_DIR" = /opt/risklive/data
export SECA_MIGRATION_BACKUP="/opt/risklive/backups/seca-three-models-$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f deployment/compose/docker-compose.prod.yml stop scheduler app web
sudo mkdir -p "$SECA_MIGRATION_BACKUP/output"
sudo cp -a /opt/risklive/data/runtime/seca "$SECA_MIGRATION_BACKUP/runtime-seca"
for variant in 3d 7d 30d; do
  if test -d "/opt/risklive/data/results/web/newsmap/seca-light-$variant"; then
    sudo cp -a "/opt/risklive/data/results/web/newsmap/seca-light-$variant" "$SECA_MIGRATION_BACKUP/output/"
  fi
done
# Reset only the incorrect new persistent database; retain lock and other diagnostics.
sudo mv /opt/risklive/data/runtime/seca/stream.sqlite3 "$SECA_MIGRATION_BACKUP/incorrect-stream.sqlite3"
for suffix in -wal -shm -journal; do
  if test -f "/opt/risklive/data/runtime/seca/stream.sqlite3$suffix"; then
    sudo mv "/opt/risklive/data/runtime/seca/stream.sqlite3$suffix" "$SECA_MIGRATION_BACKUP/"
  fi
done
# Standalone corrected bootstrap, no network or scheduler, only existing CSV inputs.
docker run --rm --pull never --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev \
  --mount type=bind,src=/opt/risklive/data/results,dst=/app/results \
  --mount type=bind,src=/opt/risklive/data/runtime,dst=/app/runtime \
  "$APP_IMAGE" python -c 'from services.seca_timeline import run_seca_light_timeline; assert run_seca_light_timeline(batch_id="migration-three-models-v2") is not None'
# Verify schema, independent states, populated dated histories, receipts and sequences.
docker run --rm -i --pull never --network none --read-only \
  --mount type=bind,src=/opt/risklive/data,dst=/data,readonly \
  "$APP_IMAGE" python - <<'PY'
import json, sqlite3
from pathlib import Path
root = Path('/data')
db = sqlite3.connect('file:/data/runtime/seca/stream.sqlite3?mode=ro', uri=True)
assert db.execute('PRAGMA user_version').fetchone()[0] == 2
assert {r[0] for r in db.execute('SELECT variant FROM models')} == {'3d', '7d', '30d'}
for variant in ('3d', '7d', '30d'):
    state = json.loads(db.execute('SELECT state FROM models WHERE variant=?', (variant,)).fetchone()[0])
    rows = db.execute('SELECT sequence, logical_timestamp, batch_id FROM batches WHERE variant=? ORDER BY sequence', (variant,)).fetchall()
    assert rows and [r[0] for r in rows] == list(range(len(rows)))
    assert state['last_processed_batch_index'] == rows[-1][0]
    assert all(r[2] == f'bootstrap-v2-{variant}-{r[1][:10]}' for r in rows)
    receipts = db.execute('SELECT COUNT(*), MIN(sequence), MAX(sequence) FROM ingested WHERE variant=?', (variant,)).fetchone()
    assert receipts[0] > 0 and receipts[1] >= 0 and receipts[2] <= rows[-1][0]
    directory = root / 'results/web/newsmap' / f'seca-light-{variant}'
    manifest = json.loads((directory / 'timeline_manifest.json').read_text())
    assert manifest['variant'] == variant
    assert manifest['days'] == [r[1][:10] for r in rows]
    assert len(manifest['files']) == len(rows)
    for name, row in zip(manifest['files'], rows):
        tree = json.loads((directory / name).read_text())
        stored = json.loads(db.execute('SELECT tree FROM batches WHERE variant=? AND sequence=?', (variant, row[0])).fetchone()[0])
        assert tree == stored
    print(variant, 'latest_sequence=', rows[-1][0], 'receipts=', receipts[0], 'history_days=', manifest['days'], 'gamma=', state['config']['max_batches_in_memory'])
PY
# Only after all assertions pass and output review succeeds:
docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps --no-build --pull never --wait app web
docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps --no-build --pull never scheduler
```

If bootstrap/verification fails, keep scheduling paused. A bootstrap processing failure leaves a new empty schema-2 DB; retrying the same ID is safe. A publication failure leaves all three states committed; the same ID republishes. Do not restore the incorrect singleton into the corrected service. For a full rollback, stop app/web/scheduler, restore the entire backed-up `runtime-seca` and three backed-up output directories, and start the matching previous image before resuming scheduling. Leave `results/data`, `results/backup_data`, CSVs and `seca-legacy` untouched throughout. The commands above have not been executed by Codex.

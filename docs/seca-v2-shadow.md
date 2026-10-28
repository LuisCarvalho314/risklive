# SECALight V2 shadow operations

The existing daily pipeline runs the optional V2 hook after BERTopic, reports and
dashboard export. `RISKLIVE_SECA_V2_ENABLED=false` is the default; only `true`
(case-insensitive) enables it. Failures are logged and swallowed at this boundary.
The existing fetch job stays at 06:20 Europe/London and cleanup at 06:00, with
the same IDs, locking, coalescing and DST behavior. No job or public endpoint was added.

V1 compatibility was explicitly dropped during validation. The scheduled V1
invocation is retired. Existing V1 code/artifacts and legacy routes remain, but
the packaged CLI is not compatible with the old scientific update configuration.
It is retained for CSV preprocessing only. No V1-to-V2 state migration occurs.
Existing Newsmap pages continue to read their existing artifacts; V2 is not shown
in the frontend. BERTopic, report generation and dashboard export code are unchanged.

## Build and scientific output

Pinned Rust source: `4630d280e323ed2067b9ac7a0efb4f59447d335d` in
`experimental`. Rust 1.92.0 uses the digest-pinned builder, parent-owned
`docker/seca/Cargo.lock` and `SOURCE.sha256`. CI builds/tests the Rust packages,
runs the real V2 archive/crash suite separately from the guarded Python suite,
and builds the application image. The Rust algorithms are unmodified.

`runtime/seca/v2/state.json` is authoritative. The same directory contains
`ledger.sqlite3`, `update.lock`, `latest.json` and
`reports/YYYY-MM-DD/batch-N.json`. Reports preserve the native CLI JSON schema:
`batch`, `next_batch`, `retained_source_count`, recursive `root`, `decisions`
with structural paths, reconstruction booleans and alpha/beta/importance errors.
The dated filename carries logical UTC date; no node identifiers are invented.
`latest.json` is atomically replaced after committing the receipt. A publication
failure is repaired by repeating `show-last` or the same-date update.

The existing JSON logger emits `seca_v2_update` duration per scientific update
and `seca_v2_complete` with considered/relevant rows, within-input deduplication,
already-ingested sources, accepted sources, batch date/index, retained count,
state bytes, reconstruction counts, adapter duration and peak process RSS.
RSS is a lifetime Linux high-water measurement, not incremental adapter usage.

Real archived data exposed one-ULP differences between update stdout and Rust
JSON readback in error metrics. The adapter now permits at most two ULPs for
those metrics only; batch/tree/path/reconstruction decisions remain exact.
The persisted report is always the published result. Receipt/input/evidence
checks and fail-closed recovery remain unchanged.

## Validation

See [recorded measurements](seca-v2-shadow-measurements.json). The offline archive
contained 18,658 rows, 4,712 relevant rows and 4,678 unique relevant sources
(34 within-input duplicates). Three-day bootstrap accepted 220 sources in 0.917 s.
The next update accepted 3,912 previously unseen historical sources because the
whole archive was supplied, then catch-up across one missed date accepted 265.
All 4,678 unique sources were accepted once after the final date. Latest state
was 1,099,414 bytes; maximum observed state was 12,508,814 bytes. Peak process RSS
was 242,720 KiB. Individual release Rust updates took 11.8–1,020.5 ms.
Repeating the same date accepted zero sources and preserved the state bytes.

Checks covered bootstrap, consecutive dates, missed date, repeat, restart,
missing executable, config mismatch, crash after Rust replacement, show-last
recovery, and continuation. Synthetic tests also cover pre-replacement crashes,
empty days, source forgetting, locking, artifact publication recovery and invalid
configuration. The full guarded Python suite, frontend checks, production build,
real Rust integration suite and application image build are release gates.
App health/routes and scheduler startup/SIGTERM were checked in a read-only,
no-network image with temporary mounts and dummy credentials.

To repeat the real archive probe, explicitly copy the two enriched CSV members
of an archive into a temporary workspace, then run:

```bash
export PYTHONPATH=src:.
export RISKLIVE_SECA_V2_CLI=/absolute/path/to/seca-v2-cli
export RISKLIVE_SECA_CLI=/absolute/path/to/realtime-seca-cli
python tests/integration/seca_v2_shadow_probe.py \
  --csv /tmp/archive/current.csv --csv /tmp/archive/backup.csv \
  --root /tmp/new-v2-replay
```

The probe refuses an existing root or a root outside `/tmp`. It does not discover
or access production data. Standard tests use tracked fixtures only.

## Deployment and activation

Run only after the selected revision passes CI and deployment is authorized.
Keep the current Compose project, data root, environment files and web/Caddy
images. Never use the helper to implicitly change unrelated services.

```bash
export COMPOSE_PROJECT_NAME=risklive-prod
export RISKLIVE_DATA_DIR=/opt/risklive/data
export APP_ENV_FILE="$RISKLIVE_DATA_DIR/env/app.env"
export WEB_ENV_FILE="$RISKLIVE_DATA_DIR/env/web.env"
export CADDY_ENV_FILE="$RISKLIVE_DATA_DIR/env/caddy.env"
export APP_IMAGE="risklive-app:$(git rev-parse --short=12 HEAD)"
export WEB_IMAGE=risklive-web:e2a553c  # Preserve the deployed web image.
export SECA_COMPOSE=deployment/compose/docker-compose.prod.yml

git submodule update --init --checkout experimental
docker build -f docker/Dockerfile.app -t "$APP_IMAGE" .
docker compose -f "$SECA_COMPOSE" stop scheduler
```

Back up results/runtime/logs/private env while writers are stopped; keep secrets
out of repository artifacts. If V2 has already been initialized, take its lock
while copying its entire directory. For a new stream, bootstrap exactly once
using available enriched current/backup CSVs and an explicitly chosen final UTC
date (normally the current UTC date):

```bash
docker compose -f "$SECA_COMPOSE" run --rm --no-deps --pull never \
  -e RISKLIVE_SECA_V2_ENABLED=false app \
  python -m services.seca_v2 bootstrap --date "$(date -u +%F)"
```

If a V2 ledger already exists, inspect `show-last` and validate/recover it; never
bootstrap or replay old history over it. Set `RISKLIVE_SECA_V2_ENABLED=true` in
the private app env file only after inspecting the bootstrap result, then:

```bash
docker compose -f "$SECA_COMPOSE" up -d --no-deps --no-build --pull never --wait app scheduler
docker compose -f "$SECA_COMPOSE" exec -T app python -m services.seca_v2 show-last
```

Confirm app health, scheduler logs, native artifact, state/ledger receipt, and
same-date idempotency. Do not invoke news-fetch or report routes to smoke test.

## Disable, restore, replay

Set `RISKLIVE_SECA_V2_ENABLED=false` in the private app env file and recreate
`app scheduler` with the same command. Keep the V2 runtime for inspection; disabling
does not roll back reports or delete state. To restore, stop both writer containers,
preserve the failed runtime separately and restore the entire matched V2 directory
(state plus ledger) from the same backup. Restart only after offline validation.
Never restore SQLite alone or copy V1 snapshots into V2.

For unusable state, replay explicitly into a fresh root, using the adapter's
`bootstrap` then date-controlled `update` commands with archived enriched CSVs.
Inspect `latest.json` and receipts and compare source counts before any separately
authorized promotion of that directory. No automatic historical replay is done by
the scheduler. See [adapter recovery details](seca-v2-adapter.md).

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/deployment/compose/docker-compose.prod.yml"
verifier="$repo_root/scripts/verify_seca_diagnostics.py"

: "${COMPOSE_PROJECT_NAME:?Set COMPOSE_PROJECT_NAME}"
: "${RISKLIVE_DATA_DIR:?Set RISKLIVE_DATA_DIR}"
: "${APP_IMAGE:?Set corrected immutable APP_IMAGE}"
: "${WEB_IMAGE:?Set corrected immutable WEB_IMAGE}"
: "${APP_ENV_FILE:?Set APP_ENV_FILE}"
: "${WEB_ENV_FILE:?Set WEB_ENV_FILE}"
: "${CADDY_ENV_FILE:?Set CADDY_ENV_FILE}"

[[ "$RISKLIVE_DATA_DIR" == "/opt/risklive/data" ]] || {
  echo "Refusing to run: RISKLIVE_DATA_DIR must be /opt/risklive/data" >&2
  exit 1
}

[[ -f "$verifier" ]] || {
  echo "Missing verifier: $verifier" >&2
  exit 1
}

docker image inspect "$APP_IMAGE" >/dev/null
docker image inspect "$WEB_IMAGE" >/dev/null

seca_runtime="$RISKLIVE_DATA_DIR/runtime/seca"
newsmap_root="$RISKLIVE_DATA_DIR/results/web/newsmap"
stream_db="$seca_runtime/stream.sqlite3"

[[ -f "$stream_db" ]] || {
  echo "Missing existing SECA database: $stream_db" >&2
  exit 1
}

backup="/opt/risklive/backups/seca-diagnostics-$(date -u +%Y%m%dT%H%M%SZ)"
compose=(docker compose -f "$compose_file")

echo "APP_IMAGE=$APP_IMAGE"
echo "WEB_IMAGE=$WEB_IMAGE"
echo "Backup destination: $backup"

echo "Stopping scheduler, app and web..."
"${compose[@]}" stop scheduler app web

echo "Backing up SECA state and outputs..."
sudo mkdir -p "$backup/output"
sudo cp -a "$seca_runtime" "$backup/runtime-seca"

for variant in 3d 7d 30d; do
  src="$newsmap_root/seca-light-$variant"
  if [[ -d "$src" ]]; then
    sudo cp -a "$src" "$backup/output/"
  fi
done

echo "Removing current SECA database from active state..."
sudo mv "$stream_db" "$backup/pre-diagnostics-stream.sqlite3"

for suffix in -wal -shm -journal; do
  sidecar="${stream_db}${suffix}"
  if [[ -f "$sidecar" ]]; then
    sudo mv "$sidecar" "$backup/"
  fi
done

echo "Running historical diagnostics rebootstrap..."
docker run --rm --pull never --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev \
  --mount "type=bind,src=$RISKLIVE_DATA_DIR/results,dst=/app/results" \
  --mount "type=bind,src=$RISKLIVE_DATA_DIR/runtime,dst=/app/runtime" \
  "$APP_IMAGE" \
  python -c 'from services.seca_timeline import run_seca_light_timeline; assert run_seca_light_timeline(timeout_seconds=3600, batch_id="diagnostics-rebootstrap-v2") is not None'

echo "Verifying regenerated diagnostics..."
docker run --rm -i --pull never --network none --read-only \
  --mount "type=bind,src=$RISKLIVE_DATA_DIR,dst=/data,readonly" \
  "$APP_IMAGE" \
  python - /data < "$verifier"

echo "Verification passed. Restarting services..."
"${compose[@]}" up -d --no-deps --no-build --pull never --wait app web scheduler

"${compose[@]}" ps

echo
echo "SECA diagnostics rebootstrap complete."
echo "Backup retained at: $backup"

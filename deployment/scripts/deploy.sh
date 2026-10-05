#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/deployment/compose/docker-compose.prod.yml"
: "${RISKLIVE_DATA_DIR:?Set an absolute persistent data root}"
: "${APP_ENV_FILE:?Set an absolute app env file path}"
: "${WEB_ENV_FILE:?Set an absolute web env file path}"
: "${CADDY_ENV_FILE:?Set an absolute Caddy env file path}"
: "${APP_IMAGE:?Set the prebuilt local app image tag}"
: "${WEB_IMAGE:?Set the prebuilt local web image tag}"
: "${COMPOSE_PROJECT_NAME:?Set the deployment project name}"
for variable in RISKLIVE_DATA_DIR APP_ENV_FILE WEB_ENV_FILE CADDY_ENV_FILE; do
  [[ "${!variable}" = /* ]] || { echo "$variable must be absolute" >&2; exit 1; }
done
for file in "$APP_ENV_FILE" "$WEB_ENV_FILE" "$CADDY_ENV_FILE"; do
  [[ -r "$file" && "$file" != *.example ]] || { echo "Missing deployment env file: $file" >&2; exit 1; }
  if grep -q 'replace_me' "$file"; then
    echo "Replace placeholder credentials in $file" >&2; exit 1
  fi
done
for directory in results logs runtime; do
  [[ -d "$RISKLIVE_DATA_DIR/$directory" ]] || { echo "Missing data directory: $directory" >&2; exit 1; }
done
export RISKLIVE_DATA_DIR APP_ENV_FILE WEB_ENV_FILE CADDY_ENV_FILE APP_IMAGE WEB_IMAGE COMPOSE_PROJECT_NAME
compose=(docker compose -f "$compose_file")
"${compose[@]}" config --quiet
# Local-image deployment: no implicit pulls, builds, or orphan deletion.
for image in "$APP_IMAGE" "$WEB_IMAGE" caddy:2.8.4-alpine; do
  docker image inspect "$image" >/dev/null
done
"${compose[@]}" run --rm --no-deps --pull never caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
"${compose[@]}" up -d --no-build --pull never --wait
"${compose[@]}" ps
echo "Deployment complete."

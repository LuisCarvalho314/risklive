#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export COMPOSE_PROJECT_NAME=risklive-dev
unset COMPOSE_PROFILES COMPOSE_FILE
export RISKLIVE_DATA_DIR="${RISKLIVE_DEV_DATA_DIR:-/opt/risklive/dev-data}"
[[ "$RISKLIVE_DATA_DIR" = /* && "$RISKLIVE_DATA_DIR" != / ]] || { echo 'Development root must be absolute' >&2; exit 1; }
[[ "$(realpath -m "$RISKLIVE_DATA_DIR")" = "$RISKLIVE_DATA_DIR" ]] || { echo 'Development root must be canonical without symlinks' >&2; exit 1; }
export APP_ENV_FILE="$RISKLIVE_DATA_DIR/env/app.env"
export WEB_ENV_FILE="$RISKLIVE_DATA_DIR/env/web.env"
export CADDY_ENV_FILE="$RISKLIVE_DATA_DIR/env/caddy.env"
export APP_IMAGE="risklive-dev-app:${RISKLIVE_DEV_IMAGE_TAG:-local}"
export WEB_IMAGE="risklive-dev-web:${RISKLIVE_DEV_IMAGE_TAG:-local}"
compose=(docker compose --project-name risklive-dev -f "$repo_root/deployment/compose/docker-compose.prod.yml" -f "$repo_root/deployment/compose/docker-compose.smoke.yml" -f "$repo_root/deployment/compose/docker-compose.dev.yml")
action="${1:-status}"
shift || true
if [[ "$action" = init ]]; then
  # Never initialize over an existing directory (including a production root).
  [[ ! -e "$RISKLIVE_DATA_DIR" ]] || { echo 'init requires a new development data directory' >&2; exit 1; }
  umask 077
  mkdir -p "$RISKLIVE_DATA_DIR"/{env,results,logs,runtime,caddy-data,caddy-config}
  cp "$repo_root/deployment/env/"{app,web,caddy}.env.example "$RISKLIVE_DATA_DIR/env/"
  for role in app web caddy; do mv "$RISKLIVE_DATA_DIR/env/$role.env.example" "$RISKLIVE_DATA_DIR/env/$role.env"; done
  sed -i -e 's/replace_me/offline/g' -e 's@https://replace-me.openai.azure.com/@https://disabled.invalid/@' -e 's/DISABLE_SCHEDULER=false/DISABLE_SCHEDULER=true/' "$APP_ENV_FILE"
  printf '\nRISKLIVE_EXTERNAL_APIS_ENABLED=false\nRISKLIVE_ENVIRONMENT=development\n' >> "$APP_ENV_FILE"
  cp "$APP_ENV_FILE" "$RISKLIVE_DATA_DIR/env/live.env"
  chmod 755 "$RISKLIVE_DATA_DIR" "$RISKLIVE_DATA_DIR/"{results,logs,runtime,caddy-data,caddy-config}
  touch "$RISKLIVE_DATA_DIR/.risklive-development"
  echo "Created $RISKLIVE_DATA_DIR. Set results/logs/runtime ownership to 10001:10001 before startup (see guide)."
  exit
fi
[[ -f "$RISKLIVE_DATA_DIR/.risklive-development" ]] || { echo 'Run init with a new isolated root first' >&2; exit 1; }
# Reject symlink escapes, unsafe mounts, project drift and network/port changes.
validate() {
  for file in "$APP_ENV_FILE" "$WEB_ENV_FILE" "$CADDY_ENV_FILE"; do
    [[ -f "$file" && "$(realpath -m "$file")" = "$file" ]] || { echo "Missing or symlinked development env file" >&2; return 1; }
  done
  "${compose[@]}" --profile '*' config --format json | python3 -I "$repo_root/deployment/scripts/validate-dev.py" "$RISKLIVE_DATA_DIR"
}
case "$action" in
  config) validate; "${compose[@]}" config ;;
  up|restart)
    validate
    extra=(); [[ "$action" != restart ]] || extra=(--force-recreate)
    "${compose[@]}" up -d --no-deps --no-build --pull never --wait "${extra[@]}" app web caddy ;;
  down) validate; "${compose[@]}" --profile '*' down ;;
  status) validate; "${compose[@]}" ps ;;
  logs) validate; "${compose[@]}" logs --tail 100 app web caddy ;;
  build)
    validate
    docker build -f "$repo_root/docker/Dockerfile.app" -t "$APP_IMAGE" "$repo_root"
    docker build -f "$repo_root/docker/Dockerfile.web" -t "$WEB_IMAGE" "$repo_root" ;;
  live-test)
    [[ "${1:-}" = --acknowledge-paid-api-calls && "$#" -ge 2 ]] || { echo 'Usage: dev.sh live-test --acknowledge-paid-api-calls COMMAND [ARGS...]' >&2; exit 1; }
    shift
    validate
    export RISKLIVE_DEV_LIVE_ENV_FILE="$RISKLIVE_DATA_DIR/env/live.env"
    [[ -f "$RISKLIVE_DEV_LIVE_ENV_FILE" && "$(realpath -m "$RISKLIVE_DEV_LIVE_ENV_FILE")" = "$RISKLIVE_DEV_LIVE_ENV_FILE" ]] || exit 1
    # Credential file is fixed to the development root; never inherit production env paths.
    live=("${compose[@]}" -f "$repo_root/deployment/compose/docker-compose.dev-live.yml")
    "${live[@]}" --profile '*' config --format json | python3 -I "$repo_root/deployment/scripts/validate-dev.py" "$RISKLIVE_DATA_DIR" --live
    # Foreground, no dependencies, no ports, no scheduler; offline serving stack unchanged.
    "${live[@]}" run --rm --no-deps --pull never app "$@" ;;
  *) echo 'Usage: dev.sh init|config|up|down|restart|status|logs|build|live-test' >&2; exit 1 ;;
esac

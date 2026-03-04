#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-deployment/compose/docker-compose.prod.yml}"

: "${APP_ENV_FILE:=/opt/risklive/data/env/app.env}"
: "${WEB_ENV_FILE:=/opt/risklive/data/env/web.env}"
: "${CADDY_ENV_FILE:=/opt/risklive/data/env/caddy.env}"

echo "Using compose file: ${COMPOSE_FILE}"

docker pull caddy:2.8-alpine

APP_ENV_FILE="${APP_ENV_FILE}" \
WEB_ENV_FILE="${WEB_ENV_FILE}" \
CADDY_ENV_FILE="${CADDY_ENV_FILE}" \
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans --pull never

docker compose -f "${COMPOSE_FILE}" ps

echo "Deployment complete."
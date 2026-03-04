#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-deployment/compose/docker-compose.prod.yml}"

echo "Using compose file: ${COMPOSE_FILE}"
docker pull caddy:2.8-alpine
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans --pull never
docker compose -f "${COMPOSE_FILE}" ps

echo "Deployment complete."
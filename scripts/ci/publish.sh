#!/usr/bin/env bash
set -euo pipefail
# Never invoked on PRs. Scanned local images are pushed without rebuilding.
[[ "$GITHUB_EVENT_NAME" == push && "$GITHUB_REPOSITORY" == LuisCarvalho314/risklive ]]
[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]
tag="sha-${GITHUB_SHA}-run${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
# Keep the ephemeral login outside the workspace and remove it even on failure.
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$GH_TOKEN" | docker login ghcr.io --username "$GITHUB_ACTOR" --password-stdin
for component in app web; do
  image="ghcr.io/luiscarvalho314/risklive-${component}"
  docker tag "risklive-${component}:ci" "${image}:${tag}"
  docker push "${image}:${tag}"
  docker image inspect "${image}:${tag}" --format '{{json .RepoDigests}}' > "${component}-digests.json"
done
python scripts/ci/candidate.py

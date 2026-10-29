# On-demand development on jarvis

Development reuses the production app/Gunicorn, Next.js and Caddy images and
configuration, with the unchanged smoke overlay plus a development overlay.
Production's release helper and port 8888 are unchanged. Development has fixed
project `risklive-dev`, port `127.0.0.1:8188`, separate project networks, and no
scheduler. Smoke remains disposable validation; development keeps its data across
stops and feature image rebuilds. Run only one development stack per VM.

## Setup and ordinary operation

Requires Docker access and Compose >= 2.24.4 (the `!override` merge tag). Work in
your isolated feature worktree. No command below deploys production. Initialize
the existing pinned submodule before building; do not update its revision:

```bash
git submodule update --init --checkout experimental
# The existing /opt/risklive parent stays unchanged. init requires a new root.
sudo ./deployment/scripts/dev.sh init
sudo chown -R "$USER:$(id -gn)" /opt/risklive/dev-data/env
sudo chown 10001:10001 /opt/risklive/dev-data/{results,logs,runtime}
./deployment/scripts/dev.sh config
./deployment/scripts/dev.sh build
# Caddy must already exist locally, or pull this pinned version explicitly:
docker pull caddy:2.8.4-alpine
./deployment/scripts/dev.sh up
./deployment/scripts/dev.sh status
./deployment/scripts/dev.sh logs
./deployment/scripts/dev.sh restart
./deployment/scripts/dev.sh down
```

Never change ownership of `/opt/risklive` or production data. Use `RISKLIVE_DEV_DATA_DIR=/absolute/new/path` on **every** command to
choose another root; symlink escapes are rejected. Env files are private, generated
from the existing examples, with dummy offline credentials. No production files
are read. `init` refuses existing roots. Keep the default root directory readable
for container traversal; `env` remains mode 0700 and files mode 0600.

`build` uses `risklive-dev-app:local` and `risklive-dev-web:local`, never production
tags. Set `RISKLIVE_DEV_IMAGE_TAG=my-feature` consistently on build/up/restart to
keep multiple development revisions. Builds can use significant CPU, memory and
disk despite runtime limits: schedule them with production load in mind. Runtime
limits are app 1 CPU/2 GiB, web 0.5 CPU/768 MiB and Caddy 0.25 CPU/128 MiB; ML work
may require deliberately adjusting them. No images are implicitly pulled at startup.

From your workstation:

```bash
ssh -N -L 8188:127.0.0.1:8188 jarvis
# Open http://localhost:8188; health is /health, dashboard is /topics.
```

App/web have no published ports and attach only to Docker's internal network.
Only Caddy has an edge bridge. Health routes and WSGI startup perform no ingestion,
enrichment or report generation. Trigger routes remain manual and fail at the
provider boundary while offline. The scheduler profile also has a failing
entrypoint, and Python refuses development job registration even during live tests.
`DISABLE_SCHEDULER` alone is insufficient for the dedicated scheduler.

## Offline fixtures

Existing archive tests exercise report/dashboard output with stored rows and
stubbed report responses; they do not claim to generate new LLM prose offline.
No cache framework is added. Run in the checkout with its locked Python environment:

```bash
uv sync --frozen
uv run --frozen --no-sync pytest -p no:cacheprovider --no-cov \
  tests/regression/test_regression_archived_report.py \
  tests/regression/test_regression_archived_dashboard.py \
  tests/deployment/test_dev_stack.py
python3 deployment/scripts/check-dev.py
(cd web && pnpm install --frozen-lockfile && pnpm typecheck && pnpm test)
```

The Python suite enforces no network/model loading. Its fixture stubs replace
provider work; setting the external API flag false is appropriate for serving,
but tests that explicitly exercise provider construction use fake clients instead.
Existing sanitized datasets may be copied **into development results** manually.
Local topic/model workflows may need pre-provisioned model assets; offline network
is deliberately unable to download them. Do not mount production data or secrets.

## Explicit live tests and costs

Edit only `/opt/risklive/dev-data/env/live.env` with separately authorised Azure
OpenAI and/or Valyu development credentials. Initially it contains dummy keys.
Use `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_API_VERSION`, and `VALYU_API_KEY`.
The helper always uses this fixed development file, not inherited production env
paths. Protect it and use provider-side development credentials/quotas.

```bash
# One Azure request, no pipeline or scheduler; logs usage and no prompt content.
./deployment/scripts/dev.sh live-test --acknowledge-paid-api-calls python -c \
  'import asyncio; from utils.logging import configure_logging; configure_logging(); from adapters.llm import build_model; from pydantic_ai import Agent; asyncio.run(Agent(build_model()).run("Reply OK"))'
# One Valyu search rather than the configured many-query fetch pipeline:
./deployment/scripts/dev.sh live-test --acknowledge-paid-api-calls python -c \
  'from utils.logging import configure_logging; configure_logging(); from adapters.valyu import fetch_news; fetch_news(["nuclear safety"], hours=1)'
# An intentional manual pipeline, after reviewing its inputs and call volume:
./deployment/scripts/dev.sh live-test --acknowledge-paid-api-calls risklive report
```

Live testing launches a foreground disposable app container with outbound networking,
no dependencies, no published ports and no scheduled work. It shares **development**
results/logs/runtime. It never reconfigures the offline serving containers. On command
exit it is removed; ordinary `up`/`restart` always enforce false. Interrupt with Ctrl-C
and check `status` if the client/daemon disconnects. Do not run background daemons
as a test command. The live bridge grants outbound connectivity, not a provider
allowlist; execute trusted, specific commands only.

Guards reject Azure model construction and requests (including streams), and Valyu
adapter calls before network activity when `RISKLIVE_EXTERNAL_APIS_ENABLED=false`.
Unset retains production behavior. Valyu Search is the only current Valyu call;
there are no Contents/DeepResearch clients in this revision. Future paid providers
must use the same boundary policy; the offline network also blocks indirect calls.
Development provider requests initialise existing persistent logging automatically. Request records include
provider, operation and logical request count; Azure completion records include
input/output tokens. SDK retries can incur additional wire requests. Valyu logs
reported source prices where available. No query/prompt or credentials are included
in the new audit records. Estimates, request counts and provider quotas are **not
guaranteed billing caps**. A full fetch/extract/report pipeline can issue many paid
calls; budgets and access control remain operator/provider responsibilities.

## Persistence, cleanup and runtime verification

All writable serving binds live under the validated development root: results,
logs, runtime (SQLite and future RAG state), caddy-data and caddy-config. Web sees
results/logs read-only. Keep future indexes within results/runtime. `down` removes
only this project's containers/networks without `-v`; no persistent bind data is
deleted. `restart` recreates serving containers with the same mounts.

Use `du -sh /opt/risklive/dev-data/*` and `docker system df` to inspect disk use.
Rotate/archive development logs and explicitly remove obsolete **development image
tags** only when unused. There is no automatic data cleanup and no global prune.
Back up development results/runtime before intentionally removing test datasets.

On jarvis, after static checks and image builds, verify runtime behavior:

```bash
./deployment/scripts/dev.sh up
curl -f http://127.0.0.1:8188/health
curl -f http://127.0.0.1:8188/topics
# Inspect only development resources; no scheduler should be running.
docker ps --filter label=com.docker.compose.project=risklive-dev
# Verify app cannot reach external HTTP; expected network failure:
docker exec "$(docker ps -q --filter label=com.docker.compose.project=risklive-dev --filter label=com.docker.compose.service=app)" \
  curl --connect-timeout 3 --max-time 5 https://example.com
# Write a harmless artifact, restart, and check persistence:
printf 'persistent test\n' | sudo tee /opt/risklive/dev-data/runtime/dev-persistence-check.txt
./deployment/scripts/dev.sh restart
cat /opt/risklive/dev-data/runtime/dev-persistence-check.txt
./deployment/scripts/dev.sh down
```

Inspect app/web network attachments, mounts and loopback binding with `docker
inspect` on the development container IDs. Also verify ownership, health, absence
of background jobs and existing SQLite/RAG/test artifacts across restart. Static
configuration tests cannot establish these runtime facts. Never run production
teardown, global prune, Docker daemon restart, or volume deletion for development.

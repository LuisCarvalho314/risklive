# Docker deployment

The only supported container deployment uses `docker/Dockerfile.app`,
`docker/Dockerfile.web`, `deployment/compose/docker-compose.prod.yml`, and
`deployment/caddy/Caddyfile.prod`. The old root Dockerfile/Compose files and
standalone ops Caddy config were removed: they targeted retired API/Streamlit
entrypoints or contained fixed credentials. Existing host services are not managed
by this deployment. Do not run cutover commands on a live VM until cutover is
explicitly authorized and its existing port bindings have been resolved.

Python is 3.11; uv 0.9.15 installs the frozen lock without the dev group.
The locked torch source is the CPU-only index. The app runs as UID/GID 10001.
The web image builds with pinned pnpm 10.30.3 and the frozen frontend lock, then
runs the standalone Next.js output as the Node user, without build dependencies.
The four services are `app` (Gunicorn), `scheduler` (foreground APScheduler),
`web` (Next.js), and `caddy` (edge proxy). App and scheduler use the same Python
image. Only Caddy publishes host ports. It proxies app routes using `app:5001` and
frontend/ops routes using `web:3000`.

## Recent changes and release status

The recent commits available in this checkout are:

| Commit | Change |
|---|---|
| `f14b049` | Production Docker images, persistent mounts, dedicated scheduler and deployment helper. |
| `6b2550b` | Preserve plain HTTP on host port 8888 and remove Caddy basic authentication. |
| `a97b653` | Bound experimental web inputs, coalesce concurrent loads and reduce ops CSV allocations. |

These are local commit references, not a verified remote push or CI-success record.
The latest SECA generator fix, 128 MiB request budget and compatibility-patch
header correction are working-tree changes at the time of this documentation
update. See [SECA hardening](seca-timeline-hardening.md) for measurements and the
reported image-build/scratch-regeneration status. Commit and push the intended
release changes and require CI success for that exact revision before production
promotion. Preserve the existing production Compose project name during updates.

## HTTP and scheduler lifecycle

The HTTP command is:

```bash
gunicorn app.wsgi:app --bind 0.0.0.0:5001 --workers 2 --timeout 0 --access-logfile - --error-logfile -
```

Gunicorn 23.0.0 is an explicit production dependency in `uv.lock`. Two workers
provide modest HTTP concurrency without multiplying the heavier Python runtime
unnecessarily. `--timeout 0` preserves existing synchronous manual pipeline
requests, which can exceed Gunicorn's default 30-second worker timeout. A manual
request occupies a worker until it completes. The `/` health route returns JSON status only and launches no work.
Operational pipeline dependencies are imported only when work is requested.

The scheduler command is `python -m app.scheduler`. It constructs exactly one
`BlockingScheduler`, registers jobs once through `app.scheduler_jobs.register_jobs`,
and blocks in `start()`. It constructs no Flask app, serves no HTTP, and exposes
no port. `src/app/schedules.json` is the canonical schedule for Python registrations
and the ops dashboard. It retains the existing host timings: `fetch_and_process`
daily at 06:20 and `cleanup_old_data` daily at 06:00 in **Europe/London**. Cron
triggers explicitly use that timezone. In BST these are 05:20/05:00 UTC; in GMT
06:20/06:00 UTC. The earlier container smoke used UTC defaults; that would have
shifted summer production timing. App/web image defaults and env examples now set
`TZ=Europe/London` for consistent local log timestamps. The dashboard calculates
next runs in the canonical timezone and advances calendar days across DST,
rather than adding a fixed 24 hours. Each has a stable job ID, `max_instances=1`, and `coalesce=True`. The fetch
job retains its dashboard export and SECA work; cleanup retains configured retention.
There is no eager run at process startup.

Run **only one scheduler container** per deployment/data root. Compose fixes its
replica count at one. An exclusive nonblocking Linux file lock on
`/app/runtime/scheduler.lock`, held for the full lifecycle, rejects duplicate owners
sharing that runtime mount before scheduler construction or job registration. Do not
scale schedulers or give duplicate owners separate runtime mounts. Gunicorn worker
count has no effect on scheduler count. This lock does not coordinate with the
legacy host scheduler: an authorized cutover must stop that owner before starting
the production scheduler container. The existing host deployment remains unchanged.

SIGTERM/SIGINT unwind the foreground loop and call `shutdown(wait=True)` before
releasing ownership; signal handlers are restored afterward. Compose allows five
minutes for in-flight work to finish before its forced termination deadline.

## Packaged SECA CLI

Initialize the repository's existing gitlink before building:

```bash
git submodule update --init --checkout experimental
```

`docker/Dockerfile.app` builds from pinned SECA commit
`a03e2ba3385d328a10eacbf584c57cddc6f40a62` with Rust 1.92.0 Bookworm, pinned by image digest.
Build inputs are checked against `docker/seca/SOURCE.sha256`. The parent-owned
`docker/seca/Cargo.lock` supplies the workspace lockfile; core and CLI tests/builds
use `--locked`. Only `/usr/local/bin/realtime-seca-cli` is copied into Python.
Cargo, rustc, target directories and sources are absent from the final image.

The Rust repository now includes `timeline-many` and the persistent `update`
command directly. The former Docker compatibility patch has been removed.
RiskLive converts one incoming batch and calls `update`, restoring the committed
schema-3 engine, evolving selected HKTs and pruning source memberships to gamma.
`config/seca_timeline.json` uses gamma=30 batches and branch threshold 10;
`RISKLIVE_SECA_GAMMA_BATCHES` overrides the former. One transactional database at
`/app/runtime/seca/stream.sqlite3` owns model state, receipts and snapshot history.
App and scheduler already share its runtime mount. See [SECA-Light state and
migration details](seca-light-stream.md) before changing model configuration.

Publication of this pinned Rust commit was attempted but blocked by shell DNS
and connector write permissions. Push the Rust branch before distributing a
parent checkout that needs to initialize that gitlink. No deployment was run.

CLI resolution is explicit `RISKLIVE_SECA_CLI`, then installed CLI on PATH,
then source release/debug binaries, then Cargo only with a source workspace.
The image sets `RISKLIVE_SECA_CLI=/usr/local/bin/realtime-seca-cli`. Standalone
execution uses absolute data/output paths and no source cwd; only the Cargo
fallback needs a workspace cwd. `/app/experimental` is not required at runtime.
The 30d/7d/3d directories select snapshot history by UTC generation day; they
are views of one model. Source retention is measured in successful batches.
Processing uses existing enriched CSVs and does not require fetching or LLM credits.

## Prepare a new deployment

Code and images are disposable. Persistent state belongs outside the checkout.
The following commands are for an explicitly authorized new deployment, **not**
for testing beside the current production instance. Never recursively change
ownership of `/opt/risklive` or an existing production data directory.

```bash
# Run only when provisioning a NEW, approved data root.
sudo install -d -o 10001 -g 10001 -m 0755 \
  /opt/risklive/data/results /opt/risklive/data/logs /opt/risklive/data/runtime
sudo install -d -o "$USER" -g "$(id -gn)" -m 0700 /opt/risklive/data/env
umask 077
cp deployment/env/app.env.example /opt/risklive/data/env/app.env
cp deployment/env/web.env.example /opt/risklive/data/env/web.env
cp deployment/env/caddy.env.example /opt/risklive/data/env/caddy.env
```

Set real credentials in the private app env file. Keep `HOST=0.0.0.0`,
`PORT=5001`. `DISABLE_SCHEDULER` controls only the legacy host/server entrypoint;
it has no role in container ownership. Gunicorn imports `app.wsgi:app`, which only
constructs the Flask application and never calls scheduler startup.
Keep web on port 3000. The web mounts results/logs read-only; app-created files
must remain readable by its UID 1000 (normally directory 0755/file 0644).

The current deployment uses `CADDY_SITE_ADDRESS=http://:80` and publishes
container port 80 on host port **8888**. The host binding is controlled by
`CADDY_HTTP_BIND`, whose default is `0.0.0.0:8888`. Caddy admin and app/web ports
are not published. HTTPS is not configured by the current deployment.

The current Caddyfile has **no basic authentication** and does not consume
`OPS_USER` or `OPS_PASSWORD_HASH`. Access follows the existing Azure/network
boundary; changing that policy is a separate deployment change. `/trigger/*`
routes proxy the app, while frontend/ops routes proxy the web container.
`/health` and `/healthz` proxy the app's existing `/` health response. Never
commit real env files. See [access configuration](ops-auth-caddy.md).

## CI gate before release

The repository's [CI workflow](../.github/workflows/ci.yml) runs on pull requests
and pushes to `main`, `develop` and `dev/**`. It runs the full isolated backend
suite, frontend type checks and unit tests, and a Next.js production build using
locked dependencies. Local checks supplement these checks; they do not establish
that a GitHub Actions run passed.

Before promotion, commit all required source, configuration, tests and documentation,
push the release branch, and verify both CI jobs passed for that exact commit.
Build versioned Docker images from the same revision. This workflow currently
does not build/publish Docker images or deploy production; those remain separate
steps. A previously built image from uncommitted changes is scratch validation
evidence, not a CI-verified release. Do not create a replacement deployment
pipeline without reviewing the existing release process.

## Build and deploy local images

Use the existing project name for an update, a unique project name for a new
deployment, and versioned image tags. Do not retag images used by current
production containers during development. Complete the CI gate above first.

```bash
export COMPOSE_PROJECT_NAME=risklive-prod
export RISKLIVE_DATA_DIR=/opt/risklive/data
export APP_ENV_FILE="$RISKLIVE_DATA_DIR/env/app.env"
export WEB_ENV_FILE="$RISKLIVE_DATA_DIR/env/web.env"
export CADDY_ENV_FILE="$RISKLIVE_DATA_DIR/env/caddy.env"
# Run from a clean checkout of the exact revision that passed CI.
test -z "$(git status --porcelain)"
export RELEASE_REV="$(git rev-parse --short=12 HEAD)"
export APP_IMAGE="risklive-app:$RELEASE_REV"
export WEB_IMAGE="risklive-web:$RELEASE_REV"

docker build -f docker/Dockerfile.app -t "$APP_IMAGE" .
docker build -f docker/Dockerfile.web -t "$WEB_IMAGE" .
docker pull caddy:2.8.4-alpine

docker compose -f deployment/compose/docker-compose.prod.yml config --quiet
./deployment/scripts/deploy.sh
```

The helper requires absolute, readable env paths, an explicit data root/project
and prebuilt images. It rejects example files and placeholder credentials,
validates Caddy in a one-off container, starts with `--no-build --pull never
--wait`, and prints status. It never deletes persistent data or unrelated
containers. Compose itself requires env/data variables and refuses to create
missing bind directories. `CADDY_HTTP_BIND` defaults to `0.0.0.0:8888`;
there is no HTTPS host binding in the current Compose file. App/web ports are
never published.

The helper starts **all services, including the fetching scheduler**. When API
credits are unavailable, keep that scheduler stopped and update only serving
containers after scratch regeneration and validation:

```bash
export SECA_COMPOSE=deployment/compose/docker-compose.prod.yml
docker compose -f "$SECA_COMPOSE" stop scheduler
docker compose -f "$SECA_COMPOSE" up -d \
  --no-deps --no-build --pull never --wait app web
```

This does not regenerate existing SECA artifacts. Follow the
[offline regeneration procedure](seca-timeline-hardening.md#safe-offline-regeneration-and-promotion)
to validate scratch outputs, quarantine old directories and promote complete
replacements. Keep the scheduler stopped until fetching/LLM credits are available.

Keep these exports for all day-to-day commands:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml ps
docker compose -f deployment/compose/docker-compose.prod.yml logs --tail 100
```

Back up results/logs/runtime/env and Caddy certificate storage (the project-scoped
`caddy_data` volume) before cutover or updates. Protect backups containing secrets.
For rollback, select previous versioned image tags and restore any quarantined
artifact directories while readers/writers are stopped. Use the serving-only
command above if the scheduler must remain stopped; otherwise use the helper.
Never use `down -v` to operate on production. Do not restore backups over live data
without an approved recovery plan.

## Isolated validation beside production

Requires an existing accessible Docker daemon and Compose >= 2.24.4. Do not
install/start/reconfigure a daemon on the production host as part of a smoke test.
Initial smoke validation must run only `app web caddy`. The scheduler is behind
the `scheduler-disabled-in-smoke` profile; never enable that profile, select the
scheduler service, or set `COMPOSE_PROFILES` during smoke validation. The explicit
service list plus `--no-deps` below prevents scheduler startup even if profiles
are set externally. Do not start any smoke containers until runtime testing is
authorized. Check port 8188 is free first. The override replaces the production binding
with one loopback HTTP binding and isolates Caddy storage. App, web and scheduler
attach only to the internal network, which blocks outbound traffic. Caddy also
attaches to a separate edge bridge so Docker can publish its loopback port;
publishing ports from an internal-only network does not work on this Docker host.

```bash
export COMPOSE_PROJECT_NAME=risklive-container-test
export RISKLIVE_DATA_DIR="$PWD/.container-test/data"
export APP_ENV_FILE="$RISKLIVE_DATA_DIR/env/app.env"
export WEB_ENV_FILE="$RISKLIVE_DATA_DIR/env/web.env"
export CADDY_ENV_FILE="$RISKLIVE_DATA_DIR/env/caddy.env"
export APP_IMAGE=risklive-app:dev
export WEB_IMAGE=risklive-web:dev
mkdir -p "$RISKLIVE_DATA_DIR"/{results,logs,runtime,env,caddy-data,caddy-config}
# Ownership applies ONLY to isolated development directories.
sudo chown 10001:10001 "$RISKLIVE_DATA_DIR"/{results,logs,runtime}
chmod 0755 "$RISKLIVE_DATA_DIR"/{results,logs,runtime}
umask 077
cp deployment/env/app.env.example "$APP_ENV_FILE"
cp deployment/env/web.env.example "$WEB_ENV_FILE"
cp deployment/env/caddy.env.example "$CADDY_ENV_FILE"
# Edit app.env: dummy keys, OPENAI_API_BASE=https://disabled.invalid/,
# DISABLE_SCHEDULER=true. Keep caddy.env: CADDY_SITE_ADDRESS=http://:80.
# No basic-auth variables are needed. Never use production secrets.
compose=(docker compose -f deployment/compose/docker-compose.prod.yml \
  -f deployment/compose/docker-compose.smoke.yml)
"${compose[@]}" config
# Check all data sources are under .container-test/data before proceeding.
docker build -f docker/Dockerfile.app -t "$APP_IMAGE" .
docker build -f docker/Dockerfile.web -t "$WEB_IMAGE" .
docker image inspect "$APP_IMAGE" "$WEB_IMAGE" --format '{{.RepoTags}} {{.Size}}'
# Pull Caddy explicitly if it is not already available; not done by deployment.
docker pull caddy:2.8.4-alpine
"${compose[@]}" run --rm --no-deps --pull never caddy \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
"${compose[@]}" up -d --no-build --pull never --no-deps --wait app web caddy
"${compose[@]}" ps
curl -i http://127.0.0.1:8188/topics
curl -i http://127.0.0.1:8188/health
curl -i http://127.0.0.1:8188/ops
curl -i http://127.0.0.1:8188/api/ops/overview
# The current proxy has no basic auth. NEVER invoke trigger routes as a smoke check.
"${compose[@]}" exec -T app sh -c \
  'id; test "$DISABLE_SCHEDULER" = true; for d in results logs runtime; do echo harmless > /app/$d/container-smoke.txt; done'
"${compose[@]}" exec -T web sh -c \
  'cat /app/results/container-smoke.txt; cat /app/logs/container-smoke.txt; test ! -w /app/results; test ! -w /app/logs'
"${compose[@]}" up -d --no-build --pull never --no-deps --force-recreate --wait app
"${compose[@]}" exec -T app cat /app/runtime/container-smoke.txt
# Inspect running mounts/network/ports and logs; check no scheduler/job starts.
"${compose[@]}" logs --tail 100
# Stop ONLY this uniquely named isolated stack when done; preserve its data.
"${compose[@]}" --profile '*' down
UV_CACHE_DIR=/tmp/risklive-uv-cache DISABLE_SCHEDULER=true \
  uv run --frozen --no-sync pytest -p no:cacheprovider --no-cov tests
(cd web && pnpm typecheck && pnpm test && NEXT_TELEMETRY_DISABLED=1 pnpm build)
```

A successful Next.js build or static config validation does not prove container
health, runtime permissions, proxy routing, or restart persistence. Those require
the running isolated stack. Initial smoke testing deliberately excludes the dedicated
scheduler; it validates HTTP serving without operational execution. Scheduler
runtime validation requires a separate explicitly authorized isolated exercise.

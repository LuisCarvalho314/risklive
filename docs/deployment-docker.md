# Docker Deployment (Single VPS)

This deployment layout is aligned with the current runtime:

- Python app/scheduler: `src/app/server.py`
- Next.js UI + ops pages: `web/`
- Edge proxy + ops auth: Caddy

This document recommends a **VM-friendly layout** where:

- the repo is cloned to `/opt/risklive/repo`
- persistent data lives outside the repo under `/opt/risklive/data`
- Docker Compose runs the full stack (`app`, `web`, `caddy`)
- logs are accessed with `docker compose logs`
- results/logs/runtime are accessed directly on the host

## Files

- App image: `docker/Dockerfile.app`
- Web image: `docker/Dockerfile.web`
- Compose stack: `deployment/compose/docker-compose.prod.yml`
- Caddy config: `deployment/caddy/Caddyfile.prod`
- Env templates: `deployment/env/*.env.example`
- Deploy helper: `deployment/scripts/deploy.sh`

## Recommended host layout on Ubuntu


/opt/risklive/
  repo/
  data/
    env/
      app.env
      web.env
      caddy.env
    results/
    logs/
    runtime/
  backups/


Recommended paths:

* Repo: `/opt/risklive/repo`
* App env: `/opt/risklive/data/env/app.env`
* Web env: `/opt/risklive/data/env/web.env`
* Caddy env: `/opt/risklive/data/env/caddy.env`
* Results: `/opt/risklive/data/results`
* Logs: `/opt/risklive/data/logs`
* Runtime files: `/opt/risklive/data/runtime`
* Backups: `/opt/risklive/backups`

## 1) Clone the repo and create host directories

```bash
sudo mkdir -p /opt/risklive
sudo chown -R $USER:$USER /opt/risklive

git clone <your-repo-url> /opt/risklive/repo

mkdir -p /opt/risklive/data/env
mkdir -p /opt/risklive/data/results
mkdir -p /opt/risklive/data/logs
mkdir -p /opt/risklive/data/runtime
mkdir -p /opt/risklive/backups
```

## 2) Prepare env files

Copy the example env files into the persistent host env directory:

```bash
cp /opt/risklive/repo/deployment/env/app.env.example /opt/risklive/data/env/app.env
cp /opt/risklive/repo/deployment/env/web.env.example /opt/risklive/data/env/web.env
cp /opt/risklive/repo/deployment/env/caddy.env.example /opt/risklive/data/env/caddy.env
```

Edit values in:

* `/opt/risklive/data/env/app.env` for application secrets such as Valyu/OpenAI keys
* `/opt/risklive/data/env/web.env` for web runtime configuration if needed
* `/opt/risklive/data/env/caddy.env` for `OPS_USER`, `CADDY_SITE_ADDRESS`, and related Caddy settings

Generate a password hash:

```bash
caddy hash-password --plaintext 'your-strong-password'
```

## Caddy auth note

For local testing, using the bcrypt hash directly in `deployment/caddy/Caddyfile.prod` is often the least error-prone option.

A working local HTTP-only example is:

```caddy
{
	auto_https off
}

http://localhost {
	encode gzip zstd

	@ops path /ops /ops/* /api/ops /api/ops/*
	basic_auth @ops bcrypt {
		{$OPS_USER:opsadmin} <bcrypt-hash>
	}

	@app path /trigger /trigger/* /health /healthz
	reverse_proxy @app app:5001

	reverse_proxy web:3000
}
```

For real VPS deployment with a domain, update the site address accordingly, for example:

```caddy
dashboard.example.com {
	...
}
```

## 3) Recommended compose path pattern on the VM

For a real VPS deployment, use **absolute host paths** for bind mounts.

Recommended bind mounts:

* `/opt/risklive/data/results:/app/results`
* `/opt/risklive/data/logs:/app/logs`
* `/opt/risklive/data/runtime:/app/runtime`

Recommended env file paths:

* `/opt/risklive/data/env/app.env`
* `/opt/risklive/data/env/web.env`
* `/opt/risklive/data/env/caddy.env`

If your current compose file still uses relative paths like `../../results`, update it for the VM or pass explicit env file variables when deploying.

## 4) Build images on the VM

Change into the repo:

```bash
cd /opt/risklive/repo
```

Build the app and web images:

```bash
docker build -f docker/Dockerfile.app -t risklive-app:latest .
docker build -f docker/Dockerfile.web -t risklive-web:latest .
```

Pull Caddy once if needed:

```bash
docker pull caddy:2.8-alpine
```

## 5) Validate configuration

```bash
cd /opt/risklive/repo

APP_ENV_FILE=/opt/risklive/data/env/app.env \
WEB_ENV_FILE=/opt/risklive/data/env/web.env \
CADDY_ENV_FILE=/opt/risklive/data/env/caddy.env \
docker compose -f deployment/compose/docker-compose.prod.yml config
```

## 6) Deploy

If your deploy helper is set up for local-image deployment, run:

```bash
cd /opt/risklive/repo
./deployment/scripts/deploy.sh
```

A safer explicit VM command is:

```bash
cd /opt/risklive/repo

APP_ENV_FILE=/opt/risklive/data/env/app.env \
WEB_ENV_FILE=/opt/risklive/data/env/web.env \
CADDY_ENV_FILE=/opt/risklive/data/env/caddy.env \
docker compose -f deployment/compose/docker-compose.prod.yml up -d --remove-orphans --pull never
```

Equivalent day-to-day commands:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml ps
docker compose -f deployment/compose/docker-compose.prod.yml logs -f
docker compose -f deployment/compose/docker-compose.prod.yml logs -f app
docker compose -f deployment/compose/docker-compose.prod.yml logs -f web
docker compose -f deployment/compose/docker-compose.prod.yml logs -f caddy
```

## 7) Verify

Check status:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml ps
```

Test the site:

```bash
curl -i http://<host>/
curl -i http://<host>/topics
curl -i http://<host>/alerts
curl -i http://<host>/newsmap
```

Test ops endpoints without credentials:

```bash
curl -i http://<host>/ops
curl -i http://<host>/api/ops/overview
```

Test ops endpoints with credentials:

```bash
curl -u opsadmin:<password> -i http://<host>/api/ops/overview
```

Follow logs:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml logs -f caddy web app
```

## Day-to-day operations

### Check container status

```bash
docker compose -f deployment/compose/docker-compose.prod.yml ps
```

### Follow logs

```bash
docker compose -f deployment/compose/docker-compose.prod.yml logs -f
```

### Restart one service

```bash
docker compose -f deployment/compose/docker-compose.prod.yml restart app
docker compose -f deployment/compose/docker-compose.prod.yml restart web
docker compose -f deployment/compose/docker-compose.prod.yml restart caddy
```

### Recreate Caddy after config changes

```bash
docker compose -f deployment/compose/docker-compose.prod.yml up -d --force-recreate caddy
```

### Stop the stack

```bash
docker compose -f deployment/compose/docker-compose.prod.yml down
```

## Where logs and outputs live

Container logs are accessed with Docker:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml logs -f app
docker compose -f deployment/compose/docker-compose.prod.yml logs -f web
docker compose -f deployment/compose/docker-compose.prod.yml logs -f caddy
```

Persistent output files are accessed directly on the host:

```bash
ls -R /opt/risklive/data/results
ls -R /opt/risklive/data/logs
ls -R /opt/risklive/data/runtime
```

Inside containers, these same host paths appear as:

* `/app/results`
* `/app/logs`
* `/app/runtime`

## Update workflow

Recommended update flow:

1. Back up persistent data
2. Pull latest code
3. Rebuild images
4. Re-run Compose
5. Verify status and logs

Example:

```bash
cd /opt/risklive/repo

timestamp=$(date +%Y%m%d-%H%M%S)
tar -czf /opt/risklive/backups/risklive-data-$timestamp.tar.gz \
  /opt/risklive/data/results \
  /opt/risklive/data/runtime \
  /opt/risklive/data/env

git pull

docker build -f docker/Dockerfile.app -t risklive-app:latest .
docker build -f docker/Dockerfile.web -t risklive-web:latest .

APP_ENV_FILE=/opt/risklive/data/env/app.env \
WEB_ENV_FILE=/opt/risklive/data/env/web.env \
CADDY_ENV_FILE=/opt/risklive/data/env/caddy.env \
docker compose -f deployment/compose/docker-compose.prod.yml up -d --remove-orphans --pull never

docker compose -f deployment/compose/docker-compose.prod.yml ps
docker compose -f deployment/compose/docker-compose.prod.yml logs --tail=100
```

## Backup workflow

Back up the persistent host data, not the containers.

Recommended backup targets:

* `/opt/risklive/data/results`
* `/opt/risklive/data/logs`
* `/opt/risklive/data/runtime`
* `/opt/risklive/data/env`

Create a backup:

```bash
timestamp=$(date +%Y%m%d-%H%M%S)
tar -czf /opt/risklive/backups/risklive-data-$timestamp.tar.gz \
  /opt/risklive/data/results \
  /opt/risklive/data/logs \
  /opt/risklive/data/runtime \
  /opt/risklive/data/env
```

List backups:

```bash
ls -lh /opt/risklive/backups
```

Restore a backup:

```bash
tar -xzf /opt/risklive/backups/risklive-data-YYYYMMDD-HHMMSS.tar.gz -C /
```

## Rollback

If a deploy is bad, the simplest rollback is usually:

1. Check out the previous known-good commit
2. Rebuild the images
3. Re-run Compose

Example:

```bash
cd /opt/risklive/repo
git log --oneline -n 5
git checkout <previous-good-commit>

docker build -f docker/Dockerfile.app -t risklive-app:latest .
docker build -f docker/Dockerfile.web -t risklive-web:latest .

APP_ENV_FILE=/opt/risklive/data/env/app.env \
WEB_ENV_FILE=/opt/risklive/data/env/web.env \
CADDY_ENV_FILE=/opt/risklive/data/env/caddy.env \
docker compose -f deployment/compose/docker-compose.prod.yml up -d --remove-orphans --pull never
```

If the issue is data-related, restore the previous backup tarball.

## Optional registry-based deployment

If you later move to registry-based deployments, tag and push the images:

```bash
docker tag risklive-app:latest <registry>/risklive-app:<tag>
docker tag risklive-web:latest <registry>/risklive-web:<tag>
docker push <registry>/risklive-app:<tag>
docker push <registry>/risklive-web:<tag>
```

Then set:

* `APP_IMAGE=<registry>/risklive-app:<tag>`
* `WEB_IMAGE=<registry>/risklive-web:<tag>`

and use a pull-based deploy flow.

## Notes

* Current app routes proxied to Python service include `/trigger*` and health paths
* Next.js handles frontend routes and `/api/ops/*`
* The root route may redirect to `/topics`
* `results`, `logs`, and `runtime` should be persisted on the host outside the repo
* For local testing, `http://localhost` or `http://localhost/topics` is appropriate
* For internet-facing deployments, use HTTPS with a real domain where possible
* Prefer absolute host paths on the VM rather than relative bind mounts


# Docker Deployment (Single VPS)

This deployment layout is aligned with the current runtime:

- Python app/scheduler: `src/app/server.py`
- Next.js UI + ops pages: `web/`
- Edge proxy + ops auth: Caddy

## Files

- App image: `docker/Dockerfile.app`
- Web image: `docker/Dockerfile.web`
- Compose stack: `deployment/compose/docker-compose.prod.yml`
- Caddy config: `deployment/caddy/Caddyfile.prod`
- Env templates: `deployment/env/*.env.example`
- Deploy helper: `deployment/scripts/deploy.sh`

## 1) Prepare env files

```bash
cp deployment/env/app.env.example deployment/env/app.env
cp deployment/env/web.env.example deployment/env/web.env
cp deployment/env/caddy.env.example deployment/env/caddy.env
```

Edit values in:

- `deployment/env/app.env` (Valyu/OpenAI secrets)
- `deployment/env/caddy.env` (`OPS_PASSWORD_HASH`, site address)

Generate password hash:

```bash
caddy hash-password --plaintext 'your-strong-password'
```

If you skip this step, Compose falls back to `*.env.example` files by default.
That is useful for local wiring checks but not for real production credentials.

## 2) Build and tag images

```bash
docker build -f docker/Dockerfile.app -t risklive-app:latest .
docker build -f docker/Dockerfile.web -t risklive-web:latest .
```

For registry releases, tag and push:

```bash
docker tag risklive-app:latest <registry>/risklive-app:<tag>
docker tag risklive-web:latest <registry>/risklive-web:<tag>
docker push <registry>/risklive-app:<tag>
docker push <registry>/risklive-web:<tag>
```

Then set:

- `APP_IMAGE=<registry>/risklive-app:<tag>`
- `WEB_IMAGE=<registry>/risklive-web:<tag>`

in shell environment before deploy.

## 3) Validate configuration

```bash
docker compose -f deployment/compose/docker-compose.prod.yml config
```

## 4) Deploy

```bash
./deployment/scripts/deploy.sh
```

Equivalent manual commands:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml pull
docker compose -f deployment/compose/docker-compose.prod.yml up -d --remove-orphans
docker compose -f deployment/compose/docker-compose.prod.yml ps
```

## 5) Verify

Without creds:

```bash
curl -i http://<host>/ops
curl -i http://<host>/api/ops/overview
```

With creds:

```bash
curl -u opsadmin:<password> -i http://<host>/api/ops/overview
```

Check logs:

```bash
docker compose -f deployment/compose/docker-compose.prod.yml logs -f caddy web app
```

## Rollback

1. Set previous `APP_IMAGE`/`WEB_IMAGE` tags.
2. Re-run deploy.

```bash
APP_IMAGE=<registry>/risklive-app:<old_tag> \
WEB_IMAGE=<registry>/risklive-web:<old_tag> \
./deployment/scripts/deploy.sh
```

## Notes

- Current app routes proxied to Python service: `/trigger*` and health paths.
- Next.js handles all frontend routes and `/api/ops/*`.
- `results/`, `logs/`, and `runtime/` are mounted from host for persistence.
- For internet-facing deployments, use HTTPS with a domain when possible.

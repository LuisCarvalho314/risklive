# Ops and trigger authentication

The canonical container proxy is `deployment/caddy/Caddyfile.prod`.
See [Docker deployment](deployment-docker.md) for configuration and validation.

Caddy requires `OPS_USER` and `OPS_PASSWORD_HASH` from the explicit Caddy env
file. Single-quote the bcrypt hash so Compose preserves its dollar signs.
Authentication protects `/ops`, `/ops/*`, `/api/ops`, `/api/ops/*`, `/trigger`,
and `/trigger/*`. Health and normal frontend routes are public.
Use a real domain in `CADDY_SITE_ADDRESS` for automatic HTTPS.
Never verify authentication by invoking an authenticated trigger endpoint.

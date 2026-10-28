# Ops and trigger access

The canonical container proxy is `deployment/caddy/Caddyfile.prod`.
See [Docker deployment](deployment-docker.md) for configuration and validation.

Commit `6b2550b` preserves the existing plain-HTTP deployment on host port
**8888** and removes Caddy basic authentication. The current template uses
`CADDY_SITE_ADDRESS=http://:80`; Compose maps that container port to
`${CADDY_HTTP_BIND:-0.0.0.0:8888}`. HTTPS is not configured by this stack.

`OPS_USER` and `OPS_PASSWORD_HASH` are not required or consumed by the current
Caddyfile. Access follows the existing Azure/network boundary. `/ops` and
`/api/ops/*` route to the frontend; `/trigger` and `/trigger/*` route to the app.
`/health` and `/healthz` proxy the app's health response.

Adding authentication or HTTPS is a separate reviewed deployment change, not
part of the SECA generator fix. Verify serving behavior using pages and health
routes; trigger endpoints start operational work and must not be used as access
checks while fetching/LLM credits are unavailable.

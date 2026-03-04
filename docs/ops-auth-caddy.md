# Ops Route Protection with Caddy (Option 1)

This runbook protects `"/ops"` and `"/api/ops/*"` with HTTP Basic Auth at the reverse proxy.

It does not require application auth code changes.

## 1) Generate a password hash

```bash
caddy hash-password --plaintext 'your-strong-password'
```

Copy the generated hash.

## 2) Apply Caddy config

Use [`deployment/caddy/Caddyfile.ops.example`](/Users/lcarv/PycharmProjects/risklive/deployment/caddy/Caddyfile.ops.example) as a template.

Update:
- Hostname (`dashboard.example.com`)
- Password hash (`REPLACE_WITH_CADDY_HASH`)
- Upstream port if needed (`127.0.0.1:3000`)

The matcher is intentionally limited to:
- `/ops`
- `/ops/*`
- `/api/ops/*`

All other routes remain unchanged.

## 3) Validate and reload

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 4) Verify behavior

Without credentials:

```bash
curl -i https://<your-host>/ops
curl -i https://<your-host>/api/ops/overview
```

Both should be blocked by auth (`401` or equivalent challenge).

With credentials:

```bash
curl -u opsadmin:<password> -i https://<your-host>/ops
curl -u opsadmin:<password> -i https://<your-host>/api/ops/overview
```

Both should succeed.

## Security notes

- Keep HTTPS enabled.
- Use a long random password.
- Rotate credentials periodically.
- Share ops credentials only with operators.

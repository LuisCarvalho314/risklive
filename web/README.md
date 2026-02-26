# Web Dashboard Testing

The `web/` app uses a layered test strategy:

- Unit/component/API tests: Vitest + React Testing Library
- End-to-end smoke: Playwright
- Runtime payload validation: `ajv` against `web/schema/dashboard.schema.json`

## Commands

- Unit tests: `pnpm test`
- Watch mode: `pnpm test:watch`
- E2E smoke: `pnpm test:smoke`
- All e2e: `pnpm test:e2e`
- Type check: `pnpm typecheck`

## Notes

- UI pages load dashboard data from `../results/web/dashboard.json` by default.
- You can override the dashboard source with `DASHBOARD_JSON_PATH` (used by e2e tests to avoid writing to `results/`).
- E2E smoke seeds a deterministic fixture payload before navigating pages.

## Ops Route Protection

For VPS deployments with Caddy, protect `"/ops"` and `"/api/ops/*"` at the proxy layer:

- Config template: [`deployment/caddy/Caddyfile.ops.example`](/Users/lcarv/PycharmProjects/risklive/deployment/caddy/Caddyfile.ops.example)
- Runbook: [`docs/ops-auth-caddy.md`](/Users/lcarv/PycharmProjects/risklive/docs/ops-auth-caddy.md)

## Ops Dashboard

- UI route: `/ops`
- API routes:
  - `/api/ops/overview`
  - `/api/ops/artifacts`
  - `/api/ops/logs`

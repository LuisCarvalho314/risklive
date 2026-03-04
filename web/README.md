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
- Experimental Newsmap timeline route: `/newsmap-experimental`.
- Experimental timeline loader order:
  1. SECA static timeline files under:
  - `../results/web/newsmap/seca-light-30d/` (rolling 30-day)
  - `../results/web/newsmap/seca-light-7d/` (rolling 7-day)
  each with `manifest.json` or `timeline_manifest.json` + `tree_batch_*.json`
  2. CSV fallback read-only from:
  - `../results/backup_data/news_data.csv`
  - `../results/data/news_data.csv`
- In SECA mode, `/newsmap-experimental` preserves native HKT parent-node structure (no synthetic category flattening).
- One batch equals one UTC day of input rows. `/newsmap-experimental` shows a local selector for `30 days` and `7 days` when both SECA timelines are available.
- If SECA timelines are missing/invalid, the experimental page falls back to `dashboard.newsmap`.

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

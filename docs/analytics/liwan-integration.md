# RiskLive Liwan integration

Implementation only. **Production deployment and tracking activation are not
approved.** Both `LIWAN_ENABLED` flags default to false. The optional Compose
`analytics` profile is off. No production command below was executed.

The [original feasibility report](liwan-feasibility.md),
[synthetic POC evidence](liwan-poc-evidence.json) and
[POC runner](../../tools/analytics/liwan_poc.py) are preserved as historical
assessment artifacts. Their NO-GO decision for separate article event names was
resolved by explicit approval of shared `article_opened` events. Their references
to the old GoatCounter test are historical; use `test_liwan.py` now. The previous
inactive GoatCounter tracker/service wiring has been superseded. This change does
not touch the Flask analytics API, its models or its SQLite storage.

## Architecture and files

| Files | Responsibility |
|---|---|
| `deployment/compose/docker-compose.prod.yml` | Optional Liwan 1.8.1, pinned multi-platform digest; its own `liwan_data` volume, internal analytics network, no app mounts. Native admin bound to host **127.0.0.1:9042 only**. App/web/scheduler do not depend on Liwan. |
| `deployment/liwan/config.toml` | NTP/favicons disabled, no MaxMind/external auth, 512 MiB DuckDB memory limit and two threads. Proxy trust is restricted by the dedicated network boundary. |
| `deployment/liwan/collection-settings.json` | Proposed 730-day event retention, daily network-prefix grouping, no geo, UTM or sessions. Apply privately before activation; these are database settings, not automatically imported by the service. |
| `deployment/caddy/Caddyfile.prod` | Only exact POST `/analytics/event`, with no query string and a 16 KiB body limit, can proxy to Liwan when explicitly enabled. Rewrites to its `/api/event`; no dashboard, batch API, script, export or login paths are exposed. Cookies, auth, referrer and language are stripped; User-Agent is replaced with a constant. |
| `deployment/env/{web,caddy}.env.example` | Separate default-off flags and client collection categories. No build-time public activation flags. |
| `web/lib/analytics/{config,events,send}.ts` | Environment gate, approved-route/event/property schemas, opt-out, category switches and official SDK calls. The SDK's payload hook reconstructs an exact allowlisted payload. |
| `web/lib/analytics/article-id.mjs` and declarations | Shared, versioned URL normalization and full SHA-256 article identity. Pure JS hashing also works without browser Web Crypto. |
| `web/components/analytics/{provider,article-link}.tsx` | App Router committed-path tracking, Strict Mode deduplication, article click-throughs (including middle-click) and browser opt-out. |
| `web/app/layout.tsx` | Runtime server configuration and a global no-referrer policy. Request-time rendering keeps flags out of build-time configuration; pages are request-rendered as a tradeoff. |
| Alerts, Topics and Newsmap components | Deliberate actions only; no hover, keystroke, mouse movement or content capture. Canvas source double-clicks use the same article helper as links. |
| `web/app/privacy/page.tsx`, topbar | Privacy notice and discoverable browser opt-out; neither privacy nor ops routes count. Contact/final policy still require approval before activation. |
| `web/package.json`, lockfile | Official `@liwan.dev/tracker` **1.8.0**, shipped with validated server 1.8.1; `@noble/hashes` 2.0.1 for SHA-256. No external script/CDN at runtime. |
| `web/scripts/article-map.mjs` | Offline local reverse mapping from article IDs to existing source metadata. Never part of Liwan, a public route or a reporting backend. |
| `tools/analytics/liwan_admin.py` | Loopback-only client for built-in configuration/prune API. Interactive credentials or private scheduler environment; no aggregation. |
| `web/tests/unit/liwan.test.tsx`, `tests/deployment/test_liwan.py` | Schema, identity, route, navigation, opt-out, runtime/category, Compose and real Caddy routing tests. |
| `tools/analytics/liwan_integration.py`, `web/scripts/liwan-browser-test.mjs` | Disposable built-app/official-SDK/Caddy/Liwan/browser acceptance test with synthetic data and no production dependency. |
| `web/playwright.config.ts`, `web/vitest.config.ts` | Ordinary browser tests explicitly disable analytics. Vitest retains test mode without a hard-coded environment replacement, enabling production-gate unit tests. |

Liwan uses DuckDB for events and embedded SQLite for accounts/configuration. Both
files belong to its own volume. No PostgreSQL, Redis, new public listener or
custom event ingestion/aggregation/reporting backend is added. Administration uses
Liwan's native local authentication over an approved SSH tunnel or existing VPN.
Loopback publishing is a proposed deployment change; it has not been applied.

## Event taxonomy and interpretation

| Event | Exact properties | Trigger |
|---|---|---|
| `pageview` | none | Committed navigation to `/topics`, `/alerts`, `/newsmap`, `/newsmap-experimental` |
| `article_opened` | `article_id`, `section`, `risk_level` | Article outbound link or standard Newsmap source double-click |
| `topic_selected` | fixed `section=topics` | Topic selection changes |
| `topic_filter_used` | fixed `section=topics` | Changed filter committed by Enter or blur; no query text |
| `alert_filter_changed` | fixed `section=alerts`, `severity=all/red/yellow` | Severity changes |
| `newsmap_node_selected` | fixed section, enumerated `node_type`, bounded integer `depth` | Deliberate node click; depth is relative to the current displayed hierarchy root |
| `newsmap_view_changed` | fixed section, enumerated `mode` | Layout, experimental metric/direction or timeline-window changes |

Article sections are exactly `alerts`, `newsmap`, `newsmap-experimental`. Risk is
`red`, `yellow`, or `unknown`; it is never inferred from a parent node or an
unrelated alert. Experimental references without an article-specific risk flag
are unknown. Counts measure observed click-through actions, not confirmed
publisher reads or impression-normalized engagement rates. Link context-menu
commands cannot be reliably observed; normal and middle-clicks are covered.

The SDK is bundled and manually invoked; automatic `trackPageviews()` and exit
signals are not enabled. Consecutive identical pathname notifications and Strict
Mode replay count once; A→B→A counts a return visit. Query/hash-only changes do
not count. A pending send is dropped if navigation moved to a different route
before SDK loading completes. Delivery is best-effort, without retries.

## Article identity and local mapping

All components use `url-v1-<64 lowercase hex SHA-256 digits>`, derived from a
normalized article URL, never a topic/leaf/category/index ID. URL parsing
canonicalizes host/default port, removes fragments and known `utm_*`, `fbclid`,
`gclid`, `msclkid` parameters, and sorts remaining query keys. Other queries and
path case remain because they can identify different articles. URLs with embedded
credentials or non-HTTP(S) schemes are rejected. The scheme and trailing slash
remain significant; no publisher redirects are fetched or guessed.

Consequently identical normalized URLs match across sections. Publisher aliases,
HTTP/HTTPS variants and unrelated canonical URL aliases need an upstream canonical
identifier/mapping if they must be merged; silently conflating them would produce
incorrect counts. Changing the normalization rules requires a new version prefix
and an explicit migration decision.

Existing RiskLive dashboard/source JSON remains the metadata source. Produce a
private local mapping when investigating article counts:

```bash
cd web
umask 077
node scripts/article-map.mjs /absolute/path/to/dashboard.json > /private/path/article-map.json
```

Supply additional existing JSON files when needed for experimental sources. This
mapping contains publisher URLs and must never be uploaded to Liwan, placed in
`web/public`, committed, or served through the public proxy. Hashes are opaque
labels, not encryption of the source URLs.

## Privacy and runtime controls

Set web runtime `LIWAN_ENABLED=true` only after approval; set Caddy's independent
flag true only when the service/settings are ready. Missing flags leave collection
off. Web `LIWAN_PAGEVIEWS`, `LIWAN_ARTICLES`, `LIWAN_FEATURES` independently disable
those categories when set to `false`. The global flag still controls all three.
`ANALYTICS_TEST_MODE=true` disables production-server collection for automated
tests; non-production builds and `navigator.webdriver` are also rejected.

The SDK hook transmits only `name`, `entity_id`, an approved RiskLive origin/path
without query/hash, and the exact properties above. It drops global SDK property
defaults, referrer, screen metadata, orientation and attribution. The article URL
is used only to calculate an ID locally. No titles, search terms, article text,
visitor IDs or arbitrary property names are added. Caddy strips the browser's
HTTP metadata before forwarding; its fixed User-Agent preserves ingest parsing
without persisting the real browser family in Liwan. The browser may send
same-origin cookies to Caddy using the official SDK transport; Caddy removes them
before Liwan and does not enable access logging in this template.

An erratum to the historical feasibility report: the pinned official tracker does
honour the `disable-liwan` localStorage preference. RiskLive's visible control
uses that same preference and additionally checks it before importing/sending.
Unavailable preference storage fails closed. Opt-out blocks future requests,
including from other tabs on their next send; it does not erase previous records
or cause deployment flags to enable. Preference storage is not a visitor ID.

Liwan processes IP metadata for network-prefix grouping and rate limiting. It
stores group hashes, not raw IP/User-Agent event columns. Daily network groups do
not identify people and do not yield reliable monthly unique-person totals. Its
fixed ingress User-Agent and geo/session/UTM settings reduce collection; this is
not a claim about every host/proxy log or dependency path. Configure log access
and retention separately. The dedicated internal Docker network blocks server
internet egress; NTP/favicons are disabled and no GeoIP credentials, external SSO,
custom head HTML or third-party assets should be configured.

Replacing User-Agent also reduces server-side browser/bot classification; the
frontend automation gates remain necessary. The public tracking endpoint is unauthenticated by design. Its body limit and
frontend schema do not validate hostile callers' JSON or guarantee authentic
usage. Attackers can fabricate events/properties for known entities. Restrict
Liwan entity allowed hostnames, monitor abuse and review edge rate limits before
activation. Do not add a secret to browser JavaScript or claim that UI category
switches enforce a server-side schema.

## Built-in reporting

Through private administration, open the RiskLive project and select the
`article_opened` event. In Properties choose `article_id`, select the full date
range and Views; the existing dashboard sorts counts, so its first 20 rows are
the combined top articles. Filter `section` to compare Alerts and either Newsmap;
choose `risk_level` for the risk breakdown. Select an article property filter and
monthly graph interval for historical engagement. The Events card compares
feature-event completions. No RiskLive custom dashboard or SQL aggregation is
needed.

Authenticated JSON equivalents are Liwan's existing dashboard endpoints:
`POST /api/dashboard/project/risklive/dimension`, `/graph` and `/custom-events`.
For an article breakdown, send `dimension: "property"`, `propertyKey:
"article_id"`, `event: "article_opened"`, `metric: "views"`, `range` and `filters`.
Property filters use `{dimension:"property", key:"section", filterType:"equal",
value:"newsmap"}`. Read APIs currently need login-session authentication; API
keys are for batch ingestion, not private reporting. These endpoints are private
and version-sensitive. The retained original POC covers 24-month reports.

## Local validation

```bash
cd web
pnpm install --frozen-lockfile
pnpm test
pnpm exec tsc --noEmit --incremental false
pnpm build
cd ..
CADDY_BINARY=/path/to/caddy-2.8.4 python3 tests/deployment/test_liwan.py
# Install Chromium into a disposable location when needed:
cd web
PLAYWRIGHT_BROWSERS_PATH=/tmp/risklive-playwright pnpm exec playwright install chromium
cd ..
PLAYWRIGHT_BROWSERS_PATH=/tmp/risklive-playwright python3 tools/analytics/liwan_integration.py \
  --binary /path/to/official/liwan-1.8.1 \
  --caddy /path/to/caddy-2.8.4 \
  --output /tmp/liwan-integration-evidence.json
```

No containers or production services are used by these tests. The integration
runner copies the standalone build, creates synthetic results in /tmp, starts
loopback-only processes and stops/removes them. Browser requests to a synthetic
hostname are forwarded only to the disposable local Caddy. External source
navigation is fulfilled with synthetic text. Only the positive synthetic browser
context masks WebDriver; a separate normal automated context verifies exclusion.
No application bypass for automated tracking is introduced. The experimental source-list double-click handler is dispatched as a DOM event
in the browser test because its existing hover tooltip can intercept a second
simulated pointer click. Standard Newsmap uses a physical double-click. A second runtime
server with tracking disabled verifies zero transmissions.

On the development VM Chromium needed libgbm/libwayland, downloaded/extracted
under /tmp without installing or changing system libraries. Supply an appropriate
`LD_LIBRARY_PATH` in that environment; on a supported CI image use its installed
browser dependencies. No OS package installation is part of production activation.

## Recorded validation result

The [integration evidence](liwan-integration-evidence.json) records the actual
browser payloads and built-in Liwan report responses. The same UI-tested article
has three live synthetic clicks (one per section) plus 25 historical synthetic
clicks, giving a combined count of **28**. The 25-ID dataset yields a top-20
selection, section totals Alerts=170, Newsmap=157, experimental=1, and risk totals
red=171, yellow=156, unknown=1. Its Newsmap-only article count is 13. Monthly
article counts cover the synthetic history and current clicks; the preserved POC
separately verifies a full 24-month history.

Validation passed: **114 frontend tests**, TypeScript, the production build,
Compose rendering/isolation and Caddy 2.8.4 routing tests. The real-browser test
verifies all four routes, shared identity, payload fields, opt-out, ops exclusion,
a disabled production server, automation exclusion and public admin denials.
Existing experimental treemap tests still emit React `act(...)` warnings.

## Proposed retention, pruning and backups

The proposed **730 days retains event records**, not only precomputed aggregates.
Liwan calculates aggregates from those records. It does not automatically prune
just because a limit is configured. Backups are proposed to expire after 30 days,
subject to the existing infrastructure policy. Deletions can therefore remain in
old backups until those expire. Neither schedule is installed by this change.

The helper uses Liwan's existing authenticated API and restricts its URL to
loopback. For manual use over an approved tunnel, it prompts for credentials:

```bash
python3 tools/analytics/liwan_admin.py configure
python3 tools/analytics/liwan_admin.py prune          # dry run
python3 tools/analytics/liwan_admin.py prune --apply  # deletes expired events
```

After infrastructure approval, have the existing scheduler run the final command
daily on the host. Supply `LIWAN_ADMIN_USERNAME` and `LIWAN_ADMIN_PASSWORD` through
a restricted secret/environment file (not argv or committed configuration), log
only the returned counts and alert on failure. Native prune needs administrator
privileges; review credential ownership/rotation. Do not run the offline CLI
against the active DuckDB writer. The retained POC verified dry-run and deletion
of one expired synthetic event.

A verified backup procedure requires an authorized Liwan-only maintenance window:

1. Disable public ingestion and apply that Caddy change first; avoid accepting
   events while taking a cold backup. Do not interrupt app/web/scheduler.
2. Gracefully stop only Liwan (Compose gives 60 seconds for drain/checkpoint).
3. Copy the stopped container's **entire `/data` directory** to a protected,
   dated backup directory. `docker compose ... cp liwan:/data/. BACKUP_DIR` works
   without installing a shell in the distroless image. Include both
   `liwan-app.sqlite` and `liwan-events.duckdb` and any sidecar files.
4. Restart only Liwan, verify private login and counts, then restore the approved
   ingestion state. Never run `down -v` or overwrite the existing app data root.
5. Use the existing backup system to encrypt/restrict backups and enforce the
   separately approved 30-day expiry; verify successful copies and restore drills.

Restore first into a new isolated volume/container on a loopback-only listener,
using the same pinned image and UID 1000 ownership. Copy the whole backup into
that stopped volume/container, then start it, authenticate, and verify settings,
project access, article rankings and counts. Run a prune dry-run and apply the
current approved retention policy before promotion. Restoring SQLite also
restores accounts, sessions and salts; review credential/session rotation.
Image rollback alone cannot undo a storage/schema migration. The preserved POC
successfully cold-copied both databases and queried 8,700 restored article events.

## Exact future production activation sequence — NOT executed or approved

Use the existing deployment project/env variables documented in
[Docker deployment](../deployment-docker.md), on the exact CI-approved release.
Do not deploy this feature branch directly. Only after explicit production
approval:

1. Approve the final privacy notice/contact, 730-day event policy, 30-day backup
   policy, grouping/log treatment, private access, TLS and prune schedule. Confirm
   host loopback port 9042 is unused; choose `LIWAN_ADMIN_PORT` otherwise. Ensure
   existing Azure/firewall rules never publish it. No new public ports are needed.
2. Build/version the web image from the approved commit using the existing
   deployment process. Keep `LIWAN_ENABLED=false` in both private web and Caddy
   env files. Keep `ANALYTICS_TEST_MODE=true` for test servers.
3. Render and review configuration without starting services:

   ```bash
   docker compose -f deployment/compose/docker-compose.prod.yml --profile analytics config
   ```

4. Start **only** the optional service after its provisioning is approved:

   ```bash
   docker compose -f deployment/compose/docker-compose.prod.yml --profile analytics up -d --no-deps liwan
   ```

5. Establish the approved tunnel from an operator workstation:

   ```bash
   ssh -N -L 9042:127.0.0.1:9042 OPERATOR@APPROVED_VM
   ```

   Browse `http://localhost:9042` through the encrypted tunnel. Retrieve the
   onboarding token privately from Liwan's logs, create a native administrator,
   and create a **private** `risklive` project and `risklive` entity linked to it.
   Do not use public/unlisted visibility. Protect logs/bootstrap links. If using
   another admin port, make the tunnel/browser match `LIWAN_BASE_URL`.
6. Apply the proposed collection settings with `liwan_admin.py configure`, review
   entity overrides/allowed hostnames in the private UI, verify NTP/favicons are
   disabled and no external auth/GeoIP providers are configured. Prove private
   reports are inaccessible anonymously. Establish pruning and backups.
7. Update only the web service to the approved image while tracking is still off:

   ```bash
   docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps web
   ```

   Follow the existing deployment health/rollback procedure. Do not restart the
   app or scheduler, run triggers or change their mounts.
8. After separate **collection activation** approval, set private web runtime
   `LIWAN_ENABLED=true`, choose the three category switches and set
   `ANALYTICS_TEST_MODE=false`. Recreate only web with the previous command.
   Caddy remains disabled during this step.
9. Set private Caddy env `LIWAN_ENABLED=true` and apply through the existing
   authorized Caddy update procedure. Because env substitution occurs at Caddy
   startup and Docker env-file changes require recreation, the explicit command
   for this Compose deployment is:

   ```bash
   docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps --force-recreate caddy
   ```

   This is a production edge restart and requires its own change-window approval.
   This task did not run it. Preserve the existing public bind and site address;
   do not introduce TLS or firewall changes without their separate approvals.
10. Verify one approved pageview and source click, the combined report, opt-out,
    ops exclusion and public admin denials. Never use operational trigger routes
    as analytics/access checks. Record the activation time and approved settings.

For rollback, set Caddy's flag false and apply its authorized recreation first,
then disable web and apply its recreation. This blocks stale enabled clients at
the public boundary. Optionally stop only Liwan in a separate approved step;
preserve its volume and backups. No Flask/SQLite rollback is needed.

# Liwan feasibility and article-analytics proof of concept

Assessment date: 2026-10-27. Branch: `feat/liwan-feasibility`.

**NO-GO for integration with the exact requested event taxonomy.** Liwan 1.8.1
can analyse custom properties, but its property rankings and graphs accept one
event name per report. It cannot produce a combined top-20 article ranking across
`alert_source_opened` and `newsmap_source_opened` using its existing dashboard or
report API. Do not build a custom union/aggregation/reporting service to fill this
gap. A separate control using one `article_opened` event passes, so a small,
explicitly approved taxonomy change would make Liwan a viable candidate.

No RiskLive integration, production deployment, restart, authentication, TLS,
firewall or port changes were made. Existing Flask/SQLite analytics and the
previous disabled GoatCounter work were preserved. Only this report, synthetic
API evidence and a standalone proof-of-concept runner were added. Approval of a
revised taxonomy and the privacy/operations decisions below is required before
implementation.

## Version and evidence

- Latest release from the GitHub releases API: `liwan-v1.8.1`, published
  2026-10-23T12:58:29Z, source
  `f9e1a1fcc1a98b81c8b178d5fe8396bca536c1e6`.
- Current main inspected independently:
  `7b44be3c258aa3c3b5f25d6a6197239442b84c2f`, dated 2026-10-26.
  Main also has single-event report selection; it does not remove the blocker.
- Official Linux x86_64 release archive SHA-256, verified against GitHub's asset
  digest: `51ec2d5ef4ba46e72d7797c740114a3a20e708bb1c50d4aa57018054f03205ed`.
- Official image exists for amd64 and arm64:
  `ghcr.io/explodingcamera/liwan:1.8.1@sha256:ed1eb1f7a208ab8e43648b86d22735513dfedd2fdc60ba4aae7cddd4468c6f2e`.
  Manifest inspected; no container was created or image installed in production.
- The actual POC used the official standalone release binary, which the official
  container workflow packages unchanged. No source build or patched Liwan was used.
- [Raw requests and responses](liwan-poc-evidence.json) include report results,
  negative API tests, settings, explicit retention pruning, cold restore and
  outbound-connect observations. No passwords, session cookies or API keys are
  retained in the evidence.
- [Reproducible runner](../../tools/analytics/liwan_poc.py) uses only Python's
  standard library, synthetic records and Liwan's built-in HTTP APIs. It is a
  disposable acceptance test, not a RiskLive analytics pipeline or reporting layer.

## Phase 1: verified capabilities

| Requirement | Assessment | Evidence and limits |
|---|---|---|
| Self-contained Docker service without PostgreSQL/Redis | PASS | Official Containerfile packages one non-root binary (UID 1000). POC created `liwan-events.duckdb` and `liwan-app.sqlite`: events use DuckDB; accounts/config use embedded SQLite. Both are Liwan-owned, separate from RiskLive SQLite. |
| Page views and approximate unique visits | PASS, with qualifications | 288 synthetic pageviews and two distinct visitor groups returned from the stats API. Network-prefix modes and daily rotating salts are implemented. These are group counts, not identified people or reliable monthly unique-person counts. |
| Custom events and structured properties | PASS for flat properties | Strings, numbers and booleans are accepted; values are coerced to strings. Nested objects/arrays are rejected. Release limits: 30 properties, 64-character keys, 255-character values. No built-in arbitrary numeric sum/average over property values. |
| Filter/group/count properties in existing dashboard | PASS for one event name | Dashboard Properties drilldown and property filters invoke built-in dimension reports. API returned exact expected article, section and risk counts, including two simultaneous property filters. Cross-event ranking FAILS; see Phase 2. |
| Programmatic reports or exports | PASS for programmatic queries; no verified built-in CSV export | Authenticated dashboard POST endpoints return JSON. Login-session authentication works. API keys currently permit batch ingestion only: a key without a login session received 404 for a private report. Do not promise a versioned read API, API-key report export or scheduled CSV exports. |
| Configurable data collection | PARTIAL | Global/entity controls cover grouping, geo detail, UTM, session metrics, retention and drop rules. Referrer and parsed browser/device fields have no independent server-side collection toggle; hiding dashboard dimensions does not stop storage. A future integration must remove referrer in the SDK payload AND HTTP header, and suppress/fix User-Agent at trusted ingress to avoid storing real browser families. |
| External runtime requests can be avoided | PASS in the tested server configuration, with scope limits | Disable NTP and external favicons, omit MaxMind credentials and external auth providers. Final traced server run showed no outbound `connect()` calls. Default NTP behavior did make a UDP connection in an earlier probe. Favicon behavior was verified in source, not a browser network capture. |
| Retention and backups | PARTIAL operationally; mechanisms PASS | Settings accept 730 days. An expired synthetic event remained queryable until explicit prune; dry-run and actual prune each identified/deleted exactly one event. A graceful stop, cold copy of BOTH databases and restart from the copies restored all 8,700 control article events. No built-in recurring pruning/backup schedule or backup expiry was found. |
| Licensing and maintenance | Technically suitable, subject to institutional review | Apache-2.0 license and NOTICE in source. Releases 1.8.0 (2026-10-17), 1.8.1 (2026-10-23), and main activity on 2026-10-26 indicate current maintenance. Custom properties/events are recent additions, so pin versions and rerun this acceptance test before upgrades. No operational SLA is established. |

The observed retention limit is event retention, not an aggregate roll-up store.
Liwan retains event records to compute aggregates on demand; it does not provide a
verified way to delete detailed events after a short period while keeping only
24-month aggregate statistics. A 730-day policy means event rows and their
properties can remain for approximately 24 months, until the prune job runs.

## Phase 2: article proof of concept

Two isolated private projects received **9,324 events each** across 25 articles,
three sections and three risk levels over **24 months**, November 2024–October
2026. Each project contains 8,700 article click-throughs, 216 topic selections,
120 Newsmap node selections and 288 pageviews. The second project differs only
by using the shared `article_opened` name for every article click-through.
Synthetic IPs come from documentation-only address ranges; no real visitors,
article URLs, headlines, contents or search text were used. Reports were inspected
through Liwan's actual dashboard HTTP endpoints; the browser UI was not rendered.

| Acceptance question | Result for requested taxonomy | Actual result |
|---|---|---|
| 1. Top 20 most-clicked articles across RiskLive | **FAIL** | Per-event article rankings pass. Missing `event` defaults to pageviews and yields no articles; `event: "*"` yields no articles; an array of the two event names returns 422. Shared-event control returns all 25 article counts correctly: article-001=636, article-002=612, article-003=588. Built-in dashboard sorting can display its top 20. |
| 2. Article engagement through Alerts versus Newsmap | **PASS** | Article-001 has 204 Alerts clicks and 432 combined Newsmap clicks. Filtering `section` splits standard and experimental Newsmap into 222 and 210. All article counts for each section match synthetic expectations. Separate built-in reports can be compared; no single cross-tab/pivot was demonstrated. |
| 3. High-risk versus medium-risk engagement | **PASS for click totals** | Alerts risk breakdown returns red=960, yellow=972, unknown=960. This does not establish click-through rates or risk preference: exposure/impression denominators were not collected. |
| 4. Individual article engagement over time | **PASS per event; combined trend needs shared event** | Article-001 graphs return the exact 24 expected monthly values for both current event names. The control returns combined monthly values 25, 26, 27 and 28 across successive six-month blocks. |
| 5. Most-used dashboard features | **PASS** | Built-in custom-events report returns Newsmap sources=5,808, Alerts sources=2,892, topic selections=216 and Newsmap node selections=120. |
| 6. Multiple months | **PASS** | All 24 monthly buckets and totals match known synthetic counts. Default maximum report range is 3,660 days; default dimension cap is 1,000 values, enough for top-20 but not an unlimited article export. |
| 7. All answers without custom reporting infrastructure | **FAIL for exact taxonomy** | Built-in reports answer the passing questions. Question 1 needs either a shared event name or an external union/aggregation. No such aggregation was implemented. |

The 16 positive checks in the runner pass, including property filtering,
per-event counts, shared-event control, monthly graphs, retention and restore.
The negative combined-event cases are intentionally preserved as evidence, not
silently worked around. Synthetic data expected-value calculations validate the
responses; actual report values come from Liwan, not from local SQL or a custom
production aggregator.

The unique-group test replays history in one ingestion run and therefore uses the
current salt. It verifies grouping support, not daily salt rotation over 24 real
months or an empirical accuracy guarantee for visitor estimates.

## Privacy and outbound-network findings

Verified in the 1.8.1 source:

- `app/models.rs` and `web/routes/event.rs`: raw IP and raw User-Agent are used in
  processing but are not event columns. Browser/platform/device families and a
  visitor-group hash are stored. Logs and reverse-proxy behavior must be reviewed
  separately; the event schema alone does not establish a system-wide guarantee.
- `visitor_group_mode = network_standard` hashes a /24 IPv4 or /56 IPv6 prefix,
  entity and daily rotating salt, without incorporating User-Agent. This still
  groups activity within the rotation period; it is not anonymous individual
  counting. `random_per_request` removes repeat grouping but makes unique counts
  approximate event counts and disables useful session metrics.
- `disable_ntp_check = true` prevents `pool.ntp.org` synchronization checks.
  Default is false. This was found in source although the website config table
  does not list it. Final POC explicitly disabled it.
- `disable_favicons = true` prevents dashboard images from
  `icons.duckduckgo.com`; these requests otherwise originate in the administrator's
  browser and reveal displayed domains. Source verified; not browser-captured.
- MaxMind downloads occur when account/license settings are supplied. None were
  supplied. Geo tracking and proxy geo headers should also be disabled.
- OIDC/Google/Entra authentication makes discovery/token requests when configured.
  Local account login avoids those providers. No optional custom head HTML or
  third-party footer assets should be configured.
- No general usage telemetry, Sentry/error-report uploader or application update
  checker was found in the reviewed source. This is a scoped source-review result,
  not proof against every dependency path or future version. A dedicated internal
  container network is still appropriate defense in depth after approval.
- The official tracker retains attribution query parameters by default, sends
  screen metadata and can send page-exit signals. A future SDK integration needs
  explicit payload sanitization, `exit: false`, UTM disabled server-side, and an
  approved-route/automation/opt-out gate. Its fallback listens to `popstate`, not
  every `history.pushState`; use App Router pathname changes and explicit SDK
  events with deduplication rather than assuming all Next.js transitions work.
- No built-in consent/opt-out gate was found in the tracker. RiskLive must supply
  that small frontend gate and privacy notice if integration is approved.

## Retention and backup decisions

A reliable deployment needs an approved recurring call to Liwan's existing prune
operation (or offline CLI), monitoring for failure, and an existing backup
scheduler/policy. This is operational scheduling, not a new aggregation service,
but it is not delivered automatically by adding a container. The CLI opens the
DuckDB database itself, so do not assume a second CLI writer can run beside the
server; prefer the authenticated built-in pruning API while online, or an
approved offline maintenance window. UI reports use login-session authentication.

The tested backup method is a cold directory copy after graceful shutdown and
checkpoint. Copying the live DuckDB file by itself is not a verified backup and
can miss WAL state. Save SQLite configuration/accounts and DuckDB events together;
protect backup credentials and grouping salts. No online-backup mechanism was
verified. A 30-day backup-expiry rule needs infrastructure-policy approval and
means deleted events may remain in older backups until those expire. On restore,
reapply current collection settings and pruning before making data accessible.

## Brief alternative comparison: Vince

[Vince](https://github.com/vinceanalytics/vince) is also self-contained without
external database servers. Its [official Stats API concepts](https://www.vinceanalytics.com/blog/api-concepts/)
document custom-property breakdowns/filters using `event:props:<name>`, event
metrics, date ranges and goal filters. This makes it a candidate for a separate
article-ranking POC, not an already validated substitute. Its
[license](https://github.com/vinceanalytics/vince/blob/main/LICENSE) is AGPL-3.0,
compared with Liwan's Apache-2.0. A fresh release/security and privacy review plus
the same cross-event ranking acceptance test are still necessary. Vince was not
installed, tested or integrated; no platform substitution was made.

## Recommended decision before implementation

Approve **one common `article_opened` analytics event**, with fixed `section`,
`article_id`, `risk_level` and optional `source_action`/`event_type` properties.
The existing UI actions can still be distinguished by property values
`alert_source_opened` and `newsmap_source_opened`, but those would no longer be
separate analytics event names. This is a requested taxonomy revision, not an
implemented change. Recording both separate events and duplicate canonical events
is not recommended because it inflates usage totals and complicates interpretation.

If that revision is approved, the control POC supports a conditional GO without
custom reporting infrastructure. Otherwise retain NO-GO and assess Vince separately.
Additional approval decisions:

1. Accept event-level 730-day retention rather than aggregate-only storage;
   establish prune schedule and 30-day backup policy.
2. Choose daily network grouping versus random-per-request. Approve the handling
   of IP, parsed browser metadata and salts, including proxy and application logs.
3. Choose private administration through existing VPN/SSH infrastructure, native
   local authentication, credential ownership and TLS termination. No new public
   ports; any network/TLS/authentication changes need explicit authorization.
4. Approve per-category collection switches, privacy notice and opt-out UX. All
   collection must remain disabled by default until governance and deployment
   approval.
5. Decide whether to replace or retain the existing uncommitted disabled
   GoatCounter integration. Do not allow parallel trackers to activate silently.

Article identifiers must be shared across components. Current Newsmap leaf IDs
contain topic/category/index context, so they cannot be assumed to match Alerts.
If no shared upstream article ID is available, use an explicitly specified
normalised-URL hash and keep its source mapping in existing RiskLive metadata.
This needs cross-component tests at implementation time. Only observed outbound
click-throughs can be measured; RiskLive cannot confirm a read on an external
publisher's site.

## Reproduction and validation

Download the official release archive into a disposable directory and verify its
SHA-256 above against the release asset metadata. Extract `liwan` and run from the
RiskLive repository root, for example:

```bash
python3 tools/analytics/liwan_poc.py \
  --binary /tmp/risklive-liwan-bin/liwan \
  --output /tmp/risklive-liwan-evidence.json
python3 -m unittest discover -s tests/deployment -p test_goatcounter.py \
  -k test_compose_is_opt_in_and_isolated
cd web
pnpm test
pnpm exec tsc --noEmit --incremental false
```

The runner starts only ephemeral loopback listeners, uses temporary storage and
random disposable credentials, gracefully stops its instances, and removes their
data. `strace` is required for the outbound-connect check. It does not use Docker
or existing VM services. It must run in an environment permitting local sockets
and ptrace. No browser dashboard screenshot, Docker runtime resource measurement,
production integration test or 24-month storage-capacity benchmark was performed.

Validation performed: 16 POC checks passed; 101 existing frontend tests passed;
TypeScript passed; current Compose configuration/isolation test passed. Existing
React `act(...)` warnings occur in experimental treemap tests. No RiskLive source
or deployment files were changed by this assessment, so no activation steps are
provided: implementation and a concrete production activation procedure remain
conditional on the review above.

## Upstream source references

All paths below refer to the tested release unless marked current main:

- [Release](https://github.com/explodingcamera/liwan/releases/tag/liwan-v1.8.1)
- [Containerfile](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/data/Containerfile)
- [App storage, background NTP and checkpoint](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/app/mod.rs)
- [Dashboard report request types and handlers](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/web/routes/dashboard.rs)
- [Property aggregation](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/app/core/reports/dimension.rs)
- [Dashboard sorting](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/packages/web/src/hooks/api.ts)
- [Property drilldown UI](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/packages/web/src/components/dashboard/project/dimensions/index.tsx)
- [Collection models](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/app/models.rs)
- [Event processing and property validation](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/web/routes/event.rs)
- [Pruning implementation](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/app/core/events.rs)
- [API key permissions](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/crates/liwan/src/app/core/api_keys.rs)
- [Favicon fetching](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/packages/web/src/components/dashboard/project/icons.tsx)
- [Tracker](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/packages/tracker/src/script.ts)
- [License](https://github.com/explodingcamera/liwan/blob/liwan-v1.8.1/LICENSE.md)
- [Current main report interface](https://github.com/explodingcamera/liwan/blob/7b44be3c258aa3c3b5f25d6a6197239442b84c2f/crates/liwan/src/web/routes/dashboard.rs)

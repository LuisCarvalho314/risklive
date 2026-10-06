# Next.js heap investigation — 6 October 2026

## Subsequent SECA work and rollout

The original containment below was committed as `a97b653`. Subsequent work
fixes SECA generation with pre-construction source-window filtering, explicit
configuration and fresh daily baseline snapshots. At the operator's request,
the experimental aggregate read budget is now **128 MiB** in the working tree;
the individual-file limit remains **8 MiB**, with fallback and concurrent-load
coalescing retained. The 32 MiB figures below describe the original containment
patch and its measurements, not the revised budget.

The isolated regenerated snapshot sets total 102,626,134 bytes across 30d/7d/3d.
See [SECA timeline hardening](seca-timeline-hardening.md) for source/node counts,
artifact sizes, the compatibility-patch correction and reported host build/
scratch-generation status. Production promotion and remote CI success remain
unconfirmed. Require the existing CI workflow to pass for the release revision
before promotion; successful local tests or Docker builds do not replace it.

## Original investigation

Source patch only, in `/home/azureuser/risklive-dev` (HEAD `6b2550b`, containing
production image revision `f14b049`). The web code and Dockerfile have no changes
between these two commits before this patch. No production container, image,
persistent data, or rollback asset was changed.

## Findings

`/newsmap-experimental` calls `loadExperimentalNewsmap()` on each dynamic server
render. Each of the three window attempts first reads/parses the entire source
CSV to build a lookup, even before checking whether its manifest exists. It then
reads each verbose JSON batch, parses the complete object, constructs several
indexes and a display tree, and retains the converted batches until rendering.
There is no input size or total workload bound.

In the mounted production snapshot, the backup source CSV is 29,488,773 bytes.
The 30-day and 7-day manifests are absent. The 3-day manifest names batches of
10,126,738; 73,865,495; 786,177,243; and 1,783,283,286 bytes. Other window directories
also contain batches approaching or exceeding a GB. These are verbose pipeline
artifacts, not a compact payload suitable for interactive rendering.

An isolated invocation of the original production loader with an explicit
512 MB Node heap reproduced a fatal V8 allocation failure. Instrumented reads
showed three complete source CSV reads followed by the 3-day batches; the final
read logged before failure was the 786 MB batch. This proves a heap exhaustion
path with actual data. It does not identify the triggering request for every
observed production restart: Docker socket access is denied in this session,
so container logs, live heap snapshots, and request correlation were unavailable.

`/ops` also repeatedly allocates heavily. Its cost aggregator reads the entire
130 MB backup CSV, parses every field into row objects, and builds strings one
character at a time, including article bodies it never uses. The original cost
loader also fatally exhausted the isolated 512 MB heap. The page refreshes every
five seconds and concurrently reads logs twice: once for overview and once for
the table. Each log call reads/splits the complete 83 MB log before selecting a
tail. A standalone log read used about 208 MiB heap at completion, returning to
about 24 MiB after forced GC. This is a secondary allocation hotspot; it was not
changed in this patch.

No unbounded server-side historical cache was found in these loaders. Their
indexes are local to each call. The text measurement cache is browser-oriented
and limited to 5,000 entries. The dashboard artifact is about 123 KB; its API
returns the raw file. Client dashboard polling runs every 60 seconds with an
in-flight guard. These sizes and code paths do not explain a 4 GB working set.

## Runtime and healthcheck

Docker uses Node 20 Alpine and the standalone production Next.js server
(`node server.js`, cwd `/app/web`), with results/logs mounted read-only at
`/app/results` and `/app/logs`. The older Dockerfile in the home checkout uses
`pnpm start`; the April 8 deployment report documents the former manual host
frontend running from that checkout with an explicit `DASHBOARD_JSON_PATH`.
The historical host command, Node flags, and active container environment could
not be verified. The migration places the accumulated persistent artifacts in
the paths used by the relative filesystem loaders; the heavy loaders themselves
also exist in the home checkout.

The deployed source `/` route redirects to `/topics`. That page renders a client
wrapper; it does not call these server loaders. `wget` follows the redirect but
does not execute client JavaScript or polling. The healthcheck therefore does
not invoke the experimental or ops workloads. No healthcheck change is needed
for this fix.

## Patch and validation

* Bound each experimental text input to 8 MiB and aggregate reads to 32 MiB per
  load. Check size before allocation, enforce the limit while reading to handle
  concurrent file growth, and always close the handle. Oversized inputs take
  the existing fallback path. Bounds are conservative operational limits,
  not a claim that these verbose artifacts legitimately need a larger heap.
* Coalesce simultaneous experimental loads into one promise, released on
  completion. Subsequent requests reload current artifacts.
* Parse ops cost CSV fields from spans rather than per-character concatenation;
  only materialize the nine fields actually consumed by the cost summary.
  Preserve existing cost, quoting, and deduplication behavior.

Three repeated patched cost loads of the production snapshot completed with the
512 MB heap cap, around 344 MiB heap at completion and 19 MiB after GC. Patched
experimental loads returned fallback in 2–4 ms, around 21–23 MiB heap at
completion (about 101 MiB maximum RSS for the process including its TypeScript
transpilation harness). These are isolated loader measurements using host Node
20.20.0, not full Next.js request/RSC serialization measurements.

43 tests pass across bounded reads, experimental loading, cost aggregation,
ops overview API/status aggregation, dashboard API and loading. Coverage includes
rejecting oversized inputs before reading, growth after stat, aggregate budget
accounting, UTF-8 byte accounting, concurrent load coalescing, fresh subsequent
loads, fallback, and large quoted CSV fields with deduplication. TypeScript
`tsc --noEmit --incremental false` and `git diff --check` pass. No build was run.

Measurement harness and before/after logs are in
`/tmp/risklive-heap-investigation`. Every measurement subprocess used
`node --expose-gc --max-old-space-size=512` and read production artifacts only.

Review tradeoff: large experimental history becomes unavailable and the normal
dashboard newsmap is displayed instead. A future compact artifact or lazy batch
API can restore history without parsing GB-sized files inside Next.js. The ops
cost loader still reads the CSV as a whole, and log reads remain expensive;
streaming these is a separate improvement if future data growth or measured
concurrency warrants it. Live stability must be checked after an explicitly
reviewed deployment. No heap increase forms part of this patch.

The pre-existing uncommitted env example addition setting an 8 GB Node heap was
preserved and is outside this patch.

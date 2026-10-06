# SECA timeline hardening — 2026-10-06

> Historical baseline workaround. The generator design described here is superseded by [the persistent SECA-Light stream](seca-light-stream.md). The loader limits and deployment observations remain useful historical context.

## Release and rollout status

The locally recorded recent commits are `f14b049` (container deployment),
`6b2550b` (HTTP 8888 without Caddy basic authentication), and `a97b653` (bounded
web loaders and ops allocation fixes). At this update, `dev/isolation` is at
`a97b653`; the generator/configuration changes, 128 MiB budget and patch-header
repair remain working-tree changes. Remote refs could not be refreshed, so
push status and GitHub Actions results are not verified here.

The operator reported successful host builds of:

| Image | Reported image ID |
|---|---|
| `risklive-app:seca-hardening-20261006b` | `sha256:ec96a69d5b19bb81cc1b18070a0e45943ade5ee1137311b3a89d0fd71badb2dc` |
| `risklive-web:seca-hardening-20261006b` | `sha256:e60e458e52b37e2873057afe6b8c6342ed765fde601f03ab563888345e477d3d` |

Docker reused cached successful layers, including the corrected patch and
Rust tests/build. These image builds do not establish CI success for a committed
release revision. The operator also reported scratch generation returning
`/app/results/web/newsmap/seca-light-30d/timeline_manifest.json`. Validation of
all three scratch windows and production promotion have not been confirmed.

The last operator-supplied Compose status identified project `risklive-prod`:
app/scheduler used `risklive-app:f14b049` and were stopped; web used
`risklive-web:a97b653` and was stopped; Caddy remained healthy on port 8888.
Those image tags are rollback references, not a claim about current live state.
Recheck container status before resuming the rollout. Keep the scheduler stopped
while API credits are unavailable.

Before production promotion, commit/push the intended changes and require both
jobs in [the existing CI workflow](../.github/workflows/ci.yml) to pass for that
exact revision. Build release images from that committed revision; retain the
scratch outputs and originals while validating. See the
[deployment CI gate](deployment-docker.md#ci-gate-before-release). Local test
results below are distinct from remote CI results.

## Findings

The Python generator reads relevant LLM-enriched rows from `results/data/news_data_with_llm_info.csv` followed by `results/backup_data/news_data_with_llm_info.csv`. The production current CSV is empty; the backup contains 68,108 rows, including 13,589 relevant rows spanning 2026-04-07 through 2026-10-03. There are 72 repeated relevant URL occurrences across that archive.

The original generator **already filtered rows before CSV conversion and SECA construction**. It anchored each window at the latest relevant source timestamp, not the wall clock. Its inclusive `latest - timedelta(days=N)` boundary included N+1 UTC dates when the latest timestamp was midnight: 31/8/4 dates and 2,030/697/381 sources for the observed 30d/7d/3d inputs. This was a boundary error, not ingestion of the entire April–October archive.

Two construction problems explain the much larger amplification:

- Python never supplied `--config`. The CLI used `SecaConfig::default()` with `minimum_number_of_sources_to_create_branch_for_node=1`, rather than the intended experimental configuration's threshold of 10. Recursive branches repeat source references and word lists across many nodes.
- `timeline-many` fed daily batches into `process_batch` and exported the complete verbose engine tree after every day. The pinned core retains batches in `MemoryMode::Full` and performs experimental recursive scope/reconstruction work. A small bounded source set therefore produced rapidly increasing tree topology. Merely passing the intended configuration did not solve this: the old 8-day/697-source replay still grew to an 89 MB intermediate batch and timed out at 120 seconds. Fresh baseline construction of the same source set completed in under a second and produced a 4.59 MB pretty JSON tree.

The core paths are `experimental/crates/realtime-seca-core/src/tree/hkt_builder.rs` (`create_branches`), `src/engine/mod.rs` (`process_batch`), `src/engine/rebuild.rs` (scoped reconstruction and retained batches), and `src/engine/snapshotting.rs` (verbose node/source/word expansion). The compatibility command is in `docker/seca/timeline-many.patch`; it creates a new engine on each invocation. It does **not** load previous manifests or engine caches. Python previously passed explicit newly generated batch paths, not a glob of the runtime directory. The 399 retained runtime batch files were not all replayed. Across invocations the output was cleaned, not appended; within one invocation every daily snapshot was cumulative. Cleaning before generation also meant an interrupted run could destroy the old manifest and leave huge partial outputs.

All callers are `app.server.run_seca_light` (manual `/trigger/seca-light`, also invoked after normal processing) and `services.replay.run_replay_days` when `run_seca=True`. The normal processing/replay paths fetch and run LLM stages; **do not use those paths for this regeneration**. No callers, Dockerfiles, compose files or Rust submodule files were changed. A subsequent Docker build exposed a malformed final hunk count in the existing compatibility patch; only that header was corrected from `@@ -588,6 +715,7 @@` to `@@ -588,5 +715,6 @@`. The corrected patch passes `git apply --check`, apply and reverse-check against a checksum-verified temporary copy of the pinned source. No Rust code changed. The frontend aggregate budget was subsequently updated at the user’s explicit request.

## Production inventory (read-only inspection)

Sizes are decimal bytes. Oversized JSON was inspected with bounded prefix/tail reads and line-by-line counters; it was never decoded into an in-memory JSON object.

| Directory | Tree files | Manifest | Total JSON bytes | Largest batch | Nodes in largest batch |
|---|---:|---|---:|---:|---:|
| seca-light-30d | 5 | Missing | 1,712,877,091 | 1,341,374,860 | 68,549 |
| seca-light-7d | 3 | Missing | 916,083,811 | 890,157,957 | 86,211 |
| seca-light-3d | 4 | Present | 2,653,453,078 | 1,783,283,286 | 123,304 |

The 3d manifest lists four files, `total_batches=4`, `sources_total=381`, `chunk_count=4`, `chunk_size_effective=118`, and days September 30, October 1, October 2, October 3. Its penultimate batch is 786,177,243 bytes. The 30d and 7d outputs are partial, so their file date ranges cannot be verified from a manifest. Associated runtime CSVs describe intended September 3–October 3 and September 26–October 3 windows, respectively; those CSV dates do not prove all those dates occur in the partial trees.

## Source change

`src/services/seca_timeline.py` now:

1. Makes two streaming CSV passes to establish the latest relevant observation and retain only the widest 30-day input window. Historical rows never reach expensive conversion/construction.
2. Selects N UTC calendar days including the latest source day, with timestamp/API-timestamp fallback and UTC normalization. This deliberately preserves data-anchored offline replay: an October 3 archive produces October 1–3 for 3d, even when regenerated October 6.
3. Deduplicates URL identities across input files and fetch timestamps, retaining the latest timestamp; the current CSV wins ties. Rows without a URL retain title/timestamp identity.
4. Constructs each daily cumulative **in-window prefix** using a fresh `baseline` engine and an explicit `config/seca_timeline.json`. That config copies the existing intended experimental settings, including branch threshold 10. No `process_batch`, snapshots or archived reconstruction state enter generation.
5. Gives sources their URL identity, with namespaced synthetic IDs for URL-less records. Raw `row_N` IDs would otherwise resolve to unrelated historical rows in the frontend's full CSV lookup. No schema fields change.
6. Compacts newly generated JSON without removing fields, nodes or source references. This is lossless whitespace removal, not byte-based truncation or source selection.
7. Builds in a unique staging directory and publishes only complete outputs, restoring the old directory if publication fails. Empty inputs publish an empty manifest and remove stale trees. A per-root advisory lock prevents overlapping manual/scheduler generations. Temporary CSV/batch files are removed after generation.

The tree and manifest schemas and daily cumulative interpretation remain. Fresh baselines can assign different node/word IDs and topology between dates and omit incremental reconstruction tombstones. The frontend builds each batch independently. Source URLs remain stable. This fix avoids the experimental incremental reconstruction path; it does not repair that upstream algorithm for other consumers.

## Validation and measurements

The final source was run twice against an isolated copy of the existing 130 MB production backup, using the already available local SECA release binary. Both generations were byte-identical, including manifests. No network, fetching, model inference or LLM stages were invoked. Only `/tmp/risklive-seca-fixed-validation` was written.

| Window | Source dates | Sources | Daily snapshots | Total tree bytes | Largest tree bytes | Final nodes / HKTs |
|---|---|---:|---:|---:|---:|---:|
| 30d | Sep 4–Oct 3 | 1,986 | 30 | 84,061,062 | 7,189,196 | 3,427 / 510 |
| 7d | Sep 27–Oct 3 | 663 | 7 | 17,299,583 | 4,143,588 | 2,117 / 363 |
| 3d | Oct 1–Oct 3 | 263 | 3 | 1,265,489 | 580,030 | 208 / 43 |

The final source legends contain exactly 1,986/663/263 entries. The complete generator took roughly 11 seconds before the additional compact-serialization/source-identity work; final repeated runs also completed without a timeout.

The preserved cumulative snapshot format repeats in-window content across dates. Consequently the 30d set exceeds the previous frontend 32 MB **aggregate request** budget, despite individual artifacts being below 8 MB on this fixture. At the user’s subsequent request, the aggregate request budget was raised to 128 MiB while preserving the 8 MiB individual-file bound, fallback and coalescing. The three regenerated sets total 102,626,134 bytes (about 98 MiB), so they fit that revised aggregate budget. Future news density can change sizes; no byte cap determines membership.

Checks:

- `python -m pytest --no-cov tests`: **182 passed**, with two existing runpy warnings.
- SECA-specific regression module: **20 passed**. Covers all window boundaries, historical rows excluded before CLI construction, repeated generation/expiry, stale outputs, URL deduplication and latest anchor, source identity, empty windows, conversion/baseline/timeout/missing-output failure preservation, publish rollback, concurrency and CLI resolution.
- Ruff lint and format checks on changed Python files: pass.
- Pyright on the generator with the local Python interpreter and explicit installed typeshed path: zero errors/warnings.
- Frontend `pnpm typecheck`: pass. `pnpm test`: **71 passed**, with existing React act warnings. ESLint parser/unused-variable checks on the changed loader and its regression test also passed. The loader tests accept 112 MiB of individually bounded batches and reject a 133 MiB request.
- `git diff --check`: pass.

The Rust workspace was left untouched. An attempted isolated locked offline Rust build could not resolve cached `stop-words=0.10.1`; actual artifact validation used the existing release CLI and its unchanged `from-csv`/`baseline` commands, which are also present in the Docker CLI.

## What to preserve

These verbose trees contain derived word/source legends and topology, not unique fetched article bodies, LLM summaries or annotations. The preserved enriched CSV is the source of truth for regeneration. The old topology and synthetic IDs are historical derived results and will not be reproduced identically by fresh baselines. Keep them in quarantine for rollback/forensics until the replacement has been reviewed. They need not remain served or be merged into the new timelines. After that review, the oversized derived directories may be deleted; preserve the source CSVs and their backups. Existing runtime SECA intermediate files are also derived and are not inputs to the fixed generator.

## Safe offline regeneration and promotion

The agent did not modify production data during investigation or execute the
host rollout: its sandbox denies Docker socket access. The operator reported
the builds and scratch generation above; live artifact replacement remains
unconfirmed. The following procedure includes production writes only at the
explicit promotion step.

1. Commit and push the intended release changes, verify both existing CI jobs pass for the exact revision, then build versioned app and web images from that revision containing this source/config and the revised aggregate budget. No deployment infrastructure change is needed. Use the existing SECA CLI; do not fetch news or invoke regular, full, trending or replay pipeline triggers.
2. Coordinate a quiet period for source CSV writes and SECA generation. Copy the existing enriched CSVs into a new scratch root, preserving production originals. Keep source-copy checksums with the run. For example, on the host:

   ```bash
   export SECA_STAGE="$(mktemp -d /tmp/risklive-seca-regenerate.XXXXXX)"
   mkdir -p "$SECA_STAGE/results/data" "$SECA_STAGE/results/backup_data" "$SECA_STAGE/runtime"
   cp /opt/risklive/data/results/data/news_data_with_llm_info.csv "$SECA_STAGE/results/data/"
   cp /opt/risklive/data/results/backup_data/news_data_with_llm_info.csv "$SECA_STAGE/results/backup_data/"
   sha256sum "$SECA_STAGE"/results/{data,backup_data}/news_data_with_llm_info.csv > "$SECA_STAGE/input.sha256"
   sudo chown -R 10001:10001 "$SECA_STAGE"
   ```

3. Run only the generator from the corrected image against the scratch mounts. `APP_IMAGE` must name the corrected, already-built local image. This container has no network, credentials, production mounts or scheduler:

   ```bash
   docker run --rm --pull never --network none --read-only \
     --tmpfs /tmp:rw,nosuid,nodev \
     --mount "type=bind,src=$SECA_STAGE/results,dst=/app/results" \
     --mount "type=bind,src=$SECA_STAGE/runtime,dst=/app/runtime" \
     "$APP_IMAGE" python -c 'from services.seca_timeline import run_seca_light_timeline; result = run_seca_light_timeline(); assert result is not None, "SECA generation failed"; print(result)'
   ```

4. Review **all three** staged manifests and listed files. The entry point returns the 30d manifest; separate per-variant failure logs must also be checked. Verify sources/dates against the copied CSV, file existence, source/node counts and sizes. Confirm 30/7/3 maximum source-day counts, and that no source precedes its variant cutoff. Parse only newly generated artifacts. Do not parse old giant files to compare them. Keep the source copies for reproducibility.
5. For promotion, stop scheduler/manual SECA generation and briefly stop the web reader. Prepare the three new directories on the same filesystem as production, outside their live names. Rename the existing live directories into a dated quarantine location, then rename the prepared replacement directories into the live names. Preserve the current UID/GID and permissions. Roll back using the quarantined directories if validation fails. Replace whole directories, not individual files or just the manifest, to prevent stale batches. Do not delete or modify `results/data`, `results/backup_data` or the original source CSVs.
6. Start the web/app with the corrected versioned app and web images using `docker compose -f deployment/compose/docker-compose.prod.yml up -d --no-deps --no-build --pull never --wait app web` with the existing production environment exports. Do not use `deploy.sh` while credits are unavailable: it starts the scheduler too. Validate manifests and `/newsmap-experimental`; restart the web reader to discard process-local cached timelines. Check all three timeline views under the revised 128 MiB aggregate budget. Resume scheduling only when fetching/LLM credits are available; until then keep the fetching scheduler stopped.
7. Remove quarantined derived artifacts only after successful review and the desired rollback retention period. Reassess the temporary 8 GB Node heap override separately after runtime observation; this source change does not alter that setting.

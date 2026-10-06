# Persistent SECA-Light in RiskLive

This change replaces independent daily CA baselines with one evolving Rust SECA-Light model. It is a code change only; production data and deployment have not been changed.

RiskLive milestone: [SECA production path corrected to persistent SECA-Light](milestones.md#seca-production-path-corrected-to-persistent-seca-light).

## Investigation: previous production flow

`src/app/schedules.json` schedules the fetch job. `src/app/scheduler_jobs.py` invokes the server fetch/process pipeline; the manual pipeline produces enriched articles and dashboard output and invokes `run_seca_light_timeline`. The manual SECA trigger and replay pipeline use the same service. Failures in this optional dashboard stage are logged without breaking article ingestion.

Before this change, `src/services/seca_timeline.py::_run_timeline_variant` read relevant (`Relevance=Yes`) rows from current and backup enriched CSVs, deduplicated URLs, filtered against the latest article timestamp, grouped UTC dates and ran the Rust `baseline` command separately for each cumulative daily prefix. It did this independently for 30-, 7- and 3-day views. The next run loaded CSVs again, not yesterday's tree. Thus each date's tree was static CA reconstructed from that window's articles, despite the SECA-Light name. Previous articles survived in data/backup CSVs and verbose historical output, but no resumable active model was used.

The Rust builder already contained SECA machinery: `SecaEngine`, `MemoryMode::SlidingWindow`, `process_batch`, top-down scope mapping, trigger metrics and targeted reconstruction. The production path bypassed these. Additional gaps prevented simply switching commands: schema-2 snapshots omitted the tree; the baseline scope helper considered only the first retained batch; candidate words changed the old vocabulary before comparison; the fallback rebuilt the whole tree; and forgetting removed empty structural nodes. Source statistics and duplicate source identities also needed correction.

`experimental/crates/realtime-seca-core/src/engine/baseline.rs` constructs the initial tree through `tree/hkt_builder.rs`. `engine/trigger.rs` evaluates scoped HKTs; `engine/rebuild.rs` replaces selected subtrees; `engine/snapshotting.rs` now saves and restores the complete engine. The production CLI entry point is `realtime-seca-cli/src/update.rs`.

## Paper mapping and interpretation

Reference: Al Sulaimani and Starkey, *Real-Time Event Detection Using Self-Evolving Contextual Analysis (SECA) Approach*, IEEE Access (2023), DOI [10.1109/ACCESS.2023.3331219](https://doi.org/10.1109/ACCESS.2023.3331219). Sections V–VII and the real-world configuration were reviewed in the [author-uploaded full text](https://www.researchgate.net/publication/375503068_Real-Time_Event_Detection_Using_Self-Evolving_Contextual_Analysis_SECA_Approach).

For scoped source sets, let `df(w)` count distinct sources containing a word, `N(node)` be the node's source membership, and `W0` the HKT's old vocabulary:

- Strength is `df(w) / max(df(v))` in the HKT scope. The alpha condition is strength >= alpha.
- Eligibility is `|sources(w) intersect N(node)| / |N(node)|`. The beta condition is eligibility >= beta.
- Alpha-Error is the mean over old words of `max(0, alpha - strength1(w))` (equation 6).
- Beta-Error is the mean over old words of `max(0, beta - eligibility1(w))` (equation 9).
- Word importance normalizes document frequency over old and newly eligible vocabulary. Word-Importance-Error is `1 - sum(importance1(w), w in W0)` (equation 12).

Production selects Option1 for all three measures. Options2/3 remain legacy diagnostics and are not the paper's active rule. Threshold comparisons use full precision and strict `>`; only log rendering rounds values. Builder alpha/beta must match update alpha/beta.

Traversal starts at Seed-HKT with the new batch. Child scopes inherit sources adopted by their parent node. Sources may belong to multiple nodes; unmatched sources enter refuge. A threshold crossing replaces that HKT and its descendants, stopping further descent there. Otherwise its existing structure is retained and children are inspected. Reconstruction uses retained source batches plus the current batch, excluding words already adopted along the ancestor path.

SECA-Light prunes source data **after** this update. The paper's phrase “before theta-gamma” has an inclusive-boundary ambiguity relative to “up to gamma batches”; we retain exactly the latest gamma successfully committed batches, as requested. The real-world paper uses gamma=3 with minute batches; RiskLive uses batches rather than minutes or days.

Forgetting alone does not erase learned topology. Zero-support nodes may remain until their container is reconstructed. Selective replacement can shrink a subtree, so the tree does not only grow. The paper does not establish a strict bound on tree size; gamma bounds retained batches, not nodes, sources per batch, vocabulary, or audit history. Empty scopes have no new evidence and do not trigger a rebuild. This is an explicit engineering interpretation of an undefined empty denominator.

## State lifecycle and storage

`run_seca_light_timeline` now locks the stream, loads its committed engine, selects previously unseen relevant articles, converts one batch, runs `update`, and commits its staged outputs in one SQLite transaction. Only afterwards are presentation files published.

| Concept | Storage and lifecycle |
| --- | --- |
| Active model | Singleton `model.state` in `runtime/seca/stream.sqlite3`; full schema-3 Rust engine snapshot, tree, legends, ID counters and update configuration |
| Active source window | Within that engine: latest gamma batch payloads and source/node/word membership sets |
| Historical output | Immutable `batches` rows: ordered sequence, explicit batch ID, timestamp, verbose tree, metrics and configuration |
| Current presentation | Existing `results/web/newsmap/seca-light-{30,7,3}d` directories and manifest/tree JSON contracts; three views of the same model's snapshots |

A batch is one successful service invocation, including an empty invocation after bootstrap. It has an explicit caller-supplied ID or a generated run UUID and a monotonic integer sequence. Calendar dates appear only in the presentation layer. Supplying the same committed ID retries publication without processing it twice. A failed attempt consumes neither sequence nor ingestion receipts. Scheduler runs currently use generated IDs; article receipts prevent repeated searches from reintroducing the same article.

`config/seca_timeline.json` sets `memory_mode=SlidingWindow` and `max_batches_in_memory=30`. `RISKLIVE_SECA_GAMMA_BATCHES` overrides gamma with a positive number of batches. Thirty preserves approximately the previous daily horizon for the normal schedule; extra successful manual runs also consume batches. It is not a guarantee of thirty calendar days.

Within the active window the engine needs stable source ID, batch order and normalized tokens, plus membership sets. Raw article text, metadata and timestamps are discarded from model payloads. URLs remain stable source IDs; URL-less articles receive a hash derived from article identity metadata. Current/backup CSVs remain the article-detail store. A separate `ingested` table retains identity receipts beyond gamma, without article payloads, so duplicates across searches and later runs are not counted again. Corrections to an existing URL are currently ignored; versioning corrected articles would require an explicit identity policy.

Pruning removes expired IDs from retained batch payloads, source legends, global identity lookup, node memberships and pending sets, word memberships and word pending sets. Node display counts and mirrored HKT/global node indexes are synchronized. Future metrics recompute frequencies from retained membership/batches; cumulative old counts cannot influence them. In-memory removed-subtree archives are cleared in Light mode; historical snapshots provide audit history. Learned vocabulary and topology persist.

No existing snapshot can safely initialize the stream: old presentation JSON and schema-2 snapshots are not resumable state. The first nonempty invocation builds once from currently available relevant input (the existing 30-day input discovery limit remains). Empty bootstrap waits; later empty batches preserve topology while advancing and pruning the source window. Failed processing preserves the last committed state.

Rust snapshot schema/version and SQLite `user_version` are checked. Unknown versions and changed model configuration fail explicitly, rather than silently resetting the model. Changing gamma or alpha/beta requires an explicit migration or replay into a separate state directory; do not delete production state to bypass this guard.

## Reliability, replay and compatibility

A POSIX `flock` serializes scheduled/manual writers across processes. Rust processes clone the engine before mutation. The CLI writes a temporary state with fsync and atomic rename. The Python service stages everything under runtime and commits model, history and receipts together using SQLite with synchronous FULL. A conversion/update/validation failure cannot replace committed state. Publication failure leaves committed history recoverable on the next invocation. Each view directory is atomically replaced; the three views are not one filesystem transaction.

Existing daily output directories are copied once into `results/web/newsmap/seca-legacy/<variant>` before the first new-format publication. Existing tree filenames and verbose HKT/node/source legend fields remain readable by `web/lib/newsmap-experimental.ts` and the ops artifact inspector. Manifests add batch IDs and model metadata. The 30/7/3 labels now mean snapshot presentation horizons, not three independent trained models. Multiple runs on one day can produce multiple snapshots. Existing loader file/aggregate size limits still apply.

Set `RISKLIVE_SECA_ARCHIVE_BATCHES=1` before processing to persist normalized input JSON in historical rows for deterministic replay. It defaults off to avoid retaining source payloads outside gamma. With archives enabled, export `input_batch` and `config` in sequence order, run the pinned CLI's `update` command into a separate directory, passing each prior `--state-out` as the next `--state-in`. Replay requires the same engine version, configuration and tokenized inputs. CSV backups alone do not guarantee exact replay because tokenization and ingestion order can change. Historical trees/configuration/receipts grow independently of the bounded active payload window; archive retention is a separate operational policy.

Docker copies the pinned Rust submodule, checks `docker/seca/SOURCE.sha256`, uses the parent-owned locked dependencies and tests both core and CLI. The previous timeline-many patch is incorporated into the Rust repository; Docker no longer reapplies it. Runtime/results mounts already shared by the app and scheduler preserve state across containers. Existing CSV cleanup does not delete `runtime/seca`.

## Verification

Focused Rust tests in `tests/seca_light_stream.rs` prove persisted continuation, unchanged structure below thresholds, child-only rebuild with a retained sibling, gamma=3 forgetting without reset, subtree shrinkage, duplicate suppression, empty updates, failed mutation rollback and restart equivalence. Existing core/integration regressions remain part of the suite.

`tests/unit/services/test_seca_timeline.py` checks transaction failure paths, publication recovery, IDs/receipts, empty bootstrap, bounded payloads, historical views and retry semantics. `tests/integration/seca_light_probe.py` exercises eight independent Rust update processes through the real Python/SQLite service with gamma=3, using a fixture converter. It deliberately uses the exact production update module via the core example, allowing offline execution without the CLI's uncached tokenizer/network dependency graph.

Verified locally: **145 Rust tests**, **29 Python tests**, **20 dashboard/ops tests**, and the eight-process probe with identical archived-batch replay. Rust commit `a03e2ba3385d328a10eacbf584c57cddc6f40a62` is on local branch `fix/seca-light-stream`; the push attempt failed because shell DNS could not resolve GitHub and the connector denied tree creation with HTTP 403.

Run the core suite with `cargo test -p realtime-seca-core --offline`, the focused Python tests with pytest, and the probe with the project virtualenv. A full CLI/container build still requires uncached crates and was not available in this network-restricted environment; this limitation must not be represented as a passing Docker build.

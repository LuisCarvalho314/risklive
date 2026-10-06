# SECA diagnostics schema v2

The unchanged treemap geometry had two causes: decision traversal intentionally evaluated only a few HKTs, and one missing metric caused snapshot-wide equal weighting. Decision traversal must remain sparse when that is what SECA actually does. The display sweep is separate and observational.

`BatchProcessingResult.decision_diagnostics: Vec<HktDecisionDiagnostics>` records actual state0 evaluations, thresholds, reasons, policy, and reconstruction provenance (`hkt_id` → optional `output_hkt_id`). `hkts_inspected` remains exactly its length. The trigger algorithm, reconstruction actions, and equations are unchanged.

`display_diagnostics: Vec<HktDisplayDiagnostics>` identifies final-tree IDs directly. It runs after reconstruction and pruning. On a private cloned observation view, it removes incoming sources from retained batches and node/word membership, keeping final topology, vocabulary and configuration. This partitions evidence into disjoint retained prior sources and incoming sources; otherwise an already merged/rebuilt incoming source would be counted twice by the state0 + state1 equations. The view maps incoming sources down final branches with existing Rust scope mapping and ancestor context. It visits branches even when their incoming subset is empty or the decision traversal stopped above them. No decisions, state1 applications, membership merges, counters, ID allocation, or live-state writes occur.

Measurements assess the final vocabulary on retained old + incoming evidence. They are final-tree fitness observations, not historical state0 decision errors, and can differ after reconstruction/pruning. For unchanged equivalent scopes the Option1 errors agree with decision errors. All three equations come from `compute_update_stage_for_scope`, `compute_word_change_metrics_for_scope`, and `compute_paper_scope_metrics_from_change_metrics`. Display explicitly selects Option1 (the enforced production option). It never parses notes or duplicates equations outside Rust.

| Selector | Definition |
|---|---|
| Mapped Sources | Unique retained active sources in the union of final HKT node memberships, including refuge members; multi-node membership counts once |
| Alpha Error | Real paper Option1 alpha error on final vocabulary |
| Beta Error | Real paper Option1 beta error on final vocabulary |
| Word-Importance Error | Real paper Option1 WI error on final vocabulary |
| Combined Error | RMS of available real alpha/beta/WI terms; all missing means unavailable |
| Triggered | Actual decision only: triggered → 4, evaluated but not triggered → 1, not evaluated → unavailable |
| Composite | Explicit existing legacy proxy |

Retained membership is useful for tree size even where no incoming sources arrived. It also remains available on baseline initialization. Incoming mapped counts retain their original meaning in decision records.

An error needs a current non-refuge vocabulary and evidence supporting at least one current word. No supporting evidence, no words, and baseline initialization produce null error fields with `unavailable_reason` (`no_applicable_evidence`, `no_current_words`, `baseline_no_comparison`). Refuge-only evidence cannot manufacture a word metric. Real computed zero remains zero. With retained evidence, an empty incoming subset can still have meaningful Option1 final fitness; it is not automatically unavailable.

Publication emits `diagnostics_schema_version: 2`, `update_context: {variant, sequence, batch_index}`, `decision_diagnostics`, and `display_diagnostics` from the exact SQLite `(variant, sequence)` row. SQLite remains schema 2; no migration is needed. 3d, 7d and 30d remain independent persistent models. Old reports lacking the new arrays expose unavailable metrics until replay.

Frontend sizing handles availability among local sibling HKT groups. Available scores use `score + 1e-9`; inverse direction uses `max + min - score + 1e-9`, using only available siblings for extrema. Each unavailable sibling receives the mean available sibling weight, or weight 1 if all are unavailable. This allocates a neutral average sibling budget without inventing a diagnostic value or substituting Composite. Missing distant scopes cannot neutralize real siblings. The UI shows available/total coverage and per-scope metadata records the selected availability, neutral treatment, comparison reason and three-state actual trigger status.

Each sibling HKT group owns one budget, distributed among its visual member nodes by source membership. Descendants partition that budget, and only leaves carry D3 sum mass. No metric is added through both ancestors and descendants. Real zero/tiny errors remain distinguishable through the existing weighted-tree/D3 path.

## Operator verification and rebootstrap

`scripts/verify_seca_diagnostics.py ROOT` is read-only. It validates each published snapshot against its matching stored report/tree, verifies display IDs exactly match final HKTs, reports decision/display/alpha/beta/WI coverage, and warns when non-baseline evaluable coverage falls below 25%. It does not demand 100% error availability.

Existing production history needs one final historical replay: sparse old decision records cannot supply final display diagnostics faithfully. Keep `deployment/scripts/rebootstrap-seca-diagnostics.sh` as the operator path. Its verifier now expects schema v2. Do not run it as part of development validation. No production actions or deployment are needed for these changes.

## Future SECA bumps

Commit RealtimeSECA changes first. Then:

```bash
git -C experimental checkout <revision>
./scripts/update-seca-pin.sh
git add experimental docker/seca/SOURCE_REVISION docker/seca/SOURCE.sha256
```

The helper refuses dirty submodules, stages the revision and hashes for exactly the paths already listed in `SOURCE.sha256`, verifies staged hashes, then replaces provenance files with rollback on failure and rechecks the final pin/hash set. It also updates the Docker image revision label; include `docker/Dockerfile.app` in the RiskLive commit. CI retains its independent revision equality and `sha256sum --check` checks. Filesystem replacement is atomic per file; the multi-file update is staged and rollback-protected, not a filesystem transaction. Do not run concurrent pin updates/checkouts.

## Validation

```bash
cargo test --manifest-path experimental/Cargo.toml --workspace --release
cargo build --manifest-path experimental/Cargo.toml --release -p realtime-seca-cli
.venv/bin/pytest -p no:cacheprovider --no-cov tests/unit
.venv/bin/python tests/integration/seca_light_probe.py experimental/target/release/realtime-seca-cli
.venv/bin/python tests/integration/seca_diagnostics_probe.py experimental/target/release/realtime-seca-cli
(cd web && npm test && npm run typecheck && npm run build)
```

Rust tests compare complete serialized engine state before/after inspection (including topology, all membership, retained batches, legends, counters, configuration and last index), subsequent decisions/reconstruction, equivalent Option1 values, null empty/baseline errors, and post-pruning/rebuilt final IDs. The controlled 260-HKT fixture requires exactly three normal decisions while sweeping all 260 scopes. A separate large article fixture measures actual evaluable coverage. Frontend tests check rectangles produced by `buildWeightedTree` and D3, including a 260-HKT/three-decision/245-display fixture, ranking reversal, partial availability, direction, zero/tiny values and conservation. Replay probes verify independent historical contracts and deterministic transactions across all horizons.

## Measured fixture results

| Fixture | Final HKTs | Actual decisions / previous display coverage | Display records | Alpha / Beta / WI available |
|---|---:|---:|---:|---:|
| Controlled sparse traversal | 260 | 3 | 260 | 260 / 260 / 260 |
| Large article data with production branch admission | 41 | 12 | 41 | 41 / 41 / 41 |
| Frontend partial-coverage regression | 260 | 3 | 245 | Alpha 245 |

These are fixture measurements, not a production replay. The production result will be measured by the read-only verifier after an operator rebootstrap.

`tests/integration/seca_decision_parity_probe.py OLD_CLI NEW_CLI` compares separately preserved pre-feature and new Rust executables. Against pre-feature revision `a03e2ba3385d328a10eacbf584c57cddc6f40a62`, 24 updates across 3d/7d/30d included 21 reconstructions, with identical complete reports (apart from the explicit diagnostic contract), final trees/IDs, and entire persisted snapshots. Use separate Cargo target directories when building the two revisions to avoid shared executable/cache collisions.

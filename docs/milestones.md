# RiskLive milestones

## Three independent persistent SECA-Light horizons

Recorded: 2026-10-06. Corrects the singleton architecture described in the earlier milestone below. RiskLive now maintains independent 3d, 7d and 30d Rust models, each chronologically replayed through its own historical source window. Schema 2 scopes state, sequences, history and receipts by variant; all three bootstrap histories commit atomically. Defaults are gamma 3/7/30 batches, with per-model overrides. See [design and operator migration](seca-light-stream.md). Production migration remains an operator action.

## SECA production path corrected to persistent SECA-Light

Recorded: 2026-10-06. Status: implemented and verified locally; deployment is a separate release step.

RiskLive's SECA production code path now continues one persisted contextual model across ordered batches. Previously, it constructed independent daily CA baselines. The existing Rust engine was adapted to restore complete model state, evaluate paper-defined Alpha/Beta/Word-Importance errors, selectively reconstruct HKT subtrees, and forget source contributions outside a configurable gamma-batch window without resetting learned topology.

Model state, active source memory, historical snapshots and dashboard presentation are now explicit separate concepts. Model/history/ingestion receipts commit atomically; historical dashboard output remains available. This milestone establishes the stream semantics required for subsequent SECA evaluation and operational work.

Implementation references:

- RiskLive commit: `6192a33` — production stream integration, persistence, compatibility and documentation.
- RealtimeSECA commit: `a03e2ba3385d328a10eacbf584c57cddc6f40a62` — persistent engine state and selective evolution, on `fix/seca-light-stream`.
- [Investigation, paper mapping, design and operational guide](seca-light-stream.md).

Verification: 145 Rust tests, 30 Python tests, 20 frontend tests, and an isolated eight-process continuation probe with identical deterministic replay. Tests cover unchanged topology below thresholds, targeted reconstruction, bounded source membership, forgetting, restart equivalence, empty batches and failure isolation.

CI gate: the `Persistent SECA-Light` job in `.github/workflows/ci.yml` checks the pinned submodule revision and source hashes, tests core and CLI with the production toolchain/lockfile, runs the persistence/replay probe with the real CSV converter, and builds the app image without deploying. Existing backend and frontend jobs remain required checks for this work. The workflow runs on pull requests and pushes to `main`, `develop` and `dev/**`, including `dev/isolation`.

Release follow-through: complete the full CLI/container build and confirm publication of both repository commits before deployment. Agent push attempts were blocked by GitHub DNS resolution and connector HTTP 403; subsequent operator publication has not been verified here. No production data was changed and no deployment was performed as part of this milestone. Gamma bounds retained batches, not tree size.

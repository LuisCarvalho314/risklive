# Improvements Over Legacy

This document explains design decisions and justifies the shift from legacy `risklive/` to the current `src/` + `web/` implementation.

## Design Decisions and Justification

## 1) Orchestration: script-centric to stage-centric

- Legacy pattern: operational logic distributed across scripts and task functions.
- Current pattern: explicit stage functions in `src/services/pipeline.py`.
- Decision rationale: enforce clear boundaries (`fetch`, `save`, `extract`, `topic`, `report`, `dashboard_export`, `cleanup`).
- Improvement impact: predictable execution flow, easier selective reruns, simpler incident isolation.

## 2) Contracts: implicit schema to typed models

- Legacy pattern: CSV/DataFrame shape treated as implicit contract.
- Current pattern: typed models in `src/models/*` and explicit row conversions in `src/utils/rows.py`.
- Decision rationale: reduce silent schema drift and make lineage explicit.
- Improvement impact: safer changes, better tests, clearer onboarding for new engineers.

## 3) Logging: ad-hoc records to structured event contract

- Legacy pattern: mixed logging styles and weaker run correlation.
- Current pattern: standardized JSON logs via `src/utils/logging.py`.
- Decision rationale: make operational status machine-readable and composable.
- Improvement impact: `/ops` can derive real health from execution events, not guesses.

## 4) Operations: artifact inference to log-derived truth

- Legacy pattern: operator confidence often depended on artifact presence and manual checks.
- Current pattern: stage and schedule status computed from `pipeline_run_*`, `pipeline_stage_*`, and scheduler events.
- Decision rationale: artifacts can be stale; structured run events represent actual execution outcomes.
- Improvement impact: lower false positives and better operational trust.

## 5) UI and API boundaries: tighter coupling to explicit contracts

- Legacy pattern: dashboard paths more tightly coupled to direct data reading patterns.
- Current pattern: web app consumes typed API route outputs (`/api/dashboard`, `/api/ops/*`).
- Decision rationale: isolate presentation from source storage layout.
- Improvement impact: easier UI iteration, better test isolation, controlled backward compatibility.

## 6) Edge security: implicit exposure to explicit ops boundary

- Legacy pattern: less formalized operator endpoint boundary.
- Current pattern: Caddy edge layer protects `/ops` and `/api/ops/*` with auth.
- Decision rationale: keep operational telemetry restricted without deeply coupling auth logic into app code.
- Improvement impact: clearer security posture for internet-facing deployment.

## 7) Deployment: manual process patterns to reproducible topology

- Legacy pattern: local/manual startup variability.
- Current pattern: Docker Compose with app, web, and caddy services plus mounted persistence.
- Decision rationale: reproducibility and straightforward rollback behavior.
- Improvement impact: reduced environment drift and cleaner handoffs between engineers.

## 8) Testability: effectively untested to comprehensive test suite

- Legacy pattern: no meaningful comprehensive test suite coverage for end-to-end runtime confidence.
- Current pattern: broad unit and integration coverage across `src/` and `web/`, including pipeline and ops parsing/aggregation behavior.
- Decision rationale: prevent regressions during refactor and operational changes.
- Improvement impact: safer releases, faster incident triage, and higher confidence in behavior changes.

## 9) Groundwork for Agentic Workflow

Current architecture introduces foundational capabilities needed for agentic orchestration:

- stage boundaries in `src/services/pipeline.py`
- typed stage I/O in `src/models/*`
- adapter abstraction in `src/adapters/*`
- explicit agent modules in `src/agents/extraction` and `src/agents/report`
- structured telemetry suitable for supervision and state-aware recovery

This moves the system from monolithic script behavior toward composable execution primitives.

## Independent Future Paths (No forced coupling)

The following future paths are separate at present:

- Agentic Workflow path (execution and orchestration model)
- LangExtract path (Story Frame extraction and retrieval support)
- SECA-based path (external validated clustering alternative)

They may complement each other later, but none is currently a dependency of another.

### LangExtract as a separate improvement track

- Expected improvement: stronger same-story grouping signals and interpretability.
- Source note: `docs/LangExtract in RiskLive.md`.
- Runtime status in this repo: not currently active as primary flow.

### SECA as a separate improvement track

- Expected improvement: alternative event/topic clustering quality profile.
- Evidence status: external validated prototype in another project.
- Runtime status in this repo: not currently active.
- Potential business impact: higher quality same-story grouping and richer topic-change explainability for analysts and operators.
- Evaluation status in this repo: pending benchmark against current BERTopic path (see [SECA Evaluation Blueprint](./seca-evaluation-blueprint.md)).

## Required Changes (No Timeline)

## 1) Establish architecture governance

- Define one canonical architecture source.
- Assign owners and lifecycle state for major components.
- Mark legacy modules as retained, transitional, or deprecated.

## 2) Version and govern data contracts

- Version schemas for all production artifacts in `results/data/` and `results/web/`.
- Define compatibility and breaking-change policy.
- Require explicit origin or derivation for user-facing fields.

## 3) Add run lineage manifesting

- Persist per-run manifest linking inputs, outputs, prompt/model versions, and cost metrics.
- Ensure reproducibility of report/dashboard outcomes from a `run_id`.

## 4) Formalize SLO semantics

- Document freshness, success-rate, and duration criteria for each stage/job.
- Align `/ops` status labels directly to those criteria.

## 5) Standardize failure handling policy

- Define retry/backoff/escalation strategy per stage.
- Clarify fail-fast versus continue behavior and user-visible outcomes.

## 6) Harden security controls

- Define secrets lifecycle and rotation expectations.
- Apply least privilege for runtime credentials and ops access.
- Standardize audit expectations for operational access.

## 7) Formalize backup and restore

- Define protected datasets and retention policy.
- Document restore procedure and verification checks.

## 8) Enforce release quality gates

- Require tests, contract checks, and docs consistency before deploy.
- Prevent deployment when interface or observability contracts regress.

## 9) Track agentic readiness explicitly

- Define readiness checklist for idempotency, replayability, and supervision.
- Mark each pipeline stage as ready, partial, or blocked.

Back to orientation: [Onboarding Index](./index.md).

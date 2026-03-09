# RiskLive Onboarding Guide

This guide is the fastest path to understand how RiskLive works and why the current implementation differs from legacy.

## Status legend

- `Current Runtime`: implemented and used by this repository today
- `Legacy Baseline`: historical implementation retained for context
- `Future Path`: documented direction that is not active runtime
- `External Validated Prototype`: implemented outside this repository, validated externally, not integrated here

## What Is Legacy vs Current

- Legacy implementation (`Legacy Baseline`): `risklive/` package (older Flask/Streamlit/script-oriented flow)
- Current implementation (`Current Runtime`): `src/` (pipeline services + structured logging) and `web/` (Next.js UI and `/ops`)

## Future Paths (Separate for now)

RiskLive has three future paths that are independent at this stage:

- Agentic Workflow path (orchestration and execution control)
- LangExtract path (structured story-frame extraction)
- SECA-based path (alternative clustering method, `External Validated Prototype`)

These paths may intersect later, but there is no current requirement that any one path depends on another.

```mermaid
flowchart LR
    A[Current runtime]
    B[Agentic path]
    C[LangExtract path]
    D[SECA path]
    A --> B
    A --> C
    A --> D
```

## Improvement-First Summary

| Area | Legacy | Current | Why It Matters |
| --- | --- | --- | --- |
| Pipeline orchestration | Script/function coupling | Explicit stages in `src/services/pipeline.py` | Faster debugging and safer changes |
| Data contracts | Implicit CSV/DataFrame shape | Typed models in `src/models/*` | Fewer schema regressions |
| Logging | Mostly free-form | Structured JSON contract in `src/utils/logging.py` | Reliable ops health and incident analysis |
| Operations visibility | Manual/artifact inference | `/ops` computed from run/stage/scheduler logs | Status aligned with execution truth |
| Web delivery | Legacy dashboard patterns | Next.js app in `web/` + API routes | Better UX isolation and testability |
| Deployment boundary | Mostly process-level setup | Docker Compose + Caddy edge controls | Reproducibility and safer internet exposure |
| Test coverage | No comprehensive suite | Comprehensive unit and integration test suite | Safer releases and stronger regression protection |

## System Map

```mermaid
flowchart LR
    V[Valyu API]
    subgraph L[Legacy runtime risklive]
        L1[Legacy ingestion]
        L2[Legacy LLM extraction]
        L3[Legacy topic modeling]
        L4[Legacy report generation]
        L5[Legacy dashboard]
    end
    subgraph C[Current runtime src and web]
        C1[Pipeline fetch and save]
        C2[Pipeline extraction]
        C3[Pipeline topic and report]
        C4[Dashboard export]
        C5[Next.js UI and Ops]
    end
    V --> L1 --> L2 --> L3 --> L4 --> L5
    V --> C1 --> C2 --> C3 --> C4 --> C5
```

## Read Next

- [Legacy Baseline](./legacy-baseline.md)
- [Current Architecture](./current-architecture.md)
- [Improvements Over Legacy](./improvements-over-legacy.md)
- [Agentic Workflow Groundwork](./agentic-groundwork.md)
- [LangExtract Path](./langextract-path.md)
- [SECA Path](./seca-path.md)
- [SECA Evaluation Blueprint](./seca-evaluation-blueprint.md) (required decision gate before SECA adoption discussion)
- [Future Path Intersections](./future-path-intersections.md)

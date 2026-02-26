# Legacy Baseline (`risklive/`)

This document describes the legacy runtime so new team members can understand historical behavior and compare it to the current stack.

## Purpose

Legacy RiskLive ingests Valyu news, enriches rows with LLM extraction, clusters topics, generates report rows, and renders dashboard outputs from CSV artifacts under `results/`.

## Tech Stack (Legacy)

- Python
- Flask + APScheduler (`risklive/server`)
- Streamlit dashboards (`risklive/dashboard`)
- pandas-centric CSV processing
- BERTopic + HDBSCAN + sentence-transformers for topic modeling
- Azure OpenAI integrations in legacy data-processing modules

## Legacy Execution Paths

- API and scheduler: `python -m risklive.server.app`
- One-shot full run: `python -m risklive.jumpstart`
- Legacy dashboard path: modules under `risklive/dashboard/`

## Legacy End-to-End Data Flow

```mermaid
flowchart LR
    A[Valyu API]
    B[aggregate_regular_news]
    C[results data news_data.csv]
    D[process_df LLM extraction]
    E[results data news_data_with_llm_info.csv]
    F[compute_topic_modeling]
    G[results data df_with_response_and_topics.csv]
    H[get_report]
    I[results data df_report.csv]
    J[legacy dashboards]
    A --> B --> C --> D --> E --> F --> G --> H --> I --> J
```

## Legacy Sequence

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant T as risklive.server.tasks
    participant V as Valyu API
    participant L as LLM provider
    participant FS as results folder
    participant UI as Legacy dashboard

    S->>T: save_regular_news
    T->>V: fetch articles
    V-->>T: article list
    T->>FS: write news_data.csv

    S->>T: llm_info_extraction
    T->>L: enrich row text
    L-->>T: structured extraction
    T->>FS: write news_data_with_llm_info.csv

    S->>T: compute_save_topic_model
    T->>FS: write df_with_response_and_topics.csv

    S->>T: generate_report
    T->>L: summarize red topics
    L-->>T: report text
    T->>FS: write df_report.csv

    UI->>FS: read CSV artifacts
```

## Legacy Field Lineage

```mermaid
flowchart TD
    A[Valyu fields title url description query]
    B[news_data.csv]
    C[LLM response fields]
    D[news_data_with_llm_info.csv]
    E[topic assignment]
    F[df_with_response_and_topics.csv]
    G[report grouping red alerts by topic]
    H[df_report.csv]

    A --> B
    B --> C --> D
    D --> E --> F
    F --> G --> H
```

## Legacy Logging and Ops Behavior

- Logging exists but is less standardized than current structured contracts.
- Operational state is often inferred from file outputs and process logs rather than strict stage-event semantics.
- Incident triage can require manual interpretation across scripts.

## Legacy Constraints

- Weaker stage boundaries and less explicit contracts.
- More implicit assumptions in CSV schema and DataFrame operations.
- Harder to derive reliable health from logs alone.

This baseline is the reference point for understanding improvements in the current implementation.

Back to orientation: [Onboarding Index](./index.md).

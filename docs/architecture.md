# RiskLive System Architecture

## Overview
RiskLive is a news-driven risk analysis pipeline for the nuclear industry. It ingests news via the Valyu API, enriches articles with LLM-based extraction, performs topic modeling, and produces summaries and visualizations. The deployed runtime is the legacy pipeline under `risklive/`. The refactor under `src/` mirrors the flow but is not the currently deployed system.

## Codebase Versions
- **Deployed (current production)**: `risklive/` (Flask + APScheduler + Streamlit).
- **Next (in refactor)**: `src/` (services-based pipeline, typed models, Pydantic-AI adapters).

## High-Level Information Flow (Deployed)
1. **Ingest**: Queries from `config/config.yml` are sent to Valyu to fetch recent news.
2. **Persist raw**: Articles are normalized into CSV rows and stored in `results/data/news_data.csv`.
3. **Extract (LLM)**: Title/description pairs are passed to an Azure OpenAI model to produce structured extraction (`LLMEnrichedRow`).
4. **Persist enriched**: Enriched rows are stored in `results/data/news_data_with_llm_info.csv`.
5. **Topic modeling**: BERTopic clusters keywords into topics and stores artifacts/models.
6. **Report**: Red-flagged topic clusters are summarized into report entries.
7. **Visualize**: Plotly/BERTopic assets are saved for dashboards or further analysis.

## Component Map (Deployed)

### Entry Points
- `risklive/server/app.py`: Flask API with scheduled jobs and `/trigger/*` routes.
- `risklive/server/tasks.py`: Orchestrates ingest, extraction, modeling, reporting.
- `risklive/jumpstart.py`: One-shot pipeline run.
- `risklive/dashboard/alerts.py`: Streamlit dashboard reading `results/data/news_data_with_llm_info.csv`.

### Core Services (Deployed)
- `risklive/data_extraction/valyu_api.py` -> Valyu ingestion, writes `news_data.csv`.
- `risklive/data_processing/info_extraction.py` -> LLM extraction, writes `news_data_with_llm_info.csv`.
- `risklive/topic_modeling/train_model.py` -> BERTopic training + visualization artifacts.
- `risklive/topic_modeling/make_report.py` -> report generation, writes `df_report.csv`.
- `risklive/server/data_maintenance.py` -> cleanup + backups.

### Agents (Deployed)
- `risklive/data_processing/lm.py`: Azure OpenAI client and API calls.
- `risklive/data_processing/info_extraction.py`: prompt formatting + structured extraction.
- Prompts resolved via `risklive/config.py` using `config/config.yml`.

### Adapters (Deployed)
- `risklive/data_extraction/valyu_api.py`: Valyu API wrapper.

## Detailed Flow by Stage (Deployed)

### 1) Ingestion
- **Input**: Query list from `config/config.yml` (`CATEGORIES`, `QUERIES`, optional `TRENDING`).
- **Processing**: `risklive/data_extraction/valyu_api.py` aggregates news and writes CSV.
- **Output**: `results/data/news_data.csv`.

### 2) Raw Storage
- **Input**: Valyu results.
- **Processing**: `risklive/data_extraction/valyu_api.py` formats rows with `Title`, `URL`, `Description`, `Timestamp`, `Query`.
- **Output**: `results/data/news_data.csv`.

### 3) LLM Extraction
- **Input**: `results/data/news_data.csv`.
- **Processing**: `risklive/data_processing/info_extraction.py` calls Azure OpenAI and enriches rows.
- **Output**: `results/data/news_data_with_llm_info.csv`.

### 4) Topic Modeling
- **Input**: `results/data/news_data_with_llm_info.csv`.
- **Processing**: `risklive/topic_modeling/train_model.py` (SentenceTransformers + HDBSCAN + BERTopic).
- **Output**:
  - `results/models/topic_model/` (BERTopic model)
  - `results/data/df_with_response_and_topics.csv`
  - `results/images/*.json`, `results/images/treemap.pkl`, `results/images/topic_tree.txt`

### 5) Report Generation
- **Input**: `results/data/df_with_response_and_topics.csv`.
- **Processing**: `risklive/topic_modeling/make_report.py` aggregates Red alerts by topic and calls Azure OpenAI.
- **Output**: `results/data/df_report.csv`.

### 6) Visualizations
- **Input**: Topic model and `df_with_response_and_topics.csv`.
- **Processing**: `risklive/topic_modeling/train_model.py` generates Plotly JSON, hierarchy artifacts, and treemaps.
- **Output**: `results/images/*.json`, `results/images/treemap.pkl`, `results/images/topic_tree.txt`.

## Runbook (Deployed)
- **Start API + scheduler**: `python -m risklive.server.app` (starts Flask + APScheduler).
- **Run once (full pipeline)**: `python -m risklive.jumpstart`.
- **Dashboard**: `streamlit run risklive/dashboard/alerts.py`.

## Data Freshness and Authority (Deployed)
- **Scheduler cadence**: daily fetch at 07:00, report generation at 07:30, cleanup at 06:30.
- **Dashboard source of truth**: `results/data/news_data_with_llm_info.csv`.
- **Reporting source of truth**: `results/data/df_report.csv`.
- **Topic modeling source of truth**: `results/models/topic_model/` and `results/data/df_with_response_and_topics.csv`.

## Data Contracts (Key Models)
- Deployed pipeline uses loose dict/CSV schemas rather than explicit Pydantic models.
- `news_data.csv` is the primary contract for ingestion output.
- `news_data_with_llm_info.csv` is the primary contract for LLM enrichment output.
- Refactor introduces explicit Pydantic models in `src/models/*` for CSV rows and LLM outputs.

## Data Lineage and CSV Schemas

### Deployed version (`risklive/`)
1. `results/data/news_data.csv`
   Columns: `Title`, `URL`, `Description`, `Timestamp`, `Query` (from Valyu extraction).
2. `results/data/news_data_with_llm_info.csv`
   Adds extraction fields:
   `LLM_Response`, `LLM_Price`, `LLM_Token_Usage`, `PromptTokens`, `CompletionTokens`, `TotalTokens`,
   `RelevantKeywords`, `ShortSummary`, `Relevance`, `RelevanceReason`, `AlertFlag`, `AlertReason`,
   `NewsCategory`, `API_Timestamp`
3. `results/data/df_with_response_and_topics.csv`
   Adds `topic` assignments from BERTopic.
4. `results/data/df_report.csv`
   Columns: `topic`, `keyword`, `input_prompt`, `response`, `price`, `token_usage`

### Next version (`src/`)
1. `results/data/news_data.csv`
   Columns (from `models.csv.NewsRow`):
   `Title`, `URL`, `Description`, `Timestamp`, `Query`
2. `results/data/news_data_with_llm_info.csv`
   Extends the above with:
   `LLM_Response`, `LLM_Price`, `LLM_Token_Usage`, `PromptTokens`, `CompletionTokens`, `TotalTokens`,
   `RelevantKeywords`, `ShortSummary`, `Relevance`, `RelevanceReason`, `AlertFlag`, `AlertReason`,
   `NewsCategory`, `API_Timestamp`, `topic`
3. `results/data/df_with_response_and_topics.csv`
   Topic model output with `topic` assignments added (superset of enriched fields).
4. `results/data/df_report.csv`
   Columns: `topic`, `keyword`, `input_prompt`, `response`

## Configuration and Secrets
- `config/config.yml`: query definitions, prompt paths, intervals, save locations, Valyu runtime limits.
- `.env` (required):
  - `VALYU_API_KEY`
  - `OPENAI_API_BASE` or `AZURE_OPENAI_ENDPOINT`
  - `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY`
  - `OPENAI_API_VERSION` or `AZURE_OPENAI_API_VERSION`
- Deployed config loader: `risklive/config.py`.
- Refactor config loader: `src/config/settings.py`.

## Runtime Modes (Deployed)
- **API**: `risklive/server/app.py` exposes `/trigger/*` routes and runs APScheduler.
- **Scheduler**: daily fetch at 07:00, report generation at 07:30, cleanup at 06:30.
- **Dashboard**: `risklive/dashboard/alerts.py` (Streamlit) reads CSV outputs.
- **One-shot**: `risklive/jumpstart.py` runs the full pipeline once.

## Storage and Dependencies
- **Storage**: CSV and model artifacts under `results/` (configurable via `SAVE_DIR`).
- **External services**:
  - Valyu (news search).
  - Azure OpenAI via `openai.AzureOpenAI` (deployed) or `pydantic_ai` (refactor).
- **Key Python libraries**:
  - Flask, APScheduler, Streamlit.
  - BERTopic, HDBSCAN, SentenceTransformers, UMAP, Plotly, pandas.

## Observability
- Deployed pipeline uses `risklive/utils/logging_config.py` with a rotating `logs/app.log`.
- Valyu adapter logs fetch parameters and result counts.
- Refactor uses `utils.logging.configure_logging` (CLI enables it).

## Changes From Deployed to Refactor (Why and Tradeoffs)

### Summary of Changes
- **Service boundaries**: deployed functions in `risklive/` were split into explicit services under `src/services`.
- **Typed models**: `models.csv` and `models.*` introduce structured data contracts in the refactor.
- **LLM client**: refactor uses `pydantic_ai` agents in `src/agents` instead of direct `openai.AzureOpenAI` calls.
- **Storage helpers**: refactor centralizes path handling and CSV IO in `services.storage`.
- **Topic modeling**: refactor moved topic modeling to `services/topic_modeling` with explicit configuration and run metadata.
- **Orchestration**: refactor standardizes around `src/app/cli.py` and `src/app/server.py`.

### Rationale, Pros, and Cons
- **Services-based pipeline**: Pros are clearer separation of concerns and easier testing/swapping; cons are more indirection and more files to trace.
- **Typed models and validation**: Pros are consistent schema handling and safer URL/timestamp parsing; cons are added boilerplate and dependency on Pydantic.
- **Pydantic-AI agents**: Pros are structured outputs and reusable agents; cons are tighter coupling to the Pydantic-AI API and provider config.
- **Centralized storage utilities**: Pros are consistent data/backup paths and reuse; cons are CSV persistence and lack of transactions.
- **Topic modeling split**: Pros are explicit training and visualization steps; cons are a hard dependency on prior artifacts for visualization.

### New Features in `src/`
- **URL-based deduping** when writing CSVs (`services.pipeline._dedupe_rows`).
- **Per-run metadata** for topic modeling (`results/images/run_metadata.json`).
- **Selective visualizations**: topics-over-time is only generated when timestamp data is valid.
- **Configurable save directories** via `config/config.yml` and `services.storage`.

## Operational Notes and Failure Modes
- **Valyu ingestion**: network failures or empty responses lead to missing rows; the pipeline continues without raising unless the caller enforces it.
- **LLM extraction**: failures produce empty/None fields in CSV; the pipeline still persists rows (legacy version retries once with a 60s delay on 429).
- **Topic modeling**: requires non-empty `RelevantKeywords`; otherwise model training will fail.
- **Report generation**: requires `topic` column and `AlertFlag == "Red"`; otherwise report output is empty.
- **Cleanup**: rows with invalid timestamps are dropped during cleanup; backups go to `results/backup_data/`.

## Failure Recovery (Deployed)
- **Re-run extraction only**: run `risklive/data_processing/info_extraction.py` against the current `news_data.csv`.
- **Re-run topic modeling only**: run `risklive/topic_modeling/train_model.py` against `news_data_with_llm_info.csv`.
- **Re-run report only**: run `risklive/topic_modeling/make_report.py` against `df_with_response_and_topics.csv`.

## Security and Secrets
- `.env` must exist at the repo root for deployed runs. Missing keys will cause ingestion or LLM calls to fail.
- Avoid committing `.env` and any generated CSVs that include sensitive metadata or pricing/tokens.

## Known Gaps / Mismatches
- **Deployed**: `risklive/HKT/` is not wired into the pipeline and can be treated as standalone.
- **Refactor**:
  - `apps/api.py` imports `services.api.create_app`, but the actual Flask app lives in `src/app/server.py`.
  - `apps/worker.py` imports `services.worker.run_once`, but no `services/worker.py` exists.
  - `apps/scheduler.py` imports `services.scheduler.run_scheduler`, but no `services/scheduler.py` exists.

## Extension Points
- Swap Valyu with other ingest providers via `src/adapters`.
- Adjust prompts via `prompts/` and `config/config.yml`.
- Replace CSV storage with a database by reworking `services.storage`.

## Refactor Architecture (src/)

### Refactor Entry Points
- `src/app/cli.py`: CLI runner for fetch/extract/topic/visualize/report/full/cleanup.
- `src/app/server.py`: Flask API and scheduler (daily fetch at 07:00, cleanup at 06:30).
- `src/dashboard/alerts.py`: Streamlit alert dashboard.
- `apps/*`: Legacy runners that reference missing `services.*` modules (see Known Gaps).

### Refactor Services and Agents
- `src/services/pipeline.py`: end-to-end orchestration functions.
- `src/services/ingestion.py` + `src/adapters/valyu.py`: Valyu ingestion.
- `src/services/extraction.py` + `src/agents/extraction/agent.py`: LLM extraction.
- `src/services/reporting.py` + `src/agents/report/agent.py`: report generation.
- `src/services/topic_modeling/*`: modeling and visualization artifacts.
- `src/services/storage.py`: CSV IO, data and backup paths.

### Refactor Data Contracts
- `src/models/csv.py` defines `NewsRow` and `LLMEnrichedRow` with validation and alias mapping.
- `src/models/extraction.py` defines `ExtractionResult` and token usage fields.
- `src/models/report.py` defines `ReportEntry`.

## Future Work
- **Refactor CLI**:
- **Refactor dashboard**:
- **Refactor tests**:
- **Refactor logging**:
- **Refactor monitoring**:
- **Refactor secrets**:
- **Refactor storage**:
- **Refactor topic modeling**:
- **Refactor visualization**:
- **Refactor deployment**:
- **Refactor documentation**:
- **Refactor CI/CD**:
- **Refactor monitoring**:

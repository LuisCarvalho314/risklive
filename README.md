# RiskLive

RiskLive is a real-time risk analysis dashboard for the nuclear industry. It aggregates news and data from various sources, processes the information using advanced natural language processing techniques, and presents insights through an interactive web interface.

## Status

RiskLive currently runs on the `src/` + `web/` stack documented under `docs/onboarding/`.

- `Current Runtime`: `src/` services pipeline and `web/` Next.js app with `/ops`
- `Legacy Baseline`: historical `risklive/` implementation retained for context
- `Experimental Runtime`: persistent SECA-Light model with bounded source memory and historical views for `/newsmap-experimental`
- `Future Paths` (separate, not active runtime): Agentic Workflow and LangExtract

Recorded milestone: [SECA production path corrected to persistent SECA-Light](docs/milestones.md#seca-production-path-corrected-to-persistent-seca-light).

## Features

- Real-time news aggregation from multiple sources
- Automated information extraction using LLM (Large Language Models)
- Topic modeling for trend analysis
- Interactive web dashboard for data visualization
- Scheduled tasks for regular data updates and maintenance

## Technology Stack

- Python
- Flask served by Gunicorn in containers; dedicated foreground APScheduler process
- Pandas for data manipulation
- OpenAI's API for LLM-based processing
- Bing API for news aggregation
- APScheduler for task scheduling

## Project Structure
```
risklive/
├── apps/                 # Entry points (api, worker, scheduler, dashboard)
├── config/               # Defaults, logging, prompts
├── docs/                 # Architecture notes
├── src/                  # Python package (risklive)
├── tests/                # Unit and integration tests
├── runtime/              # Local runtime data (ignored by git)
├── .env
├── docker/
├── deployment/
├── pyproject.toml
└── README.md
```

- `apps/`: Runtime entry points for services
- `src/`: Main package source code (services pipeline, adapters, models, app entrypoints)
- `config/`: Configuration files and prompts
- `runtime/`: Generated data and artifacts (ignored)

## Installation

RiskLive uses `uv` for environment and dependency management.

1. Install `uv` (if not already installed):
   ```
   pip install uv
   ```

2. Clone the repository:
   ```
   git clone https://github.com/yourusername/risklive.git
   cd risklive
   ```

3. Create the virtual environment and sync dependencies from `pyproject.toml`/`uv.lock`:
   ```
   uv sync
   ```

4. Run commands inside the managed environment:
   ```
   uv run risklive --help
   ```

If you need a shell in the virtual environment, use:
```
uv shell
```

## Configuration

- `config/config.yml`: Main configuration file
- `.env`: Environment-specific secrets and API keys

## Operations Access Control

The current deployment serves HTTP on host port 8888 without Caddy basic
authentication, following the existing Azure/network access boundary.

- Caddy template: [`deployment/caddy/Caddyfile.prod`](deployment/caddy/Caddyfile.prod)
- Access configuration: [`docs/ops-auth-caddy.md`](docs/ops-auth-caddy.md)

## Docker Deployment

For single-VPS Docker orchestration (Python app + Next web + Caddy), use:

- Runbook and CI release gate: [`docs/deployment-docker.md`](docs/deployment-docker.md)
- Compose stack: `deployment/compose/docker-compose.prod.yml`
- SECA investigation, measurements and offline regeneration: [`docs/seca-timeline-hardening.md`](docs/seca-timeline-hardening.md)

Require the existing GitHub Actions backend/frontend checks to pass for the
release commit before production promotion. The workflow validates code and
builds Next.js; it does not publish Docker images or deploy production. Keep the
fetching scheduler stopped while API credits are unavailable; the general
deployment helper starts it along with the serving containers.

## Onboarding Documentation

For legacy and current implementation onboarding, start with:

- [`docs/onboarding/index.md`](docs/onboarding/index.md)
- [`docs/onboarding/legacy-baseline.md`](docs/onboarding/legacy-baseline.md)
- [`docs/onboarding/current-architecture.md`](docs/onboarding/current-architecture.md)
- [`docs/onboarding/improvements-over-legacy.md`](docs/onboarding/improvements-over-legacy.md)
- [`docs/onboarding/agentic-groundwork.md`](docs/onboarding/agentic-groundwork.md)
- [`docs/onboarding/langextract-path.md`](docs/onboarding/langextract-path.md)
- [`docs/onboarding/seca-path.md`](docs/onboarding/seca-path.md)
- [`docs/onboarding/seca-evaluation-blueprint.md`](docs/onboarding/seca-evaluation-blueprint.md)
- [`docs/onboarding/future-path-intersections.md`](docs/onboarding/future-path-intersections.md)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

© 2025 University of Aberdeen. All rights reserved

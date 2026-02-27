# RiskLive

RiskLive is a real-time risk analysis dashboard for the nuclear industry. It aggregates news and data from various sources, processes the information using advanced natural language processing techniques, and presents insights through an interactive web interface.

## Status

RiskLive currently runs on the `src/` + `web/` stack documented under `docs/onboarding/`.

- `Current Runtime`: `src/` services pipeline and `web/` Next.js app with `/ops`
- `Legacy Baseline`: historical `risklive/` implementation retained for context
- `Future Paths` (separate, not active runtime): Agentic Workflow, LangExtract, and SECA

## Features

- Real-time news aggregation from multiple sources
- Automated information extraction using LLM (Large Language Models)
- Topic modeling for trend analysis
- Interactive web dashboard for data visualization
- Scheduled tasks for regular data updates and maintenance

## Technology Stack

- Python
- Flask for web server
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
├── Dockerfile
├── docker-compose.yml
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

If you expose an operations UI (for example `/ops`), protect it at the reverse proxy.

- Caddy template: [`deployment/caddy/Caddyfile.ops.example`](/Users/lcarv/PycharmProjects/risklive/deployment/caddy/Caddyfile.ops.example)
- Setup guide: [`docs/ops-auth-caddy.md`](/Users/lcarv/PycharmProjects/risklive/docs/ops-auth-caddy.md)

## Docker Deployment

For single-VPS Docker orchestration (Python app + Next web + Caddy), use:

- Runbook: [`docs/deployment-docker.md`](/Users/lcarv/PycharmProjects/risklive/docs/deployment-docker.md)
- Compose stack: `deployment/compose/docker-compose.prod.yml`

## Onboarding Documentation

For legacy and current implementation onboarding, start with:

- [`docs/onboarding/index.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/index.md)
- [`docs/onboarding/legacy-baseline.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/legacy-baseline.md)
- [`docs/onboarding/current-architecture.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/current-architecture.md)
- [`docs/onboarding/improvements-over-legacy.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/improvements-over-legacy.md)
- [`docs/onboarding/agentic-groundwork.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/agentic-groundwork.md)
- [`docs/onboarding/langextract-path.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/langextract-path.md)
- [`docs/onboarding/seca-path.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/seca-path.md)
- [`docs/onboarding/seca-evaluation-blueprint.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/seca-evaluation-blueprint.md)
- [`docs/onboarding/future-path-intersections.md`](/Users/lcarv/PycharmProjects/risklive/docs/onboarding/future-path-intersections.md)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

© 2025 University of Aberdeen. All rights reserved

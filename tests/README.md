# Test Suite Layout

This repository organizes tests by production domain, mirroring `src/`.

## Structure

- `tests/unit/adapters/`
- `tests/unit/agents/`
- `tests/unit/app/`
- `tests/unit/config/`
- `tests/unit/models/`
- `tests/unit/services/`
- `tests/unit/utils/`
- `tests/regression/` archived data and contract regression checks
- `tests/integration/` broader integration checks
- `tests/fixtures/` shared test helpers/builders/contracts/stubs

## Conventions

- Prefer module-focused test files over catch-all files.
- Reuse helpers from `tests/fixtures/` for archive loading and contracts.
- Keep unit tests offline and deterministic; stub external API calls.
- Use pytest markers:
  - `unit`
  - `integration`
  - `regression`

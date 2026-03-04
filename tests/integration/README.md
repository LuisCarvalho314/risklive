# Integration Tests

Integration tests validate end-to-end local wiring across services with real file I/O
and serialization, while staying offline and deterministic.

## Scope

- Pipeline flow from staged CSV input data to report/dashboard artifacts.
- Contract validation for generated CSV/JSON outputs.

## Rules

- Must not call external network dependencies (Valyu/Azure/OpenAI).
- Use deterministic stubs only at external boundaries.
- Use isolated `tmp_path` workspaces and never write outside test workspace.

## Running

- Integration only: `pytest -m integration -q`
- Exclude integration: `pytest -m \"not integration\" -q`

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

## Frozen archive and isolation

Integration and regression tests default to the small sanitized snapshot in
`tests/fixtures/archive/`; see its README for provenance, selection and contracts.
No VM backup, production files or live credentials are required. Snapshot files
are copied into each test's temporary workspace; dashboard time is fixed.

Run with `VIRTUAL_ENV` unset, `DISABLE_SCHEDULER=true` and dummy credentials:

```sh
env -u VIRTUAL_ENV DISABLE_SCHEDULER=true \
  VALYU_API_KEY=test-valyu-key OPENAI_API_KEY=test-openai-key \
  OPENAI_API_BASE=https://example.openai.azure.com \
  OPENAI_API_VERSION=2024-10-21 .venv/bin/pytest --no-cov tests
```

Global test guards reject network connections/listeners, subprocesses, production
filesystem access and writes outside temporary storage. Model-library sentinels
prevent inference/downloads, and background thread starts fail. Pytest's local
cache is disabled and bytecode writes are disabled during collection. Tests stub
external boundaries explicitly. Guards are Python-level backstops, not an OS
sandbox for arbitrary native code.

For manual experiments only, `extract_archive_to_workspace(explicit_archive_path,
workspace_root)` remains available to callers. It is not selected by an environment
variable or normal pytest execution; latest-archive discovery was removed.
`risklive/test_tasks.py` is outside pytest.ini's `testpaths = tests`.

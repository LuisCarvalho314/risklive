# Offline SECALight V2 adapter

`src/services/seca_v2.py` is opt-in and has no pipeline or scheduling hook.
Rust owns `runtime/seca/v2/state.json`. Do not run the Rust CLI directly against
that file: this adapter must be its sole writer, using `update.lock`.

## Configuration

`config/seca_v2.json` uses V2's native schema:

```json
{
  "alpha": 0.7,
  "beta": 0.5,
  "error_limits": {"alpha": 0.1, "beta": 0.2, "importance": 0.3},
  "minimum_branch_sources": 10,
  "window": 3
}
```

These are provisional experimental RiskLive settings, not a validated optimum.
Window 3 retains three logical batches of evidence; the learned hierarchy
continues across updates. Configuration changes require a separate runtime and replay.

## Local commands

Install the two executables on PATH or set absolute paths:

```bash
export RISKLIVE_SECA_V2_CLI=/absolute/path/to/seca-v2-cli
export RISKLIVE_SECA_CLI=/absolute/path/to/realtime-seca-cli
export PYTHONPATH=src

python -m services.seca_v2 bootstrap --root /tmp/risklive-v2-replay \
  --csv tests/fixtures/archive/news_data_with_llm_info.csv
python -m services.seca_v2 update --root /tmp/risklive-v2-replay \
  --csv tests/fixtures/archive/news_data_with_llm_info.csv --date 2026-10-28
python -m services.seca_v2 show-last --root /tmp/risklive-v2-replay
```

`--csv` is repeatable. Without it, the adapter reads the existing enriched CSV
and backup CSV beneath `--root`. No enrichment, searches, or LLM calls occur.
The V1 executable is used only for `from-csv`: title, short summary and description,
existing English stop words, and existing tokenization. V2 receives sorted unique
words, with URL identities matching the existing timeline; URL-less records use
a deterministic hash of the existing title/timestamp row key.

Bootstrap processes exactly three UTC calendar days ending on the latest relevant
archived article date, or on `--date` when supplied. Indices begin at zero.
Older archived articles are excluded from these initial three batches. Subsequent
updates accept all unseen articles dated at or before the next uncommitted day,
including older arrivals, and fill each missing calendar day with a batch.
`update` defaults to today's UTC date; `--date` makes replay independent of the clock.
An update for an already committed date returns the latest summary without advancing.
Late articles wait until the next uncommitted date. The first eligible record per
source ID wins permanently, even after Rust forgets its evidence.

Output is V2's JSON report: batch indices, retained count, recursive `root` HKT,
and reconstruction `decisions`. `show-last` also recovers pending receipts; it
can finish a previously prepared update. No model is duplicated in SQLite.

## Ledger and recovery

`runtime/seca/v2/ledger.sqlite3` uses standard-library sqlite3, FULL synchronous
writes, and two tables:

```sql
CREATE TABLE batches (
    sequence INTEGER PRIMARY KEY, day TEXT NOT NULL UNIQUE,
    input TEXT NOT NULL, input_hash TEXT NOT NULL, config TEXT NOT NULL,
    previous_hash TEXT, state_hash TEXT, result_hash TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending','committed'))
);
CREATE TABLE sources (
    id TEXT PRIMARY KEY, sequence INTEGER NOT NULL REFERENCES batches(sequence)
);
```

The batch JSON is stored once with its SHA-256 hash, native configuration and
preceding state hash before Rust runs. A successful update must agree with
`show-last`; its exact retained evidence must match the prepared ledger inputs.
Only then does a SQLite transaction commit the receipt and source IDs. Receipts
store state/result hashes, not a copy of the scientific model or HKT.

Recovery holds the same exclusive nonblocking flock as updates. It validates
consecutive indices/dates, input hashes, configuration, source uniqueness and the
source ledger. If a pending batch still has the preceding state hash, it runs
that exact prepared input. If Rust has advanced, `show-last`, batch/config identity,
and exact retained evidence establish the pending receipt before finalization.
This also handles empty batches. No committed update is rerun. Missing, changed,
or incompatible state/receipts fail closed; preserve both files for investigation.

This protocol assumes exclusive ownership of the state by the adapter. V2 does
not record an input hash or logical date; an unrelated external writer producing
the same batch/config/evidence cannot be distinguished during pending recovery.
Do not edit or replace a pending state manually. Back up the whole V2 runtime
under its lock. V1's stream database is never opened.

## Tests

The normal repository audit guard intentionally forbids subprocesses. Run the
real Rust integration suite separately without loading the parent conftest:

```bash
PYTHONPATH=src:. .venv/bin/pytest --confcutdir=tests/integration \
  tests/integration/test_seca_v2.py --no-cov
```

Set the executable environment variables above. For this checkout, binaries can
be built offline in the existing V2 source worktree:

```bash
cd .worktrees/seca-v2-build/experimental
cargo build --offline -p realtime-seca-v2 --bin seca-v2-cli \
  -p realtime-seca-cli --bin realtime-seca-cli
```

Tests require real binaries (missing prerequisites fail), use archived fixtures
and synthetic rows, and keep all state in pytest's temporary directories.
They make no network or LLM calls. The regular guarded test run skips this
subprocess suite; the separate command runs it in full. The adapter does not
install or pin the Rust binaries; a compatible V2 build and V1 converter remain
local runtime prerequisites.

"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
import uuid
import fcntl
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.logging import get_logger, log_artifact_written, pipeline_stage

logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_seca_command(seca_root: Path | None) -> list[str]:
    """Prefer standalone installs; Cargo is only a source-workspace fallback."""
    override = os.getenv("RISKLIVE_SECA_CLI", "").strip()
    if override:
        return [override]

    installed = shutil.which("realtime-seca-cli")
    if installed:
        return [installed]

    if seca_root is not None:
        for profile in ("release", "debug"):
            candidate = seca_root / "target" / profile / "realtime-seca-cli"
            if candidate.is_file():
                return [str(candidate)]
        if (seca_root / "Cargo.toml").is_file() and shutil.which("cargo"):
            return ["cargo", "run", "-p", "realtime-seca-cli", "--"]

    raise FileNotFoundError(
        "realtime-seca-cli not found (set RISKLIVE_SECA_CLI, install realtime-seca-cli, "
        "or use a SECA source workspace with cargo)"
    )


def _seca_working_directory(command: list[str], seca_root: Path | None) -> Path | None:
    # Explicit/PATH/source binaries consume absolute inputs and need no source cwd.
    # Only cargo needs the workspace manifest in its working directory.
    return seca_root if command[:2] == ["cargo", "run"] else None


def _llm_input_paths(root: Path) -> list[Path]:
    return [
        root / "results" / "data" / "news_data_with_llm_info.csv",
        root / "results" / "backup_data" / "news_data_with_llm_info.csv",
    ]


def _row_key(row: dict[str, str]) -> str:
    url = (row.get("URL") or "").strip()
    ts = (row.get("Timestamp") or "").strip()
    title = (row.get("Title") or "").strip()
    if url:
        return f"url:{url}"
    return f"title:{title}|ts:{ts}"


def _collect_relevant_rows(paths: list[Path]) -> tuple[int, int, list[dict[str, str]]]:
    # Two streaming passes: retain only the widest source window in memory.
    # Anchor to the latest observation, allowing offline replay of archived news.
    latest: datetime | None = None
    for csv_path in paths:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Relevance") or "").strip().lower() != "yes":
                    continue
                timestamp = _row_timestamp(row)
                if timestamp is not None and (latest is None or timestamp > latest):
                    latest = timestamp
    cutoff = _window_start(latest, days=30) if latest is not None else None
    total_rows = 0
    relevant_rows: list[dict[str, str]] = []
    seen: dict[str, int] = {}
    deduped_rows = 0

    for csv_path in paths:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                total_rows += 1
                relevance = (row.get("Relevance") or "").strip().lower()
                if relevance != "yes":
                    continue
                timestamp = _row_timestamp(row)
                if cutoff is None or timestamp is None or timestamp < cutoff:
                    continue
                key = _row_key(row)
                duplicate_index = seen.get(key)
                if duplicate_index is not None:
                    deduped_rows += 1
                    previous_timestamp = _row_timestamp(relevant_rows[duplicate_index])
                    if (
                        previous_timestamp is not None
                        and timestamp <= previous_timestamp
                    ):
                        continue
                normalized_row = {
                    "Title": (row.get("Title") or "").strip(),
                    "URL": (row.get("URL") or "").strip(),
                    "Description": (row.get("Description") or "").strip(),
                    "Timestamp": (row.get("Timestamp") or "").strip(),
                    "ShortSummary": (row.get("ShortSummary") or "").strip(),
                    "API_Timestamp": (row.get("API_Timestamp") or "").strip(),
                    "Query": (row.get("Query") or "").strip(),
                    "NewsCategory": (row.get("NewsCategory") or "").strip(),
                    "AlertFlag": (row.get("AlertFlag") or "").strip(),
                    "Relevance": "Yes",
                }
                if duplicate_index is None:
                    seen[key] = len(relevant_rows)
                    relevant_rows.append(normalized_row)
                else:
                    relevant_rows[duplicate_index] = normalized_row
    return total_rows, deduped_rows, relevant_rows


def _parse_timestamp(value: str) -> datetime | None:
    ts = value.strip()
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _row_timestamp(row: dict[str, str]) -> datetime | None:
    return _parse_timestamp(row.get("Timestamp") or "") or _parse_timestamp(
        row.get("API_Timestamp") or ""
    )


def _window_start(latest: datetime, *, days: int) -> datetime:
    if days < 1:
        raise ValueError("timeline days must be positive")
    # N UTC calendar days, including the latest source day (not N+1 days).
    return latest.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days - 1
    )


def _rolling_window_rows(
    rows: list[dict[str, str]], *, days: int
) -> list[dict[str, str]]:
    stamped: list[tuple[dict[str, str], datetime]] = []
    for row in rows:
        parsed = _row_timestamp(row)
        if parsed is not None:
            stamped.append((row, parsed))
    if not stamped:
        return []
    max_ts = max(ts for _, ts in stamped)
    cutoff = _window_start(max_ts, days=days)
    return [row for row, ts in stamped if ts >= cutoff]


def _group_rows_by_utc_day(
    rows: list[dict[str, str]],
) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        parsed = _row_timestamp(row)
        if parsed is None:
            continue
        day = parsed.date().isoformat()
        grouped.setdefault(day, []).append(row)
    return [(day, grouped[day]) for day in sorted(grouped.keys())]


def _write_relevant_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Title",
        "URL",
        "Description",
        "Timestamp",
        "ShortSummary",
        "API_Timestamp",
        "Query",
        "NewsCategory",
        "AlertFlag",
        "Relevance",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _identify_sources(batch_path: Path, *, variant_name: str, batch_index: int) -> int:
    # Only our freshly converted, window-filtered batch is read here. Never
    # inspect existing verbose trees. Synthetic row_N IDs otherwise resolve to
    # unrelated historical rows in the frontend's full CSV source lookup.
    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    for source in payload["sources"]:
        metadata = source.get("metadata") or {}
        url = (metadata.get("URL") or "").strip()
        source["source_id"] = (
            url or "article:" + hashlib.sha256(_row_key(metadata).encode()).hexdigest()
        )
    batch_path.write_text(json.dumps(payload), encoding="utf-8")
    return len(payload["sources"])


def _publish_timeline(staged: Path, output: Path) -> None:
    """Replace a complete generation; preserve the previous one on failure."""
    previous = staged.parent / "previous"
    if output.exists():
        output.rename(previous)
    try:
        staged.rename(output)
    except Exception:
        if previous.exists():
            previous.rename(output)
        raise
    if previous.exists():
        shutil.rmtree(previous)


def _open_stream(root: Path) -> sqlite3.Connection:
    """State, ingestion receipts and history have one transactional commit point."""
    directory = root / "runtime" / "seca"
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "stream.sqlite3", timeout=30)
    db.execute("PRAGMA synchronous=FULL")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1):
        db.close()
        raise ValueError(f"Unsupported SECA stream schema: {version}")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS model (singleton INTEGER PRIMARY KEY CHECK(singleton=1), state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS batches (sequence INTEGER PRIMARY KEY, batch_id TEXT UNIQUE NOT NULL,
            generated_at TEXT NOT NULL, tree TEXT NOT NULL, report TEXT NOT NULL,
            input_batch TEXT, config TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ingested (source_key TEXT PRIMARY KEY, sequence INTEGER NOT NULL);
        PRAGMA user_version=1;
    """)
    return db


def _publish_stream_views(root: Path, db: sqlite3.Connection) -> Path:
    """Calendar windows are presentation filters over a single model's history."""
    latest = db.execute("SELECT generated_at FROM batches ORDER BY sequence DESC LIMIT 1").fetchone()
    anchor = _parse_timestamp(latest[0]) if latest else None
    for days in (30, 7, 3):
        output = root / "results" / "web" / "newsmap" / f"seca-light-{days}d"
        output.parent.mkdir(parents=True, exist_ok=True)
        cutoff = _window_start(anchor, days=days).isoformat() if anchor else ""
        with tempfile.TemporaryDirectory(prefix=f".seca-light-{days}d-", dir=output.parent) as work:
            staged = Path(work) / "output"
            staged.mkdir()
            files, dates, batch_ids = [], [], []
            source_count = 0
            for sequence, identity, generated, tree in db.execute(
                "SELECT sequence, batch_id, generated_at, tree FROM batches WHERE generated_at>=? ORDER BY sequence", (cutoff,)
            ):
                name = f"tree_batch_{sequence:04}.json"
                (staged / name).write_text(tree, encoding="utf-8")
                files.append(name)
                dates.append(generated[:10])
                batch_ids.append(identity)
                source_count = len(json.loads(tree).get("source_legend", []))
            (staged / "timeline_manifest.json").write_text(json.dumps({
                "total_batches": len(files), "sources_total": source_count,
                "chunk_count": len(files), "chunk_size_effective": 0,
                "files": files, "days": dates, "batch_ids": batch_ids,
                "model": "persistent-seca-light", "source_window_unit": "batches",
            }), encoding="utf-8")
            if output.exists() and files:
                old_manifest = output / "timeline_manifest.json"
                if old_manifest.exists() and json.loads(old_manifest.read_text()).get("model") != "persistent-seca-light":
                    legacy = output.parent / "seca-legacy" / output.name
                    if not legacy.exists():
                        legacy.parent.mkdir(parents=True, exist_ok=True)
                        archive = Path(work) / "legacy"
                        shutil.copytree(output, archive)
                        archive.rename(legacy)
            _publish_timeline(staged, output)
    return root / "results/web/newsmap/seca-light-30d/timeline_manifest.json"


def run_seca_light_timeline(*, timeout_seconds: int = 600, batch_id: str | None = None) -> Path | None:
    """Ingest one successful run as a batch; an explicit ID makes retries idempotent."""
    root = _project_root()
    lock_dir = root / "runtime" / "seca"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / "timeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("seca_timeline_already_running")
            return None
        return _run_seca_light_timeline(root=root, timeout_seconds=timeout_seconds, batch_id=batch_id)


def _run_seca_light_timeline(*, root: Path, timeout_seconds: int, batch_id: str | None = None) -> Path | None:
    seca_root = next((p for p in (root / "experimental/RealtimeSECA", root / "experimental") if p.is_dir()), None)
    identity = batch_id or f"run-{uuid.uuid4()}"
    db = None
    with pipeline_stage(logger, stage="seca_light", component="services.seca_timeline", operation="stream_update", batch_id=identity) as end_stage:
        try:
            paths = _llm_input_paths(root)
            if not any(p.exists() for p in paths):
                raise FileNotFoundError("missing:news_data_with_llm_info.csv")
            command = _resolve_seca_command(seca_root)
            db = _open_stream(root)
            if db.execute("SELECT 1 FROM batches WHERE batch_id=?", (identity,)).fetchone():
                manifest = _publish_stream_views(root, db)
                end_stage("succeeded", skip_reason="batch_already_committed")
                return manifest
            total, deduped, rows = _collect_relevant_rows(paths)
            incoming = [row for row in rows if not db.execute(
                "SELECT 1 FROM ingested WHERE source_key=?", (_row_key(row),)
            ).fetchone()]
            previous = db.execute("SELECT state FROM model WHERE singleton=1").fetchone()
            sequence = db.execute("SELECT COALESCE(MAX(sequence), -1)+1 FROM batches").fetchone()[0]
            if not previous and not incoming:
                end_stage("succeeded", skip_reason="awaiting_nonempty_baseline", input_rows=total, output_rows=0)
                return None
            with tempfile.TemporaryDirectory(prefix="batch-", dir=root / "runtime/seca") as work:
                directory = Path(work)
                csv_path, batch_path = directory / "sources.csv", directory / "batch.json"
                state_in, state_out = directory / "previous.json", directory / "state.json"
                tree_path, config_path = directory / "tree.json", directory / "config.json"
                config = json.loads((Path(__file__).resolve().parents[2] / "config/seca_timeline.json").read_text())
                gamma = os.getenv("RISKLIVE_SECA_GAMMA_BATCHES")
                if gamma is not None:
                    config["max_batches_in_memory"] = int(gamma)
                config_path.write_text(json.dumps(config), encoding="utf-8")
                _write_relevant_csv(csv_path, incoming)
                def cli(args):
                    result = subprocess.run([*command, *args], cwd=_seca_working_directory(command, seca_root),
                        capture_output=True, text=True, check=False, timeout=timeout_seconds)
                    if result.returncode:
                        raise RuntimeError(f"{args[0]}: {(result.stderr or str(result.returncode))[-1000:]}")
                    return result
                if incoming:
                    cli(["from-csv", str(csv_path), str(batch_path), "--batch-index", str(sequence), "--min-tokens", "1"])
                    _identify_sources(batch_path, variant_name="stream", batch_index=sequence)
                else:
                    batch_path.write_text(json.dumps({"batch_index": sequence, "sources": []}), encoding="utf-8")
                batch = json.loads(batch_path.read_text())
                # The conversion may filter every row. This is still an empty successful batch.
                if not previous and not batch["sources"]:
                    end_stage("succeeded", skip_reason="awaiting_tokenized_baseline", input_rows=total, output_rows=0)
                    return None
                args = ["update", str(batch_path), "--config", str(config_path), "--state-out", str(state_out), "--dump-tree-verbose", str(tree_path)]
                if previous:
                    state_in.write_text(previous[0], encoding="utf-8")
                    args.extend(["--state-in", str(state_in)])
                result = cli(args)
                state_text, tree_text = state_out.read_text(), tree_path.read_text()
                state, tree = json.loads(state_text), json.loads(tree_text)
                if state["last_processed_batch_index"] != sequence:
                    raise ValueError("SECA returned an incorrect batch sequence")
                report = json.loads(result.stdout)
                generated = datetime.now(UTC).isoformat()
                # The DB transaction is the sole model commit. CLI writes only temporary files.
                with db:
                    db.execute("INSERT OR REPLACE INTO model VALUES (1, ?)", (state_text,))
                    db.execute("INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (sequence, identity, generated, json.dumps(tree, separators=(",", ":")), json.dumps(report),
                            json.dumps(batch) if os.getenv("RISKLIVE_SECA_ARCHIVE_BATCHES") == "1" else None, json.dumps(config)))
                    db.executemany("INSERT INTO ingested VALUES (?, ?)", [(_row_key(row), sequence) for row in incoming])
                for note in report.get("notes", []):
                    logger.info("seca_batch_detail", extra={"batch_id": identity, "batch_index": sequence, "detail": note})
                logger.info("seca_model_persisted", extra={"batch_id": identity, "batch_index": sequence,
                    "sources_added": report.get("sources_processed", 0), "sources_forgotten": report.get("sources_forgotten", 0), "active_source_count": len(tree.get("source_legend", [])),
                    "hkts_inspected": report.get("hkts_inspected", []),
                    "reconstructed_hkt_ids": report.get("reconstructed_hkt_ids", []),
                    "model_state_persisted": True})
            # Publication is recoverable: retrying the ID republishes committed history.
            manifest = _publish_stream_views(root, db)
            log_artifact_written(logger, stage="seca_light", operation="stream_update", component="services.seca_timeline", artifact_path=manifest, artifact_type="json")
            end_stage("succeeded", input_rows=total, output_rows=len(batch["sources"]), deduped_rows=deduped)
            return manifest
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
            end_stage("failed", error_code="seca_stream_failed", skip_reason=str(exc)[:1000])
            return None
        finally:
            if db is not None:
                db.close()

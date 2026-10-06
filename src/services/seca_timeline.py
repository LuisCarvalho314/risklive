"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import csv
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
            url or f"seca-{variant_name}-{batch_index}:{source['source_id']}"
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


def _run_timeline_variant(
    *,
    root: Path,
    seca_root: Path | None,
    command: list[str],
    variant_name: str,
    operation: str,
    output_dir_name: str,
    rows: list[dict[str, str]],
    total_rows: int,
    deduped_rows: int,
    timeout_seconds: int,
) -> Path | None:
    with pipeline_stage(
        logger,
        stage="seca_light",
        component="services.seca_timeline",
        operation=operation,
        timeline_variant=variant_name,
    ) as end_stage:
        out_dir = root / "results" / "web" / "newsmap" / output_dir_name
        manifest_path = out_dir / "timeline_manifest.json"
        daily_batches = _group_rows_by_utc_day(rows)
        config_path = (
            Path(__file__).resolve().parents[2] / "config" / "seca_timeline.json"
        )
        try:
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            # Never reuse old CSVs, batches or engine snapshots. A failed build
            # leaves the published directory intact, including its manifest.
            with tempfile.TemporaryDirectory(
                prefix=f".{output_dir_name}-", dir=out_dir.parent
            ) as work:
                work_dir = Path(work)
                staged = work_dir / "output"
                staged.mkdir()
                cumulative_rows: list[dict[str, str]] = []
                files: list[str] = []
                source_count = 0
                for batch_index, (_day, day_rows) in enumerate(daily_batches):
                    cumulative_rows.extend(day_rows)
                    csv_path = work_dir / "sources.csv"
                    batch_path = work_dir / "sources.json"
                    _write_relevant_csv(csv_path, cumulative_rows)
                    name = f"tree_batch_{batch_index:04}.json"
                    # Incremental reconstruction in the pinned core amplifies
                    # trees across batches. Rebuild the bounded prefix with a
                    # fresh engine, retaining the verbose tree output schema.
                    commands = [
                        [
                            *command,
                            "from-csv",
                            str(csv_path),
                            str(batch_path),
                            "--batch-index",
                            str(batch_index),
                            "--min-tokens",
                            "1",
                        ],
                        [
                            *command,
                            "baseline",
                            str(batch_path),
                            "--config",
                            str(config_path),
                            "--dump-tree-verbose",
                            str(staged / name),
                        ],
                    ]
                    for command_index, cli_command in enumerate(commands):
                        result = subprocess.run(
                            cli_command,
                            cwd=_seca_working_directory(command, seca_root),
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=timeout_seconds,
                        )
                        if result.returncode != 0:
                            tail = (result.stderr or "").strip().splitlines()
                            reason = (
                                tail[-1] if tail else f"exit_code={result.returncode}"
                            )
                            raise RuntimeError(
                                f"{cli_command[len(command)]}: {reason[:240]}"
                            )
                        if command_index == 0:
                            source_count = _identify_sources(
                                batch_path,
                                variant_name=variant_name,
                                batch_index=batch_index,
                            )
                    tree_path = staged / name
                    if not tree_path.is_file():
                        raise RuntimeError(f"missing:{name}")
                    # The CLI writes pretty JSON. Compact only this new bounded
                    # tree; preserve every field, node and source reference.
                    tree = json.loads(tree_path.read_text(encoding="utf-8"))
                    tree_path.write_text(
                        json.dumps(tree, separators=(",", ":")), encoding="utf-8"
                    )
                    files.append(name)
                manifest = {
                    "total_batches": len(files),
                    "sources_total": source_count,
                    "chunk_count": len(files),
                    "chunk_size_effective": len(daily_batches[0][1])
                    if daily_batches
                    else 0,
                    "files": files,
                    "days": [day for day, _ in daily_batches],
                }
                (staged / "timeline_manifest.json").write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )
                _publish_timeline(staged, out_dir)
        except subprocess.TimeoutExpired:
            end_stage(
                "failed",
                error_code="seca_timeout",
                skip_reason=f"timeout_seconds={timeout_seconds}",
                input_rows=total_rows,
                output_rows=len(rows),
                deduped_rows=deduped_rows,
            )
            return None
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            end_stage(
                "failed",
                error_code="seca_timeline_failed",
                skip_reason=str(exc)[:240],
                input_rows=total_rows,
                output_rows=len(rows),
                deduped_rows=deduped_rows,
            )
            return None

        log_artifact_written(
            logger,
            stage="seca_light",
            operation=operation,
            component="services.seca_timeline",
            artifact_path=manifest_path,
            artifact_type="json",
        )
        end_stage(
            "succeeded",
            input_rows=total_rows,
            output_rows=len(cumulative_rows),
            deduped_rows=deduped_rows,
        )
        return manifest_path


def run_seca_light_timeline(*, timeout_seconds: int = 600) -> Path | None:
    root = _project_root()
    lock_dir = root / "runtime" / "seca"
    lock_dir.mkdir(parents=True, exist_ok=True)
    # Scheduler and manual requests may overlap across processes. Do not allow
    # competing directory publications or concurrent expensive SECA builds.
    with (lock_dir / "timeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("seca_timeline_already_running")
            return None
        return _run_seca_light_timeline(root=root, timeout_seconds=timeout_seconds)


def _run_seca_light_timeline(*, root: Path, timeout_seconds: int) -> Path | None:
    seca_root = next(
        (
            candidate
            for candidate in (
                root / "experimental" / "RealtimeSECA",
                root / "experimental",
            )
            if candidate.is_dir()
        ),
        None,
    )

    llm_paths = _llm_input_paths(root)
    if not any(path.exists() for path in llm_paths):
        with pipeline_stage(
            logger,
            stage="seca_light",
            component="services.seca_timeline",
            operation="timeline_prepare",
        ) as end_stage:
            end_stage(
                "failed",
                error_code="seca_input_missing",
                skip_reason="missing:news_data_with_llm_info.csv",
            )
        return None

    total_rows, deduped_rows, relevant_rows = _collect_relevant_rows(llm_paths)
    relevant_rows_30d = _rolling_window_rows(relevant_rows, days=30)
    relevant_rows_7d = _rolling_window_rows(relevant_rows, days=7)
    relevant_rows_3d = _rolling_window_rows(relevant_rows, days=3)

    try:
        command = _resolve_seca_command(seca_root)
    except OSError as exc:
        with pipeline_stage(
            logger,
            stage="seca_light",
            component="services.seca_timeline",
            operation="timeline_prepare",
        ) as end_stage:
            end_stage(
                "failed", error_code="seca_cli_missing", skip_reason=str(exc)[:240]
            )
        return None

    thirty_manifest = _run_timeline_variant(
        root=root,
        seca_root=seca_root,
        command=command,
        variant_name="30d",
        operation="timeline_30d",
        output_dir_name="seca-light-30d",
        rows=relevant_rows_30d,
        total_rows=total_rows,
        deduped_rows=deduped_rows,
        timeout_seconds=timeout_seconds,
    )
    _run_timeline_variant(
        root=root,
        seca_root=seca_root,
        command=command,
        variant_name="7d",
        operation="timeline_7d",
        output_dir_name="seca-light-7d",
        rows=relevant_rows_7d,
        total_rows=total_rows,
        deduped_rows=deduped_rows,
        timeout_seconds=timeout_seconds,
    )
    _run_timeline_variant(
        root=root,
        seca_root=seca_root,
        command=command,
        variant_name="3d",
        operation="timeline_3d",
        output_dir_name="seca-light-3d",
        rows=relevant_rows_3d,
        total_rows=total_rows,
        deduped_rows=deduped_rows,
        timeout_seconds=timeout_seconds,
    )
    return thirty_manifest

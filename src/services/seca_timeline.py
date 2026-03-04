"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.logging import get_logger, log_artifact_written, pipeline_stage

logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_seca_command(seca_root: Path) -> list[str]:
    override = os.getenv("RISKLIVE_SECA_CLI", "").strip()
    if override:
        return [override]

    for candidate in (
        seca_root / "target" / "release" / "realtime-seca-cli",
        seca_root / "target" / "debug" / "realtime-seca-cli",
    ):
        if candidate.exists():
            return [str(candidate)]

    installed = shutil.which("realtime-seca-cli")
    if installed:
        return [installed]

    if shutil.which("cargo"):
        return ["cargo", "run", "-p", "realtime-seca-cli", "--"]

    raise FileNotFoundError(
        "realtime-seca-cli not found (set RISKLIVE_SECA_CLI, install realtime-seca-cli, or install cargo)"
    )


def _llm_input_paths(root: Path) -> list[Path]:
    return [
        root / "results" / "data" / "news_data_with_llm_info.csv",
        root / "results" / "backup_data" / "news_data_with_llm_info.csv",
    ]


def _row_key(row: dict[str, str]) -> str:
    url = (row.get("URL") or "").strip()
    ts = (row.get("Timestamp") or "").strip()
    title = (row.get("Title") or "").strip()
    if url and ts:
        return f"url:{url}|ts:{ts}"
    return f"title:{title}|ts:{ts}"


def _collect_relevant_rows(paths: list[Path]) -> tuple[int, int, list[dict[str, str]]]:
    total_rows = 0
    relevant_rows: list[dict[str, str]] = []
    seen: set[str] = set()
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
                key = _row_key(row)
                if key in seen:
                    deduped_rows += 1
                    continue
                seen.add(key)
                relevant_rows.append(
                    {
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
                )
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
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row_timestamp(row: dict[str, str]) -> datetime | None:
    return _parse_timestamp(row.get("Timestamp") or "") or _parse_timestamp(row.get("API_Timestamp") or "")


def _rolling_window_rows(rows: list[dict[str, str]], *, days: int) -> list[dict[str, str]]:
    stamped: list[tuple[dict[str, str], datetime]] = []
    for row in rows:
        parsed = _row_timestamp(row)
        if parsed is not None:
            stamped.append((row, parsed))
    if not stamped:
        return []
    max_ts = max(ts for _, ts in stamped)
    cutoff = max_ts - timedelta(days=days)
    return [row for row, ts in stamped if ts >= cutoff]


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


def _run_timeline_variant(
    *,
    root: Path,
    seca_root: Path,
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
        runtime_dir = root / "runtime" / "seca"
        filtered_csv_path = runtime_dir / f"relevant_news_data_{variant_name}.csv"
        filtered_batch_path = runtime_dir / f"relevant_news_data_{variant_name}_batch.json"

        if not rows:
            end_stage(
                "skipped",
                input_rows=total_rows,
                output_rows=0,
                deduped_rows=deduped_rows,
                skip_reason=f"no_relevant_rows_{variant_name}",
            )
            return None

        _write_relevant_csv(filtered_csv_path, rows)
        log_artifact_written(
            logger,
            stage="seca_light",
            operation=operation,
            component="services.seca_timeline",
            artifact_path=filtered_csv_path,
            artifact_type="csv",
            artifact_rows=len(rows),
        )

        try:
            from_csv = subprocess.run(
                [
                    *command,
                    "from-csv",
                    str(filtered_csv_path),
                    str(filtered_batch_path),
                    "--batch-index",
                    "0",
                    "--min-tokens",
                    "1",
                ],
                cwd=seca_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            if from_csv.returncode != 0:
                stderr_tail = (from_csv.stderr or "").strip().splitlines()
                reason = stderr_tail[-1] if stderr_tail else f"exit_code={from_csv.returncode}"
                end_stage(
                    "failed",
                    error_code="seca_from_csv_failed",
                    skip_reason=reason[:240],
                    input_rows=total_rows,
                    output_rows=len(rows),
                    deduped_rows=deduped_rows,
                )
                return None

            timeline = subprocess.run(
                [
                    *command,
                    "timeline",
                    str(filtered_batch_path),
                    "--out-dir",
                    str(out_dir),
                    "--clean-out-dir",
                ],
                cwd=seca_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
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
        except Exception as exc:
            end_stage(
                "failed",
                error_code="seca_runtime_error",
                skip_reason=str(exc)[:240],
                input_rows=total_rows,
                output_rows=len(rows),
                deduped_rows=deduped_rows,
            )
            return None

        if timeline.returncode != 0:
            stderr_tail = (timeline.stderr or "").strip().splitlines()
            reason = stderr_tail[-1] if stderr_tail else f"exit_code={timeline.returncode}"
            end_stage(
                "failed",
                error_code="seca_timeline_failed",
                skip_reason=reason[:240],
                input_rows=total_rows,
                output_rows=len(rows),
                deduped_rows=deduped_rows,
            )
            return None

        if not manifest_path.exists():
            end_stage(
                "failed",
                error_code="seca_manifest_missing",
                skip_reason=f"missing:{manifest_path}",
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
            output_rows=len(rows),
            deduped_rows=deduped_rows,
        )
        return manifest_path


def run_seca_light_timeline(*, timeout_seconds: int = 600) -> Path | None:
    root = _project_root()
    seca_root = root / "experimental" / "RealtimeSECA"

    if not seca_root.exists():
        with pipeline_stage(
            logger,
            stage="seca_light",
            component="services.seca_timeline",
            operation="timeline_prepare",
        ) as end_stage:
            end_stage("failed", error_code="seca_root_missing", skip_reason=f"missing:{seca_root}")
        return None

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
    except Exception as exc:
        with pipeline_stage(
            logger,
            stage="seca_light",
            component="services.seca_timeline",
            operation="timeline_prepare",
        ) as end_stage:
            end_stage("failed", error_code="seca_cli_missing", skip_reason=str(exc)[:240])
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

"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path
import shutil
import tarfile


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_backup_archive(base_dir: Path | None = None) -> Path:
    root = base_dir or (project_root() / "results" / "test_archives")
    archives = sorted(root.glob("backup_data_*.tar.gz"))
    if not archives:
        raise FileNotFoundError(f"No backup archives found in {root}")
    return archives[-1]


def prepare_results_layout(workspace_root: Path) -> dict[str, Path]:
    results_dir = workspace_root / "results"
    backup_dir = results_dir / "backup_data"
    data_dir = results_dir / "data"
    web_dir = results_dir / "web"
    images_dir = results_dir / "images"
    backup_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    return {
        "results_dir": results_dir,
        "backup_dir": backup_dir,
        "data_dir": data_dir,
        "web_dir": web_dir,
        "images_dir": images_dir,
    }


def _validate_archive_members(members: list[tarfile.TarInfo]) -> None:
    for member in members:
        member_path = Path(member.name)
        if member_path.name.startswith("._"):
            continue
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"Unsafe path in archive: {member.name}")
        if member.name == "backup_data":
            continue
        if not member.name.startswith("backup_data/"):
            raise ValueError(f"Unexpected archive member: {member.name}")


def extract_archive_to_workspace(archive_path: Path, workspace_root: Path) -> Path:
    layout = prepare_results_layout(workspace_root)
    results_dir = layout["results_dir"]

    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        _validate_archive_members(members)
        safe_members = [m for m in members if not Path(m.name).name.startswith("._")]
        tar.extractall(path=results_dir, members=safe_members, filter="data")

    backup_dir = layout["backup_dir"]
    required = [
        backup_dir / "news_data.csv",
        backup_dir / "news_data_with_llm_info.csv",
        backup_dir / "df_with_response_and_topics.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Archive is missing required files: {missing}")
    return backup_dir


def stage_backup_csvs_to_data(workspace_root: Path, backup_dir: Path | None = None) -> dict[str, Path]:
    layout = prepare_results_layout(workspace_root)
    source_backup = backup_dir or layout["backup_dir"]
    data_dir = layout["data_dir"]

    for name in (
        "news_data.csv",
        "news_data_with_llm_info.csv",
        "df_with_response_and_topics.csv",
        "df_report.csv",
    ):
        src = source_backup / name
        if src.exists():
            shutil.copy2(src, data_dir / name)
    return layout

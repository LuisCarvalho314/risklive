from __future__ import annotations

from pathlib import Path

import pytest

from app import server as server_app
from models.errors import StorageError
from services import storage as storage_service


def test_storage_error_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(StorageError):
        storage_service.ensure_dir(tmp_path / "x")

    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(StorageError):
        storage_service.read_csv(tmp_path / "a.csv")
    with pytest.raises(StorageError):
        storage_service.write_csv([{"a": 1}], tmp_path / "b.csv")


def test_server_job_wrapper_failure_and_success(monkeypatch):
    ok = {"value": False}

    def _ok():
        ok["value"] = True

    server_app._run_job("ok", _ok)
    assert ok["value"]

    with pytest.raises(RuntimeError):
        server_app._run_job("bad", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

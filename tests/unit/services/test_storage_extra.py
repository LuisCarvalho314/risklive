"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from services.storage import write_csv, read_csv


def test_write_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    write_csv([], path)
    assert read_csv(path) == []

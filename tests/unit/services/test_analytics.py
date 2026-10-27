import sqlite3
from contextlib import closing
from pathlib import Path

from services.analytics import initialise_database, record_event


def test_initialise_database_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime" / "analytics.sqlite3"

    initialise_database(db_path)

    assert db_path.is_file()

    with closing(sqlite3.connect(db_path)) as connection:
        columns = connection.execute("PRAGMA table_info(analytics_events)").fetchall()

    column_names = {column[1] for column in columns}

    assert column_names == {
        "id",
        "event_id",
        "timestamp",
        "session_id",
        "event_type",
        "page_path",
    }


def test_record_event(tmp_path: Path) -> None:
    db_path = tmp_path / "analytics.sqlite3"
    initialise_database(db_path)

    inserted = record_event(
        db_path,
        event_id="event-001",
        event_type="page_view",
        page_path="/topics",
    )

    assert inserted is True


def test_repeated_initialisation(tmp_path: Path) -> None:
    db_path = tmp_path / "analytics.sqlite3"

    initialise_database(db_path)

    inserted = record_event(
        db_path,
        event_id="event-001",
        event_type="page_view",
        page_path="/topics",
    )

    assert inserted is True

    # Reinitialise an existing database
    initialise_database(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT event_id, event_type, page_path, session_id
            FROM analytics_events
            """
        ).fetchall()

    assert rows == [("event-001", "page_view", "/topics", None)]


def test_record_event_duplication(tmp_path: Path) -> None:

    db_path = tmp_path / "analytics.sqlite3"
    initialise_database(db_path)

    first = record_event(db_path, "event-001", "page_view", "/topics")
    second = record_event(db_path, "event-001", "page_view", "/topics")

    assert first is True
    assert second is False

    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute("SELECT event_id FROM analytics_events").fetchall()

    assert rows == [("event-001",)]

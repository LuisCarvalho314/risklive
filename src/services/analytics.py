import sqlite3
from pathlib import Path

from datetime import datetime, timezone


def initialise_database(db_path: Path) -> None:

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5.0)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                event_type TEXT NOT NULL,
                page_path TEXT NOT NULL
            
            );
            """
        )
        connection.commit()

    finally:
        connection.close()


def record_event(
    db_path: Path,
    event_id: str,
    event_type: str,
    page_path: str,
    session_id: str | None = None,
) -> bool:

    timestamp = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(db_path, timeout=5.0)

    parameters = (
        event_id,
        timestamp,
        event_type,
        page_path,
        session_id,
    )

    sql: str = """
            INSERT INTO analytics_events (
            event_id, 
            timestamp,
            event_type, 
            page_path, 
            session_id 
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO NOTHING;
        """

    try:
        with connection:
            cursor = connection.execute(sql, parameters)
            success = cursor.rowcount == 1

    finally:
        connection.close()

    return success

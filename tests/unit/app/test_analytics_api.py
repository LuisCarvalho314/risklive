import app.server as server
import pytest
import sqlite3
from contextlib import closing


def read_stored_events(db_path):
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(
            """
            SELECT event_id, event_type, page_path, session_id
            FROM analytics_events
            ORDER BY id
            """
        ).fetchall()


def test_analytics_event_endpoint(analytics_client):

    client, db_path = analytics_client

    response = client.post(
        "/analytics/events",
        json={
            "event_id": "event-001",
            "event_type": "page_view",
            "page_path": "/topics",
            "session_id": None,
        },
    )

    assert response.status_code == 201
    assert response.json == {"inserted": True}
    assert read_stored_events(db_path) == [("event-001", "page_view", "/topics", None)]


@pytest.mark.parametrize(
    "payload",
    [
        {"event_id": "1", "event_type": "unknown", "page_path": "/topics"},
        {"event_id": "", "event_type": "page_view", "page_path": "/topics"},
        {"event_id": "1", "event_type": "page_view"},
    ],
    ids=[
        "unsupported-event-type",
        "empty-event-id",
        "missing-page-path",
    ],
)
def test_invalid_analytics_event(analytics_client, payload):

    client, db_path = analytics_client

    response = client.post(
        "/analytics/events",
        json=payload,
    )

    assert response.status_code == 400
    assert read_stored_events(db_path) == []


def test_duplicate_analytics_event(analytics_client):
    client, db_path = analytics_client

    payload = {
        "event_id": "event-001",
        "event_type": "page_view",
        "page_path": "/topics",
    }

    first = client.post("/analytics/events", json=payload)
    second = client.post("/analytics/events", json=payload)

    assert first.status_code == 201
    assert first.json == {"inserted": True}

    assert second.status_code == 200
    assert second.json == {"inserted": False}

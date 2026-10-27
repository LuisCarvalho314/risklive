import app.server as server
import pytest


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

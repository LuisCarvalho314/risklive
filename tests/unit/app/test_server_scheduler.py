"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import pytest

from app import server as server_app


pytestmark = pytest.mark.usefixtures("isolated_app")


def test_start_scheduler(monkeypatch):
    class DummyScheduler:
        def __init__(self):
            self.jobs = []
            self.started = False

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):
            # Record startup without starting a thread or executing a job.
            self.started = True

    monkeypatch.setattr(server_app, "BackgroundScheduler", DummyScheduler)

    app = server_app.create_app()
    scheduler = server_app.start_scheduler(app)
    assert scheduler.started
    assert len(scheduler.jobs) == 2
    assert [kwargs for _, kwargs in scheduler.jobs] == [
        {"hour": 6, "minute": 20},
        {"hour": 6, "minute": 0},
    ]

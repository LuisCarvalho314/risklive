from __future__ import annotations

from app import server as server_app


def test_start_scheduler(monkeypatch):
    class DummyScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):
            return None

    monkeypatch.setattr(server_app, "BackgroundScheduler", DummyScheduler)

    app = server_app.create_app()
    scheduler = server_app.start_scheduler(app)
    assert scheduler.jobs

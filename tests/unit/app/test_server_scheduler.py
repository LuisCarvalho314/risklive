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
        {"id": "fetch_and_process", "hour": 6, "minute": 20, "max_instances": 1, "coalesce": True, "timezone": "Europe/London"},
        {"id": "cleanup_old_data", "hour": 6, "minute": 0, "max_instances": 1, "coalesce": True, "timezone": "Europe/London"},
    ]


@pytest.mark.parametrize("month,expected_hour", [(1, 6), (7, 5)])
def test_canonical_schedule_preserves_london_wall_time_across_dst(month, expected_hour):
    from datetime import datetime, timezone
    from apscheduler.schedulers.blocking import BlockingScheduler
    from app.scheduler_jobs import register_jobs

    scheduler = BlockingScheduler()
    register_jobs(scheduler)
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"fetch_and_process", "cleanup_old_data"}
    now = datetime(2026, month, 15, tzinfo=timezone.utc)
    for job_id, minute in (("fetch_and_process", 20), ("cleanup_old_data", 0)):
        trigger = jobs[job_id].trigger
        assert str(trigger.timezone) == "Europe/London"
        assert trigger.get_next_fire_time(None, now).astimezone(timezone.utc) == datetime(2026, month, 15, expected_hour, minute, tzinfo=timezone.utc)
    assert not scheduler.running

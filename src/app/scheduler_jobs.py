"""Canonical schedule shared by the host/server, dedicated scheduler, and ops UI."""

import json
from pathlib import Path

SCHEDULE = json.loads(Path(__file__).with_name("schedules.json").read_text())


def register_jobs(scheduler, app=None) -> None:
    from app import server

    cfg = server.get_config()
    callbacks = {
        "fetch_and_process": lambda: server._run_job(
            "fetch_and_process", lambda: server.fetch_and_process(app)
        ),
        "cleanup_old_data": lambda: server._run_job(
            "cleanup_old_data", lambda: server.cleanup_old_data(cfg.cleanup_days_to_keep)
        ),
    }
    for job in SCHEDULE["jobs"]:
        scheduler.add_job(
            callbacks[job["id"]], "cron", id=job["id"],
            hour=job["hour"], minute=job["minute"], timezone=SCHEDULE["timezone"],
            max_instances=1, coalesce=True,
        )

"""Dedicated foreground scheduler. No Flask app or HTTP server is constructed."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import signal

from apscheduler.schedulers.blocking import BlockingScheduler

from app.scheduler_jobs import register_jobs
from utils.logging import configure_logging, get_project_root


@contextmanager
def scheduler_ownership():
    """Reject duplicate owners sharing the persistent runtime mount."""
    runtime = get_project_root() / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "scheduler.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another scheduler owns this runtime directory") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def main() -> None:
    configure_logging()
    with scheduler_ownership():
        scheduler = BlockingScheduler()
        previous = {}

        def stop(signum, frame):
            # Unwind the blocking loop; finally waits for any active job to finish.
            raise SystemExit(0)

        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.signal(signum, stop)
            register_jobs(scheduler)
            scheduler.start()
        finally:
            # Ignore repeated signals while completing graceful shutdown.
            for signum in previous:
                signal.signal(signum, signal.SIG_IGN)
            try:
                if scheduler.running:
                    scheduler.shutdown(wait=True)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)


if __name__ == "__main__":  # pragma: no cover
    main()

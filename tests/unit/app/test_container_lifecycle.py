"""Container lifecycle tests; fake schedulers never execute jobs or start threads."""

import builtins
import importlib
import signal
from unittest.mock import Mock

import pytest

from app import scheduler, scheduler_jobs, server


@pytest.mark.usefixtures("isolated_app")
def test_wsgi_import_is_http_only(monkeypatch, tmp_path):
    from utils import logging as app_logging

    monkeypatch.setattr(app_logging, "get_project_root", lambda: tmp_path)
    start = Mock(side_effect=AssertionError("scheduler startup from WSGI"))
    monkeypatch.setattr(server, "start_scheduler", start)
    monkeypatch.setattr(server, "BackgroundScheduler", start)
    monkeypatch.setattr(scheduler, "BlockingScheduler", start)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "services.pipeline" or name.startswith(("adapters.", "agents.")):
            raise AssertionError(f"WSGI imported operational dependency: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    # Re-execute server imports, rather than relying on modules warmed by collection.
    importlib.reload(server)
    monkeypatch.setattr(server, "start_scheduler", start)
    monkeypatch.setattr(server, "BackgroundScheduler", start)
    wsgi = importlib.import_module("app.wsgi")
    importlib.reload(wsgi)
    from gunicorn.util import import_app

    app = import_app("app.wsgi:app")
    assert app is wsgi.app
    assert app.test_client().get("/").json == {"status": "ok"}
    assert server.create_app().test_client().get("/").status_code == 200
    start.assert_not_called()


@pytest.mark.usefixtures("isolated_app")
def test_shared_job_registrations_and_callbacks(monkeypatch):
    fake = Mock()
    fetch = Mock()
    cleanup = Mock()
    monkeypatch.setattr(server, "fetch_and_process", fetch)
    monkeypatch.setattr(server, "cleanup_old_data", cleanup)
    scheduler_jobs.register_jobs(fake)
    calls = fake.add_job.call_args_list
    assert len(calls) == 2
    assert [call.args[1] for call in calls] == ["cron", "cron"]
    assert [call.kwargs for call in calls] == [
        dict(id="fetch_and_process", hour=6, minute=20, max_instances=1, coalesce=True, timezone="Europe/London"),
        dict(id="cleanup_old_data", hour=6, minute=0, max_instances=1, coalesce=True, timezone="Europe/London"),
    ]
    fake.start.assert_not_called()
    for call in calls:
        call.args[0]()
    fetch.assert_called_once_with(None)
    cleanup.assert_called_once_with(server.get_config().cleanup_days_to_keep)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_scheduler_has_one_owner_and_shuts_down(monkeypatch, tmp_path, signum):
    handlers = {}
    originals = {signal.SIGTERM: object(), signal.SIGINT: object()}
    monkeypatch.setattr(scheduler, "configure_logging", lambda: None)
    monkeypatch.setattr(scheduler, "get_project_root", lambda: tmp_path)

    def set_signal(number, handler):
        previous = handlers.get(number, originals[number])
        handlers[number] = handler
        return previous

    monkeypatch.setattr(scheduler.signal, "signal", set_signal)
    fake = Mock(running=True)
    fake.start.side_effect = lambda: handlers[signum](signum, None)
    factory = Mock(return_value=fake)
    register = Mock()
    monkeypatch.setattr(scheduler, "BlockingScheduler", factory)
    monkeypatch.setattr(scheduler, "register_jobs", register)
    monkeypatch.setattr(server, "create_app", Mock(side_effect=AssertionError("HTTP app in scheduler")))
    with pytest.raises(SystemExit) as stopped:
        scheduler.main()
    assert stopped.value.code == 0
    factory.assert_called_once_with()
    register.assert_called_once_with(fake)
    fake.start.assert_called_once_with()
    fake.shutdown.assert_called_once_with(wait=True)
    assert handlers == originals
    # Shutdown released ownership; subsequent lifecycle may acquire it.
    with scheduler.scheduler_ownership():
        pass


def test_duplicate_scheduler_rejected_before_construction(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(scheduler, "configure_logging", lambda: None)
    factory = Mock()
    monkeypatch.setattr(scheduler, "BlockingScheduler", factory)
    with scheduler.scheduler_ownership():
        with pytest.raises(RuntimeError, match="Another scheduler owns"):
            scheduler.main()
    factory.assert_not_called()


def test_startup_failure_releases_owner_and_restores_signals(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(scheduler, "configure_logging", lambda: None)
    signals = Mock(return_value=signal.SIG_DFL)
    monkeypatch.setattr(scheduler.signal, "signal", signals)
    fake = Mock(running=False)
    monkeypatch.setattr(scheduler, "BlockingScheduler", lambda: fake)
    monkeypatch.setattr(scheduler, "register_jobs", Mock(side_effect=ValueError("bad config")))
    with pytest.raises(ValueError, match="bad config"):
        scheduler.main()
    fake.start.assert_not_called()
    fake.shutdown.assert_not_called()
    assert signals.call_args_list[-2:] == [
        ((signal.SIGTERM, signal.SIG_DFL),), ((signal.SIGINT, signal.SIG_DFL),),
    ]
    with scheduler.scheduler_ownership():
        pass

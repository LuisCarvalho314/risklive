"""Opt-in isolation for CLI/Flask branch tests; never run operational work."""

import socket
import subprocess
import threading

import pytest
from flask import Flask

from app import cli, server


@pytest.fixture
def isolated_app(monkeypatch, tmp_path, reset_settings_cache):
    # Fail at the app boundary, before runtime data or API clients are accessed.
    # Individual tests replace only the collaborators they intend to exercise.
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected operational work in an isolated application test")

    for module in (cli, server):
        monkeypatch.setattr(module, "configure_logging", lambda: None)
        monkeypatch.setattr(module, "data_path", lambda name: tmp_path / name)
        for name in (
            "fetch_news", "save_news", "read_csv", "extract_news_info",
            "run_topic_modeling", "generate_report", "export_dashboard",
            "cleanup_old_data", "run_topic_visualizations",
            "manual_fetch_and_process", "fetch_and_process", "run_seca_light",
            "run_seca_light_timeline", "BackgroundScheduler",
        ):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)

    # Backstops also catch accidental changes to the route/CLI call graph.
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "bind", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(Flask, "run", forbidden)

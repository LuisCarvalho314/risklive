"""The optional shadow hook must never alter the existing pipeline contract."""
import json

import pytest

from app import server
from services import seca_v2
from utils.logging import JsonFormatter


def pipeline(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "manual_fetch_and_process", lambda **kwargs: calls.append("reports"))
    monkeypatch.setattr(server, "export_dashboard", lambda: calls.append("dashboard"))
    monkeypatch.setattr(server, "run_seca_light", lambda: pytest.fail("retired V1 invocation"))
    return calls


@pytest.mark.parametrize("flag", [None, "false", "0", "invalid"])
def test_disabled_has_no_adapter_effects(monkeypatch, flag):
    calls = pipeline(monkeypatch)
    if flag is None:
        monkeypatch.delenv("RISKLIVE_SECA_V2_ENABLED", raising=False)
    else:
        monkeypatch.setenv("RISKLIVE_SECA_V2_ENABLED", flag)
    monkeypatch.setattr(seca_v2, "run", lambda **kwargs: pytest.fail("disabled adapter ran"))
    server.fetch_and_process(None)
    assert calls == ["reports", "dashboard"]


def test_enabled_runs_after_pipeline(monkeypatch):
    calls = pipeline(monkeypatch)
    monkeypatch.setenv("RISKLIVE_SECA_V2_ENABLED", "true")
    def run(**kwargs):
        assert kwargs == {}  # Never implicitly bootstrap or replay live history.
        calls.append("v2")
    monkeypatch.setattr(seca_v2, "run", run)
    server.fetch_and_process(None)
    assert calls == ["reports", "dashboard", "v2"]


@pytest.mark.parametrize("failure", [FileNotFoundError("CLI missing"), ValueError("configuration mismatch"), RuntimeError("CLI failed")])
def test_shadow_failures_are_logged_and_nonblocking(monkeypatch, caplog, failure):
    calls = pipeline(monkeypatch)
    monkeypatch.setenv("RISKLIVE_SECA_V2_ENABLED", "true")
    monkeypatch.setattr(seca_v2, "run", lambda: (_ for _ in ()).throw(failure))
    server.fetch_and_process(None)
    assert calls == ["reports", "dashboard"]
    assert any(r.getMessage() == "seca_v2_non_blocking_error" for r in caplog.records)


@pytest.mark.usefixtures("isolated_app")
def test_no_new_routes(monkeypatch):
    routes = []
    for flag in ("false", "true"):
        monkeypatch.setenv("RISKLIVE_SECA_V2_ENABLED", flag)
        routes.append({(r.rule, tuple(sorted(r.methods))) for r in server.create_app().url_map.iter_rules()})
    assert routes[0] == routes[1]
    assert not any("v2" in rule for rule, methods in routes[0])


def test_measurements_survive_structured_formatting():
    import logging
    from utils.logging import log_context
    with log_context(batch_date="2026-10-28", total_adapter_ms=1.5, state_bytes=200, peak_rss_kib=300):
        payload = json.loads(JsonFormatter().format(logging.LogRecord("test", logging.INFO, "", 1, "measured", (), None)))
    assert payload["batch_date"] == "2026-10-28"
    assert payload["state_bytes"] == 200
    assert payload["total_adapter_ms"] == 1.5


@pytest.mark.parametrize("change,accepted", [("ulp", True), ("metric", False), ("decision", False), ("tree", False), ("batch", False), ("missing", False)])
def test_update_comparison_preserves_identity_and_allows_metric_readback(change, accepted):
    import copy
    report = {"batch": 4, "root": {"nodes": []}, "decisions": [{
        "path": [1], "reconstructed": False,
        "errors": {"alpha": 0.1, "beta": 0.2, "importance": 0.18518518518518515}}]}
    output = copy.deepcopy(report)
    if change == "ulp":
        output["decisions"][0]["errors"]["importance"] = 0.18518518518518517
    elif change == "metric":
        output["decisions"][0]["errors"]["importance"] = 0.19
    elif change == "decision":
        output["decisions"][0]["reconstructed"] = True
    elif change == "tree":
        output["root"]["nodes"] = [{}]
    elif change == "batch":
        output["batch"] = 5
    else:
        output.pop("decisions")
    assert seca_v2._same_update(output, report) is accepted

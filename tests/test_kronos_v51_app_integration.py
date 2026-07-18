from __future__ import annotations

import importlib
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

from webui.v51_research_api import V51_API_FALSE_LOCKS, V51_RESEARCH_CLAIMS


V51_ENV = ("KRONOS_V51_ARTIFACT_DIR",)
EXPECTED_V51_RULES = {
    "/api/daily-close-v51/source-coverage",
    "/api/daily-close-v51/causal-panel",
    "/api/daily-close-v51/accounting",
    "/api/daily-close-v51/evaluator",
    "/api/daily-close-v51/benchmark-overlay",
    "/api/daily-close-v51/reports",
    "/api/daily-close-v51/reports/<report_id>",
}
V51_GET_CASES = (
    ("/api/daily-close-v51/source-coverage", "SOURCE_COVERAGE"),
    ("/api/daily-close-v51/causal-panel", "CAUSAL_PANEL"),
    ("/api/daily-close-v51/accounting", "ACCOUNTING"),
    ("/api/daily-close-v51/evaluator", "EVALUATOR"),
    ("/api/daily-close-v51/benchmark-overlay", "BENCHMARK_OVERLAY"),
    ("/api/daily-close-v51/reports", "REPORTS"),
    ("/api/daily-close-v51/reports/not-present", "REPORT_READ"),
)
V51_ARTIFACT_ROUTE_IDS = {
    "SOURCE_COVERAGE",
    "CAUSAL_PANEL",
    "ACCOUNTING",
    "EVALUATOR",
    "BENCHMARK_OVERLAY",
}
V51_METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
OFFICIAL_SHELL_MARKER = "kronos-dashboard-shell"
LEGACY_PUBLIC_MARKERS = ("kronos-v2-version", "p1-ssr", "p1-5-spa")


def _clear_v51_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in V51_ENV:
        monkeypatch.delenv(name, raising=False)


def _reload_app(monkeypatch: pytest.MonkeyPatch, **env: str):
    _clear_v51_env(monkeypatch)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    import webui.app as app_module
    return importlib.reload(app_module)


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: pytest.MonkeyPatch):
    yield
    _clear_v51_env(monkeypatch)
    if "webui.app" in sys.modules:
        importlib.reload(sys.modules["webui.app"])


def _json(response) -> dict[str, object]:
    payload = response.get_json()
    assert isinstance(payload, dict)
    return payload


def _location_path_and_query(location: str | None) -> str:
    assert location is not None
    parsed = urlparse(location)
    path = parsed.path or "/"
    return f"{path}?{parsed.query}" if parsed.query else path


def _assert_official_shell(body: str) -> None:
    assert OFFICIAL_SHELL_MARKER in body
    for marker in LEGACY_PUBLIC_MARKERS:
        assert marker not in body


def _assert_false_locks_and_no_claims(payload: dict[str, object]) -> None:
    assert payload["locks"] == V51_API_FALSE_LOCKS
    assert payload["claims"] == V51_RESEARCH_CLAIMS


def test_official_app_import_registers_v51_once_and_preserves_v3_v5_and_legacy_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _reload_app(monkeypatch)
    rules = list(app_module.app.url_map.iter_rules())
    rule_paths = [rule.rule for rule in rules]

    assert EXPECTED_V51_RULES <= set(rule_paths)
    for expected in EXPECTED_V51_RULES:
        assert rule_paths.count(expected) == 1
    assert [name for name in app_module.app.blueprints if name == "kronos_v51_research_api"] == ["kronos_v51_research_api"]
    assert app_module.app.config["KRONOS_V51_READ_ONLY"] is True
    assert app_module.app.config["KRONOS_V51_ARTIFACT_DIR"] == ""
    assert app_module.app.config["KRONOS_V51_AVAILABLE"] is False

    assert "/" in set(rule_paths), "official V3 dashboard shell route must remain registered"
    assert "/api/v5/rl/runs" in set(rule_paths), "official V5 v2 API route must remain registered"
    assert "/api/v5/rl/matrix" in set(rule_paths), "V5 v2 query-scoped route must remain registered"
    assert not any(path.startswith("/api/v5/daily-close-v51") for path in rule_paths)

    client = app_module.app.test_client()
    shell_response = client.get("/")
    assert shell_response.status_code == 200
    _assert_official_shell(shell_response.get_data(as_text=True))

    legacy_response = client.get("/v2", follow_redirects=False)
    assert legacy_response.status_code == 301
    assert _location_path_and_query(legacy_response.headers.get("Location")) == "/"

    rl_response = client.get("/rl", follow_redirects=False)
    assert rl_response.status_code == 301
    assert _location_path_and_query(rl_response.headers.get("Location")) == "/?tab=rl"


def test_v51_get_routes_are_registered_read_only_and_fail_closed_without_default_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _reload_app(monkeypatch)
    client = app_module.app.test_client()

    for path, route_id in V51_GET_CASES:
        response = client.get(path)
        payload = _json(response)

        assert response.status_code == 200, path
        assert response.mimetype == "application/json"
        assert payload["route_id"] == route_id
        _assert_false_locks_and_no_claims(payload)
        if route_id in V51_ARTIFACT_ROUTE_IDS:
            assert payload["status"] == "BLOCKED"
            assert payload["status_reason"] == "BLOCKED_ARTIFACT_UNAVAILABLE"


def test_v51_routes_are_read_only_in_official_app(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _reload_app(monkeypatch)
    client = app_module.app.test_client()

    for path, _route_id in V51_GET_CASES:
        for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            response = client.open(path, method=method)
            assert response.status_code == 405, (path, method)
            assert response.headers["Allow"] == "GET"
            if method != "HEAD":
                payload = _json(response)
                assert payload["error"]["code"] == "BAD_REQUEST"
                _assert_false_locks_and_no_claims(payload)


def test_v51_missing_configured_artifact_dir_blocks_without_creating_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-v51-artifacts"
    app_module = _reload_app(monkeypatch, KRONOS_V51_ARTIFACT_DIR=str(missing_dir))
    client = app_module.app.test_client()

    response = client.get("/api/daily-close-v51/source-coverage")
    payload = _json(response)

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert payload["route_id"] == "SOURCE_COVERAGE"
    assert payload["status"] == "BLOCKED"
    assert payload["status_reason"] == "BLOCKED_ARTIFACT_UNAVAILABLE"
    _assert_false_locks_and_no_claims(payload)
    assert app_module.app.config["KRONOS_V51_ARTIFACT_DIR"] == str(missing_dir.resolve(strict=False))
    assert app_module.app.config["KRONOS_V51_AVAILABLE"] is False
    assert not missing_dir.exists()


def test_v51_route_methods_are_registered_on_all_seven_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _reload_app(monkeypatch)
    by_rule = {rule.rule: rule for rule in app_module.app.url_map.iter_rules() if rule.rule in EXPECTED_V51_RULES}

    assert set(by_rule) == EXPECTED_V51_RULES
    for rule in by_rule.values():
        assert set(V51_METHODS) <= rule.methods
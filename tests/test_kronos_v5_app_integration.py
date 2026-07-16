from __future__ import annotations

from contextlib import contextmanager
import importlib
import json
import sys
import types
from pathlib import Path

import pytest
from flask import Blueprint, jsonify, request


V5_ENV = (
    "KRONOS_V5_REGISTRY_PATH",
    "KRONOS_V5_ARTIFACT_ROOT",
    "KRONOS_V5_CURSOR_KEY",
    "KRONOS_V5_CURSOR_KEY_HEX",
    "KRONOS_V5_FIXTURE_MODE",
)
V5_METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
EXPECTED_LEGACY_POST_RULES = {
    "/api/trading-command/jobs",
    "/api/daily-ohlcv/research-workflows/<workflow_id>/job-intents",
    "/api/load-data",
    "/api/predict",
    "/api/load-model",
}
CANONICAL_QUERY_SCOPED_V5_RULES = {
    "/api/v5/rl/matrix",
    "/api/v5/rl/ledger",
    "/api/v5/rl/artifacts",
}
NONCANONICAL_NESTED_V5_RULES = {
    "/api/v5/rl/runs/<run_id>/matrix",
    "/api/v5/rl/runs/<run_id>/ledger",
    "/api/v5/rl/runs/<run_id>/artifacts",
}
SIX_FALSE_LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}


def _clear_v5_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in V5_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: pytest.MonkeyPatch):
    yield
    _clear_v5_env(monkeypatch)
    if "webui.app" in sys.modules:
        importlib.reload(sys.modules["webui.app"])


def _reload_app(monkeypatch: pytest.MonkeyPatch, **env: str):
    _clear_v5_env(monkeypatch)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    import webui.app as app_module
    return importlib.reload(app_module)


@contextmanager
def _fake_v5_modules(captured: dict[str, object]):
    originals = {name: sys.modules.get(name) for name in ("webui.v5_rl_api", "stom_rl.v5_registry")}
    missing = {name for name, module in originals.items() if module is None}

    api_module = types.ModuleType("webui.v5_rl_api")
    registry_module = types.ModuleType("stom_rl.v5_registry")

    class FakeRegistry:
        def __init__(self, path, *, cursor_keys):
            resolved = Path(path).resolve(strict=False)
            assert resolved.is_file()
            captured["registry_init_path"] = resolved
            captured["registry_cursor_keys"] = dict(cursor_keys)

        def runs_payload(self):
            return {
                "route_id": "RUNS",
                "source": {
                    "source_sha256": "a" * 64,
                    "generated_at": "2026-07-15T00:00:00Z",
                },
                "list": {"items": [], "next_cursor": None},
                "locks": dict(SIX_FALSE_LOCKS),
            }

    def create_v5_rl_api_blueprint(*, registry_path=None, registry_provider=None, cursor_key=None, artifact_root=None, unavailable_reason=None, **_kwargs):
        captured["factory_registry_path"] = Path(registry_path).resolve(strict=False) if registry_path is not None else None
        captured["factory_artifact_root"] = Path(artifact_root).resolve(strict=False) if artifact_root is not None else None
        captured["factory_cursor_key"] = cursor_key
        captured["factory_unavailable_reason"] = unavailable_reason
        bp = Blueprint("fake_kronos_v5_rl_api", __name__, url_prefix="/api/v5/rl")

        @bp.route("/runs", methods=list(V5_METHODS), provide_automatic_options=False)
        def runs():
            if request.method != "GET":
                return jsonify({"route_id": "RUNS", "error": {"code": "BAD_REQUEST", "message": "method not allowed"}}), 405
            if unavailable_reason:
                return jsonify({"route_id": "RUNS", "error": {"code": "INTERNAL_ERROR", "message": unavailable_reason}}), 503
            return jsonify(registry_provider().runs_payload())

        return bp

    api_module.create_v5_rl_api_blueprint = create_v5_rl_api_blueprint
    registry_module.KronosV5Registry = FakeRegistry
    sys.modules["webui.v5_rl_api"] = api_module
    sys.modules["stom_rl.v5_registry"] = registry_module
    try:
        yield
    finally:
        for name, module in originals.items():
            if name in missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _json(response) -> dict[str, object]:
    return json.loads(response.get_data(as_text=True))


def test_app_import_registers_v5_prefix_and_preserves_legacy_post_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _reload_app(monkeypatch)
    rules = list(app_module.app.url_map.iter_rules())

    v5_rules = [rule for rule in rules if rule.rule.startswith("/api/v5/")]
    assert v5_rules, "official Flask app must register V5 routes at import time"
    assert all(rule.rule.startswith("/api/v5/rl") for rule in v5_rules)
    assert "/api/v5/rl/runs" in {rule.rule for rule in v5_rules}
    v5_rule_paths = {rule.rule for rule in v5_rules}
    assert CANONICAL_QUERY_SCOPED_V5_RULES <= v5_rule_paths
    assert not (NONCANONICAL_NESTED_V5_RULES & v5_rule_paths)

    legacy_post_rules = {rule.rule for rule in rules if "POST" in rule.methods and not rule.rule.startswith("/api/v5/")}
    assert legacy_post_rules == EXPECTED_LEGACY_POST_RULES


def test_v5_absent_store_fails_closed_without_creating_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = tmp_path / "missing-store" / "registry.sqlite"
    artifact_root = tmp_path / "missing-artifacts"
    app_module = _reload_app(
        monkeypatch,
        KRONOS_V5_REGISTRY_PATH=str(registry_path),
        KRONOS_V5_ARTIFACT_ROOT=str(artifact_root),
        KRONOS_V5_CURSOR_KEY_HEX="11" * 32,
    )

    response = app_module.app.test_client().get("/api/v5/rl/runs")

    assert response.status_code == 503
    assert response.mimetype == "application/json"
    assert len(response.get_data()) < 1024
    assert _json(response)["route_id"] == "RUNS"
    assert not registry_path.exists()
    assert not registry_path.parent.exists()
    assert not artifact_root.exists()


def test_v5_mutating_methods_are_405(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _reload_app(
        monkeypatch,
        KRONOS_V5_REGISTRY_PATH=str(tmp_path / "missing.sqlite"),
        KRONOS_V5_CURSOR_KEY_HEX="22" * 32,
    )
    client = app_module.app.test_client()

    for method in ("POST", "PATCH", "DELETE"):
        response = client.open("/api/v5/rl/runs", method=method)
        assert response.status_code == 405, method
        assert _json(response)["error"]["code"] == "BAD_REQUEST"


def test_v5_temp_configured_registry_is_injected_without_default_mutation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = tmp_path / "configured" / "registry.sqlite"
    artifact_root = tmp_path / "configured-artifacts"
    registry_path.parent.mkdir()
    registry_path.write_bytes(b"synthetic registry placeholder")
    artifact_root.mkdir()
    captured: dict[str, object] = {}

    with _fake_v5_modules(captured):
        app_module = _reload_app(
            monkeypatch,
            KRONOS_V5_REGISTRY_PATH=str(registry_path),
            KRONOS_V5_ARTIFACT_ROOT=str(artifact_root),
            KRONOS_V5_CURSOR_KEY_HEX="33" * 32,
        )
        response = app_module.app.test_client().get("/api/v5/rl/runs")

    assert response.status_code == 200
    assert _json(response)["route_id"] == "RUNS"
    assert app_module.app.config["KRONOS_V5_AVAILABLE"] is True
    assert captured["factory_unavailable_reason"] is None
    assert captured["factory_registry_path"] == registry_path.resolve(strict=False)
    assert captured["factory_artifact_root"] == artifact_root.resolve(strict=False)
    assert captured["factory_cursor_key"] == bytes.fromhex("33" * 32)
    assert captured["registry_init_path"] == registry_path.resolve(strict=False)
    assert captured["registry_cursor_keys"] == {"api": bytes.fromhex("33" * 32)}

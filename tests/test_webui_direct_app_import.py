from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from webui import app as app_module

PAYLOAD_ADAPTER = TypeAdapter(dict[str, object])


def test_direct_app_import_keeps_research_telemetry_and_governance_routes() -> None:
    # Given: the same top-level import context used by `py webui/app.py`.
    repository_root = Path(__file__).resolve().parents[1]
    script = (
        "import json, app; "
        "diagnostics=app.app.config['KRONOS_SUBSYSTEM_DIAGNOSTICS']; "
        "routes=sorted(str(rule) for rule in app.app.url_map.iter_rules()); "
        "print(json.dumps({'diagnostics':diagnostics,'routes':routes}))"
    )

    # When: the dashboard application is constructed from the webui directory.
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository_root / "webui",
        capture_output=True,
        check=True,
        text=True,
    )
    payload = PAYLOAD_ADAPTER.validate_json(completed.stdout)
    diagnostics = PAYLOAD_ADAPTER.validate_python(payload["diagnostics"])
    routes = TypeAdapter(tuple[str, ...]).validate_python(payload["routes"])

    # Then: the UI cannot start successfully while omitting its read-only APIs.
    for subsystem in (
        "v6_platform",
        "v6_insight",
        "v6_research",
        "v6_telemetry",
        "v6_governance",
    ):
        state = PAYLOAD_ADAPTER.validate_python(diagnostics[subsystem])
        assert state["available"] is True
    assert "/api/v6/summary" in routes
    assert "/api/v6/telemetry-runs" in routes
    assert "/api/v6/governance-summary" in routes
    assert "/api/v6/status" in routes
    assert "/api/v6/insight/regime" in routes


def test_v6_research_catalog_uses_configured_read_only_runs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an explicit directory accepted as the catalog's read-only root.
    run_root = tmp_path / "runs"
    run_root.mkdir()
    monkeypatch.setenv("KRONOS_V6_RESEARCH_RUNS_ROOT", str(run_root))

    # When: the Flask app wires its V6 research blueprint.
    target = app_module.create_app()

    # Then: the configured directory is usable and the research API remains present.
    assert target.config["KRONOS_SUBSYSTEM_DIAGNOSTICS"]["v6_research"] == {
        "available": True
    }
    with target.test_client() as client:
        response = client.get("/api/v6/research-runs")
    assert response.status_code == 200
    assert response.get_json()["total"] == 0


@pytest.mark.parametrize("kind", ("missing", "file"))
def test_v6_research_catalog_rejects_invalid_configured_runs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    # Given: a nonexistent path or a regular file, neither of which is a root.
    configured = tmp_path / kind
    if kind == "file":
        _ = configured.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("KRONOS_V6_RESEARCH_RUNS_ROOT", str(configured))

    # When: construction observes the invalid explicit configuration.
    target = app_module.create_app()

    # Then: research is fail-closed rather than silently falling back to defaults.
    diagnostic = target.config["KRONOS_SUBSYSTEM_DIAGNOSTICS"]["v6_research"]
    assert diagnostic["available"] is False
    assert diagnostic["error"]["type"] in {"FileNotFoundError", "RuntimeError"}
    assert not any(
        rule.rule == "/api/v6/research-runs" for rule in target.url_map.iter_rules()
    )

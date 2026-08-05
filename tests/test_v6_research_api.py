"""HTTP contract coverage for the lightweight V6 research API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask

from webui import v6_research_api
from webui.v6_research_api import create_v6_research_blueprint


@pytest.fixture()
def research_root(tmp_path: Path) -> Path:
    run = tmp_path / "daily_close_cql_seed0"
    run.mkdir()
    (run / "rl_live_summary.json").write_text(
        json.dumps({"status": "NO_GO", "algorithm": "CQL", "dataset_id": "daily-close-v2"}),
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text('{"step":1}\n', encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(research_root: Path):
    app = Flask(__name__)
    app.register_blueprint(create_v6_research_blueprint(runs_root=research_root))
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_summary_is_lightweight_and_separates_program_from_economic_score(client) -> None:
    # Given / When
    response = client.get("/api/v6/summary")
    payload = response.get_json()

    # Then
    assert response.status_code == 200
    assert payload["schema_version"] == "kronos_v6_research_summary.v1"
    assert payload["program"] == {
        "maturity_score": 63,
        "implementation_score": 78,
        "economic_model_score": 20,
        "live_readiness_score": 0,
    }
    assert payload["catalog"]["total"] == 1
    assert payload["catalog"]["by_status"] == {"NO_GO": 1}


def test_catalog_filters_and_exposes_permanent_detail_url(client) -> None:
    # Given / When
    response = client.get("/api/v6/research-runs?lane=daily_close&status=NO_GO&page=1&page_size=20")
    payload = response.get_json()

    # Then
    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["run_id"] == "daily_close_cql_seed0"
    assert payload["items"][0]["detail_url"] == "/api/v6/research-runs/daily_close_cql_seed0"


def test_run_detail_lists_bounded_artifacts_without_opening_them(client) -> None:
    # Given / When
    response = client.get("/api/v6/research-runs/daily_close_cql_seed0")
    payload = response.get_json()

    # Then
    assert response.status_code == 200
    assert payload["run"]["algorithm"] == "CQL"
    assert [artifact["name"] for artifact in payload["artifacts"]] == ["events.jsonl", "rl_live_summary.json"]
    assert all("content" not in artifact for artifact in payload["artifacts"])


def test_research_api_fails_closed_for_invalid_queries_methods_and_paths(client) -> None:
    # Given / When / Then
    assert client.get("/api/v6/research-runs?page=0").status_code == 400
    assert client.get("/api/v6/research-runs?page_size=1000").status_code == 400
    assert client.get("/api/v6/research-runs?unexpected=1").status_code == 400
    assert client.get("/api/v6/research-runs/..%2Fsecret").status_code == 400
    assert client.get("/api/v6/research-runs/missing").status_code == 404
    post = client.post("/api/v6/research-runs")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"


def test_official_dashboard_registers_the_research_catalog_routes() -> None:
    # Given
    from webui.app import app as dashboard_app

    # When
    routes = {rule.rule for rule in dashboard_app.url_map.iter_rules()}

    # Then
    assert "/api/v6/summary" in routes
    assert "/api/v6/research-runs" in routes
    assert "/api/v6/research-runs/<path:run_id>" in routes


def test_summary_catalog_and_detail_share_one_warmed_snapshot(monkeypatch, research_root: Path) -> None:
    # Given
    calls = 0
    now = [0.0]
    original = v6_research_api.discover_runs

    def counted(root: Path):
        nonlocal calls
        calls += 1
        return original(root)

    monkeypatch.setattr(v6_research_api, "discover_runs", counted)
    app = Flask(__name__)
    app.register_blueprint(create_v6_research_blueprint(runs_root=research_root, clock=lambda: now[0]))
    now[0] = 10.0

    # When
    with app.test_client() as test_client:
        assert test_client.get("/api/v6/summary").status_code == 200
        assert test_client.get("/api/v6/research-runs").status_code == 200
        assert test_client.get("/api/v6/research-runs/daily_close_cql_seed0").status_code == 200

    # Then
    assert calls == 1

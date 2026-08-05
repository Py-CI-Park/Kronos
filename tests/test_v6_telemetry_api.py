"""HTTP contract coverage for the V6 telemetry API."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

from webui.v6_telemetry_api import create_v6_telemetry_blueprint


def _client(tmp_path: Path):
    run = tmp_path / "daily_close_dqn"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        json.dumps({"global_step": 7, "phase": "train", "reward": 0.04, "equity": 1.02}) + "\n",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_telemetry_blueprint(runs_root=tmp_path))
    app.config.update(TESTING=True)
    return app.test_client()


def test_telemetry_api_lists_runs_and_returns_bounded_points(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When
    listing = client.get("/api/v6/telemetry-runs")
    telemetry = client.get("/api/v6/research-runs/daily_close_dqn/telemetry?limit=120")

    # Then
    assert listing.status_code == 200
    assert listing.get_json()["items"][0]["run_id"] == "daily_close_dqn"
    assert telemetry.status_code == 200
    payload = telemetry.get_json()
    assert payload["follow_mode"] == "FOLLOWING_FILE"
    assert payload["points"] == [
        {
            "step": 7,
            "phase": "train",
            "reward": 0.04,
            "equity": 1.02,
            "loss": None,
            "exploration": None,
            "action_name": "MISSING",
            "timestamp": "MISSING",
        }
    ]


def test_telemetry_api_rejects_invalid_limit_path_and_method(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When / Then
    assert client.get("/api/v6/research-runs/daily_close_dqn/telemetry?limit=2").status_code == 400
    assert client.get("/api/v6/research-runs/..%2Fsecret/telemetry").status_code == 400
    assert client.get("/api/v6/research-runs/missing/telemetry").status_code == 404
    post = client.post("/api/v6/telemetry-runs")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"


def test_official_dashboard_registers_telemetry_routes() -> None:
    # Given
    from webui.app import app as dashboard_app

    # When
    routes = {rule.rule for rule in dashboard_app.url_map.iter_rules()}

    # Then
    assert "/api/v6/telemetry-runs" in routes
    assert "/api/v6/research-runs/<path:run_id>/telemetry" in routes

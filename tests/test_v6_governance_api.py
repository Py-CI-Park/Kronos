"""HTTP contract coverage for the lightweight governance summary API."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

from webui.v6_governance_api import create_v6_governance_blueprint


def test_governance_summary_is_read_only_and_preserves_sealed_claims(tmp_path: Path) -> None:
    # Given
    (tmp_path / "kronos_v9_prereg_daily.json").write_text(
        json.dumps({"prereg_id": "daily-v9", "status": "FROZEN", "frozen_utc": "2026-08-05T00:00:00Z"}),
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_governance_blueprint(docs_root=tmp_path))
    app.config.update(TESTING=True)

    # When
    with app.test_client() as client:
        response = client.get("/api/v6/governance-summary")
        bad_query = client.get("/api/v6/governance-summary?detail=1")
        post = client.post("/api/v6/governance-summary")

    # Then
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["preregistrations"][0]["prereg_id"] == "daily-v9"
    assert payload["claims"] == {"fresh_oos_opened": False, "promotion_allowed": False, "human_approval_required": True}
    assert bad_query.status_code == 400
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"


def test_official_dashboard_registers_governance_summary_route() -> None:
    # Given
    from webui.app import app as dashboard_app

    # When
    routes = {rule.rule for rule in dashboard_app.url_map.iter_rules()}

    # Then
    assert "/api/v6/governance-summary" in routes

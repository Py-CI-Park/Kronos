"""Contract coverage for the read-only V6 platform API."""
from __future__ import annotations

import pytest

from webui.app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_v6_routes_return_expected_readiness_payloads(client) -> None:
    status = client.get("/api/v6/status")
    universe = client.get("/api/v6/universe")
    readiness = client.get("/api/v6/data-readiness")

    assert status.status_code == universe.status_code == readiness.status_code == 200
    assert {"schema_version", "status", "journey", "locks"} <= set(status.get_json())
    assert {"universe", "sha256", "total"} <= set(universe.get_json())
    assert {"daily_db", "fivemin_db", "audit", "index", "price_basis"} <= set(readiness.get_json())


def test_v6_rejects_non_get_methods_with_json_envelope(client) -> None:
    for method in (client.post, client.put, client.delete):
        response = method("/api/v6/status")
        assert response.status_code == 405
        assert response.headers["Allow"] == "GET"
        assert response.get_json() == {"status": "ERROR", "error": {"code": "METHOD_NOT_ALLOWED"}}


def test_v6_universe_limit_and_false_locks(client) -> None:
    universe = client.get("/api/v6/universe?limit=5").get_json()
    status = client.get("/api/v6/status").get_json()

    assert len(universe["universe"]) == 5
    assert universe["total"] == 500
    assert status["locks"] == {
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
    }


def test_v6_readiness_exposes_price_basis_and_index_blocker(client) -> None:
    readiness = client.get("/api/v6/data-readiness").get_json()

    assert readiness["price_basis"]["status"] == "UNKNOWN_CONFIRMED"
    assert readiness["index"]["state"] == "BLOCKED_INDEX_SERIES_SOURCE"


def test_v6_rejects_unknown_query_parameters(client) -> None:
    response = client.get("/api/v6/status?unexpected=value")

    assert response.status_code == 400
    assert response.get_json() == {"status": "ERROR", "error": {"code": "BAD_REQUEST"}}

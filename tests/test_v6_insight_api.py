"""Contract coverage for the read-only V6 insight API."""
from __future__ import annotations

import json
import sqlite3

import pytest

from webui import v6_insight_api
from webui.app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def insight_data(monkeypatch, tmp_path):
    database_path = tmp_path / "daily.db"
    manifest_path = tmp_path / "universe.json"
    connection = sqlite3.connect(database_path)
    for code, foreign_start, foreign_end, netbuy in (
        ("000001", 1.0, 4.0, 10.0),
        ("000002", 4.0, 1.0, -20.0),
        ("000003", 2.0, 2.5, 5.0),
    ):
        table = f"A{code}"
        connection.execute(
            f'CREATE TABLE "{table}" (date INTEGER, close REAL, volume REAL, 외국인현보유비율 REAL, 기관순매수 REAL)'
        )
        for day in range(1, 102):
            foreign = foreign_start + (foreign_end - foreign_start) * (day - 1) / 100
            connection.execute(
                f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?)',
                (20260100 + day, float(day + int(code)), float(day * 10), foreign, netbuy),
            )
    connection.commit()
    connection.close()
    manifest_path.write_text(
        json.dumps({"universe": [{"table": f"A{code}"} for code in ("000001", "000002", "000003")]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(v6_insight_api, "DAILY_DB_PATH", database_path)
    monkeypatch.setattr(v6_insight_api, "UNIVERSE_MANIFEST_PATH", manifest_path)
    v6_insight_api._FLOW_CACHE.clear()
    v6_insight_api._REGIME_CACHE.clear()
    return database_path


def test_symbol_shape_and_sampling_preserves_endpoints(client, insight_data) -> None:
    response = client.get("/api/v6/insight/symbol?code=000001&max_points=100")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["schema_version"] == "kronos_v6_insight_symbol.v1"
    assert payload["sampled"] is True
    assert payload["series"][0]["date"] == 20260101
    assert payload["series"][-1]["date"] == 20260201
    assert {"close", "volume", "foreign_ratio", "inst_netbuy"} <= set(payload["series"][0])


def test_symbol_rejects_bad_code_and_blocks_missing_table(client, insight_data) -> None:
    assert client.get("/api/v6/insight/symbol?code=abc").status_code == 400
    response = client.get("/api/v6/insight/symbol?code=999999")
    assert response.get_json() == {"status": "BLOCKED", "reason": "SYMBOL_TABLE_MISSING"}


def test_flow_ranks_planted_data_and_is_observation_only(client, insight_data) -> None:
    payload = client.get("/api/v6/insight/flow?window=5&limit=5").get_json()

    assert payload["top_inst_buy"][0]["code"] == "000001"
    assert payload["top_inst_sell"][0]["code"] == "000002"
    assert payload["top_foreign_gain"][0]["code"] == "000001"
    assert payload["top_foreign_loss"][0]["code"] == "000002"
    assert payload["not_a_recommendation"] is True


def test_regime_blocks_index_and_returns_breadth_proxy(client, insight_data, monkeypatch, tmp_path) -> None:
    from webui import v6_platform_api

    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path / "missing-index")

    payload = client.get("/api/v6/insight/regime").get_json()

    assert payload["index_regime"] == {
        "state": "BLOCKED_INDEX_SERIES_SOURCE",
        "reason": "KRX credentials required for pykrx collection",
    }
    assert {"as_of_date", "tables_evaluated", "pct_above_20s_mean", "disclaimer"} <= set(payload["breadth_proxy"])


def test_regime_reports_present_index_observation(client, insight_data, monkeypatch, tmp_path) -> None:
    from webui import v6_platform_api

    from tests.test_v6_platform_api import _write_index_artifacts

    _write_index_artifacts(tmp_path)
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path)

    payload = client.get("/api/v6/insight/regime").get_json()
    regime = payload["index_regime"]

    assert regime["state"] == "PRESENT"
    assert set(regime["markets"]) == {"KOSPI", "KOSDAQ"}
    kospi = regime["markets"]["KOSPI"]
    assert kospi["last_date"] == "2024-01-05"
    assert kospi["last_close"] == pytest.approx(2600.0 * 1.02)
    assert kospi["window_days"] == 3
    assert kospi["pct_vs_20d_mean"] == pytest.approx((1.02 / ((1 + 1.01 + 1.02) / 3) - 1.0) * 100.0)
    assert "not a trading signal" in regime["caveat"]
    assert {"as_of_date", "tables_evaluated", "pct_above_20s_mean", "disclaimer"} <= set(payload["breadth_proxy"])


def test_rejects_post_and_unknown_parameters(client, insight_data) -> None:
    response = client.post("/api/v6/insight/flow")
    assert response.status_code == 405
    assert response.headers["Allow"] == "GET"
    assert response.get_json() == {"status": "ERROR", "error": {"code": "METHOD_NOT_ALLOWED"}}
    assert client.get("/api/v6/insight/regime?unexpected=value").status_code == 400

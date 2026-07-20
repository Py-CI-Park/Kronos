"""Contract coverage for the read-only V6 platform API."""
from __future__ import annotations

import hashlib
import json

import pytest

from webui import v6_platform_api
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
    for path in ("/api/v6/status", "/api/v6/experiment", "/api/v6/runs", "/api/v6/run-detail"):
        response = client.post(path)
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
    response = client.get("/api/v6/run-detail?dataset=dataset-1&train=train-1&unexpected=value")

    assert response.status_code == 400
    assert response.get_json() == {"status": "ERROR", "error": {"code": "BAD_REQUEST"}}

@pytest.mark.parametrize("dataset, train", [("../x", "train-1"), ("dataset-1", "a b")])
def test_v6_run_detail_rejects_bad_ids(client, dataset, train) -> None:
    response = client.get("/api/v6/run-detail", query_string={"dataset": dataset, "train": train})

    assert response.status_code == 400
    assert response.get_json() == {"status": "ERROR", "error": {"code": "BAD_REQUEST"}}


def test_v6_run_detail_blocks_when_manifest_is_missing(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", tmp_path / "missing-runs")

    response = client.get("/api/v6/run-detail?dataset=dataset-1&train=train-1")

    assert response.status_code == 200
    assert response.get_json() == {"status": "BLOCKED", "reason": "RUN_MANIFEST_MISSING"}


def test_v6_run_detail_returns_manifest_sha_and_event_tail(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "dataset-1" / "train_1"
    run_dir.mkdir(parents=True)
    manifest = {"verdict_candidate": "NO_GO", "metrics": {"score": 0.0}}
    raw = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    (run_dir / "run_manifest.json").write_bytes(raw)
    (run_dir / "events.jsonl").write_text(
        '{"event":"started"}\nnot-json\n{"event":"finished"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    response = client.get("/api/v6/run-detail?dataset=dataset-1&train=1")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "schema_version": "kronos_v6_run_detail.v1",
        "status": "OK",
        "dataset_run_id": "dataset-1",
        "train_run_id": "train_1",
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "events_tail": [{"event": "started"}, {"event": "finished"}],
    }

def test_v6_experiment_reports_unfrozen_preregistration_and_read_only_plan(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "PREREG_PATH", tmp_path / "missing-prereg.json")

    payload = client.get("/api/v6/experiment").get_json()

    assert payload["prereg"] == {
        "state": "NOT_FROZEN",
        "path": "docs/kronos_v6_prereg_h1_2026-07-19.json",
        "sha256": None,
    }
    assert {"capital", "costs", "universe"} <= set(payload["planned"])
    assert payload["locks"] == {
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
    }


def test_v6_experiment_reports_frozen_preregistration(client, monkeypatch, tmp_path) -> None:
    prereg_path = tmp_path / "prereg.json"
    prereg = {"hypothesis": "H1 remains exploratory", "frozen_utc": "2026-07-19T00:00:00Z"}
    raw = json.dumps(prereg).encode("utf-8")
    prereg_path.write_bytes(raw)
    monkeypatch.setattr(v6_platform_api, "PREREG_PATH", prereg_path)

    payload = client.get("/api/v6/experiment").get_json()

    assert payload["prereg"] == {
        "state": "FROZEN",
        "path": "docs/kronos_v6_prereg_h1_2026-07-19.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        **prereg,
    }
    assert client.get("/api/v6/status").get_json()["journey"]["experiment"]["state"] == "FROZEN"


def test_v6_runs_returns_empty_payload_when_runs_root_is_absent(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", tmp_path / "missing-runs")

    payload = client.get("/api/v6/runs").get_json()

    assert payload == {
        "schema_version": "kronos_v6_runs.v1",
        "status": "OK",
        "datasets": [],
        "runs": [],
        "training_state": "NOT_RUN",
    }


def test_v6_runs_lists_dataset_manifest(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    manifest_path = runs_root / "dataset-1" / "dataset_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = {
        "run_id": "dataset-1",
        "generated_utc": "2026-07-19T00:00:00Z",
        "split_row_counts": {"train": 10, "validation": 5},
    }
    raw = json.dumps(manifest).encode("utf-8")
    manifest_path.write_bytes(raw)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    payload = client.get("/api/v6/runs").get_json()

    assert payload["training_state"] == "NOT_RUN"
    assert payload["runs"] == []
    assert payload["datasets"] == [{
        "run_id": "dataset-1",
        "path": manifest_path.as_posix(),
        "generated_utc": "2026-07-19T00:00:00Z",
        "split_row_counts": {"train": 10, "validation": 5},
        "sha256": hashlib.sha256(raw).hexdigest(),
    }]

    run_manifest_path = runs_root / "dataset-1" / "train-1" / "run_manifest.json"
    run_manifest_path.parent.mkdir()
    run_manifest_path.write_text(
        json.dumps({"dataset_run_id": "dataset-1", "verdict_candidate": "NO_GO"}),
        encoding="utf-8",
    )

    runs = client.get("/api/v6/runs").get_json()["runs"]

    assert runs == [{
        "run_id": "train-1",
        "dataset_run_id": "dataset-1",
        "path": run_manifest_path.as_posix(),
        "state": None,
        "seeds": [],
        "generated_utc": None,
        "verdict_candidate": "NO_GO",
    }]

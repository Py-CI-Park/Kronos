"""Contract coverage for the read-only V6 platform API."""
from __future__ import annotations

import hashlib
import json

import os
import pytest
from pathlib import Path

from webui import v6_platform_api
from webui.app import app

@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client

def _write_index_artifacts(directory):
    """Write valid KOSPI/KOSDAQ normalized artifacts through the custody boundary."""
    from stom_rl.korean_index_source import collect_index_artifacts, write_normalized_index_artifact

    def provider(*, market, index_code, index_name, start_date, end_date):
        base = 2600.0 if market == "KOSPI" else 800.0
        return [
            {"date": "2024-01-02", "종가": base},
            {"date": "2024-01-03", "종가": base * 1.01},
            {"date": "2024-01-05", "종가": base * 1.02},
        ]

    written = {}
    for market in ("KOSPI", "KOSDAQ"):
        artifacts = collect_index_artifacts(
            market=market,
            start_date="2024-01-02",
            end_date="2024-01-05",
            provider=provider,
            collected_at="2026-07-20T00:00:00Z",
        )
        written[market] = write_normalized_index_artifact(directory, artifacts["normalized"])
    return written



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


def test_v6_readiness_exposes_price_basis_and_index_blocker(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path / "missing-index")

    readiness = client.get("/api/v6/data-readiness").get_json()
    status = client.get("/api/v6/status").get_json()

    assert readiness["price_basis"]["status"] == "UNKNOWN_CONFIRMED"
    assert readiness["index"] == {
        "state": "BLOCKED_INDEX_SERIES_SOURCE",
        "reason": "KRX credentials required for pykrx collection",
    }
    assert status["journey"]["data"]["index_overlay"] == "BLOCKED_INDEX_SERIES_SOURCE"
    assert status["journey"]["data"]["index_blocker_reason"] == "KRX credentials required for pykrx collection"


def test_v6_index_present_state_and_series_route(client, monkeypatch, tmp_path) -> None:
    _write_index_artifacts(tmp_path)
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path)

    readiness = client.get("/api/v6/data-readiness").get_json()
    status = client.get("/api/v6/status").get_json()
    series = client.get("/api/v6/index-series?market=KOSPI").get_json()

    assert readiness["index"]["state"] == "PRESENT"
    assert set(readiness["index"]["markets"]) == {"KOSPI", "KOSDAQ"}
    assert readiness["index"]["markets"]["KOSPI"]["row_count"] == 3
    assert status["journey"]["data"]["index_overlay"] == "PRESENT"
    assert "index_blocker_reason" not in status["journey"]["data"]
    assert series["schema_version"] == "kronos_v6_index_series.v1"
    assert series["market"] == "KOSPI"
    assert series["index_code"] == "1001"
    assert [row["date"] for row in series["series"]] == ["2024-01-02", "2024-01-03", "2024-01-05"]
    assert series["row_count"] == 3
    assert series["provider_package"] == {"name": "pykrx", "version": "1.2.8", "required_version": "1.2.8"}
    assert series["normalization_method"] == "extract_close_levels_without_interpolation_fill_or_fallback"
    assert series["hashes"]["normalized_sha256"] == readiness["index"]["markets"]["KOSPI"]["normalized_sha256"]
    assert all(value is False for value in series["false_locks"].values())
    assert all(value is False for value in series["claims"].values())


def test_v6_index_series_blocked_and_bad_requests(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path / "empty")

    blocked = client.get("/api/v6/index-series?market=KOSPI")
    assert blocked.status_code == 404
    assert blocked.get_json() == {"status": "BLOCKED", "reason": "BLOCKED_INDEX_SERIES_SOURCE"}

    assert client.get("/api/v6/index-series").status_code == 400
    assert client.get("/api/v6/index-series?market=NASDAQ").status_code == 400
    assert client.get("/api/v6/index-series?market=KOSPI&market=KOSDAQ").status_code == 400
    assert client.get("/api/v6/index-series?market=KOSPI&unexpected=1").status_code == 400
    post = client.post("/api/v6/index-series")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"
    assert post.get_json() == {"status": "ERROR", "error": {"code": "METHOD_NOT_ALLOWED"}}


def test_v6_index_tampered_artifact_fails_closed(client, monkeypatch, tmp_path) -> None:
    written = _write_index_artifacts(tmp_path)
    tampered = json.loads(written["KOSPI"].read_text(encoding="utf-8"))
    tampered["series"][0]["close"] = 1.0
    written["KOSPI"].write_text(json.dumps(tampered, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path)

    readiness = client.get("/api/v6/data-readiness").get_json()

    assert readiness["index"]["state"] == "BLOCKED_INDEX_SERIES_SOURCE"
    assert client.get("/api/v6/index-series?market=KOSPI").status_code == 404
    assert client.get("/api/v6/index-series?market=KOSDAQ").status_code == 200
def test_v6_index_cache_revalidates_same_stat_tampering_and_prunes_deleted_paths(monkeypatch, tmp_path) -> None:
    written = _write_index_artifacts(tmp_path)
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path)
    v6_platform_api._INDEX_OVERLAY_CACHE.clear()

    assert "KOSPI" in v6_platform_api._index_overlays()
    path = written["KOSPI"]
    original_stat = path.stat()
    original = path.read_bytes()
    artifact = json.loads(original)
    old_value = artifact["series"][0]["close"]
    new_value = old_value - 1000
    old_token = json.dumps(old_value).encode("ascii")
    new_token = json.dumps(new_value).encode("ascii")
    assert len(old_token) == len(new_token)
    needle = next(
        candidate
        for candidate in (b'"close":' + old_token, b'"close": ' + old_token)
        if candidate in original
    )
    replacement = needle.removesuffix(old_token) + new_token
    tampered = original.replace(needle, replacement, 1)
    assert tampered != original
    path.write_bytes(tampered)
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert "KOSPI" not in v6_platform_api._index_overlays()
    path.unlink()
    v6_platform_api._index_overlays()
    assert path.as_posix() not in v6_platform_api._INDEX_OVERLAY_CACHE


def test_v6_index_cache_is_bounded(monkeypatch, tmp_path) -> None:
    written = _write_index_artifacts(tmp_path)
    source = written["KOSPI"].read_bytes()
    for index in range(v6_platform_api._INDEX_OVERLAY_CACHE_LIMIT + 1):
        (tmp_path / f"korean-index-copy-{index}-normalized-test.json").write_bytes(source)
    monkeypatch.setattr(v6_platform_api, "INDEX_ARTIFACT_DIR", tmp_path)
    v6_platform_api._INDEX_OVERLAY_CACHE.clear()

    v6_platform_api._index_overlays()

    assert len(v6_platform_api._INDEX_OVERLAY_CACHE) <= v6_platform_api._INDEX_OVERLAY_CACHE_LIMIT


def test_v6_registry_reuses_single_request_report_snapshot(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    _write_valid_report_chain(runs_root, docs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)
    calls = 0
    original = v6_platform_api._build_report_entries

    def counted():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(v6_platform_api, "_build_report_entries", counted)
    assert client.get("/api/v6/research-registry").status_code == 200
    assert calls == 1


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
    run_dir = runs_root / "dataset-1" / "train-1"
    run_dir.mkdir(parents=True)
    manifest = {"verdict_candidate": "NO_GO", "metrics": {"score": 0.0}}
    raw = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    (run_dir / "run_manifest.json").write_bytes(raw)
    (run_dir / "events.jsonl").write_bytes(
        b'{"event":"started"}\nnot-json\n{"event":"finished"}\n'
    )
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    response = client.get("/api/v6/run-detail?dataset=dataset-1&train=train-1")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "schema_version": "kronos_v6_run_detail.v1",
        "status": "OK",
        "dataset_run_id": "dataset-1",
        "train_run_id": "train-1",
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "events_tail": [{"event": "started"}, {"event": "finished"}],
        "events_tail_diagnostics": {
            "state": "PARTIAL",
            "invalid_line_count": 1,
            "bytes_scanned": len(b'{"event":"started"}\nnot-json\n{"event":"finished"}\n'),
            "truncated": False,
        },
        "states": {
            "training_state": "MISSING",
            "validation_state": "NOT_RECORDED",
            "test_state": "MISSING",
            "evaluation_state": "TEST_MISSING",
        },
    }


def test_v6_events_tail_is_bounded_and_preserves_newest_object_events(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    with path.open("wb") as event_file:
        event_file.write((b'{"padding":"' + b"x" * 1024 + b'"}\n') * 1100)
        for index in range(60):
            event_file.write(json.dumps({"event": index}).encode("utf-8") + b"\n")

    events, diagnostics = v6_platform_api._events_tail(path)

    assert events == [{"event": index} for index in range(10, 60)]
    assert diagnostics["bytes_scanned"] <= 1024 * 1024
    assert diagnostics["truncated"] is True
    assert diagnostics["state"] == "PARTIAL"


@pytest.mark.parametrize(
    ("contents", "state", "invalid_count"),
    [(None, "MISSING", 0), (b"", "EMPTY", 0), (b"not-json\n", "CORRUPT", 1)],
)
def test_v6_events_tail_reports_artifact_states(tmp_path, contents, state, invalid_count) -> None:
    path = tmp_path / "events.jsonl"
    if contents is not None:
        path.write_bytes(contents)

    events, diagnostics = v6_platform_api._events_tail(path)

    assert events == []
    assert diagnostics["state"] == state
    assert diagnostics["invalid_line_count"] == invalid_count


def test_v6_events_tail_reports_trailing_corruption_and_snapshot_boundaries(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"event":"before"}\n{"event":"after"}\npartial')

    events, diagnostics = v6_platform_api._events_tail(path)

    assert events == [{"event": "before"}, {"event": "after"}]
    assert diagnostics == {
        "state": "PARTIAL",
        "invalid_line_count": 1,
        "bytes_scanned": len(b'{"event":"before"}\n{"event":"after"}\npartial'),
        "truncated": False,
    }
def test_v6_events_tail_uses_initial_size_during_concurrent_append(monkeypatch, tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"event":"before"}\n')
    original_open = Path.open

    class AppendingReader:
        appended = False

        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.close()

        def seek(self, offset, whence=0):
            result = self.handle.seek(offset, whence)
            if offset == 0 and whence == 2 and not self.appended:
                self.appended = True
                with original_open(path, "ab") as writer:
                    writer.write(b'{"event":"after"}\n')
            return result

        def __getattr__(self, name):
            return getattr(self.handle, name)

    def open_with_append(self, *args, **kwargs):
        handle = original_open(self, *args, **kwargs)
        return AppendingReader(handle) if self == path and args == ("rb",) else handle

    monkeypatch.setattr(Path, "open", open_with_append)
    events, diagnostics = v6_platform_api._events_tail(path)

    assert events == [{"event": "before"}]
    assert diagnostics["bytes_scanned"] == len(b'{"event":"before"}\n')

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
        "training_state": "MISSING",
        "validation_state": "NOT_RECORDED",
        "test_state": "MISSING",
        "evaluation_state": "TEST_MISSING",
    }]


def _write_report(runs_root, dataset="dataset-r1", train="train-r1", verdict="NO_GO"):
    run_dir = runs_root / dataset / train
    run_dir.mkdir(parents=True)
    html_text = f"<!DOCTYPE html><html><body><div class=\"badge\">{verdict}</div></body></html>"
    (run_dir / "report.html").write_text(html_text, encoding="utf-8")
    manifest = {
        "schema_version": "kronos_v7_report.v1",
        "builder_version": "kronos_v7_report_builder.v1",
        "generated_utc": "2026-07-20T01:00:00Z",
        "verdict": verdict,
        "test_state": "NOT_RUN",
        "index_overlay_state": "PRESENT",
        "report_sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
    }
    (run_dir / "report_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir
def _write_valid_report_chain(runs_root, docs_root, dataset="dataset-r1", train="train-1"):
    run_dir = runs_root / dataset / train
    run_dir.mkdir(parents=True)
    docs_root.mkdir(parents=True, exist_ok=True)
    prereg_path = docs_root / "kronos_v7_prereg_demo_2026-07-20.json"
    prereg = {"prereg_id": "KRONOS-V7-PREREG-DEMO", "schema_version": "kronos_v7_prereg.v1"}
    prereg_path.write_text(json.dumps(prereg), encoding="utf-8")
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    dataset_manifest_path = run_dir.parent / "dataset_manifest.json"
    dataset_manifest_path.write_text(json.dumps({"schema_version": "kronos_v7_dataset.v1"}), encoding="utf-8")
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = {
        "schema_version": "kronos_v7_run.v1",
        "dataset_run_id": dataset,
        "prereg": {"id": prereg["prereg_id"], "sha256": prereg_sha},
        "test": {"state": "NOT_RUN"},
    }
    run_manifest_path.write_text(json.dumps(run_manifest), encoding="utf-8")
    html_text = "<!DOCTYPE html><html><body>NO_GO</body></html>"
    (run_dir / "report.html").write_text(html_text, encoding="utf-8")
    report_manifest = {
        "schema_version": "kronos_v7_report.v1",
        "verdict": "NO_GO",
        "test_state": "NOT_RUN",
        "report_sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
        "source_sha256": {
            "run_manifest": hashlib.sha256(run_manifest_path.read_bytes()).hexdigest(),
            "dataset_manifest": hashlib.sha256(dataset_manifest_path.read_bytes()).hexdigest(),
            "prereg": prereg_sha,
        },
        "false_research_locks": dict(v6_platform_api.SIX_FALSE_LOCKS),
    }
    (run_dir / "report_manifest.json").write_text(json.dumps(report_manifest), encoding="utf-8")
    return run_dir, prereg_path


def test_v6_reports_catalog_and_html_viewer_contract(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    _write_report(runs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    catalog = client.get("/api/v6/reports").get_json()
    status = client.get("/api/v6/status").get_json()
    html = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1")
    download = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1&download=1")

    assert catalog["schema_version"] == "kronos_v6_reports.v2"
    assert len(catalog["reports"]) == 1
    entry = catalog["reports"][0]
    assert entry["dataset_run_id"] == "dataset-r1"
    assert entry["train_run_id"] == "train-r1"
    assert entry["verdict"] == "NO_GO"
    assert entry["integrity"] == "OK"
    assert entry["chain_integrity"] == "LEGACY_UNVERIFIED"
    assert entry["chain_reasons"] == ["LEGACY_SOURCE_CUSTODY_NOT_RECORDED"]
    assert entry["compatibility_state"] == "LEGACY_UNVERIFIED"
    assert entry["availability"] == "BLOCKED"
    assert status["journey"]["report"]["state"] == "HAS_REPORTS"
    assert html.status_code == 409
    assert html.get_json() == {
        "status": "BLOCKED",
        "reason": "UNKNOWN_OR_LEGACY_REPORT_FAMILY",
    }
    assert download.status_code == 409
    assert download.get_json() == html.get_json()
    assert "Content-Disposition" not in download.headers
def test_v6_reports_and_prereg_registry_retain_invalid_artifacts(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "dataset-r1" / "train-r1"
    run_dir.mkdir(parents=True)
    (run_dir / "report_manifest.json").write_text("{not-json", encoding="utf-8")
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "kronos_v7_prereg_broken_2026-07-20.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    report = client.get("/api/v6/reports").get_json()["reports"][0]
    prereg = client.get("/api/v6/research-registry").get_json()["preregistrations"][0]

    assert report["integrity"] == "INVALID"
    assert report["integrity_reasons"] == ["REPORT_MANIFEST_INVALID", "REPORT_NOT_FOUND"]
    assert prereg["status"] == "INVALID"
    assert prereg["integrity_reasons"] == ["PREREG_PARSE_FAILED"]

def test_v6_valid_report_chain_round_trips_opaque_run_and_not_run_test(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    _write_valid_report_chain(runs_root, docs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    catalog = client.get("/api/v6/reports").get_json()["reports"]
    runs = client.get("/api/v6/runs").get_json()["runs"]
    detail = client.get("/api/v6/run-detail?dataset=dataset-r1&train=train-1").get_json()
    viewer = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-1")
    status = client.get("/api/v6/status").get_json()

    assert catalog[0]["chain_integrity"] == "CHAIN_OK"
    assert catalog[0]["chain_reasons"] == []
    assert runs[0]["run_id"] == "train-1"
    assert runs[0]["test_state"] == "NOT_RUN"
    assert catalog[0]["test_state"] == "NOT_RUN"
    assert catalog[0]["evaluation_state"] == "TEST_NOT_RUN"
    assert runs[0]["evaluation_state"] == "TEST_NOT_RUN"
    assert detail["train_run_id"] == "train-1"
    assert detail["states"]["test_state"] == "NOT_RUN"
    assert detail["states"]["evaluation_state"] == "TEST_NOT_RUN"
    assert status["journey"]["evaluation"]["state"] == "TEST_NOT_RUN"
    assert viewer.status_code == 200


@pytest.mark.parametrize(
    ("tamper", "expected_reason"),
    [
        ("prereg", "PREREG_NOT_FOUND_OR_SHA_MISMATCH"),
        ("locks", "FALSE_RESEARCH_LOCKS_MISMATCH"),
        ("source", "RUN_MANIFEST_SHA_MISMATCH"),
    ],
)
def test_v6_report_source_chain_tampering_fails_closed(client, monkeypatch, tmp_path, tamper, expected_reason) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    run_dir, prereg_path = _write_valid_report_chain(runs_root, docs_root)
    if tamper == "prereg":
        prereg_path.write_text(json.dumps({"prereg_id": "KRONOS-V7-PREREG-DEMO", "schema_version": "tampered"}), encoding="utf-8")
    elif tamper == "source":
        run_manifest_path = run_dir / "run_manifest.json"
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        run_manifest["source_tampered"] = True
        run_manifest_path.write_text(json.dumps(run_manifest), encoding="utf-8")
    else:
        report_manifest_path = run_dir / "report_manifest.json"
        report_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
        report_manifest["false_research_locks"]["go_summary_allowed"] = True
        report_manifest_path.write_text(json.dumps(report_manifest), encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    entry = client.get("/api/v6/reports").get_json()["reports"][0]
    blocked = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-1")

    assert entry["chain_integrity"] == "CHAIN_INVALID"
    assert expected_reason in entry["chain_reasons"]
    assert blocked.status_code == 409
    assert blocked.get_json()["reason"] == expected_reason


def test_v6_reports_empty_and_report_html_guards(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", tmp_path / "missing-runs")

    assert client.get("/api/v6/reports").get_json()["reports"] == []
    assert client.get("/api/v6/status").get_json()["journey"]["report"]["state"] == "NOT_RUN"
    missing = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1")
    assert missing.status_code == 404
    assert missing.get_json() == {"status": "BLOCKED", "reason": "REPORT_NOT_FOUND"}

    assert client.get("/api/v6/report-html").status_code == 400
    assert client.get("/api/v6/report-html?dataset=../x&train=train-1").status_code == 400
    assert client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1&download=2").status_code == 400
    assert client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1&unexpected=1").status_code == 400
    post = client.post("/api/v6/report-html")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"
    assert client.post("/api/v6/reports").status_code == 405


def test_v6_report_html_blocks_sha_mismatch(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    run_dir = _write_report(runs_root)
    (run_dir / "report.html").write_text("<!DOCTYPE html><html><body>tampered</body></html>", encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    catalog = client.get("/api/v6/reports").get_json()
    blocked = client.get("/api/v6/report-html?dataset=dataset-r1&train=train-r1")

    assert catalog["reports"][0]["integrity"] == "SHA_MISMATCH"
    assert blocked.status_code == 409
    assert blocked.get_json() == {"status": "BLOCKED", "reason": "REPORT_SHA_MISMATCH"}


def test_v6_research_registry_links_prereg_runs_and_reports(client, monkeypatch, tmp_path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "kronos_v7_prereg_demo_2026-07-20.json").write_text(
        json.dumps({"prereg_id": "KRONOS-V7-PREREG-DEMO", "status": "FROZEN",
                    "frozen_utc": "2026-07-20T00:00:00Z", "algorithm": {"family": "demo_family"}}),
        encoding="utf-8",
    )
    (docs_root / "kronos_v7_demo_result_2026-07-20.md").write_text("# Demo Result\n\nverdict INCONCLUSIVE\n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    run_dir = runs_root / "ds-1" / "train-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"prereg": {"id": "KRONOS-V7-PREREG-DEMO"}, "trainer_version": "demo.v1",
                    "verdict_candidate": {"value": "INCONCLUSIVE"}, "test": {"state": "NOT_RUN"},
                    "generated_utc": "2026-07-20T01:00:00Z"}),
        encoding="utf-8",
    )
    html_text = "<!DOCTYPE html><html><body><div class=\"badge\">INCONCLUSIVE</div></body></html>"
    (run_dir / "report.html").write_text(html_text, encoding="utf-8")
    (run_dir / "report_manifest.json").write_text(
        json.dumps({"verdict": "INCONCLUSIVE", "test_state": "NOT_RUN", "index_overlay_state": "PRESENT",
                    "generated_utc": "2026-07-20T02:00:00Z", "builder_version": "b.v1",
                    "report_sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)

    registry = client.get("/api/v6/research-registry").get_json()

    assert registry["schema_version"] == "kronos_v6_research_registry.v1"
    assert len(registry["preregistrations"]) == 1
    entry = registry["preregistrations"][0]
    assert entry["prereg_id"] == "KRONOS-V7-PREREG-DEMO"
    assert entry["status"] == "FROZEN"
    assert entry["family"] == "demo_family"
    assert entry["run_count"] == 1
    assert entry["verdicts"] == ["INCONCLUSIVE"]
    run = entry["runs"][0]
    assert run["dataset_run_id"] == "ds-1" and run["train_run_id"] == "train-1"
    assert run["has_report"] is True
    assert any(doc["doc"] == "kronos_v7_demo_result_2026-07-20.md" for doc in registry["result_docs"])


def test_v6_research_doc_serves_allowlisted_markdown_and_blocks_traversal(client, monkeypatch, tmp_path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "kronos_v7_demo_result_2026-07-20.md").write_text("# Demo\n\nbody\n", encoding="utf-8")
    (docs_root / "secret.md").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    ok = client.get("/api/v6/research-doc?doc=kronos_v7_demo_result_2026-07-20.md").get_json()
    assert ok["format"] == "markdown"
    assert ok["content"].startswith("# Demo")
    assert ok["sha256"] == hashlib.sha256((docs_root / "kronos_v7_demo_result_2026-07-20.md").read_bytes()).hexdigest()

    # non-allowlisted name, traversal, missing, and mutation are all closed
    assert client.get("/api/v6/research-doc?doc=secret.md").status_code == 400
    assert client.get("/api/v6/research-doc?doc=../secret.md").status_code == 400
    assert client.get("/api/v6/research-doc?doc=kronos_v7_missing.md").status_code == 404
    assert client.get("/api/v6/research-doc").status_code == 400
    assert client.get("/api/v6/research-registry?x=1").status_code == 400
    for path in ("/api/v6/research-registry", "/api/v6/research-doc"):
        response = client.post(path)
        assert response.status_code == 405
        assert response.headers["Allow"] == "GET"
def _write_project_report(runs_root, docs_root):
    project_dir = runs_root / "_projects" / "KRONOS-PROJECT-TEST"
    project_dir.mkdir(parents=True)
    docs_root.mkdir(parents=True, exist_ok=True)
    prereg_path = docs_root / "prereg.json"
    run_path = runs_root / "cycle-source-run.json"
    prereg_path.write_text('{"state":"FROZEN"}', encoding="utf-8")
    run_path.write_text('{"verdict":"NO_GO","test":"NOT_RUN"}', encoding="utf-8")
    html = "<!DOCTYPE html><html><body>NO_GO NOT_RUN</body></html>"
    (project_dir / "project_report.html").write_text(html, encoding="utf-8")
    manifest = {
        "schema_version": "kronos_v7_project_report.v2",
        "builder_version": "kronos_v7_project_report_builder.v2",
        "generated_utc": "2026-07-20T00:00:00Z",
        "project_id": "KRONOS-PROJECT-TEST",
        "title": "Two-cycle project",
        "report_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "source_sha256": [
            {"label": "prereg", "path": str(prereg_path), "sha256": hashlib.sha256(prereg_path.read_bytes()).hexdigest()},
            {"label": "run", "path": str(run_path), "sha256": hashlib.sha256(run_path.read_bytes()).hexdigest()},
        ],
        "cycle_count": 2,
        "run_count": 2,
        "verdicts": ["NO_GO"],
        "test_states": ["NOT_RUN"],
        "cycles": [
            {"cycle_id": "C1", "runs": [{"verdict": "NO_GO", "test_state": "NOT_RUN"}]},
            {"cycle_id": "C2", "runs": [{"verdict": "NO_GO", "test_state": "NOT_RUN"}]},
        ],
        "false_research_locks": dict(v6_platform_api.SIX_FALSE_LOCKS),
    }
    manifest_path = project_dir / "project_report_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return project_dir, manifest_path, run_path


def test_v6_project_reports_catalog_and_html_contract(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    _write_project_report(runs_root, docs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    payload = client.get("/api/v6/project-reports").get_json()
    viewer = client.get("/api/v6/project-report-html?project=KRONOS-PROJECT-TEST")
    download = client.get("/api/v6/project-report-html?project=KRONOS-PROJECT-TEST&download=1")

    assert payload["schema_version"] == "kronos_v7_project_reports.v2"
    assert payload["status"] == "OK"
    entry = payload["projects"][0]
    assert {key for key in ("project_id", "title", "generated_utc", "builder_version", "report_sha256", "size_bytes",
                            "cycle_count", "run_count", "verdicts", "test_states", "cycles", "integrity",
                            "integrity_reasons")} <= set(entry)
    assert entry["cycle_count"] == entry["run_count"] == 2
    assert len(entry["cycles"]) == 2
    assert entry["verdicts"] == ["NO_GO"] and entry["test_states"] == ["NOT_RUN"]
    assert entry["integrity"] == "CHAIN_OK" and entry["integrity_reasons"] == []
    assert viewer.status_code == 200
    assert viewer.headers["Content-Security-Policy"] == "default-src 'none'; style-src 'unsafe-inline'"
    assert download.headers["Content-Disposition"] == 'attachment; filename="kronos-project-report-KRONOS-PROJECT-TEST.html"'


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        ("html", "REPORT_SHA_MISMATCH"),
        ("source", "SOURCE_SHA256_MISMATCH"),
        ("locks", "FALSE_RESEARCH_LOCKS_MISMATCH"),
        ("schema", "PROJECT_REPORT_SCHEMA_MISMATCH"),
        ("escape", "SOURCE_PATH_INVALID"),
    ],
)
def test_v6_project_reports_fail_closed_on_tampering(client, monkeypatch, tmp_path, tamper, reason) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    project_dir, manifest_path, run_path = _write_project_report(runs_root, docs_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if tamper == "html":
        (project_dir / "project_report.html").write_text("<html>tampered</html>", encoding="utf-8")
    elif tamper == "source":
        run_path.write_text('{"tampered":true}', encoding="utf-8")
    elif tamper == "locks":
        manifest["false_research_locks"]["go_summary_allowed"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif tamper == "schema":
        manifest["schema_version"] = "wrong"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        secret = tmp_path / "secret.json"
        secret.write_text("secret", encoding="utf-8")
        manifest["source_sha256"][0]["path"] = str(secret)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    entry = client.get("/api/v6/project-reports").get_json()["projects"][0]
    blocked = client.get("/api/v6/project-report-html?project=KRONOS-PROJECT-TEST")

    assert entry["integrity"] == "CHAIN_INVALID"
    assert reason in entry["integrity_reasons"]
    assert blocked.status_code == 409
    assert blocked.get_json()["reason"] == reason


def test_v6_project_report_query_and_method_guards(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "runs"
    docs_root = tmp_path / "docs"
    _write_project_report(runs_root, docs_root)
    monkeypatch.setattr(v6_platform_api, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs_root)

    assert client.get("/api/v6/project-reports?unexpected=1").status_code == 400
    assert client.get("/api/v6/project-report-html?project=../escape").status_code == 400
    assert client.get("/api/v6/project-report-html?project=missing").status_code == 404
    assert client.get("/api/v6/project-report-html?project=KRONOS-PROJECT-TEST&project=duplicate").status_code == 400
    assert client.post("/api/v6/project-reports").status_code == 405
    post = client.post("/api/v6/project-report-html")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"

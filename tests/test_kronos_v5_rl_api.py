from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from typing import Any

from flask import Flask
import pytest

from webui.v5_api_contract import MATRIX_ORDER, SIX_LOCKS, V5ApiContractError, decode_cursor, validate_payload
from webui.v5_downloads import MAX_DOWNLOAD_BYTES
from webui.v5_rl_api import _cursor_query_scope, create_v5_rl_api_blueprint

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/data/kronos_v5_api_fixture.json").read_text(encoding="utf-8"))
RUN_UID = FIXTURE["run_uid"]
SECOND_RUN_UID = FIXTURE["second_run_uid"]
REVISION = FIXTURE["revision"]
SOURCE_SHA = FIXTURE["source"]["source_sha256"]
CURSOR_KEY = bytes.fromhex(FIXTURE["cursor_key_hex"])
D0_FIXTURE = ROOT / "tests/data/kronos_d0_price_basis_evidence_synthetic.v1.json"
D1_FIXTURE = ROOT / "tests/data/kronos_d1_universe_evidence_synthetic.v1.json"


class RegistryNotFound(Exception):
    status_code = 404
    code = "NOT_FOUND"


class RegistryGone(Exception):
    status_code = 410
    code = "INVALID_CURSOR"


class RegistryCorrupt(Exception):
    status_code = 503
    code = "INTERNAL_ERROR"


class Page:
    def __init__(self, items: list[dict[str, Any]], next_cursor: str | None = None, next_after_global_seq: int | None = None) -> None:
        self.items = items
        self.next_cursor = next_cursor
        self.next_after_global_seq = next_after_global_seq
        self.snapshot_global_seq = len(items)


class SnapshotRead:
    def __init__(self, snapshot: dict[str, Any], revision: int | None = None) -> None:
        self.snapshot = snapshot
        self.registry_epoch = 1
        self.snapshot_global_seq = 1
        self.run_revision = snapshot["revision"] if revision is None else revision


def _cells() -> list[dict[str, Any]]:
    cycle = FIXTURE["matrix_state_cycle"]
    cells = []
    for index, (row_id, column_id) in enumerate(MATRIX_ORDER):
        fold_id, variant_id = column_id.split(":", 1)
        cells.append({
            "row_id": row_id,
            "column_id": column_id,
            "seed_id": row_id,
            "fold_id": fold_id,
            "variant_id": variant_id,
            "status": cycle[index % len(cycle)],
        })
    return cells


def _snapshot(run_uid: str = RUN_UID, *, created_at: str = "2026-07-15T00:00:00Z", revision: int = REVISION) -> dict[str, Any]:
    snapshot = deepcopy(FIXTURE["snapshot"])
    snapshot["run_uid"] = run_uid
    snapshot["revision"] = revision
    snapshot["created_at"] = created_at
    snapshot["run_revision"] = revision
    snapshot["cells"] = _cells()
    for artifact in snapshot["artifacts"]:
        artifact["run_uid"] = run_uid
        artifact["revision"] = revision
        artifact["run_revision"] = revision
    return snapshot


def _two_ledger_snapshot(run_uid: str = RUN_UID, *, revision: int = REVISION, created_at: str = "2026-07-15T00:00:00Z") -> dict[str, Any]:
    snapshot = _snapshot(run_uid, revision=revision, created_at=created_at)
    snapshot["ledger_entries"] = [
        {"entry_id": "entry-1", "occurred_at": "2026-07-15T00:00:10Z", "kind": "DEBIT", "amount": 1.25},
        {"entry_id": "entry-2", "occurred_at": "2026-07-15T00:00:11Z", "kind": "CREDIT", "amount": 0.25},
    ]
    return snapshot


def _two_artifact_snapshot(run_uid: str = RUN_UID, *, revision: int = REVISION, created_at: str = "2026-07-15T00:00:00Z") -> dict[str, Any]:
    snapshot = _snapshot(run_uid, revision=revision, created_at=created_at)
    base = deepcopy(FIXTURE["snapshot"]["artifacts"][0])
    snapshot["artifacts"] = []
    for index in (1, 2):
        artifact = deepcopy(base)
        artifact.update({
            "artifact_id": f"artifact-{index}",
            "filename": "report.json" if index == 1 else f"report-{index}.json",
            "created_at": f"2026-07-15T00:00:2{index}Z",
            "run_uid": run_uid,
            "revision": revision,
            "run_revision": revision,
        })
        snapshot["artifacts"].append(artifact)
    return snapshot

def _sequence_events(count: int = 7) -> list[dict[str, Any]]:
    return [
        {
            "global_seq": index,
            "created_utc": f"2026-07-15T00:00:{index:02d}Z",
            "event_id": f"misleading-local-{count - index + 1}",
            "occurred_at": f"2026-07-14T00:00:{count - index + 1:02d}Z",
            "event_type": "MESSAGE",
            "level": "INFO",
            "message": f"sequence event {index}",
        }
        for index in range(1, count + 1)
    ]


def _fixture_events() -> list[dict[str, Any]]:
    events = deepcopy(FIXTURE["events"])
    for index, event in enumerate(events, 1):
        event["global_seq"] = index
        event["created_utc"] = event.get("created_utc") or event.get("occurred_at")
    return events



def _fixture_root() -> dict[str, Any]:
    payload = {"route_id": "FIXTURE", "source": deepcopy(FIXTURE["source"]), "fixture": deepcopy(FIXTURE["fixture"]), "locks": deepcopy(SIX_LOCKS)}
    payload["fixture"]["run"]["run_uid"] = payload["fixture"]["run"]["run_id"]
    payload["fixture"]["run"]["run_revision"] = REVISION
    return payload


class FakeRegistry:
    def __init__(
        self,
        *,
        snapshot: dict[str, Any] | None = None,
        mode: str | None = None,
        second: dict[str, Any] | None = None,
        extra_snapshots: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.snapshot = snapshot or _snapshot()
        self.second = second or _snapshot(SECOND_RUN_UID, created_at="2026-07-14T00:00:00Z")
        self.snapshots = [self.snapshot, self.second, *(extra_snapshots or [])]
        self.mode = mode
        self.events = events if events is not None else _fixture_events()
        self.event_calls: list[dict[str, Any]] = []
        self.run_limits: list[int] = []

    def identity(self) -> dict[str, Any]:
        return {"schema_version": "kronos_rl_run_state.v2", "registry_epoch": 1, "genesis_hash": SOURCE_SHA, "cursor_key_id": "test", "created_utc": FIXTURE["source"]["generated_at"], "read_only": True, "status": "READY"}

    def list_runs(self, *, limit: int = 50, cursor: str | None = None, filters: Any = None, sort: str = "latest_desc") -> Page:
        self.run_limits.append(limit)
        if self.mode == "boom":
            raise RuntimeError("secret filesystem path D:/private/kronos/registry.sqlite")
        if self.mode == "corrupt":
            raise RegistryCorrupt("REGISTRY_CORRUPT")
        if self.mode == "gone":
            raise RegistryGone("cursor epoch is gone")
        return Page([deepcopy(self.snapshot), deepcopy(self.second)])

    def get_run(self, run_uid: str, *, revision: int) -> SnapshotRead:
        if self.mode == "unknown":
            raise RegistryNotFound("unknown run")
        for snapshot in self.snapshots:
            if run_uid == snapshot["run_uid"] and revision == snapshot["revision"]:
                if self.mode == "revision-conflict" and snapshot is self.snapshot:
                    return SnapshotRead(deepcopy(snapshot), revision=revision + 1)
                return SnapshotRead(deepcopy(snapshot))
        raise RegistryNotFound("unknown run revision")

    def list_events(self, run_uid: str, *, revision: int, attempt_uid: str | None = None, after_global_seq: int = 0, limit: int = 500) -> Page:
        self.event_calls.append({"run_uid": run_uid, "revision": revision, "after_global_seq": after_global_seq, "limit": limit})
        self.get_run(run_uid, revision=revision)
        events = deepcopy(self.events)
        if any(isinstance(event.get("global_seq"), int) for event in events):
            filtered = [event for event in events if isinstance(event.get("global_seq"), int) and event["global_seq"] > after_global_seq]
            page_items = filtered[:limit]
            next_after = page_items[-1]["global_seq"] if len(filtered) > limit and page_items else None
            return Page(page_items, next_after_global_seq=next_after)
        return Page(events)

    def get_matrix(self, run_uid: str, *, revision: int) -> dict[str, Any]:
        snapshot = self.get_run(run_uid, revision=revision).snapshot
        return {"cells": deepcopy(snapshot["cells"]), "missing_cell_ids": [], "terminal": False}

    def list_artifacts(self, run_uid: str, *, revision: int) -> list[dict[str, Any]]:
        snapshot = self.get_run(run_uid, revision=revision).snapshot
        if self.mode == "invalid-artifact-payload":
            bad = deepcopy(snapshot["artifacts"])
            bad[0]["filename"] = "con.json"
            return bad
        if self.mode == "download-traversal":
            bad = deepcopy(snapshot["artifacts"])
            bad[0]["path"] = "../secret/report.json"
            return bad
        if self.mode == "download-too-large":
            bad = deepcopy(snapshot["artifacts"])
            bad[0]["byte_length"] = MAX_DOWNLOAD_BYTES + 1
            return bad
        return deepcopy(snapshot["artifacts"])

    def get_artifact(self, run_uid: str, artifact_id: str, *, revision: int) -> dict[str, Any]:
        artifacts = self.list_artifacts(run_uid, revision=revision)
        for artifact in artifacts:
            if artifact["artifact_id"] == artifact_id:
                found = deepcopy(artifact)
                if self.mode == "artifact-revision-conflict":
                    found["revision"] = revision + 1
                return found
        raise RegistryNotFound("unknown artifact")


def _client(tmp_path: Path, registry: FakeRegistry | None = None):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(exist_ok=True)
    (artifact_root / "report.json").write_bytes(FIXTURE["artifact_bytes"].encode("utf-8"))
    app = Flask(__name__)
    app.register_blueprint(create_v5_rl_api_blueprint(
        registry=registry or FakeRegistry(),
        cursor_key=CURSOR_KEY,
        artifact_root=artifact_root,
        d0_evidence_path=D0_FIXTURE,
        d1_evidence_path=D1_FIXTURE,
        fixture_payload=_fixture_root(),
    ))
    return app.test_client()


def _json(response) -> dict[str, Any]:
    return json.loads(response.get_data(as_text=True))


SUCCESS_PATHS = {
    "RUNS": "/api/v5/rl/runs",
    "RUN_DETAIL": f"/api/v5/rl/runs/{RUN_UID}?revision={REVISION}",
    "EVENTS": f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION}",
    "MATRIX": f"/api/v5/rl/matrix?run_id={quote(RUN_UID, safe='')}&revision={REVISION}",
    "LEDGER": f"/api/v5/rl/ledger?run_id={quote(RUN_UID, safe='')}&revision={REVISION}",
    "ARTIFACTS": f"/api/v5/rl/artifacts?run_id={quote(RUN_UID, safe='')}&revision={REVISION}",
    "D0": "/api/v5/rl/d0",
    "D1": "/api/v5/rl/d1",
    "FIXTURE": "/api/v5/rl/fixture",
}

EXPECTED_SUCCESS_KEYS = {
    "RUNS": {"route_id", "source", "list", "locks"},
    "RUN_DETAIL": {"route_id", "source", "run", "locks"},
    "EVENTS": {"route_id", "source", "list", "locks", "run_id"},
    "MATRIX": {"route_id", "source", "cells", "summary", "locks"},
    "LEDGER": {"route_id", "source", "list", "locks"},
    "ARTIFACTS": {"route_id", "source", "list", "locks"},
    "D0": {"route_id", "source", "d0", "locks"},
    "D1": {"route_id", "source", "d1", "locks"},
    "FIXTURE": {"route_id", "source", "fixture", "locks"},
}


def _assert_error(response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    payload = _json(response)
    assert set(payload) == {"route_id", "error"}
    assert set(payload["error"]) == {"code", "message"}
    assert payload["error"]["code"] == code
    validate_payload(payload, cursor_key=CURSOR_KEY)
    return payload


@pytest.mark.parametrize(("route_id", "path"), SUCCESS_PATHS.items())
def test_success_routes_emit_exact_frozen_envelopes(route_id: str, path: str, tmp_path: Path) -> None:
    response = _client(tmp_path).get(path)

    assert response.status_code == 200
    payload = _json(response)
    assert payload["route_id"] == route_id
    assert payload["locks"] == SIX_LOCKS
    assert set(payload) == EXPECTED_SUCCESS_KEYS[route_id]
    validate_payload(payload, cursor_key=CURSOR_KEY)
    assert "error" not in payload
    if route_id == "RUN_DETAIL":
        assert payload["run"]["run_uid"] == RUN_UID
        assert payload["run"]["run_revision"] == REVISION


def test_route_ordering_keeps_artifact_download_boundary_distinct(tmp_path: Path) -> None:
    client = _client(tmp_path)

    list_response = client.get(SUCCESS_PATHS["ARTIFACTS"])
    assert list_response.status_code == 200
    item = _json(list_response)["list"]["items"][0]
    assert item["download_url"] == "/api/v5/rl/artifacts/artifact-1/download"
    assert item["portable_filename"] == "report.json"
    assert item["run_id"] == RUN_UID
    assert item["run_revision"] == REVISION

    download = client.get(f"{item['download_url']}?run_id={quote(item['run_id'], safe='')}&revision={item['run_revision']}")
    assert download.status_code == 200
    assert download.data == FIXTURE["artifact_bytes"].encode("utf-8")
    assert download.headers["Content-Disposition"].startswith("attachment;")

def test_public_download_route_delegates_to_hardened_download_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any], Path]] = []

    def fake_download_artifact(artifact_id: str, *, registry_root: dict[str, Any], fixture_root: Path) -> SimpleNamespace:
        calls.append((artifact_id, registry_root, Path(fixture_root)))
        return SimpleNamespace(
            body=b"delegated\n",
            headers={
                "Content-Type": "application/json",
                "Content-Length": "10",
                "Content-Disposition": "attachment; filename=\"report.json\"",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "ETag": '"sha256-delegated"',
            },
        )

    monkeypatch.setattr("webui.v5_rl_api.v5_downloads.download_artifact", fake_download_artifact)
    client = _client(tmp_path)

    response = client.get(f"/api/v5/rl/artifacts/artifact-1/download?run_id={quote(RUN_UID, safe='')}&revision={REVISION}")

    assert response.status_code == 200
    assert response.data == b"delegated\n"
    assert len(calls) == 1
    artifact_id, registry_root, fixture_root = calls[0]
    assert artifact_id == "artifact-1"
    assert fixture_root.name == "artifacts"
    assert registry_root["schema"] == "kronos_rl_run_state.v2"
    assert registry_root["artifacts"][0]["path"] == "report.json"



def test_uuid_and_revision_conflicts_return_409(tmp_path: Path) -> None:
    detail = _client(tmp_path, FakeRegistry(mode="revision-conflict")).get(SUCCESS_PATHS["RUN_DETAIL"])
    _assert_error(detail, 409, "INTERNAL_ERROR")

    download = _client(tmp_path, FakeRegistry(mode="artifact-revision-conflict")).get(f"/api/v5/rl/artifacts/artifact-1/download?run_id={quote(RUN_UID, safe='')}&revision={REVISION}")
    _assert_error(download, 409, "INTERNAL_ERROR")

def test_registry_terminal_snapshot_maps_to_succeeded(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["terminal"] = "COMPLETED"
    snapshot["phase"] = "RUN_TERMINAL"
    snapshot["progress"] = {"step": 100, "total_steps": 100}

    response = _client(tmp_path, FakeRegistry(snapshot=snapshot)).get(SUCCESS_PATHS["RUN_DETAIL"])

    assert response.status_code == 200
    state = _json(response)["run"]["state"]
    assert state["status"] == "SUCCEEDED"
    assert state["progress"]["percent"] == 100.0
    assert state["finished_at"] is not None


def test_pagination_cursor_status_and_limits(tmp_path: Path) -> None:
    registry = FakeRegistry()
    client = _client(tmp_path, registry)

    first = client.get("/api/v5/rl/runs?limit=1")
    assert registry.run_limits == [1]
    assert first.status_code == 200
    first_payload = _json(first)
    token = first_payload["list"]["next_cursor"]
    assert token
    assert decode_cursor(token, "RUNS", SOURCE_SHA, key=CURSOR_KEY)["run_id"] == RUN_UID

    second = client.get(f"/api/v5/rl/runs?cursor={token}")
    assert second.status_code == 200
    assert _json(second)["list"]["items"][0]["run_id"] == SECOND_RUN_UID
    assert registry.run_limits == [1, 100]

    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    invalid = client.get(f"/api/v5/rl/runs?cursor={tampered}")
    _assert_error(invalid, 400, "INVALID_CURSOR")

    too_large = client.get("/api/v5/rl/runs?limit=101")
    _assert_error(too_large, 413, "INTERNAL_ERROR")

    gone = _client(tmp_path, FakeRegistry(mode="gone")).get(f"/api/v5/rl/runs?cursor={token}")
    _assert_error(gone, 410, "INVALID_CURSOR")

def test_top_level_ledger_paginator_cursor_binds_run_and_revision(tmp_path: Path) -> None:
    snapshot = _two_ledger_snapshot()
    second_run = _two_ledger_snapshot(SECOND_RUN_UID, created_at="2026-07-14T00:00:00Z")
    revised_run = _two_ledger_snapshot(RUN_UID, revision=REVISION + 1)
    client = _client(tmp_path, FakeRegistry(snapshot=snapshot, second=second_run, extra_snapshots=[revised_run]))

    first = client.get(f"/api/v5/rl/ledger?run_id={quote(RUN_UID, safe='')}&revision={REVISION}&limit=1")
    assert first.status_code == 200
    token = _json(first)["list"]["next_cursor"]
    scope = _cursor_query_scope(RUN_UID, REVISION)
    assert decode_cursor(token, "LEDGER", SOURCE_SHA, key=CURSOR_KEY, run_id=scope)["entry_id"] == "entry-1"
    with pytest.raises(V5ApiContractError):
        decode_cursor(token, "LEDGER", SOURCE_SHA, key=CURSOR_KEY, run_id=_cursor_query_scope(SECOND_RUN_UID, REVISION))

    second = client.get(f"/api/v5/rl/ledger?run_id={quote(RUN_UID, safe='')}&revision={REVISION}&cursor={token}")
    assert second.status_code == 200
    assert _json(second)["list"]["items"][0]["entry_id"] == "entry-2"

    cross_run = client.get(f"/api/v5/rl/ledger?run_id={quote(SECOND_RUN_UID, safe='')}&revision={REVISION}&cursor={token}")
    _assert_error(cross_run, 400, "INVALID_CURSOR")

    cross_revision = client.get(f"/api/v5/rl/ledger?run_id={quote(RUN_UID, safe='')}&revision={REVISION + 1}&cursor={token}")
    _assert_error(cross_revision, 400, "INVALID_CURSOR")


def test_top_level_artifacts_paginator_cursor_binds_run_and_revision(tmp_path: Path) -> None:
    snapshot = _two_artifact_snapshot()
    second_run = _two_artifact_snapshot(SECOND_RUN_UID, created_at="2026-07-14T00:00:00Z")
    revised_run = _two_artifact_snapshot(RUN_UID, revision=REVISION + 1)
    client = _client(tmp_path, FakeRegistry(snapshot=snapshot, second=second_run, extra_snapshots=[revised_run]))

    first = client.get(f"/api/v5/rl/artifacts?run_id={quote(RUN_UID, safe='')}&revision={REVISION}&limit=1")
    assert first.status_code == 200
    token = _json(first)["list"]["next_cursor"]
    scope = _cursor_query_scope(RUN_UID, REVISION)
    assert decode_cursor(token, "ARTIFACTS", SOURCE_SHA, key=CURSOR_KEY, run_id=scope)["artifact_id"] == "artifact-1"

    second = client.get(f"/api/v5/rl/artifacts?run_id={quote(RUN_UID, safe='')}&revision={REVISION}&cursor={token}")
    assert second.status_code == 200
    assert _json(second)["list"]["items"][0]["artifact"]["artifact_id"] == "artifact-2"

    cross_run = client.get(f"/api/v5/rl/artifacts?run_id={quote(SECOND_RUN_UID, safe='')}&revision={REVISION}&cursor={token}")
    _assert_error(cross_run, 400, "INVALID_CURSOR")

    cross_revision = client.get(f"/api/v5/rl/artifacts?run_id={quote(RUN_UID, safe='')}&revision={REVISION + 1}&cursor={token}")
    _assert_error(cross_revision, 400, "INVALID_CURSOR")


def test_events_paginator_cursor_binds_run_and_revision(tmp_path: Path) -> None:
    snapshot = _snapshot()
    second_run = _snapshot(SECOND_RUN_UID, created_at="2026-07-14T00:00:00Z")
    revised_run = _snapshot(RUN_UID, revision=REVISION + 1)
    client = _client(tmp_path, FakeRegistry(snapshot=snapshot, second=second_run, extra_snapshots=[revised_run]))

    first = client.get(f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION}&limit=1")
    assert first.status_code == 200
    token = _json(first)["list"]["next_cursor"]
    scope = _cursor_query_scope(RUN_UID, REVISION)
    assert decode_cursor(token, "EVENTS", SOURCE_SHA, key=CURSOR_KEY, run_id=scope)["event_id"] == "global-seq-0000000000000001"
    with pytest.raises(V5ApiContractError):
        decode_cursor(token, "EVENTS", SOURCE_SHA, key=CURSOR_KEY, run_id=_cursor_query_scope(RUN_UID, REVISION + 1))

    second = client.get(f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION}&cursor={token}")
    assert second.status_code == 200
    assert _json(second)["list"]["items"][0]["event_id"] == "global-seq-0000000000000002"

    cross_run = client.get(f"/api/v5/rl/runs/{SECOND_RUN_UID}/events?revision={REVISION}&cursor={token}")
    _assert_error(cross_run, 400, "INVALID_CURSOR")

    cross_revision = client.get(f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION + 1}&cursor={token}")
    _assert_error(cross_revision, 400, "INVALID_CURSOR")

def test_events_sequence_pagination_resumes_by_global_seq_without_duplicates(tmp_path: Path) -> None:
    snapshot = _snapshot()
    second_run = _snapshot(SECOND_RUN_UID, created_at="2026-07-14T00:00:00Z")
    revised_run = _snapshot(RUN_UID, revision=REVISION + 1)
    registry = FakeRegistry(snapshot=snapshot, second=second_run, extra_snapshots=[revised_run], events=_sequence_events(7))
    client = _client(tmp_path, registry)

    cursor = None
    first_token = None
    observed: list[dict[str, Any]] = []
    for _ in range(10):
        path = f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION}&limit=2"
        if cursor is not None:
            path = f"{path}&cursor={cursor}"
        response = client.get(path)

        assert response.status_code == 200
        payload = _json(response)
        page_items = payload["list"]["items"]
        assert len(page_items) <= 2
        observed.extend(page_items)
        cursor = payload["list"]["next_cursor"]
        if first_token is None:
            first_token = cursor
        if cursor is None:
            break
    else:
        pytest.fail("event pagination did not terminate")

    expected_ids = [f"global-seq-{index:016d}" for index in range(1, 8)]
    assert first_token is not None
    assert [item["event_id"] for item in observed] == expected_ids
    assert [item["occurred_at"] for item in observed] == [f"2026-07-15T00:00:{index:02d}Z" for index in range(1, 8)]
    assert [item["message"] for item in observed] == [f"sequence event {index}" for index in range(1, 8)]
    assert len({item["event_id"] for item in observed}) == 7
    assert [call["after_global_seq"] for call in registry.event_calls] == [0, 2, 4, 6]
    assert all(call["limit"] == 3 for call in registry.event_calls)
    assert all(call["run_uid"] == RUN_UID and call["revision"] == REVISION for call in registry.event_calls)

    scope = _cursor_query_scope(RUN_UID, REVISION)
    first_key = decode_cursor(first_token, "EVENTS", SOURCE_SHA, key=CURSOR_KEY, run_id=scope)
    assert first_key["event_id"] == "global-seq-0000000000000002"
    assert first_key["occurred_at"] == "2026-07-15T00:00:02Z"
    calls_before_cross_scope = deepcopy(registry.event_calls)

    cross_run = client.get(f"/api/v5/rl/runs/{SECOND_RUN_UID}/events?revision={REVISION}&cursor={first_token}")
    _assert_error(cross_run, 400, "INVALID_CURSOR")

    cross_revision = client.get(f"/api/v5/rl/runs/{RUN_UID}/events?revision={REVISION + 1}&cursor={first_token}")
    _assert_error(cross_revision, 400, "INVALID_CURSOR")
    assert registry.event_calls == calls_before_cross_scope



def test_malformed_unknown_corrupt_loopback_and_validation_statuses(tmp_path: Path) -> None:
    client = _client(tmp_path)

    _assert_error(client.get(f"/api/v5/rl/runs/{RUN_UID}"), 400, "INTERNAL_ERROR")
    _assert_error(client.get(f"/api/v5/rl/runs/bad!?revision={REVISION}"), 400, "INTERNAL_ERROR")
    _assert_error(client.get(f"/api/v5/rl/matrix?revision={REVISION}"), 400, "INTERNAL_ERROR")
    _assert_error(client.get(f"/api/v5/rl/artifacts/artifact-1/download?revision={REVISION}"), 400, "INTERNAL_ERROR")

    unknown = _client(tmp_path, FakeRegistry(mode="unknown")).get(SUCCESS_PATHS["RUN_DETAIL"])
    _assert_error(unknown, 404, "NOT_FOUND")

    corrupt = _client(tmp_path, FakeRegistry(mode="corrupt")).get("/api/v5/rl/runs")
    _assert_error(corrupt, 503, "INTERNAL_ERROR")
    boom = _client(tmp_path, FakeRegistry(mode="boom")).get("/api/v5/rl/runs")
    boom_payload = _assert_error(boom, 503, "INTERNAL_ERROR")
    assert boom_payload["error"]["message"] == "internal server error"
    assert "D:/private" not in boom_payload["error"]["message"]


    invalid_payload = _client(tmp_path, FakeRegistry(mode="invalid-artifact-payload")).get(SUCCESS_PATHS["ARTIFACTS"])
    _assert_error(invalid_payload, 422, "INTERNAL_ERROR")

    off_loopback = client.get("/api/v5/rl/fixture", environ_base={"REMOTE_ADDR": "203.0.113.10"})
    _assert_error(off_loopback, 404, "INTERNAL_ERROR")


def test_public_download_route_uses_hardened_download_boundary_without_leaking_paths(tmp_path: Path) -> None:
    traversal = _client(tmp_path, FakeRegistry(mode="download-traversal")).get(f"/api/v5/rl/artifacts/artifact-1/download?run_id={quote(RUN_UID, safe='')}&revision={REVISION}")
    payload = _assert_error(traversal, 400, "INTERNAL_ERROR")
    assert "../secret/report.json" not in payload["error"]["message"]

    too_large = _client(tmp_path, FakeRegistry(mode="download-too-large")).get(f"/api/v5/rl/artifacts/artifact-1/download?run_id={quote(RUN_UID, safe='')}&revision={REVISION}")
    _assert_error(too_large, 413, "INTERNAL_ERROR")



@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", [*SUCCESS_PATHS.values(), f"/api/v5/rl/artifacts/artifact-1/download?run_id={quote(RUN_UID, safe='')}&revision={REVISION}"])
def test_all_non_get_methods_are_405(method: str, path: str, tmp_path: Path) -> None:
    response = _client(tmp_path).open(path, method=method)
    assert response.status_code == 405

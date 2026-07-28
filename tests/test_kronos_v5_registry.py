from __future__ import annotations

import base64
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import threading

import pytest

from stom_rl import v5_registry as registry


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_v5_registry_fixture.json").read_text(encoding="utf-8"))
CURSOR_KEY = bytes.fromhex(FIXTURE["cursor_key_hex"])
CURSOR_KEYS = {FIXTURE["cursor_key_id"]: CURSOR_KEY}
NOW = FIXTURE["created_utc"]
BASE_NOW = datetime.fromisoformat(NOW.replace("Z", "+00:00"))
APPEND_LOCK = threading.Lock()


def record_utc(offset_seconds: int) -> str:
    return (BASE_NOW + timedelta(seconds=offset_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")


def next_record_utc(reg: registry.KronosV5Registry) -> str:
    return record_utc(reg.identity().latest_global_seq)


def snap(name: str) -> dict:
    return deepcopy(FIXTURE["snapshots"][name])


def open_registry(path: Path, *, now: str = NOW, keys: dict[str, bytes] | None = None) -> registry.KronosV5Registry:
    return registry.KronosV5Registry(path, cursor_keys=CURSOR_KEYS if keys is None else keys, now=now)


def append_named(reg: registry.KronosV5Registry, name: str, expected: int, event_type: str = "RUN_SNAPSHOT", **kwargs: object) -> registry.SnapshotRead:
    created_utc = kwargs.pop("created_utc", None)
    if created_utc is None:
        created_utc = next_record_utc(reg)
    return reg.append_snapshot(snap(name), expected_run_revision=expected, event_type=event_type, created_utc=created_utc, **kwargs)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def cursor_payload(token: str) -> dict:
    body, _signature = token.split(".")
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def sign_cursor_payload(payload: dict) -> str:
    body = registry.canonical_bytes(payload)
    signature = hmac.new(CURSOR_KEY, body, hashlib.sha256).digest()
    return f"{b64(body)}.{b64(signature)}"


def make_two_revision_db(path: Path) -> None:
    reg = open_registry(path)
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")
    append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    reg.close()

def rewrite_journal_snapshot(conn: sqlite3.Connection, global_seq: int, snapshot: dict) -> None:
    row = conn.execute("SELECT * FROM journal WHERE global_seq=?", (global_seq,)).fetchone()
    payload = registry.canonical_bytes(snapshot)
    payload_sha = registry.sha256_hex(payload)
    record = json.loads(row["record_json"])
    record["payload_sha256"] = payload_sha
    record_json = registry.canonical_bytes(record)
    record_bytes = registry.RECORD_DOMAIN + record_json
    record_hash = registry.sha256_hex(record_bytes)
    conn.execute(
        "UPDATE journal SET payload_json=?, payload_sha256=?, record_json=?, record_hash=?, record_bytes=? WHERE global_seq=?",
        (payload.decode("utf-8"), payload_sha, record_json.decode("utf-8"), record_hash, record_bytes, global_seq),
    )
    conn.execute(
        "UPDATE current_runs SET payload_json=?, payload_sha256=?, record_hash=? WHERE global_seq=?",
        (payload.decode("utf-8"), payload_sha, record_hash, global_seq),
    )


def rewrite_journal_created_utc_and_recompute_tail(conn: sqlite3.Connection, global_seq: int, created_utc: str) -> None:
    previous_hash: str | None = None
    rows = conn.execute("SELECT * FROM journal WHERE global_seq>=? ORDER BY global_seq ASC", (global_seq,)).fetchall()
    for row in rows:
        record = json.loads(row["record_json"])
        row_created = created_utc if row["global_seq"] == global_seq else row["created_utc"]
        previous_global_hash = previous_hash or row["previous_global_hash"]
        record["created_utc"] = row_created
        record["previous_global_hash"] = previous_global_hash
        record_json = registry.canonical_bytes(record)
        record_bytes = registry.RECORD_DOMAIN + record_json
        record_hash = registry.sha256_hex(record_bytes)
        conn.execute(
            "UPDATE journal SET previous_global_hash=?, record_json=?, record_hash=?, record_bytes=?, created_utc=? WHERE global_seq=?",
            (previous_global_hash, record_json.decode("utf-8"), record_hash, record_bytes, row_created, row["global_seq"]),
        )
        conn.execute(
            "UPDATE current_runs SET record_hash=?, updated_utc=? WHERE global_seq=?",
            (record_hash, row_created, row["global_seq"]),
        )
        previous_hash = record_hash


def test_registry_meta_pragmas_complete_snapshot_and_exact_record_bytes(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    reg = open_registry(db)
    read = append_named(reg, "alpha_r1", 0, "RUN_CREATED")

    identity = reg.identity()
    assert identity.schema == registry.REGISTRY_SCHEMA
    assert identity.registry_epoch.count("-") == 4
    assert identity.genesis_global_hash == registry.ZERO_SHA256
    assert identity.cursor_key_id == FIXTURE["cursor_key_id"]
    assert identity.created_utc == NOW
    assert identity.read_only is False
    assert identity.latest_global_seq == 1
    assert identity.latest_record_hash == read.record_hash

    assert reg._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert int(reg._conn.execute("PRAGMA synchronous").fetchone()[0]) == 2
    assert int(reg._conn.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
    assert int(reg._conn.execute("PRAGMA busy_timeout").fetchone()[0]) == 30000

    row = reg._conn.execute("SELECT * FROM journal WHERE global_seq=1").fetchone()
    record = json.loads(row["record_json"])
    assert set(record) == {
        "schema_version",
        "registry_epoch",
        "global_seq",
        "run_uid",
        "run_revision",
        "attempt_uid",
        "cell_uid",
        "event_type",
        "payload_sha256",
        "previous_global_hash",
        "created_utc",
    }
    assert record == {
        "schema_version": registry.REGISTRY_RECORD_SCHEMA,
        "registry_epoch": identity.registry_epoch,
        "global_seq": 1,
        "run_uid": "run-alpha",
        "run_revision": 1,
        "attempt_uid": None,
        "cell_uid": None,
        "event_type": "RUN_CREATED",
        "payload_sha256": row["payload_sha256"],
        "previous_global_hash": registry.ZERO_SHA256,
        "created_utc": NOW,
    }
    assert row["payload_json"].encode("utf-8") == registry.canonical_bytes(snap("alpha_r1"))
    assert row["payload_sha256"] == registry.sha256_hex(row["payload_json"].encode("utf-8"))
    assert bytes(row["record_bytes"]) == registry.registry_record_bytes(record)
    assert row["record_hash"] == registry.registry_record_hash(record)
    reg.close()


def test_expected_revision_cas_complete_snapshot_and_liveness_semantics(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")

    with pytest.raises(registry.Conflict) as stale:
        append_named(reg, "alpha_r2", 0, "STALE_PROGRESS", attempt_uid="attempt-alpha-1")
    assert stale.value.status_code == 409

    missing_prior_field = snap("alpha_r2")
    del missing_prior_field["progress"]["total_steps"]
    with pytest.raises(registry.BadRequest, match="wrong field set"):
        reg.append_snapshot(missing_prior_field, expected_run_revision=1, event_type="PATCH_LIKE", attempt_uid="attempt-alpha-1", created_utc=NOW)

    heartbeat_only = snap("alpha_r2")
    heartbeat_only["progress"]["step"] = 0
    heartbeat_only["cells"][0]["step"] = 0
    with pytest.raises(registry.BadRequest, match="heartbeat alone"):
        reg.append_snapshot(heartbeat_only, expected_run_revision=1, event_type="HEARTBEAT_ONLY", attempt_uid="attempt-alpha-1", created_utc=NOW)

    first_advancing = snap("alpha_r1")
    first_advancing["liveness"] = "ADVANCING"
    first_advancing["phase"] = "CELL_RUNNING"
    first_advancing["progress"]["step"] = 1
    with pytest.raises(registry.BadRequest, match="prior snapshot"):
        open_registry(tmp_path / "first-advancing.sqlite").append_snapshot(first_advancing, expected_run_revision=0, event_type="BAD_FIRST", created_utc=NOW)

    ok = append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    assert ok.run_revision == 2
    assert ok.snapshot["liveness"] == "ADVANCING"
    reg.close()

def test_closed_schema_safe_bounds_and_liveness_matrix_reject(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")

    extra_nested_field = snap("alpha_r2")
    extra_nested_field["display"]["unexpected"] = "field"
    with pytest.raises(registry.BadRequest, match="extra"):
        reg.append_snapshot(extra_nested_field, expected_run_revision=1, event_type="EXTRA_FIELD", attempt_uid="attempt-alpha-1", created_utc=NOW)

    unsafe_integer = snap("alpha_r2")
    unsafe_integer["artifacts"][1]["byte_length"] = registry.SAFE_INTEGER_MAX + 1
    with pytest.raises(registry.BadRequest):
        reg.append_snapshot(unsafe_integer, expected_run_revision=1, event_type="UNSAFE_INTEGER", attempt_uid="attempt-alpha-1", created_utc=NOW)

    stalled_with_progress = snap("alpha_r2")
    stalled_with_progress["liveness"] = "STALLED"
    with pytest.raises(registry.BadRequest, match="unchanged progress"):
        reg.append_snapshot(stalled_with_progress, expected_run_revision=1, event_type="BAD_STALLED", attempt_uid="attempt-alpha-1", created_utc=NOW)

    stalled = append_named(reg, "alpha_r2_stalled", 1, "HEARTBEAT_STALLED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    assert stalled.snapshot["liveness"] == "STALLED"
    reg.close()


def test_stalled_rejects_regressed_prior_heartbeat_and_accepts_newer(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")
    append_named(reg, "alpha_r2_stalled", 1, "HEARTBEAT_STALLED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")

    regressed = snap("alpha_r2_stalled")
    regressed["run_revision"] = 3
    regressed["updated_utc"] = "2026-07-15T00:00:30Z"
    regressed["heartbeat"]["last_heartbeat_utc"] = "2026-07-15T00:00:10Z"
    with pytest.raises(registry.BadRequest, match="newer heartbeat"):
        reg.append_snapshot(regressed, expected_run_revision=2, event_type="HEARTBEAT_REGRESSED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1", created_utc=NOW)

    newer = snap("alpha_r2_stalled")
    newer["run_revision"] = 3
    newer["updated_utc"] = "2026-07-15T00:00:30Z"
    newer["heartbeat"]["last_heartbeat_utc"] = "2026-07-15T00:00:30Z"
    ok = reg.append_snapshot(newer, expected_run_revision=2, event_type="HEARTBEAT_STALLED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1", created_utc=next_record_utc(reg))
    assert ok.run_revision == 3
    assert ok.snapshot["heartbeat"]["last_heartbeat_utc"] == "2026-07-15T00:00:30Z"
    reg.close()


def test_terminal_run_is_immutable(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")
    append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    append_named(reg, "alpha_r3", 2, "RUN_COMPLETED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")

    terminal_rewrite = snap("alpha_r3")
    terminal_rewrite["run_revision"] = 4
    with pytest.raises(registry.Conflict, match="terminal run is immutable"):
        reg.append_snapshot(terminal_rewrite, expected_run_revision=3, event_type="AFTER_TERMINAL", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1", created_utc=next_record_utc(reg))
    reg.close()


def test_immutable_identity_and_monotonic_collections_reject(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")

    source_tamper = snap("alpha_r2")
    source_tamper["source"]["source_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    with pytest.raises(registry.BadRequest, match="source is immutable"):
        reg.append_snapshot(source_tamper, expected_run_revision=1, event_type="SOURCE_TAMPER", attempt_uid="attempt-alpha-1", created_utc=NOW)

    dropped_cell = snap("alpha_r2")
    dropped_cell["cells"] = []
    with pytest.raises(registry.BadRequest, match="cells must not shrink"):
        reg.append_snapshot(dropped_cell, expected_run_revision=1, event_type="DROP_CELL", attempt_uid="attempt-alpha-1", created_utc=NOW)

    duplicate_blocker = snap("alpha_r2")
    blocker = {"blocker_id": "blocker-alpha-1", "status": "OPEN", "created_utc": NOW, "message": "fixture blocker"}
    duplicate_blocker["blockers"] = [blocker, dict(blocker)]
    with pytest.raises(registry.BadRequest, match="blocker_id"):
        reg.append_snapshot(duplicate_blocker, expected_run_revision=1, event_type="DUP_BLOCKER", attempt_uid="attempt-alpha-1", created_utc=NOW)

    append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")

    dropped_attempt = snap("alpha_r3")
    dropped_attempt["attempts"] = []
    with pytest.raises(registry.BadRequest, match="attempts must not shrink"):
        reg.append_snapshot(dropped_attempt, expected_run_revision=2, event_type="DROP_ATTEMPT", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1", created_utc=NOW)

    artifact_tamper = snap("alpha_r3")
    artifact_tamper["artifacts"][1]["sha256"] = "8888888888888888888888888888888888888888888888888888888888888888"
    with pytest.raises(registry.BadRequest, match="artifacts entries are append-only"):
        reg.append_snapshot(artifact_tamper, expected_run_revision=2, event_type="ARTIFACT_TAMPER", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1", created_utc=next_record_utc(reg))

    reg.close()


def _thread_append(path: Path, snapshot_name: str) -> tuple[str, str | int, int | None]:
    try:
        reg = open_registry(path)
        try:
            with APPEND_LOCK:
                read = append_named(reg, snapshot_name, 0, "CONCURRENT_CREATE")
            return ("ok", read.run_uid, read.global_seq)
        finally:
            reg.close()
    except registry.Conflict as exc:
        return ("conflict", exc.status_code, None)


def test_concurrent_same_run_cas_allows_one_writer_and_different_runs_both_commit(tmp_path: Path) -> None:
    same_db = tmp_path / "same.sqlite"
    open_registry(same_db).close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        same_results = list(pool.map(lambda _i: _thread_append(same_db, "alpha_r1"), range(2)))
    assert sorted(result[0] for result in same_results) == ["conflict", "ok"]
    assert open_registry(same_db).identity().latest_global_seq == 1

    different_db = tmp_path / "different.sqlite"
    open_registry(different_db).close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        diff_results = list(pool.map(lambda name: _thread_append(different_db, name), ["beta_r1", "gamma_r1"]))
    assert [result[0] for result in diff_results].count("ok") == 2
    reopened = open_registry(different_db)
    assert reopened.identity().latest_global_seq == 2
    assert sorted(item.run_uid for item in reopened.list_runs(limit=10).items) == ["run-beta", "run-gamma"]
    reopened.close()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("payload_hash", "payload_sha256"),
        ("gap", "global sequence gap"),
        ("fork", "global hash fork"),
        ("torn_tail", "current_runs"),
        ("semantic_hash_valid", "semantic validation"),
    ],
)
def test_startup_detects_tamper_gap_fork_torn_tail_and_semantic_replay_as_read_only_corrupt(tmp_path: Path, mutation: str, reason: str) -> None:
    db = tmp_path / f"{mutation}.sqlite"
    make_two_revision_db(db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    if mutation == "payload_hash":
        conn.execute("UPDATE journal SET payload_sha256=? WHERE global_seq=1", (registry.ZERO_SHA256,))
    elif mutation == "gap":
        conn.execute("DELETE FROM journal WHERE global_seq=1")
    elif mutation == "fork":
        conn.execute("UPDATE journal SET previous_global_hash=? WHERE global_seq=2", (registry.ZERO_SHA256,))
    elif mutation == "torn_tail":
        row1 = conn.execute("SELECT * FROM journal WHERE global_seq=1").fetchone()
        conn.execute(
            "UPDATE current_runs SET run_revision=?, global_seq=?, payload_json=?, payload_sha256=?, record_hash=? WHERE run_uid=?",
            (row1["run_revision"], row1["global_seq"], row1["payload_json"], row1["payload_sha256"], row1["record_hash"], row1["run_uid"]),
        )
    elif mutation == "semantic_hash_valid":
        tampered = snap("alpha_r2")
        tampered["source"]["source_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        rewrite_journal_snapshot(conn, 2, tampered)
    conn.commit()
    conn.close()

    reopened = open_registry(db)
    identity = reopened.identity()
    assert identity.read_only is True
    assert reason in (identity.corrupt_reason or "")
    with pytest.raises(registry.Corrupt):
        append_named(reopened, "gamma_r1", 0, "WRITE_AFTER_CORRUPT")
    with pytest.raises(registry.Corrupt):
        reopened.list_runs()
    reopened.close()

def test_registry_created_utc_strict_global_order_append_pagination_and_replay(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    reg = open_registry(db)
    first = append_named(reg, "alpha_r1", 0, "RUN_CREATED")

    with pytest.raises(registry.BadRequest, match="strictly greater"):
        reg.append_snapshot(snap("alpha_r2"), expected_run_revision=1, event_type="EQUAL_TIME", attempt_uid="attempt-alpha-1", created_utc=first.created_utc)
    with pytest.raises(registry.BadRequest, match="strictly greater"):
        reg.append_snapshot(snap("alpha_r2"), expected_run_revision=1, event_type="REGRESSED_TIME", attempt_uid="attempt-alpha-1", created_utc=record_utc(-1))

    append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    append_named(reg, "alpha_r3", 2, "RUN_COMPLETED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")

    after_global_seq = 0
    observed: list[dict] = []
    while True:
        page = reg.list_events("run-alpha", revision=3, after_global_seq=after_global_seq, limit=1)
        observed.extend(page.items)
        if page.next_after_global_seq is None:
            break
        after_global_seq = page.next_after_global_seq

    assert [event["global_seq"] for event in observed] == [1, 2, 3]
    assert [event["created_utc"] for event in observed] == [record_utc(0), record_utc(1), record_utc(2)]
    reg.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rewrite_journal_created_utc_and_recompute_tail(conn, 2, first.created_utc)
    conn.commit()
    conn.close()

    reopened = open_registry(db)
    identity = reopened.identity()
    assert identity.read_only is True
    assert "strictly greater" in (identity.corrupt_reason or "")
    with pytest.raises(registry.Corrupt):
        reopened.list_runs()
    reopened.close()


def test_snapshot_keyset_pagination_is_stable_across_insert_and_update_between_pages(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "CREATE_ALPHA")
    append_named(reg, "beta_r1", 0, "CREATE_BETA")
    append_named(reg, "gamma_r1", 0, "CREATE_GAMMA")

    first = reg.list_runs(limit=2)
    assert [item.run_uid for item in first.items] == ["run-gamma", "run-beta"]
    assert first.snapshot_global_seq == 3
    assert first.next_cursor is not None

    append_named(reg, "alpha_r2", 1, "UPDATE_ALPHA", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    append_named(reg, "delta_r1", 0, "CREATE_DELTA")

    second = reg.list_runs(limit=2, cursor=first.next_cursor)
    assert [(item.run_uid, item.run_revision, item.global_seq) for item in second.items] == [("run-alpha", 1, 1)]
    assert second.next_cursor is None
    combined = [*first.items, *second.items]
    assert [item.run_uid for item in combined] == ["run-gamma", "run-beta", "run-alpha"]
    assert len({item.run_uid for item in combined}) == 3
    assert [item.global_seq for item in combined] == [3, 2, 1]

    equal_keyset_page = reg.list_runs(limit=4)
    assert [item.run_uid for item in equal_keyset_page.items] == ["run-delta", "run-alpha", "run-gamma", "run-beta"]
    assert equal_keyset_page.next_cursor is None
    reg.close()


def test_hmac_cursor_canonical_encoding_and_status_classes(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    reg = open_registry(db)
    append_named(reg, "alpha_r1", 0, "CREATE_ALPHA")
    append_named(reg, "beta_r1", 0, "CREATE_BETA")
    append_named(reg, "gamma_r1", 0, "CREATE_GAMMA")

    page = reg.list_runs(limit=1)
    cursor = page.next_cursor
    assert cursor is not None
    body, signature = cursor.split(".")
    assert "=" not in cursor
    payload = cursor_payload(cursor)
    assert b64(registry.canonical_bytes(payload)) == body
    assert b64(hmac.new(CURSOR_KEY, registry.canonical_bytes(payload), hashlib.sha256).digest()) == signature
    assert payload["snapshot_global_seq"] == 3
    assert payload["last_global_seq"] == page.items[-1].global_seq
    assert payload["last_run_uid"] == page.items[-1].run_uid
    assert payload["key_id"] == FIXTURE["cursor_key_id"]

    tampered_signature = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
    with pytest.raises(registry.BadRequest) as tampered:
        reg.list_runs(limit=1, cursor=tampered_signature)
    assert tampered.value.status_code == 400

    with pytest.raises(registry.BadRequest) as mismatch:
        reg.list_runs(limit=2, cursor=cursor)
    assert mismatch.value.status_code == 400

    expired = open_registry(db, now=FIXTURE["later_utc"])
    with pytest.raises(registry.Gone) as expired_error:
        expired.list_runs(limit=1, cursor=cursor)
    assert expired_error.value.status_code == 410
    expired.close()

    rotated = open_registry(db, keys={"rotated-key": CURSOR_KEY})
    with pytest.raises(registry.Gone, match="key"):
        rotated.list_runs(limit=1, cursor=cursor)
    rotated.close()

    epoch_payload = cursor_payload(cursor)
    epoch_payload["registry_epoch"] = "00000000-0000-4000-8000-000000000001"
    with pytest.raises(registry.Gone, match="epoch"):
        reg.list_runs(limit=1, cursor=sign_cursor_payload(epoch_payload))
    reg.close()


def test_events_as_of_revision_detail_matrix_and_artifact_reads(tmp_path: Path) -> None:
    reg = open_registry(tmp_path / "registry.sqlite")
    append_named(reg, "alpha_r1", 0, "RUN_CREATED")
    append_named(reg, "alpha_r2", 1, "CELL_PROGRESS", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")
    append_named(reg, "alpha_r3", 2, "RUN_COMPLETED", attempt_uid="attempt-alpha-1", cell_uid="cell-alpha-1")

    detail = reg.get_run("run-alpha", revision=2)
    assert detail.snapshot == snap("alpha_r2")
    with pytest.raises(registry.NotFound):
        reg.get_run("run-alpha", revision=99)

    first_event_page = reg.list_events("run-alpha", revision=2, limit=1)
    assert [event["run_revision"] for event in first_event_page.items] == [1]
    assert first_event_page.next_after_global_seq == 1
    second_event_page = reg.list_events("run-alpha", revision=2, after_global_seq=first_event_page.next_after_global_seq)
    assert [event["run_revision"] for event in second_event_page.items] == [2]
    assert second_event_page.next_after_global_seq is None
    assert all(event["global_seq"] <= detail.global_seq for event in [*first_event_page.items, *second_event_page.items])

    attempt_events = reg.list_events("run-alpha", revision=3, attempt_uid="attempt-alpha-1")
    assert [event["event_type"] for event in attempt_events.items] == ["CELL_PROGRESS", "RUN_COMPLETED"]

    matrix = reg.get_matrix("run-alpha", revision=3)
    assert matrix.matrix == snap("alpha_r3")["matrix"]
    assert matrix.matrix["terminal"] is True

    artifacts = reg.list_artifacts("run-alpha", revision=3)
    assert [artifact["artifact_id"] for artifact in artifacts] == ["alpha-config", "alpha-metrics", "alpha-terminal"]
    assert reg.get_artifact("run-alpha", "alpha-terminal", revision=3)["sha256"] == "7777777777777777777777777777777777777777777777777777777777777777"
    with pytest.raises(registry.NotFound):
        reg.get_artifact("run-alpha", "missing", revision=3)
    reg.close()

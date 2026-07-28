"""Complete golden and adversarial vectors for the V5 API semantic boundary."""
from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from webui.v5_api_contract import (
    MATRIX_ORDER, ROUTE_DESCRIPTORS, ROUTE_EXPORTS, SCHEMA_ID, SEMANTIC_RULES,
    SIX_LOCKS, SOURCE_IDENTITY_SCHEMA_ID, V5ApiContractError, V5_ROUTE_IDS,
    canonical_json, decode_cursor, encode_cursor, event_payload_projection, event_payload_sha256,
    validate_payload as contract_validate_payload, validate_route_payload as contract_validate_route_payload,
)

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "tests/data/kronos_rl_api_v2_vectors.json").read_text(encoding="utf-8"))
SHA = VECTORS["source"]["source_sha256"]
KEY = bytes.fromhex(VECTORS["test_metadata"]["cursor_test_key_hex"])
JCS_VECTORS = json.loads((ROOT / "tests/data/kronos_jcs_rfc8785_v1_vectors.json").read_text(encoding="utf-8"))


def root(route: str, **body: object) -> dict:
    return {"route_id": route, "source": deepcopy(VECTORS["source"]), "locks": deepcopy(VECTORS["locks"]), **body}


def run() -> dict:
    return deepcopy(VECTORS["run"])


def payload_for(route: str, *, cursor: str | None = None) -> dict:
    if route == "RUNS": return root(route, list={"items": [run()], "next_cursor": cursor})
    if route == "RUN_DETAIL": return root(route, run=run())
    if route == "EVENTS":
        items = deepcopy(VECTORS["events"])
        if cursor is not None:
            items = [event for event in items if event["event_id"] == VECTORS["cursor_cases"]["EVENTS"]["last_key"]["event_id"]]
        return root(route, run_id="run-1", list={"items": items, "next_cursor": cursor})
    if route == "MATRIX": return root(route, cells=deepcopy(VECTORS["matrix"]["cells"]), summary=deepcopy(VECTORS["matrix"]["summary"]))
    if route == "LEDGER": return root(route, list={"items": [{"entry_id":"entry-1", "occurred_at":"2026-07-15T00:00:00Z", "kind":"DEBIT", "amount":1, "currency":"KRONOS_CREDIT", "source_sha256":SHA}], "next_cursor":cursor})
    if route == "ARTIFACTS": return root(route, list={"items":[{"artifact":{"artifact_id":"artifact-1", "filename":"report.json", "media_type":"application/json", "byte_length":2, "sha256":SHA, "created_at":"2026-07-15T00:00:00Z"}, "download_url":"/api/v5/rl/artifacts/artifact-1/download", "portable_filename":"report.json"}], "next_cursor":cursor})
    if route == "D0": return root(route, d0={"status":"BLOCKED", "price_basis":"UNKNOWN", "source_sha256":SHA, "updated_at":"2026-07-15T00:00:00Z"})
    if route == "D1": return root(route, d1={"status":"BLOCKED", "universe":"UNKNOWN", "source_sha256":SHA, "updated_at":"2026-07-15T00:00:00Z"})
    return root(route, fixture={"fixture_id":"fixture-1", "run":run(), "source_sha256":SHA, "created_at":"2026-07-15T00:00:00Z"})
def validate_payload(payload: dict, *, cursor: str | None = None) -> None:
    contract_validate_payload(payload, cursor_key=KEY, cursor=cursor)


def validate_route_payload(route: str, payload: dict, *, cursor: str | None = None) -> None:
    contract_validate_route_payload(route, payload, cursor_key=KEY, cursor=cursor)



def test_vector_manifest_is_complete_and_consumed() -> None:
    assert VECTORS["manifest"] == ["source", "locks", "run", "matrix", "events", "cursor_cases", "route_ids", "error_codes", "route_error_matrix", "d0_d1_semantic_cases", "multi_page", "cursor_schema", "test_metadata", "progress_cases", "portable_filename_cases", "pagination_cases", "early_year_timestamp_order", "jcs_vector_file"]
    assert VECTORS["locks"] == SIX_LOCKS
    assert VECTORS["jcs_vector_file"] == "kronos_jcs_rfc8785_v1_vectors.json"
    assert tuple(VECTORS["matrix"]["seeds"]) == tuple(sorted({cell["row_id"] for cell in VECTORS["matrix"]["cells"]}))
    assert tuple(VECTORS["matrix"]["columns"]) == tuple(cell["column_id"] for cell in VECTORS["matrix"]["cells"][:10])


def test_shared_jcs_number_negative_zero_exponent_and_unicode_vectors_are_consumed() -> None:
    for vector in JCS_VECTORS["accepted"]:
        value = json.loads(vector["input_utf8"])
        assert canonical_json(value) == vector["canonical_utf8"].encode("utf-8")


def test_schema_exports_machine_readable_contract_and_usable_matrix_cells() -> None:
    schema = json.loads((ROOT / "docs/schemas/kronos_rl_api_v2.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == SCHEMA_ID and SOURCE_IDENTITY_SCHEMA_ID.endswith("source_identity.v1.schema.json")
    assert schema["$defs"]["semantic_rules"]["const"] == SEMANTIC_RULES
    assert schema["$defs"]["matrixCells"] == {"type":"array", "minItems":50, "maxItems":50, "items":{"$ref":"#/$defs/matrixCell"}}
    assert schema["$defs"]["cursor"] == {
        "type": "string",
        "pattern": VECTORS["cursor_schema"]["pattern"],
        "minLength": VECTORS["cursor_schema"]["min_length"],
        "maxLength": VECTORS["cursor_schema"]["max_length"],
    }
    assert tuple(ROUTE_DESCRIPTORS) == tuple(VECTORS["route_ids"]) == V5_ROUTE_IDS
    assert set(ROUTE_EXPORTS) == set(V5_ROUTE_IDS)
    for route, descriptor in ROUTE_DESCRIPTORS.items():
        published = schema["$defs"]["routeDescriptors"]["const"][route]
        assert tuple(published["allowed_errors"]) == tuple(VECTORS["route_error_matrix"][route]) == descriptor["allowed_errors"]
    assert len(schema["$defs"]["errorRoot"]["allOf"]) == len(V5_ROUTE_IDS)


@pytest.mark.parametrize("route", VECTORS["route_ids"])
def test_all_success_roots_consume_full_vector_inputs(route: str) -> None:
    validate_payload(payload_for(route))


@pytest.mark.parametrize("event", VECTORS["events"], ids=lambda event: event["event_type"])
def test_event_variants_are_closed_and_payload_digest_is_canonical(event: dict) -> None:
    assert event["payload_sha256"] == event_payload_sha256(event)
    assert set(event_payload_projection(event)) == ({"event_type", "progress"} if event["event_type"] == "PROGRESS" else {"event_type", "level", "message"} if event["event_type"] == "MESSAGE" else {"event_type", "artifact_id"} if event["event_type"] == "ARTIFACT" else {"event_type", "state"})
    validate_payload(root("EVENTS", run_id="run-1", list={"items":[deepcopy(event)], "next_cursor":None}))
    changed = deepcopy(event)
    field = next(name for name in event_payload_projection(event) if name != "event_type")
    if field == "progress": changed[field]["step"] = 2
    elif field == "state": changed[field]["status"] = "FAILED"
    elif field == "message": changed[field] = "changed"
    else: changed[field] = "artifact-2"
    with pytest.raises(V5ApiContractError): validate_payload(root("EVENTS", run_id="run-1", list={"items":[changed], "next_cursor":None}))
    cross_variant = deepcopy(event); cross_variant["artifact_id" if event["event_type"] != "ARTIFACT" else "message"] = "artifact-1"
    with pytest.raises(V5ApiContractError): validate_payload(root("EVENTS", run_id="run-1", list={"items":[cross_variant], "next_cursor":None}))


@pytest.mark.parametrize("route", VECTORS["route_ids"])
@pytest.mark.parametrize("code", VECTORS["error_codes"])
def test_error_root_full_route_code_cartesian_product(route: str, code: str) -> None:
    payload = {"route_id":route, "error":{"code":code, "message":"vector"}}
    expected = code in VECTORS["route_error_matrix"][route]
    if expected: validate_route_payload(route, payload)
    else:
        with pytest.raises(V5ApiContractError): validate_route_payload(route, payload)


@pytest.mark.parametrize("route", VECTORS["cursor_cases"])
def test_authenticated_cursor_vectors_cover_valid_tamper_stale_cross_route_and_page_order(route: str) -> None:
    case = VECTORS["cursor_cases"][route]
    assert encode_cursor(route, SHA, case["last_key"], key=KEY, run_id=case["run_id"]) == case["token"]
    assert decode_cursor(case["token"], route, SHA, key=KEY, run_id=case["run_id"]) == case["last_key"]
    assert VECTORS["cursor_schema"]["min_length"] <= len(case["token"]) <= VECTORS["cursor_schema"]["max_length"]
    payload = payload_for(route, cursor=case["token"]); validate_payload(payload)
    tampered = case["token"][:-1] + ("A" if case["token"][-1] != "A" else "B")
    with pytest.raises(V5ApiContractError): decode_cursor(tampered, route, SHA, key=KEY, run_id=case["run_id"])
    with pytest.raises(V5ApiContractError): decode_cursor(case["token"], route, "b" * 64, key=KEY, run_id=case["run_id"])
    other = next(candidate for candidate in VECTORS["cursor_cases"] if candidate != route)
    with pytest.raises(V5ApiContractError): decode_cursor(case["token"], other, SHA, key=KEY, run_id=VECTORS["cursor_cases"][other]["run_id"])
    with pytest.raises(TypeError): encode_cursor(route, SHA, case["last_key"], run_id=case["run_id"])
    with pytest.raises(TypeError): contract_validate_payload(payload)
    if route == "RUNS":
        bad_order = payload_for(route); second = run(); second["created_at"] = "2026-07-16T00:00:00Z"; bad_order["list"]["items"].append(second)
        with pytest.raises(V5ApiContractError): validate_payload(bad_order)
        tie_out_of_order = payload_for(route); second = run(); second["run_id"] = "run-0"; tie_out_of_order["list"]["items"].append(second)
        with pytest.raises(V5ApiContractError): validate_payload(tie_out_of_order)
@pytest.mark.parametrize(
    "route",
    [route for route, case in VECTORS["cursor_cases"].items() if len(case["token"]) % 4 in {2, 3}],
)
def test_authenticated_cursors_reject_noncanonical_pad_bit_spellings(route: str) -> None:
    case = VECTORS["cursor_cases"][route]
    token = case["token"]
    assert len(token) % 4 in {2, 3}
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    alias = token[:-1] + alphabet[alphabet.index(token[-1]) ^ 1]
    padding = "=" * (-len(token) % 4)
    assert base64.urlsafe_b64decode(alias + padding) == base64.urlsafe_b64decode(token + padding)
    with pytest.raises(V5ApiContractError): decode_cursor(alias, route, SHA, key=KEY, run_id=case["run_id"])
def test_multi_page_vector_preserves_canonical_global_order() -> None:
    case = VECTORS["multi_page"]
    observed = []
    cursor = None
    for page in case["pages"]:
        validate_payload(root(case["route"], list=deepcopy(page)), cursor=cursor)
        observed.extend(item["run_id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert observed == case["expected_run_ids"]
    replay = root(case["route"], list=deepcopy(case["pages"][0]))
    with pytest.raises(V5ApiContractError): validate_payload(replay, cursor=case["pages"][0]["next_cursor"])
def test_pagination_vectors_normalize_fractional_timestamps_reject_duplicate_keys_and_use_nested_artifact_keys() -> None:
    cases = VECTORS["pagination_cases"]
    chronological = cases["whole_vs_fractional"]
    validate_payload(root(chronological["route"], list={"items": deepcopy(chronological["items"]), "next_cursor": None}))
    reverse = deepcopy(chronological["items"]); reverse.reverse()
    with pytest.raises(V5ApiContractError): validate_payload(root(chronological["route"], list={"items": reverse, "next_cursor": None}))
    duplicate = cases["duplicate_complete_key"]
    with pytest.raises(V5ApiContractError): validate_payload(root(duplicate["route"], list={"items": deepcopy(duplicate["items"]), "next_cursor": None}))

    artifacts = cases["artifacts_pages"]
    first, second = deepcopy(artifacts["pages"][0]), deepcopy(artifacts["pages"][1])
    key = {"created_at": first[-1]["artifact"]["created_at"], "artifact_id": first[-1]["artifact"]["artifact_id"]}
    cursor = encode_cursor(artifacts["route"], SHA, key, key=KEY)
    validate_payload(root(artifacts["route"], list={"items": first, "next_cursor": cursor}))
    validate_payload(root(artifacts["route"], list={"items": second, "next_cursor": None}), cursor=cursor)
    assert [item["artifact"]["artifact_id"] for item in first + second] == artifacts["expected_artifact_ids"]
    with pytest.raises(V5ApiContractError): validate_payload(root(artifacts["route"], list={"items": first, "next_cursor": None}), cursor=cursor)
    


def test_early_year_timestamp_order_vector_is_consumed() -> None:
    case = VECTORS["early_year_timestamp_order"]
    validate_payload(root(case["route"], list={"items": deepcopy(case["items"]), "next_cursor": None}))
    reverse = deepcopy(case["items"])
    reverse.reverse()
    with pytest.raises(V5ApiContractError):
        validate_payload(root(case["route"], list={"items": reverse, "next_cursor": None}))

def test_matrix_exact_cartesian_order_summary_and_locks_are_semantic() -> None:
    assert tuple((cell["row_id"], cell["column_id"]) for cell in VECTORS["matrix"]["cells"]) == MATRIX_ORDER
    payload = payload_for("MATRIX"); validate_payload(payload)
    payload["cells"][0], payload["cells"][1] = payload["cells"][1], payload["cells"][0]
    with pytest.raises(V5ApiContractError): validate_payload(payload)
    locked = payload_for("D0"); locked["locks"]["go_summary_allowed"] = True
    with pytest.raises(V5ApiContractError): validate_payload(locked)

@pytest.mark.parametrize("case", VECTORS["d0_d1_semantic_cases"], ids=lambda case: case["id"])
def test_d0_d1_status_semantics_reject_pass_or_fail_unknown(case: dict) -> None:
    payload = payload_for(case["route"])
    body = payload[case["route"].lower()]
    body["status"] = case["status"]
    body["price_basis" if case["route"] == "D0" else "universe"] = case["price_basis" if case["route"] == "D0" else "universe"]
    if case["accepted"]:
        validate_payload(payload)
    else:
        with pytest.raises(V5ApiContractError):
            validate_payload(payload)


@pytest.mark.parametrize("case", VECTORS["progress_cases"], ids=lambda case: case["id"])
def test_progress_vectors_enforce_exact_rational_half_up_arithmetic_and_safe_integer_bounds(case: dict) -> None:
    state = run()["state"]
    state["progress"] = {"step": case["step"], "total_steps": case["total_steps"], "percent": case["percent"]}
    payload = root("RUN_DETAIL", run={**run(), "state": state})
    if case.get("accepted", True):
        validate_payload(payload)
    else:
        with pytest.raises(V5ApiContractError): validate_payload(payload)


@pytest.mark.parametrize("case", VECTORS["portable_filename_cases"], ids=lambda case: case["filename"])
def test_portable_filename_vectors_reject_windows_reserved_basenames(case: dict) -> None:
    payload = payload_for("ARTIFACTS")
    item = payload["list"]["items"][0]
    item["artifact"]["filename"] = case["filename"]
    item["portable_filename"] = case["filename"]
    if case["accepted"]:
        validate_payload(payload)
    else:
        with pytest.raises(V5ApiContractError): validate_payload(payload)


ARTIFACT_MEDIA_CASES = (
    ("json", "application/json"),
    ("csv", "text/csv"),
    ("jsonl", "application/jsonl"),
    ("md", "text/markdown"),
    ("png", "image/png"),
)


def artifact_payload(
    filename: str = "report.json",
    media_type: str = "application/json",
    *,
    artifact_id: str = "artifact-1",
    download_url: str | None = None,
    portable_filename: str | None = None,
    run_id: str | None = None,
    run_revision: int | None = None,
) -> dict:
    payload = payload_for("ARTIFACTS")
    item = payload["list"]["items"][0]
    item["artifact"]["artifact_id"] = artifact_id
    item["artifact"]["filename"] = filename
    item["artifact"]["media_type"] = media_type
    item["download_url"] = download_url or f"/api/v5/rl/artifacts/{artifact_id}/download"
    item["portable_filename"] = portable_filename or filename
    if run_id is not None:
        item["run_id"] = run_id
    if run_revision is not None:
        item["run_revision"] = run_revision
    return payload


@pytest.mark.parametrize(("extension", "media_type"), ARTIFACT_MEDIA_CASES)
def test_artifact_filename_mime_semantics_cover_schema_extension_set(extension: str, media_type: str) -> None:
    validate_payload(artifact_payload(f"report.{extension}", media_type))
    wrong_media_type = "text/csv" if media_type != "text/csv" else "application/json"
    with pytest.raises(V5ApiContractError):
        validate_payload(artifact_payload(f"report.{extension}", wrong_media_type))


@pytest.mark.parametrize(("filename", "media_type"), [("report.txt", "text/plain"), ("report.zip", "application/zip")])
def test_artifact_filename_mime_semantics_reject_removed_txt_zip_drift(filename: str, media_type: str) -> None:
    with pytest.raises(V5ApiContractError):
        validate_payload(artifact_payload(filename, media_type))


def test_download_url_query_bindings_accept_bare_and_exact_run_identity() -> None:
    validate_payload(artifact_payload())
    validate_payload(artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=7", run_id="run-1", run_revision=7))
    validate_payload(artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&run_revision=7", run_id="run-1", run_revision=7))


def test_download_url_query_bindings_reject_mismatch_extra_or_inconsistent_identity() -> None:
    invalid_payloads = [
        artifact_payload(download_url="/api/v5/rl/artifacts/other/download"),
        artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-2&revision=7", run_id="run-1", run_revision=7),
        artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=8", run_id="run-1", run_revision=7),
        artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=7&extra=1", run_id="run-1", run_revision=7),
        artifact_payload(download_url="/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=7"),
        artifact_payload(run_id="run-1"),
        artifact_payload(run_revision=7),
    ]
    for payload in invalid_payloads:
        with pytest.raises(V5ApiContractError):
            validate_payload(payload)



_INVALID_UTC = "2026-02-30T00:00:00Z"


def _payload_with_invalid_utc(route: str, path: tuple[str | int, ...]) -> dict:
    payload = payload_for(route)
    target: object = payload
    for segment in path[:-1]:
        target = target[segment]  # type: ignore[index]
    target[path[-1]] = _INVALID_UTC  # type: ignore[index]
    return payload


@pytest.mark.parametrize(
    ("route", "path"),
    [
        ("MATRIX", ("source", "generated_at")),
        ("RUN_DETAIL", ("run", "created_at")),
        ("RUN_DETAIL", ("run", "state", "updated_at")),
        ("RUN_DETAIL", ("run", "state", "started_at")),
        ("RUN_DETAIL", ("run", "state", "finished_at")),
        ("LEDGER", ("list", "items", 0, "occurred_at")),
        ("ARTIFACTS", ("list", "items", 0, "artifact", "created_at")),
        ("D0", ("d0", "updated_at")),
        ("D1", ("d1", "updated_at")),
        ("FIXTURE", ("fixture", "created_at")),
    ],
    ids=[
        "source-generated-at",
        "run-created-at",
        "state-updated-at",
        "state-started-at",
        "state-finished-at",
        "ledger-occurred-at",
        "artifact-created-at",
        "d0-updated-at",
        "d1-updated-at",
        "fixture-created-at",
    ],
)
def test_reachable_utc_shapes_reject_impossible_calendar_dates(route: str, path: tuple[str | int, ...]) -> None:
    with pytest.raises(V5ApiContractError):
        validate_payload(_payload_with_invalid_utc(route, path))


@pytest.mark.parametrize("event", VECTORS["events"], ids=lambda event: event["event_type"])
def test_all_event_variants_reject_impossible_occurred_at_dates(event: dict) -> None:
    invalid = deepcopy(event)
    invalid["occurred_at"] = _INVALID_UTC
    with pytest.raises(V5ApiContractError):
        validate_payload(root("EVENTS", run_id="run-1", list={"items": [invalid], "next_cursor": None}))

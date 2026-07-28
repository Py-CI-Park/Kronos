import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/schemas/kronos_v5_qa_producers.v1.schema.json"
INSTRUMENT = ROOT / "docs/kronos_dashboard_v5_usability_instrument_v1.json"
MATRIX = ROOT / "docs/kronos_dashboard_v5_browser_matrix_v1.json"

BRANCHES = (
    "fixtureDescriptor",
    "screenshotArtifact",
    "transcriptArtifact",
    "captureArtifact",
    "performanceResult",
    "securityResult",
    "bundleManifest",
    "sourceManifest",
    "distManifest",
    "machineTaskScore",
    "baselineReceipt",
)

SCHEMA_CONSTS = {
    "fixtureDescriptor": "kronos_fixture.v2",
    "screenshotArtifact": "kronos_qa_screenshot.v1",
    "transcriptArtifact": "kronos_qa_transcript.v1",
    "captureArtifact": "kronos_v5_browser_capture.v1",
    "performanceResult": "kronos_v5_performance_result.v1",
    "securityResult": "kronos_v5_security_result.v1",
    "bundleManifest": "kronos_bundle_manifest.v1",
    "sourceManifest": "kronos_source_manifest.v1",
    "distManifest": "kronos_dist_manifest.v1",
    "machineTaskScore": "kronos_machine_task_score.v2",
    "baselineReceipt": "kronos_qa_baseline_receipt.v1",
}

SHA = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
BUDGETS_MS = {
    "first_critical_cold_ms": 3000,
    "first_critical_warm_ms": 1500,
    "full_hydration_cold_ms": 10000,
    "full_hydration_warm_ms": 6000,
    "api_cold_ms": 5000,
    "api_warm_ms": 2000,
    "isolated_timeout_ms": 20500,
    "palette_ms": 100,
    "filter_1000_ms": 150,
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema_once():
    raw = SCHEMA.read_text(encoding="utf-8")
    schema, index = json.JSONDecoder().raw_decode(raw)
    assert raw[index:].strip() == ""
    return schema


def schema_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = load_schema_once()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema, jsonschema.Draft202012Validator(schema)


def uri_ref(schema="kronos_fixture.v2", suffix="artifact"):
    return {"uri": f"agent://qa/{suffix}", "sha256": SHA, "byte_length": 1, "schema": schema}


def relative_ref(path="artifact.json", media_type="application/json"):
    return {"relative_path": path, "sha256": SHA, "byte_length": 1, "media_type": media_type}


def false_locks():
    return {
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
    }


def fixture_descriptor():
    return {
        "schema": "kronos_fixture.v2",
        "nonce": SHA,
        "pid": 4101,
        "host": "127.0.0.1",
        "port": 49152,
        "source_sha256": SHA_B,
        "fixture_sha256": SHA_C,
        "registry_root": "D:/Temp/kronos/registry",
        "artifact_root": "D:/Temp/kronos/artifacts",
        "job_intent_root": "D:/Temp/kronos/intents",
        "readiness_path": "D:/Temp/kronos/registry/fixture.ready.json",
        "readiness_timestamp_utc": "2026-07-15T00:00:00Z",
        "cleanup_status": "GRACEFUL",
    }


def screenshot_artifact():
    return {
        "schema": "kronos_qa_screenshot.v1",
        "scenario_id": "S-BASE-mission-control-light-375",
        "sequence": 1,
        "png_ref": uri_ref("kronos_screenshot.v2", "screenshots/one"),
        "width": 375,
        "height": 812,
        "non_uniform": True,
        "sha256": SHA,
    }


def transcript_artifact():
    return {
        "schema": "kronos_qa_transcript.v1",
        "scenario_id": "S-BASE-mission-control-light-375",
        "sequence": 1,
        "transcript_ref": uri_ref("kronos_transcript.v1", "transcripts/one"),
        "sha256": SHA,
    }


def scenario_evidence(scenario_id):
    return {
        "scenario_id": scenario_id,
        "status": "passed",
        "screenshot_ref": relative_ref("screen.png", "image/png"),
        "screenshot": {"width": 2, "height": 1},
        "transcript_ref": relative_ref("trace.json", "application/json"),
        "console_errors": [],
        "page_errors": [],
        "network_errors": [],
        "overflow": False,
        "focus": "passed",
        "keyboard": "passed",
        "a11y": "passed",
        "chart_table_semantics": "passed",
    }


def capture_artifact():
    scenarios = list(load(MATRIX)["scenarios"])
    return {
        "schema": "kronos_v5_browser_capture.v1",
        "capture_kind": "synthetic_fixture_evidence",
        "live_browser_execution": False,
        "nonce": SHA,
        "browser_pid": 4101,
        "fixture_ref": relative_ref("fixture.json", "application/json"),
        "source_ref": relative_ref("source.mjs", "application/javascript"),
        "scenario_ids": scenarios,
        "scenario_count": 112,
        "scenarios": [scenario_evidence(scenario_id) for scenario_id in scenarios],
        "false_locks": false_locks(),
        "capture_sha256": SHA_B,
    }


def performance_result():
    return {
        "schema": "kronos_v5_performance_result.v1",
        "capture_kind": "synthetic_fixture_evidence",
        "live_browser_execution": False,
        "nonce": SHA,
        "fixture_sha256": SHA_B,
        "source_sha256": SHA_C,
        "measurement_sha256": SHA,
        "sample_contract": {
            "cold_contexts": 5,
            "warm_samples_after_discarded_warmup": 10,
            "endpoint_calls_after_discarded_warmup": 10,
            "percentile": "nearest-rank-p95",
        },
        "budgets_ms": dict(BUDGETS_MS),
        "p95_ms": dict(BUDGETS_MS),
        "retry_visible": True,
        "status": "passed",
        "result_sha256": SHA_B,
    }


def security_result():
    return {
        "schema": "kronos_v5_security_result.v1",
        "capture_kind": "synthetic_fixture_evidence",
        "live_browser_execution": False,
        "nonce": SHA,
        "fixture_ref": relative_ref("fixture.json", "application/json"),
        "source_ref": relative_ref("source.py", "text/x-python"),
        "probe_sha256": SHA_B,
        "allowed_downloads": 1,
        "denied_downloads": 1,
        "denied_probe_kinds": ["oos", "reparse", "traversal"],
        "v5_mutation_methods_rejected": ["DELETE", "PATCH", "POST", "PUT"],
        "status": "passed",
        "false_locks": false_locks(),
        "result_sha256": SHA_C,
    }


def manifest(schema):
    return {
        "schema": schema,
        "entries": [
            {
                "path": "webui/v2_src/src/app.js",
                "sha256": SHA,
                "byte_length": 1,
                "gzip9_byte_length": 21,
                "browser_transfer_byte_length": 21,
            }
        ],
        "manifest_sha256": SHA_B,
        "raw_byte_length": 1,
        "gzip9_byte_length": 21,
        "browser_transfer_byte_length": 21,
    }


def machine_task_score():
    return {
        "schema": "kronos_machine_task_score.v2",
        "operator_index": "A",
        "bitmaps": {"U": [True] * 10, "L": [True] * 10, "J": [True] * 10},
    }


def baseline_receipt():
    return {
        "schema": "kronos_qa_baseline_receipt.v1",
        "kind": "SYNTHETIC_ENGINEERING_BASELINE",
        "six_locks_false": false_locks(),
        "frozen_hashes": {
            "producer_sha256": SHA,
            "schema_sha256": SHA_B,
            "instrument_sha256": SHA_C,
            "fixture_sha256": SHA,
        },
        "manifest_sha256": {"source": SHA, "bundle": SHA_B, "dist": SHA_C},
        "evidence_refs": [uri_ref("kronos_synthetic_screenshot.v1", "baseline/synthetic-screenshot")],
        "evidence_locations": {
            "screenshot": "D:/Temp/kronos/evidence/synthetic-baseline.png",
            "metadata": "D:/Temp/kronos/evidence/synthetic-screenshot.json",
        },
        "status": "SYNTHETIC_NOT_GO",
        "receipt_ref": uri_ref("kronos_qa_baseline_receipt.v1", "baseline/receipt"),
        "receipt_location": "D:/Temp/kronos/evidence/baseline-receipt.json",
    }


def positive_payload(name):
    if name == "fixtureDescriptor":
        return fixture_descriptor()
    if name == "screenshotArtifact":
        return screenshot_artifact()
    if name == "transcriptArtifact":
        return transcript_artifact()
    if name == "captureArtifact":
        return capture_artifact()
    if name == "performanceResult":
        return performance_result()
    if name == "securityResult":
        return security_result()
    if name == "bundleManifest":
        return manifest("kronos_bundle_manifest.v1")
    if name == "sourceManifest":
        return manifest("kronos_source_manifest.v1")
    if name == "distManifest":
        return manifest("kronos_dist_manifest.v1")
    if name == "machineTaskScore":
        return machine_task_score()
    if name == "baselineReceipt":
        return baseline_receipt()
    raise AssertionError(name)


def test_qa_schema_parses_once_and_draft202012_check_schema_passes():
    jsonschema = pytest.importorskip("jsonschema")
    schema = load_schema_once()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert [item["$ref"].rsplit("/", 1)[1] for item in schema["oneOf"]] == list(BRANCHES)


def test_qa_schema_oneof_branches_are_closed_and_named_contracts():
    schema = load_schema_once()
    for name in BRANCHES:
        definition = schema["$defs"][name]
        assert definition["type"] == "object"
        assert definition["additionalProperties"] is False
        assert "schema" in definition["required"]
        assert definition["properties"]["schema"] == {"const": SCHEMA_CONSTS[name]}


def test_instrument_freezes_fixture_task_and_score_contract():
    instrument = load(INSTRUMENT)
    assert instrument["fixture"] == {
        "uid": "018f0000-0000-7000-8000-000000000001",
        "clock": "2026-07-14T09:00:00+09:00",
        "last_advance_at": "2026-07-14T08:59:30+09:00",
        "age_seconds": 30,
        "locale": "ko-KR",
        "fresh_profile_per_attempt": True,
    }
    assert [task["id"] for task in instrument["tasks"]] == [f"T{i:02d}" for i in range(1, 11)]
    assert all(task["viewport"]["theme"] == "light" for task in instrument["tasks"][:8])
    assert all(task["viewport"] == {"width": 375, "height": 812, "theme": "dark", "keyboard_only": True} for task in instrument["tasks"][8:])
    assert instrument["timing"] == {"task_timeout_seconds": 60, "corpus_timeout_seconds": 600}
    assert instrument["action_counting"] == {"back": True, "navigation": True, "wrong_selection": True, "scrolling": False}
    assert instrument["objective_failure_codes"] == [
        "TIMEOUT",
        "WRONG_RUN",
        "SOURCE_INSPECTION",
        "PRODUCER_HELP",
        "ACTION_LIMIT",
        "MISSING_TRACE",
        "INVALID_ASSIGNMENT",
        "RELOAD_NOT_REQUESTED",
        "OBJECTIVE_MISMATCH",
    ]
    assert instrument["score_rule"] == {
        "bits_per_dimension": 10,
        "points_per_true_bit": 10,
        "minimum_per_operator_dimension": 90,
        "aggregate": "COMPONENTWISE_MINIMUM",
    }
    for dimension in ("U", "L", "J"):
        assert len(instrument["ten_bit_facts"][dimension]) == 10
    assert instrument["claims"] == {"synthetic_engineering_evidence_only": True, "oos_consumed": False, "live_profit_readiness": False}


def test_browser_matrix_is_exact_unique_and_aggregated():
    matrix = load(MATRIX)
    scenarios = matrix["scenarios"]
    assert matrix["scenario_count"] == len(scenarios) == len(set(scenarios)) == 112
    groups = {"BASE": 72, "LIFE": 18, "GOV": 10, "ASYNC": 8, "KBD": 4}
    for group, count in groups.items():
        assert sum(item.startswith(f"S-{group}-") for item in scenarios) == count
    assert matrix["mobile_keyboard_only"] == ["S-KBD-mission-control", "S-KBD-rl", "S-KBD-daily-ohlcv", "S-KBD-live-training"]
    assert matrix["aggregators"]["E2.R"] == "ALL_112_PLUS_PERFORMANCE"
    assert matrix["prohibited_claims"] == ["OOS_CONSUMED", "LIVE_READY", "PROFIT_READY", "GO_READY"]


def test_schema_preserves_exact_112_scenario_grammar():
    jsonschema = pytest.importorskip("jsonschema")
    schema = load_schema_once()
    scenario_validator = jsonschema.Draft202012Validator(schema["$defs"]["scenarioId"])
    scenarios = load(MATRIX)["scenarios"]
    assert len(scenarios) == 112
    for scenario_id in scenarios:
        scenario_validator.validate(scenario_id)
    for invalid in (
        "BASE-HOME-LIGHT-375",
        "S-BASE-mission-control-light-1672",
        "S-BASE-unknown-light-375",
        "S-GOV-D0_BLOCKED-DESKTOP",
        "S-KBD-settings",
    ):
        with pytest.raises(jsonschema.ValidationError):
            scenario_validator.validate(invalid)


def frozen_schema_ids(definition):
    return [item["const"] for item in definition["prefixItems"]]


def frozen_row_ids(definition):
    return [item["allOf"][1]["properties"]["scenario_id"]["const"] for item in definition["prefixItems"]]


def test_capture_schema_freezes_exact_matrix_scenario_ids_and_rows():
    schema = load_schema_once()
    matrix = load(MATRIX)
    scenarios = matrix["scenarios"]
    evidence = schema["$defs"]["scenarioEvidence"]
    capture = schema["$defs"]["captureArtifact"]["properties"]

    assert matrix["capture_requirements"].count("network_errors") == 1
    assert "request_errors" not in matrix["capture_requirements"]
    assert "network_errors" in evidence["required"]
    assert "network_errors" in evidence["properties"]
    assert "request_errors" not in evidence["required"]
    assert "request_errors" not in evidence["properties"]
    assert capture["scenario_ids"] == {"$ref": "#/$defs/frozenScenarioIds"}
    assert capture["scenarios"] == {"$ref": "#/$defs/frozenScenarioEvidenceRows"}
    assert frozen_schema_ids(schema["$defs"]["frozenScenarioIds"]) == scenarios
    assert frozen_row_ids(schema["$defs"]["frozenScenarioEvidenceRows"]) == scenarios


@pytest.mark.parametrize("name", BRANCHES)
def test_schema_accepts_positive_producer_contracts(name):
    _, validator = schema_validator()
    validator.validate(positive_payload(name))


@pytest.mark.parametrize("name", BRANCHES)
def test_schema_rejects_unknown_fields_for_every_oneof_branch(name):
    jsonschema, validator = schema_validator()
    payload = positive_payload(name)
    payload["unknown"] = True
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)


CARDINALITY_CASES = (
    "capture-scenario-id-count",
    "capture-scenario-count",
    "capture-duplicate-scenario-id",
    "capture-scenario-id-reordered",
    "capture-row-id-duplicate",
    "capture-row-id-reordered",
    "capture-row-id-mismatched",
    "manifest-empty-entries",
    "machine-short-bitmap",
    "security-missing-denied-probe-kind",
    "security-missing-mutation-method",
    "performance-missing-p95-key",
    "baseline-empty-evidence-refs",
)


def cardinality_payload(case):
    if case == "capture-scenario-id-count":
        payload = capture_artifact()
        payload["scenario_ids"].pop()
        return payload
    if case == "capture-scenario-count":
        payload = capture_artifact()
        payload["scenarios"].pop()
        return payload
    if case == "capture-duplicate-scenario-id":
        payload = capture_artifact()
        payload["scenario_ids"][-1] = payload["scenario_ids"][0]
        return payload
    if case == "capture-scenario-id-reordered":
        payload = capture_artifact()
        payload["scenario_ids"][0], payload["scenario_ids"][1] = payload["scenario_ids"][1], payload["scenario_ids"][0]
        return payload
    if case == "capture-row-id-duplicate":
        payload = capture_artifact()
        payload["scenarios"][-1]["scenario_id"] = payload["scenarios"][0]["scenario_id"]
        return payload
    if case == "capture-row-id-reordered":
        payload = capture_artifact()
        payload["scenarios"][0], payload["scenarios"][1] = payload["scenarios"][1], payload["scenarios"][0]
        return payload
    if case == "capture-row-id-mismatched":
        payload = capture_artifact()
        payload["scenarios"][0]["scenario_id"] = payload["scenario_ids"][1]
        return payload
    if case == "manifest-empty-entries":
        payload = manifest("kronos_bundle_manifest.v1")
        payload["entries"] = []
        return payload
    if case == "machine-short-bitmap":
        payload = machine_task_score()
        payload["bitmaps"]["U"].pop()
        return payload
    if case == "security-missing-denied-probe-kind":
        payload = security_result()
        payload["denied_probe_kinds"].pop()
        return payload
    if case == "security-missing-mutation-method":
        payload = security_result()
        payload["v5_mutation_methods_rejected"].pop()
        return payload
    if case == "performance-missing-p95-key":
        payload = performance_result()
        payload["p95_ms"].pop("palette_ms")
        return payload
    if case == "baseline-empty-evidence-refs":
        payload = baseline_receipt()
        payload["evidence_refs"] = []
        return payload
    raise AssertionError(case)


@pytest.mark.parametrize("case", CARDINALITY_CASES)
def test_schema_rejects_cardinality_violations(case):
    jsonschema, validator = schema_validator()
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(cardinality_payload(case))


TAMPER_CASES = (
    "old-fixture-schema-name",
    "old-manifest-schema-name",
    "old-machine-score-schema-name",
    "invalid-scenario-id",
    "capture-old-request-error-key",
    "manifest-path-traversal",
    "relative-ref-extra-field",
    "performance-budget-exceeded",
    "security-false-lock-true",
    "baseline-go-status",
)


def tampered_payload(case):
    if case == "old-fixture-schema-name":
        payload = fixture_descriptor()
        payload["schema"] = "kronos_qa_fixture_descriptor.v1"
        return payload
    if case == "old-manifest-schema-name":
        payload = manifest("kronos_bundle_manifest.v1")
        payload["schema"] = "kronos_qa_bundle_manifest.v1"
        return payload
    if case == "old-machine-score-schema-name":
        payload = machine_task_score()
        payload["schema"] = "kronos_machine_task_score.v1"
        return payload
    if case == "invalid-scenario-id":
        payload = screenshot_artifact()
        payload["scenario_id"] = "S-BASE-mission-control-light-1672"
        return payload
    if case == "capture-old-request-error-key":
        payload = capture_artifact()
        payload["scenarios"][0]["request_errors"] = payload["scenarios"][0].pop("network_errors")
        return payload
    if case == "manifest-path-traversal":
        payload = manifest("kronos_bundle_manifest.v1")
        payload["entries"][0]["path"] = "../escape.js"
        return payload
    if case == "relative-ref-extra-field":
        payload = capture_artifact()
        payload["scenarios"][0]["screenshot_ref"]["unexpected"] = True
        return payload
    if case == "performance-budget-exceeded":
        payload = performance_result()
        payload["p95_ms"]["palette_ms"] = 101
        return payload
    if case == "security-false-lock-true":
        payload = security_result()
        payload["false_locks"]["promotion_allowed"] = True
        return payload
    if case == "baseline-go-status":
        payload = baseline_receipt()
        payload["status"] = "GO_READY"
        return payload
    raise AssertionError(case)


@pytest.mark.parametrize("case", TAMPER_CASES)
def test_schema_rejects_tampered_contracts(case):
    jsonschema, validator = schema_validator()
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(tampered_payload(case))

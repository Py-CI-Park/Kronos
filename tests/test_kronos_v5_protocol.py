"""Immutable synthetic protocol tests for the V5 daily Portfolio SB3 foundation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import stom_rl.daily_portfolio_sb3_protocol as protocol


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_daily_sb3_protocol.v1.schema.json"
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_daily_sb3_protocol_fixture.json").read_text(encoding="utf-8"))
COMMAND_MANIFEST = json.loads((ROOT / "docs" / "kronos_dashboard_v5_runner_command_manifest_v1.json").read_text(encoding="utf-8"))


def test_protocol_schema_and_golden_identity_are_deterministic() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    built = protocol.build_protocol()
    Draft202012Validator(schema).validate(built)
    protocol.validate_protocol(built)

    assert protocol.fixture_summary(built) == FIXTURE
    assert protocol.build_protocol() == built
    assert protocol.canonical_bytes(built) == protocol.canonical_bytes(protocol.build_protocol())
    assert protocol.sha256_hex(protocol.canonical_bytes(built)) == FIXTURE["canonical_protocol_sha256"]
    assert built["statement"]["closed_metadata"]["semantic_runtime_validator_required"] is True
    assert built["statement"]["closed_metadata"]["validates_dependency_paths_sha256_byte_length"] is True
    assert [dependency["name"] for dependency in built["statement"]["dependencies"]] == [
        "kronos_v5_daily_accounting_adr",
        "stom_daily_sb3_prior_stop_result",
        "kronos_research_runbook",
    ]
    for dependency in built["statement"]["dependencies"]:
        raw = (ROOT / dependency["uri"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == dependency["sha256"]
        assert len(raw) == dependency["byte_length"]
    assert len(protocol.canonical_bytes(built)) == FIXTURE["canonical_protocol_byte_length"]


def test_matrix_dimensions_order_costs_and_identities_are_exact() -> None:
    built = protocol.build_protocol()
    cells = built["matrix"]["cells"]
    expected_order = [
        (seed["seed_id"], fold_id, variant_id)
        for seed in protocol.SEEDS
        for fold_id in protocol.FOLD_IDS
        for variant_id in protocol.VARIANT_IDS
    ]

    assert built["statement"]["matrix_dimensions"] == {"seed_count": 5, "fold_count": 2, "variant_count": 5, "cell_count": 50, "order": "seed-major/fold/variant"}
    assert tuple((cell["seed_id"], cell["fold_id"], cell["variant_id"]) for cell in cells) == tuple(expected_order)
    assert [cell["ordinal"] for cell in cells] == list(range(1, 51))
    assert len({cell["cell_uid"] for cell in cells}) == 50
    assert len({cell["attempt_uid"] for cell in cells}) == 50
    assert cells[0]["cell_uid"] == FIXTURE["first_cell_uid"]
    assert cells[0]["attempt_uid"] == FIXTURE["first_attempt_uid"]
    assert cells[-1]["cell_uid"] == FIXTURE["last_cell_uid"]
    assert cells[-1]["attempt_uid"] == FIXTURE["last_attempt_uid"]

    variant_costs = {variant["variant_id"]: variant["evaluation_cost_bps"] for variant in built["statement"]["variants"]}
    assert variant_costs == {"baseline": 23, "cost-00bp": 0, "cost-23bp": 23, "cost-46bp": 46, "no-trade": 23}
    assert built["statement"]["cost_model"]["evaluation_costs_bps"] == [0, 23, 46]
    assert {cell["evaluation_cost_bps"] for cell in cells} == {0, 23, 46}
    assert all(cell["compute_mode"] == protocol.SYNTHETIC_COMPUTE_MODE for cell in cells)
    assert all(cell["heavy_compute_allowed"] is False and cell["fresh_oos_access_allowed"] is False for cell in cells)


def test_exact_fold_date_lists_purge_embargo_and_historical_secondary_window() -> None:
    statement = protocol.build_protocol()["statement"]
    folds = {fold["fold_id"]: fold for fold in statement["calendar"]["folds"]}
    historical = statement["calendar"]["historical_secondary_only_window"]

    assert folds["fold-01"]["train_sessions"] == list(protocol.FOLD1_TRAIN_SESSIONS)
    assert folds["fold-01"]["purge_embargo_sessions"] == list(protocol.FOLD1_PURGE_EMBARGO_SESSIONS)
    assert folds["fold-01"]["validation_sessions"] == list(protocol.FOLD1_VALIDATION_SESSIONS)
    assert folds["fold-02"]["train_sessions"] == list(protocol.TRAIN_SESSIONS)
    assert folds["fold-02"]["purge_embargo_sessions"] == list(protocol.FOLD2_PURGE_EMBARGO_SESSIONS)
    assert folds["fold-02"]["validation_sessions"] == list(protocol.VALIDATION_SESSIONS)
    assert historical["sessions"] == list(protocol.HISTORICAL_SECONDARY_ONLY_SESSIONS)
    assert historical["pre_access_purge_embargo_sessions"] == list(protocol.HISTORICAL_PURGE_EMBARGO_SESSIONS)

    assert FIXTURE["fold_session_counts"] == {
        "fold-01": {"train": 104, "purge_embargo": 5, "validation": 47},
        "fold-02": {"train": 156, "purge_embargo": 5, "validation": 47},
    }
    assert statement["calendar"]["available_session_count"] == 260
    assert historical["usage"] == "SECONDARY_DIAGNOSTIC_ONLY_NOT_MODEL_SELECTION_NOT_PROMOTION"
    assert historical["fresh_oos_access_allowed"] is False
    assert historical["model_go_source"] is False
    assert max(folds["fold-01"]["train_sessions"]) < min(folds["fold-01"]["purge_embargo_sessions"]) < min(folds["fold-01"]["validation_sessions"])
    assert max(folds["fold-02"]["train_sessions"]) < min(folds["fold-02"]["purge_embargo_sessions"]) < min(folds["fold-02"]["validation_sessions"])
    assert max(folds["fold-02"]["validation_sessions"]) < min(historical["pre_access_purge_embargo_sessions"]) < min(historical["sessions"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"available_sessions": list(protocol.ALL_REQUIRED_SESSIONS)[1:]},
        {"available_sessions": [*protocol.ALL_REQUIRED_SESSIONS, "2026-06-15"]},
        {"label_fit_max_by_fold": {"fold-01": "2026-01-07", "fold-02": "2026-01-07"}},
        {"fresh_oos_access_requested": True},
        {"historical_window_usage": "PRIMARY_MODEL_SELECTION"},
        {"compute_mode": "train"},
        {"ppo_config": {**protocol.DEFAULT_PPO_CONFIG, "total_timesteps_per_seed_fold": 200_001}},
        {"feature_normalization": {**protocol.DEFAULT_FEATURE_NORMALIZATION, "fit_scope": "all_sessions"}},
    ],
)
def test_builder_rejects_missing_sessions_leakage_oos_access_and_compute_drift(kwargs: dict) -> None:
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.build_protocol(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"variants": ("baseline", "base_23bp", "cost-23bp", "cost-46bp", "no-trade")},
        {"variants": ("baseline", "cost-00bp", "cost-23bp", "cost-46bp")},
        {"variants": ("baseline", "cost-00bp", "cost-23bp", "cost-46bp", "cost-46bp")},
        {"candidate_codes": ["250"]},
        {"candidate_codes": [250]},
        {"dependency_refs": [{**protocol.DEFAULT_DEPENDENCIES[0], "sha256": "A" * 64}, *protocol.DEFAULT_DEPENDENCIES[1:]]},
        {"dependency_refs": [{**protocol.DEFAULT_DEPENDENCIES[0], "sha256": "0" * 64}, *protocol.DEFAULT_DEPENDENCIES[1:]]},
        {"dependency_refs": [{**protocol.DEFAULT_DEPENDENCIES[0], "byte_length": protocol.DEFAULT_DEPENDENCIES[0]["byte_length"] + 1}, *protocol.DEFAULT_DEPENDENCIES[1:]]},
    ],
)
def test_builder_rejects_alias_variants_noncanonical_codes_hashes_and_dependency_drift(kwargs: dict) -> None:
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.build_protocol(**kwargs)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["identity"].__setitem__("protocol_sha256", "0" * 64),
        lambda payload: payload["matrix"]["cells"].pop(),
        lambda payload: payload["matrix"]["cells"][0].__setitem__("cell_uid", "kdp1-cell-" + "0" * 32),
        lambda payload: payload["matrix"]["cells"][0].__setitem__("attempt_uid", "kdp1-attempt-" + "0" * 32),
        lambda payload: payload["statement"]["variant_order"].reverse(),
        lambda payload: payload["statement"]["research_boundary"].__setitem__("training_allowed", True),
    ],
)
def test_protocol_validation_rejects_tamper_and_cardinality_changes(mutate) -> None:
    payload = deepcopy(protocol.build_protocol())
    mutate(payload)

    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.validate_protocol(payload)


def test_frozen_command_manifest_is_synthetic_verification_only() -> None:
    protocol.validate_command_manifest(COMMAND_MANIFEST)

    bad_train = deepcopy(COMMAND_MANIFEST)
    bad_train["commands"][0]["may_train"] = True
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.validate_command_manifest(bad_train)

    bad_argv = deepcopy(COMMAND_MANIFEST)
    bad_argv["commands"][0]["argv"].append("--train")
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.validate_command_manifest(bad_argv)

    bad_hash = deepcopy(COMMAND_MANIFEST)
    bad_hash["protocol_sha256"] = "0" * 64
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.validate_command_manifest(bad_hash)
    bad_receipt_command = deepcopy(COMMAND_MANIFEST)
    bad_receipt_command["pass_receipt_commands"][0]["command_id"] = "arbitrary"
    with pytest.raises(protocol.DailySb3ProtocolError):
        protocol.validate_command_manifest(bad_receipt_command)

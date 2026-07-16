"""Synthetic preregistration freeze tests for Kronos V5 daily Portfolio SB3."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import stom_rl.daily_portfolio_sb3_prereg as prereg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_daily_sb3_prereg.v1.schema.json"
PREREG_PATH = ROOT / "docs" / "stom_daily_sb3_ppo_v5_prereg_2026-07-14.json"


def _authority_freeze() -> tuple[dict, tuple[dict, ...], dict]:
    draft = prereg.build_prereg_draft()
    receipts = prereg.build_synthetic_test_receipts(draft)
    frozen = prereg.freeze_prereg(draft, receipts)
    return draft, receipts, frozen


def _rehash_receipt(receipt: dict) -> None:
    receipt["receipt_sha256"] = prereg.sha256_hex({key: receipt[key] for key in prereg._RECEIPT_BODY_KEYS})


def test_valid_synthetic_prereg_freezes_deterministically_without_compute() -> None:
    draft, receipts, frozen = _authority_freeze()
    prereg.validate_prereg(draft)
    prereg.validate_prereg(frozen)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(draft)
    Draft202012Validator(schema).validate(frozen)

    stored = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    prereg.validate_prereg(stored)
    Draft202012Validator(schema).validate(stored)

    assert stored == frozen
    assert prereg.freeze_prereg(draft, receipts) == frozen
    assert frozen["state"] == prereg.FROZEN_STATE
    assert frozen["statement"]["ppo_binding"]["full_ppo_status"] == "NOT_RUN"
    assert frozen["statement"]["historical_binding"]["status"] == "NOT_RUN"
    assert frozen["statement"]["no_heavy_compute_state"]["fresh_oos_status"] == "NOT_RUN"
    compute_locks = frozen["statement"]["no_heavy_compute_state"]["compute_locks"]
    promotion_locks = frozen["statement"]["no_heavy_compute_state"]["promotion_locks"]
    assert tuple(compute_locks) == prereg.COMPUTE_LOCK_NAMES
    assert tuple(promotion_locks) == prereg.PROMOTION_LOCK_NAMES
    assert len(compute_locks) == 3
    assert len(promotion_locks) == 6
    assert set(compute_locks.values()) == {False}
    assert set(promotion_locks.values()) == {False}
    command_binding = frozen["statement"]["command_manifest_binding"]
    assert [receipt["component"] for receipt in frozen["freeze_receipts"]] == ["protocol", "runner", "evaluator"]
    assert all(receipt["status"] == "PASS" for receipt in frozen["freeze_receipts"])
    assert all(receipt["command_manifest_sha256"] == command_binding["sha256"] for receipt in frozen["freeze_receipts"])
    assert all(receipt["command"] == "NOT_RUN_SYNTHETIC_RECEIPT" for receipt in frozen["freeze_receipts"])
    assert all(receipt["not_run_synthetic_receipt"] is True for receipt in frozen["freeze_receipts"])
    assert all(receipt["heavy_compute_run"] is False and receipt["fresh_oos_accessed"] is False for receipt in frozen["freeze_receipts"])


def test_freeze_rejects_premature_missing_receipt_and_missing_session() -> None:
    draft, receipts, _ = _authority_freeze()

    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, ())

    failed_receipt = deepcopy(receipts)
    failed_receipt[0]["status"] = "FAIL"
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, failed_receipt)

    missing_session = deepcopy(receipts)
    del missing_session[1]["session_id"]
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, missing_session)

    premature = deepcopy(draft)
    premature["state"] = prereg.FROZEN_STATE
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(premature, receipts)

    arbitrary_command = deepcopy(receipts)
    arbitrary_command[0]["approved_command_id"] = "arbitrary"
    _rehash_receipt(arbitrary_command[0])
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, arbitrary_command)


def test_frozen_hash_and_receipt_hash_drift_reject() -> None:
    _, _, frozen = _authority_freeze()

    bad_identity = deepcopy(frozen)
    bad_identity["identity"]["frozen_sha256"] = "0" * 64
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.validate_prereg(bad_identity)

    bad_receipt = deepcopy(frozen)
    bad_receipt["freeze_receipts"][0]["scope"] = "protocol_tampered_after_freeze"
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.validate_prereg(bad_receipt)

    bad_statement_hash = deepcopy(frozen)
    bad_statement_hash["statement"]["bound_hashes"]["protocol_sha256"] = "0" * 64
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.validate_prereg(bad_statement_hash)


def test_freeze_rejects_predated_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    draft, receipts, _ = _authority_freeze()

    monkeypatch.setattr(prereg, "FROZEN_AT", "2026-07-14T23:59:59Z")
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, receipts)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda draft: draft["statement"]["ppo_binding"].__setitem__("ppo_config_sha256", "0" * 64),
        lambda draft: draft["statement"]["session_binding"].__setitem__("fold_order", ["fold-02", "fold-01"]),
        lambda draft: draft["statement"]["matrix_binding"].__setitem__("cell_count", 49),
        lambda draft: draft["statement"]["bound_hashes"].__setitem__("matrix_cells_sha256", "0" * 64),
    ],
)
def test_freeze_rejects_altered_ppo_fold_and_matrix_bindings(mutate) -> None:
    draft, receipts, _ = _authority_freeze()
    mutate(draft)

    with pytest.raises(prereg.DailySb3PreregError):
        prereg.validate_prereg(draft)
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, receipts)


def test_freeze_rejects_oos_access_and_altered_run_state() -> None:
    draft, receipts, _ = _authority_freeze()

    bad_oos = deepcopy(receipts)
    bad_oos[2]["fresh_oos_accessed"] = True
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, bad_oos)

    bad_full_ppo = deepcopy(receipts)
    bad_full_ppo[1]["full_ppo_status"] = "RUN"
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.freeze_prereg(draft, bad_full_ppo)

    bad_draft_oos = deepcopy(draft)
    bad_draft_oos["statement"]["no_heavy_compute_state"]["compute_locks"]["fresh_oos_access_allowed"] = True
    with pytest.raises(prereg.DailySb3PreregError):
        prereg.validate_prereg(bad_draft_oos)

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.rl_discovery.d2_contract import D2ArmId, load_d2_prereg_bytes


PREREG = Path(__file__).resolve().parents[1] / "docs" / "kronos_rl_discovery_type2_d2_prereg_2026-07-28.json"


def test_d2_prereg_fixes_historical_scale_matrix_and_safety_boundary() -> None:
    prereg = load_d2_prereg_bytes(PREREG.read_bytes())

    assert prereg.episode_counts == (1, 8, 32, 128)
    assert tuple(arm.id for arm in prereg.arms) == tuple(D2ArmId)
    assert prereg.costs.training_round_trip_bp == 0
    assert prereg.costs.diagnostic_round_trip_bp == 23
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d2_prereg_rejects_open_fresh_oos_or_changed_scale() -> None:
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    payload["episode_counts"] = [1, 8, 64, 128]
    payload["claims_boundary"]["fresh_oos"] = "OPENED"

    with pytest.raises(ValidationError):
        load_d2_prereg_bytes(json.dumps(payload).encode())

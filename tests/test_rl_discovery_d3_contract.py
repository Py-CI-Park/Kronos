from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.rl_discovery.d3_contract import D3PolicyArmId, load_d3_prereg_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG = REPO_ROOT / "docs" / "kronos_rl_discovery_type2_d3_prereg_2026-07-29.json"


def test_d3_contract_parses_the_frozen_24_model_primary_matrix() -> None:
    # Given/When: the committed preregistration is parsed at the trust boundary.
    contract = load_d3_prereg_bytes(PREREG.read_bytes())

    # Then: the exact four-by-two-by-three matrix and sealed OOS boundary survive.
    assert tuple(arm.id for arm in contract.policy_arms) == tuple(D3PolicyArmId)
    assert len(contract.policy_arms) * len(contract.reward_arms) * len(contract.seeds) == 24
    assert contract.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d3_contract_rejects_a_post_registration_budget_change() -> None:
    # Given: one registered budget is changed after the preregistration commit.
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    payload["policy_arms"][3]["timesteps"] = 131072

    # When/Then: boundary parsing fails closed.
    with pytest.raises(ValidationError):
        load_d3_prereg_bytes(json.dumps(payload).encode())

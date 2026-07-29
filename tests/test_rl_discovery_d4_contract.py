from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, load_d4_prereg_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG = REPO_ROOT / "docs" / "kronos_rl_discovery_type2_d4_prereg_2026-07-29.json"


def test_d4_contract_separates_the_supervised_ceiling_from_three_rl_arms() -> None:
    # Given/When: the committed D4 preregistration crosses the typed boundary.
    contract = load_d4_prereg_bytes(PREREG.read_bytes())

    # Then: the exact 24-unit matrix and claim boundary remain frozen.
    assert tuple(arm.id for arm in contract.algorithm_arms) == tuple(D4AlgorithmArmId)
    assert len(contract.algorithm_arms) * len(contract.reward_arms) * len(contract.seeds) == 24
    assert contract.algorithm_arms[0].rl_claim_allowed is False
    assert contract.claims_boundary.supervised_is_not_rl is True
    assert contract.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d4_contract_rejects_turning_the_supervised_ceiling_into_rl() -> None:
    # Given: a post-registration mutation relabels the diagnostic as RL.
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    payload["algorithm_arms"][0]["rl_claim_allowed"] = True

    # When/Then: parsing fails closed.
    with pytest.raises(ValidationError):
        load_d4_prereg_bytes(json.dumps(payload).encode())

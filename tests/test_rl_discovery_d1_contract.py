from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from stom_rl.rl_discovery.d1_contract import D1ArmId, D1RewardKind, load_d1_prereg_bytes


def _payload() -> dict[str, object]:
    return {
        "schema_version": "kronos.rl-discovery.d1.prereg.v1",
        "status": "APPROVED_EXECUTABLE",
        "experiment_id": "TYPE2-D1-REWARD-ACTION",
        "primary_round_trip_cost_bp": 23,
        "hypothesis": "binary observed-candidate decoding reduces policy-head collapse",
        "claims_boundary": {
            "research_only": True,
            "profitability_claim_allowed": False,
            "fresh_oos": "NOT_RUN_NO_READ",
        },
        "arms": [
            {"id": "A_BINARY_NATIVE", "reward": "NATIVE_ECONOMIC"},
            {"id": "B_BINARY_DIAGNOSTIC", "reward": "FIRST_DECISION_DIAGNOSTIC"},
            {"id": "C_BINARY_SHUFFLED", "reward": "SHUFFLED_NATIVE"},
        ],
        "seeds": [0, 1, 2],
        "training": {"smoke_timesteps": 256, "primary_timesteps": 2048, "smoke_seeds": [0]},
        "gate": {
            "native_min_reward_ratio": 0.75,
            "native_min_delta_vs_shuffled": 0.25,
            "diagnostic_min_initial_accuracy": 0.90,
            "max_dominant_initial_action_rate": 0.90,
        },
    }


def test_d1_prereg_parses_canonical_reward_action_contract() -> None:
    prereg = load_d1_prereg_bytes(json.dumps(_payload()).encode())

    assert tuple(arm.id for arm in prereg.arms) == tuple(D1ArmId)
    assert prereg.arms[0].reward is D1RewardKind.NATIVE_ECONOMIC
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


@pytest.mark.parametrize(
    ("field", "value"),
    [("fresh_oos", "OPENED"), ("profitability_claim_allowed", True)],
)
def test_d1_prereg_rejects_unsafe_claim_boundary(field: str, value: str | bool) -> None:
    payload = _payload()
    claims = payload["claims_boundary"]
    assert isinstance(claims, dict)
    claims[field] = value

    with pytest.raises(ValidationError):
        load_d1_prereg_bytes(json.dumps(payload).encode())


def test_d1_prereg_rejects_noncanonical_arm_order() -> None:
    payload = _payload()
    arms = payload["arms"]
    assert isinstance(arms, list)
    arms.reverse()

    with pytest.raises(ValidationError):
        load_d1_prereg_bytes(json.dumps(payload).encode())

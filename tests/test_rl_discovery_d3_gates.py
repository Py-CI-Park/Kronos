from __future__ import annotations

import pytest

from stom_rl.rl_discovery.d3_contract import D3GateContract, D3PolicyArmId, D3RewardArmId
from stom_rl.rl_discovery.d3_gates import D3Outcome, evaluate_d3_gate
from stom_rl.rl_discovery.d3_training import D3Metrics


def _metrics(ratio: float) -> D3Metrics:
    return D3Metrics(accuracy=ratio, reward_ratio=ratio, total_reward=ratio, oracle_reward=1.0, trade_rate=0.5, dominant_action_rate=0.5, invalid_action_count=0)


def test_d3_gate_confirms_only_a_representation_with_native_fit_and_control_separation() -> None:
    # Given: top-five context passes two seeds and its shuffled control reverses on native replay.
    outcomes = tuple(
        D3Outcome(
            policy_arm=arm,
            reward_arm=reward,
            seed=seed,
            fit=_metrics(0.95 if arm is D3PolicyArmId.TOP5_CONTEXT_1X else 0.5),
            native=_metrics(0.95 if reward is D3RewardArmId.NATIVE and arm is D3PolicyArmId.TOP5_CONTEXT_1X else 0.1),
            cost_23bp=_metrics(0.9),
        )
        for arm in D3PolicyArmId
        for reward in D3RewardArmId
        for seed in (0, 1, 2)
    )
    thresholds = D3GateContract(
        minimum_fit_accuracy=0.9,
        minimum_fit_reward_ratio=0.9,
        minimum_passing_seed_fraction=2 / 3,
        minimum_native_delta_vs_shuffled=0.2,
        zero_invalid_actions=True,
    )

    # When: the preregistered gate evaluates the complete matrix.
    result = evaluate_d3_gate(outcomes, thresholds=thresholds)

    # Then: exactly the causal top-five context arm is confirmed.
    assert result.verdict == "D3_REPRESENTATION_ACTION_CONFIRMED"
    assert result.confirmed_policy_arms == (D3PolicyArmId.TOP5_CONTEXT_1X,)
    assert result.fresh_oos == "NOT_RUN_NO_READ"


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_d3_gate_rejects_an_incomplete_or_duplicate_primary_matrix(mutation: str) -> None:
    # Given: otherwise-passing evidence whose frozen 24-unit identity is broken.
    outcomes = [
        D3Outcome(arm, reward, seed, _metrics(0.95), _metrics(0.95), _metrics(0.9))
        for arm in D3PolicyArmId
        for reward in D3RewardArmId
        for seed in (0, 1, 2)
    ]
    outcomes = outcomes[:-1] if mutation == "missing" else [*outcomes, outcomes[0]]
    thresholds = D3GateContract(
        minimum_fit_accuracy=0.9,
        minimum_fit_reward_ratio=0.9,
        minimum_passing_seed_fraction=2 / 3,
        minimum_native_delta_vs_shuffled=0.2,
        zero_invalid_actions=True,
    )

    # When/Then: partial or repeated evidence fails closed before scoring.
    with pytest.raises(ValueError, match="24-unit matrix"):
        evaluate_d3_gate(tuple(outcomes), thresholds=thresholds)

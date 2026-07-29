from __future__ import annotations

import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4GateContract, D4RewardArmId
from stom_rl.rl_discovery.d4_gates import D4GateEvidenceError, D4Outcome, evaluate_d4_gate


def _metrics(ratio: float) -> D3Metrics:
    return D3Metrics(ratio, ratio, ratio, 1.0, 0.5, 0.5, 0)


def _thresholds() -> D4GateContract:
    return D4GateContract(
        minimum_fit_accuracy=0.9,
        minimum_fit_reward_ratio=0.9,
        minimum_passing_seed_fraction=2 / 3,
        minimum_native_delta_vs_shuffled=0.2,
        maximum_rl_gap_to_supervised_ceiling=0.1,
        zero_invalid_actions=True,
    )


def test_d4_gate_reports_optimizer_failure_when_only_the_supervised_ceiling_passes() -> None:
    # Given: supervised native seeds fit, while every real RL arm remains below threshold.
    outcomes = tuple(
        D4Outcome(
            arm,
            reward,
            seed,
            _metrics(0.96 if arm is D4AlgorithmArmId.SUPERVISED_CEILING and reward is D4RewardArmId.NATIVE else 0.2),
            _metrics(0.96 if arm is D4AlgorithmArmId.SUPERVISED_CEILING and reward is D4RewardArmId.NATIVE else 0.1),
            _metrics(0.9),
        )
        for arm in D4AlgorithmArmId
        for reward in D4RewardArmId
        for seed in (0, 1, 2)
    )

    # When: the frozen D4 gate evaluates the complete matrix.
    result = evaluate_d4_gate(outcomes, thresholds=_thresholds())

    # Then: representation capacity is separated from RL confirmation.
    assert result.verdict == "D4_RL_OPTIMIZATION_NOT_CONFIRMED"
    assert result.supervised_ceiling_confirmed is True
    assert result.confirmed_rl_arms == ()
    assert result.promotion_allowed is False


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_d4_gate_rejects_an_incomplete_or_duplicate_24_unit_matrix(mutation: str) -> None:
    # Given: an otherwise valid matrix with one identity removed or repeated.
    outcomes = [
        D4Outcome(arm, reward, seed, _metrics(0.5), _metrics(0.5), _metrics(0.4))
        for arm in D4AlgorithmArmId
        for reward in D4RewardArmId
        for seed in (0, 1, 2)
    ]
    outcomes = outcomes[:-1] if mutation == "missing" else [*outcomes, outcomes[0]]

    # When/Then: scoring fails before averages can hide the broken evidence.
    with pytest.raises(D4GateEvidenceError, match="24-unit matrix"):
        evaluate_d4_gate(tuple(outcomes), thresholds=_thresholds())

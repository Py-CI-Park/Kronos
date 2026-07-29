import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_contract import D5GateContract
from stom_rl.rl_discovery.d5_gates import D5GateEvidenceError, D5Outcome, evaluate_d5_gate


def _metrics(value: float) -> D3Metrics:
    return D3Metrics(value, value, value, 1.0, .8, .3, 0)


def _gate() -> D5GateContract:
    return D5GateContract(minimum_fit_accuracy=.9, minimum_fit_reward_ratio=.9, minimum_passing_seed_fraction=.6, minimum_native_delta_vs_shuffled=.2, zero_invalid_actions=True)


def test_d5_gate_confirms_exact_cost_trained_control_matrix() -> None:
    outcomes = tuple(D5Outcome(reward, seed, _metrics(.95), _metrics(.95 if reward is D4RewardArmId.NATIVE else -.1), _metrics(.96)) for reward in D4RewardArmId for seed in range(5))
    result = evaluate_d5_gate(outcomes, thresholds=_gate())
    assert result.verdict == "D5_FULL_TRAIN_COST_CONFIRMED"
    assert result.promotion_allowed is False


def test_d5_gate_rejects_missing_unit() -> None:
    outcomes = tuple(D5Outcome(reward, seed, _metrics(.95), _metrics(.1), _metrics(.95)) for reward in D4RewardArmId for seed in range(5))
    with pytest.raises(D5GateEvidenceError):
        evaluate_d5_gate(outcomes[:-1], thresholds=_gate())

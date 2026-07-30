import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_contract import D5GateContract
from stom_rl.rl_discovery.d5_gates import D5GateEvidenceError, D5Outcome, evaluate_d5_gate


def _metrics(value: float, *, invalid: int = 0) -> D3Metrics:
    return D3Metrics(value, value, value, 1.0, .8, .3, invalid)


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


def test_d5_gate_accepts_exact_threshold_boundaries() -> None:
    outcomes = tuple(
        D5Outcome(
            reward,
            seed,
            _metrics(.9 if seed < 3 else .89),
            _metrics(.3 if reward is D4RewardArmId.NATIVE else .1),
            _metrics(.3),
        )
        for reward in D4RewardArmId
        for seed in range(5)
    )
    result = evaluate_d5_gate(outcomes, thresholds=_gate())
    assert result.verdict == "D5_FULL_TRAIN_COST_CONFIRMED"
    assert result.native_passing_seed_fraction == .6
    assert result.shuffled_passing_seed_fraction == .6
    assert result.native_delta_vs_shuffled == pytest.approx(.2)


@pytest.mark.parametrize("failed_reward", list(D4RewardArmId))
def test_d5_gate_rejects_each_reward_arm_seed_fraction(failed_reward: D4RewardArmId) -> None:
    outcomes = tuple(
        D5Outcome(
            reward,
            seed,
            _metrics(.95 if reward is not failed_reward or seed < 2 else .1),
            _metrics(.4 if reward is D4RewardArmId.NATIVE else .1),
            _metrics(.4),
        )
        for reward in D4RewardArmId
        for seed in range(5)
    )
    assert evaluate_d5_gate(outcomes, thresholds=_gate()).verdict == "D5_FULL_TRAIN_COST_NOT_CONFIRMED"


def test_d5_gate_rejects_insufficient_delta_and_invalid_actions() -> None:
    low_delta = tuple(
        D5Outcome(reward, seed, _metrics(.95), _metrics(.19), _metrics(.2))
        for reward in D4RewardArmId
        for seed in range(5)
    )
    invalid = tuple(
        D5Outcome(reward, seed, _metrics(.95, invalid=1), _metrics(.4), _metrics(.4))
        for reward in D4RewardArmId
        for seed in range(5)
    )
    assert evaluate_d5_gate(low_delta, thresholds=_gate()).verdict == "D5_FULL_TRAIN_COST_NOT_CONFIRMED"
    assert evaluate_d5_gate(invalid, thresholds=_gate()).verdict == "D5_FULL_TRAIN_COST_NOT_CONFIRMED"


def test_d5_gate_rejects_duplicate_unit() -> None:
    outcomes = tuple(
        D5Outcome(reward, seed, _metrics(.95), _metrics(.4), _metrics(.4))
        for reward in D4RewardArmId
        for seed in range(5)
    )
    with pytest.raises(D5GateEvidenceError, match="unique ten-unit"):
        evaluate_d5_gate((*outcomes[:-1], outcomes[0]), thresholds=_gate())

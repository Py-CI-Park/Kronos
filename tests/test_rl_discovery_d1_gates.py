from __future__ import annotations

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.d1_gates import D1Outcome, evaluate_d1_gate
from stom_rl.rl_discovery.gates import RunProfile


def _outcome(arm: D1ArmId, seed: int, ratio: float, accuracy: float) -> D1Outcome:
    return D1Outcome(
        arm=arm,
        seed=seed,
        training_timesteps=256,
        economic_reward_ratio=ratio,
        initial_decision_accuracy=accuracy,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_initial_action_rate=0.75,
    )


def _complete_outcomes(seeds: tuple[int, ...]) -> tuple[D1Outcome, ...]:
    return tuple(
        outcome
        for seed in seeds
        for outcome in (
            _outcome(D1ArmId.BINARY_NATIVE, seed, 0.90, 0.90),
            _outcome(D1ArmId.BINARY_DIAGNOSTIC, seed, 0.95, 0.98),
            _outcome(D1ArmId.BINARY_SHUFFLED, seed, 0.20, 0.25),
        )
    )


def test_d1_smoke_gate_passes_plumbing_but_never_confirms_hypothesis() -> None:
    result = evaluate_d1_gate(_complete_outcomes((0,)), profile=RunProfile.SMOKE)

    assert result.status == "SMOKE_COMPLETE"
    assert result.verdict == "SMOKE_INCOMPLETE"
    assert result.smoke_pass is True
    assert result.promotion_allowed is False


def test_d1_primary_confirms_only_complete_separated_noncollapsed_matrix() -> None:
    result = evaluate_d1_gate(_complete_outcomes((0, 1, 2)), profile=RunProfile.PRIMARY)

    assert result.status == "PRIMARY_COMPLETE"
    assert result.verdict == "D1_ACTION_REWARD_CONFIRMED"
    assert result.fresh_oos == "NOT_RUN_NO_READ"


def test_d1_primary_fails_closed_when_one_arm_is_missing() -> None:
    incomplete = tuple(
        outcome
        for outcome in _complete_outcomes((0, 1, 2))
        if not (outcome.arm is D1ArmId.BINARY_SHUFFLED and outcome.seed == 2)
    )

    result = evaluate_d1_gate(incomplete, profile=RunProfile.PRIMARY)

    assert result.status == "PRIMARY_INCOMPLETE"
    assert result.verdict == "D1_ACTION_REWARD_NOT_CONFIRMED"

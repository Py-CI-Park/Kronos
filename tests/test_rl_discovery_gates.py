from __future__ import annotations

from stom_rl.rl_discovery import gates


def _outcome(arm: str, seed: int, ratio: float, *, shuffled: bool = False) -> gates.ArmOutcome:
    return gates.ArmOutcome(
        arm=arm,
        seed=seed,
        training_timesteps=256,
        oracle_reward_ratio=ratio,
        exact_basket_accuracy=ratio,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_action_rate=0.5,
        shuffled_reward=shuffled,
    )


def test_smoke_gate_never_promotes_an_overfit_result() -> None:
    # Given
    outcomes = (
        _outcome("A_PPO_ONLY", 0, 1.0),
        _outcome("B_BC_THEN_PPO", 0, 1.0),
        _outcome("C_BC_ONLY", 0, 1.0),
        _outcome("D_SHUFFLED_REWARD_PPO", 0, 0.0, shuffled=True),
    )

    # When
    result = gates.evaluate_discovery_gate(outcomes, profile="SMOKE")

    # Then
    assert result.status == "SMOKE_COMPLETE"
    assert result.verdict == "SMOKE_INCOMPLETE"
    assert result.promotion_allowed is False
    assert result.fresh_oos == "NOT_RUN_NO_READ"


def test_primary_gate_requires_every_ppo_seed_and_the_shuffled_control() -> None:
    # Given
    outcomes = tuple(
        [_outcome("A_PPO_ONLY", seed, 0.95) for seed in (0, 1, 2)]
        + [_outcome("D_SHUFFLED_REWARD_PPO", seed, 0.1, shuffled=True) for seed in (0, 1, 2)]
    )

    # When
    result = gates.evaluate_discovery_gate(outcomes, profile="PRIMARY")

    # Then
    assert result.verdict == "PPO_ONLY_OVERFIT_CONFIRMED"
    assert result.promotion_allowed is False
    assert result.profitability_claim_allowed is False

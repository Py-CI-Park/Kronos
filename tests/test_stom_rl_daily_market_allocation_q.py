from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from stom_rl.daily_close_research.offline_data import OfflineTransition
from stom_rl.daily_market_allocation_contract import AllocationAction
from stom_rl.daily_market_allocation_q import load_allocation_q, train_allocation_q
from stom_rl.daily_market_allocation_rl_contract import (
    AllocationAlgorithm,
    AllocationTrainingConfig,
)


def _known_four_action_transitions() -> tuple[OfflineTransition, ...]:
    rows: list[OfflineTransition] = []
    for sequence in range(800):
        signal = sequence % 4
        action = (sequence // 4) % 4
        state = (
            tuple(1.0 if index == signal else 0.0 for index in range(4)) + (0.0,) * 168
        )
        rows.append(
            OfflineTransition(
                sequence=sequence,
                state=state,
                action=action,
                reward=1.0 if action == signal else -1.0,
                next_state=(0.0,) * 172,
                done=True,
            )
        )
    return tuple(rows)


def _fast_config() -> AllocationTrainingConfig:
    return replace(
        AllocationTrainingConfig.registered(
            algorithm=AllocationAlgorithm.CQL,
            seed=23,
        ),
        hidden_dimensions=(32, 16),
        learning_rate=0.003,
        discount=0.0,
        cql_alpha=0.1,
        reward_scale=1.0,
        batch_size=64,
        gradient_steps=300,
        target_update_interval=20,
    )


def _observation(signal: int) -> tuple[float, ...]:
    return tuple(1.0 if index == signal else 0.0 for index in range(4)) + (0.0,) * 168


def test_cql_learns_and_restores_known_four_action_policy(tmp_path: Path) -> None:
    # Given: full behavior coverage for a known four-state/four-action reward function.
    checkpoint = tmp_path / "allocation-cql.kq"
    config = _fast_config()

    # When: CQL trains and the numeric-only checkpoint is restored.
    trained = train_allocation_q(
        _known_four_action_transitions(),
        config,
        checkpoint_path=checkpoint,
    )
    restored = load_allocation_q(checkpoint, config)

    # Then: both policies recover all four preregistered allocation actions.
    expected = tuple(AllocationAction(index) for index in range(4))
    assert (
        tuple(trained.policy.greedy_action(_observation(index)) for index in range(4))
        == expected
    )
    assert (
        tuple(restored.greedy_action(_observation(index)) for index in range(4))
        == expected
    )
    assert len(trained.losses) == 300
    assert trained.checkpoint_sha256 is not None

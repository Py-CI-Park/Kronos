from __future__ import annotations

from pathlib import Path

from stom_rl.daily_close_research.models import (
    OfflineAlgorithm,
    TrainingConfig,
    load_q_model,
    train_offline_q,
)
from stom_rl.daily_close_research.offline_data import synthetic_market_dataset


def test_cql_learns_the_known_signal_policy_and_round_trips_model_file(tmp_path: Path) -> None:
    transitions = synthetic_market_dataset(seed=7, episode_count=30, episode_length=20)
    output = tmp_path / "cql.pt"

    trained = train_offline_q(
        transitions,
        TrainingConfig.registered(algorithm=OfflineAlgorithm.CQL, seed=11, epochs=180),
        output=output,
    )
    restored = load_q_model(output)

    assert trained.model.action((-1.0, 0.0)) == 0
    assert trained.model.action((1.0, 0.0)) == 1
    assert restored.action((-1.0, 0.0)) == 0
    assert restored.action((1.0, 0.0)) == 1
    assert output.is_file()


def test_dqn_baseline_produces_finite_training_loss() -> None:
    transitions = synthetic_market_dataset(seed=5, episode_count=12, episode_length=15)

    trained = train_offline_q(
        transitions,
        TrainingConfig.registered(algorithm=OfflineAlgorithm.DQN, seed=3, epochs=40),
    )

    assert trained.losses
    assert all(loss >= 0 for loss in trained.losses)


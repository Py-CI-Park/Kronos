from __future__ import annotations

from decimal import Decimal

import pytest

from stom_rl.daily_market_rl_contract import (
    DailyMarketRlContractError,
    MarketAlgorithm,
    MarketTrainingConfig,
    base_cost_config,
    stress_cost_config,
)


def test_registered_cql_contract_matches_preregistered_actual_market_lane() -> None:
    # Given: the actual-market CQL algorithm and a registered seed.
    algorithm = MarketAlgorithm.CQL

    # When: the immutable training contract is constructed.
    config = MarketTrainingConfig.registered(algorithm=algorithm, seed=3)

    # Then: every preregistered optimization and state boundary is fixed.
    assert config.input_dimension == 172
    assert config.action_count == 2
    assert config.hidden_dimensions == (128, 64)
    assert config.learning_rate == 0.0003
    assert config.discount == 0.95
    assert config.cql_alpha == 1.0
    assert config.reward_scale == 100.0
    assert config.batch_size == 256
    assert config.gradient_steps == 600
    assert config.target_update_interval == 25
    assert config.behavior_trajectory_count == 32


def test_registered_dqn_disables_only_the_conservative_penalty() -> None:
    # Given: the DQN control algorithm.
    # When: its registered contract is constructed.
    config = MarketTrainingConfig.registered(algorithm=MarketAlgorithm.DQN, seed=0)

    # Then: it shares the lane contract but has no CQL penalty.
    assert config.cql_alpha == 0.0
    assert config.input_dimension == 172
    assert config.gradient_steps == 600


def test_every_registered_algorithm_has_an_explicit_conservative_penalty() -> None:
    # Given: the complete closed algorithm set.
    # When: every registered contract is constructed.
    penalties = {
        algorithm: MarketTrainingConfig.registered(algorithm=algorithm, seed=0).cql_alpha
        for algorithm in MarketAlgorithm
    }

    # Then: DQN is the only non-conservative arm and no new variant falls through.
    assert penalties == {
        MarketAlgorithm.DQN: 0.0,
        MarketAlgorithm.CQL: 1.0,
        MarketAlgorithm.CQL_REWARD_SHUFFLED: 1.0,
        MarketAlgorithm.CQL_ACTION_SHUFFLED: 1.0,
    }


def test_market_cost_scenarios_use_percent_first_kiwoom_assumptions() -> None:
    # Given: the two preregistered cost scenarios.
    # When: their transition configs are constructed.
    base = base_cost_config()
    stress = stress_cost_config()

    # Then: the common public unit is percent, not basis points.
    assert base.round_trip_cost_percent == Decimal("0.230")
    assert stress.round_trip_cost_percent == Decimal("0.460")


def test_training_contract_rejects_negative_seed_as_a_typed_error() -> None:
    # Given: an invalid negative model seed.
    # When / Then: contract construction fails before training starts.
    with pytest.raises(DailyMarketRlContractError, match="INVALID_MODEL_SEED"):
        _ = MarketTrainingConfig.registered(algorithm=MarketAlgorithm.CQL, seed=-1)

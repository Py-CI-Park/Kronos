import pytest

from stom_rl.etf_research.environment import MarketBar, PortfolioState, step_target_position
from stom_rl.etf_research.synthetic_gate import evaluate_synthetic_environment


def test_no_trade_keeps_flat_portfolio_unchanged() -> None:
    # Given: a cash-only portfolio and a flat market bar.
    state = PortfolioState.initial(1_000_000.0)

    # When: the target position remains zero.
    result = step_target_position(state, 0.0, MarketBar(open=100.0, close=100.0), one_way_cost_bps=11.5)

    # Then: there is no turnover, cost, or value change.
    assert result.turnover == 0.0
    assert result.transaction_cost == 0.0
    assert result.state.value == pytest.approx(1_000_000.0)
    assert result.state.position_ratio == 0.0


def test_flat_full_round_trip_charges_about_twenty_three_basis_points() -> None:
    # Given: a cash portfolio and two flat bars.
    state = PortfolioState.initial(1_000_000.0)
    bar = MarketBar(open=100.0, close=100.0)

    # When: the policy enters 100% and then returns to cash.
    entered = step_target_position(state, 1.0, bar, one_way_cost_bps=11.5)
    exited = step_target_position(entered.state, 0.0, bar, one_way_cost_bps=11.5)

    # Then: state transitions are real and the round-trip loss matches the cost contract.
    assert entered.state.units > 0
    assert entered.state.cash < state.cash
    assert exited.state.units == pytest.approx(0.0, abs=1e-8)
    loss_bps = (1.0 - exited.state.value / state.value) * 10_000.0
    assert loss_bps == pytest.approx(22.9868, abs=0.02)


def test_synthetic_environment_gate_passes_all_registered_seeds() -> None:
    # Given: a learnable state-dependent rising/falling synthetic market.
    # When: known policies are evaluated through the same accounting environment.
    receipt = evaluate_synthetic_environment((0, 1, 2))

    # Then: the action-dependent environment is learnable for every seed.
    assert receipt.verdict == "PASS_SYNTHETIC_STATEFUL_MDP"
    assert receipt.passed_seed_count == 3
    assert all(result.known_policy_value > result.always_long_value for result in receipt.results)
    assert all(result.known_policy_value > result.no_trade_value for result in receipt.results)


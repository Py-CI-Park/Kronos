from dataclasses import asdict
from decimal import Decimal, ROUND_DOWN, getcontext, setcontext

import pytest

from stom_rl.daily_type1_accounting import PortfolioState, SlotOutcome, settle_session
from stom_rl.daily_type1_contract import REWARD_QUANTUM, canonical_json_bytes


@pytest.mark.parametrize(
    ("gross_return", "cost_bp", "expected_delta"),
    [
        ("0.01", 0, Decimal("50000.00")),
        ("0", 23, Decimal("-11500.0000")),
        ("-0.01", 46, Decimal("-73000.0000")),
    ],
)
def test_filled_slot_uses_decimal_additive_cost_accounting(
    gross_return: str, cost_bp: int, expected_delta: Decimal
) -> None:
    result = settle_session(
        PortfolioState(), [SlotOutcome("000250", "FILLED", Decimal(gross_return))], cost_bp
    )
    assert result.outcomes[0].symbol == "000250"
    assert result.nav_delta == expected_delta
    assert result.state.nav == Decimal("60000000") + expected_delta
    assert result.cost_bp == Decimal(f"{cost_bp}.000000000000")
    assert result.reward == (result.nav_delta / Decimal("60000000")).quantize(REWARD_QUANTUM)


def test_no_trade_and_no_fill_do_not_change_nav_or_charge_cost() -> None:
    state = PortfolioState()
    no_trade = settle_session(state, [], 23)
    no_fill = settle_session(state, [SlotOutcome("000250", "NO_FILL")], 46)
    assert no_trade.nav_delta == no_fill.nav_delta == Decimal("0")
    assert no_trade.state == no_fill.state == state
    assert no_fill.filled_slots == 0
    assert no_fill.no_fill_slots == 1


def test_ten_slots_and_cost_monotonicity() -> None:
    outcomes = tuple(SlotOutcome(f"{index:06d}", "FILLED", Decimal("0.01")) for index in range(10))
    zero = settle_session(PortfolioState(), outcomes, 0)
    base = settle_session(PortfolioState(), outcomes, 23)
    stress = settle_session(PortfolioState(), outcomes, 46)
    assert zero.nav_delta > base.nav_delta > stress.nav_delta
    assert base.filled_slots == 10


def test_high_water_and_drawdown_are_updated_exactly() -> None:
    gain = settle_session(PortfolioState(), [SlotOutcome("000250", "FILLED", Decimal("0.01"))], 0)
    loss = settle_session(gain.state, [SlotOutcome("000251", "FILLED", Decimal("-0.02"))], 0)
    assert loss.state.high_water_nav == gain.state.nav
    assert loss.drawdown == Decimal("0.001665278934")


def test_fixed_notional_research_nav_may_fall_below_zero() -> None:
    state = PortfolioState(nav=Decimal("1000"), high_water_nav=Decimal("60000000"))
    loss = settle_session(state, [SlotOutcome("000250", "FILLED", Decimal("-0.01"))], 46)
    assert loss.state.nav == Decimal("-72000.000000")
    assert loss.drawdown == Decimal("1.001200000000")


@pytest.mark.parametrize("cost_bp", [-1, 1, 22, 24, 47, "NaN", float("nan")])
def test_invalid_costs_fail_closed(cost_bp: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        settle_session(PortfolioState(), [], cost_bp)  # type: ignore[arg-type]
@pytest.mark.parametrize(
    ("nav", "high_water_nav"),
    [
        (Decimal("1"), Decimal("0")),
        (Decimal("2"), Decimal("1")),
        (Decimal("NaN"), Decimal("60000000")),
        (1.0, Decimal("60000000")),
        (Decimal("1"), float("inf")),
    ],
)
def test_portfolio_state_invariants_and_numeric_types_fail_closed(
    nav: object, high_water_nav: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        PortfolioState(nav=nav, high_water_nav=high_water_nav)  # type: ignore[arg-type]


def test_settlement_state_and_outcome_container_types_fail_closed() -> None:
    with pytest.raises(TypeError, match="PortfolioState"):
        settle_session(object(), [])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="iterable"):
        settle_session(PortfolioState(), object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="SlotOutcome"):
        settle_session(PortfolioState(), [object()])  # type: ignore[list-item]


@pytest.mark.parametrize("outcomes", [
    [SlotOutcome("000250", "FILLED"), SlotOutcome("000250", "NO_FILL")],
    [SlotOutcome(f"{index:06d}", "FILLED") for index in range(11)],
])
def test_duplicate_symbols_and_too_many_slots_fail_closed(outcomes: list[SlotOutcome]) -> None:
    with pytest.raises(ValueError):
        settle_session(PortfolioState(), outcomes)


@pytest.mark.parametrize("kwargs", [
    {"symbol": 250, "status": "FILLED"},
    {"symbol": "250", "status": "FILLED"},
    {"symbol": "000250", "status": "MAYBE"},
    {"symbol": "000250", "status": "NO_FILL", "gross_return": Decimal("0.01")},
    {"symbol": "000250", "status": "FILLED", "gross_return": Decimal("NaN")},
])
def test_malformed_slot_values_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        SlotOutcome(**kwargs)  # type: ignore[arg-type]


def test_quantization_uses_half_even_at_q6_and_q12_boundaries() -> None:
    assert SlotOutcome("000250", "FILLED", Decimal("0.0000000000005")).gross_return == Decimal(
        "0.000000000000"
    )
    assert SlotOutcome("000251", "FILLED", Decimal("0.0000000000015")).gross_return == Decimal(
        "0.000000000002"
    )
    assert PortfolioState(nav=Decimal("1.0000005"), high_water_nav=Decimal("60000000")).nav == Decimal(
        "1.000000"
    )
    assert PortfolioState(nav=Decimal("1.0000015"), high_water_nav=Decimal("60000000")).nav == Decimal(
        "1.000002"
    )


def test_settlement_is_byte_identical_under_mutated_global_decimal_context() -> None:
    def settle_bytes() -> bytes:
        result = settle_session(
            PortfolioState(nav=Decimal("59999999.9999995"), high_water_nav=Decimal("60000000")),
            (
                SlotOutcome("000250", "FILLED", Decimal("0.0123456789015")),
                SlotOutcome("000251", "FILLED", Decimal("-0.0076543210985")),
                SlotOutcome("000252", "NO_FILL"),
            ),
            23,
        )
        return canonical_json_bytes(asdict(result))

    expected = settle_bytes()
    original = getcontext().copy()
    try:
        getcontext().prec = 6
        getcontext().rounding = ROUND_DOWN
        assert settle_bytes() == expected
    finally:
        setcontext(original)


def test_additive_settlement_is_order_deterministic() -> None:
    outcomes = (
        SlotOutcome("000250", "FILLED", Decimal("0.0199999999995")),
        SlotOutcome("000251", "FILLED", Decimal("-0.0100000000005")),
        SlotOutcome("000252", "FILLED", Decimal("0.0000000000015")),
    )
    forward = settle_session(PortfolioState(), outcomes, 46)
    reverse = settle_session(PortfolioState(), tuple(reversed(outcomes)), 46)
    assert forward.nav_delta == reverse.nav_delta
    assert forward.state == reverse.state
    assert forward.reward == reverse.reward
    assert forward.drawdown == reverse.drawdown

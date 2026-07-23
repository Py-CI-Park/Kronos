from datetime import date
from decimal import Decimal

import pytest

from stom_rl.daily_type1_accounting import SlotOutcome
from stom_rl.daily_type1_market import (
    PRIMARY_COST,
    ProtocolError,
    PublicMarketRow,
    RidgeBaseline,
    TrainOnlyNormalizer,
    assert_validation_mutation_invariant,
    blocked_failure,
    bootstrap_confidence_interval,
    chronological_pairs,
    circular_moving_block_bootstrap,
    completed_no_go,
    exposure_matched_random,
    five_seed_iqm,
    public_row_from_mapping,
    random_baseline,
    replay_fixed_notional,
    select_top_positive,
    shuffled_returns,
    stop_baseline,
    type7_quantile,
    validate_public_rows,
)


def _row(day: date, symbol: str, values=None, gross="0.0100", available=True):
    return PublicMarketRow(
        decision_date=day,
        symbol=symbol,
        features=tuple(Decimal(value) if value is not None else None for value in (values or ["1", "2", "3", "4", "5", "6", "7"])),
        gross_return=Decimal(gross) if gross is not None else None,
        entry_available=available,
    )


def test_public_dates_leading_zero_and_strict_row_schema():
    train = _row(date(2018, 1, 2), "000001")
    validation = _row(date(2025, 6, 30), "000002")
    assert validate_public_rows([train], split="train") == (train,)
    assert validate_public_rows([validation], split="reused_validation") == (validation,)
    with pytest.raises(ProtocolError):
        validate_public_rows([_row(date(2024, 1, 2), "000001")], split="train")
    with pytest.raises(ProtocolError):
        public_row_from_mapping({"symbol": "000001"})
    with pytest.raises(ProtocolError):
        _row(date(2018, 1, 2), "1")


def test_type7_normalizer_null_clip_and_non_positive_iqr_block():
    rows = [_row(date(2018, 1, 2), "000001", ["0", "0", "0", "0", "0", "0", "0"]), _row(date(2018, 1, 3), "000002", ["2", "2", "2", "2", "2", "2", "2"])]
    normalizer = TrainOnlyNormalizer.fit(rows)
    values, missing = normalizer.transform([Decimal("100"), None, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")])
    assert values[0] == 10.0 and values[1] == 0.0 and missing == (0, 1, 0, 0, 0, 0, 0)
    assert type7_quantile([Decimal("0"), Decimal("10")], Decimal("0.25")) == Decimal("2.50")
    with pytest.raises(ProtocolError):
        TrainOnlyNormalizer.fit([_row(date(2018, 1, 2), "000001"), _row(date(2018, 1, 3), "000002")])


def test_chronological_pairs_record_odd_tail_and_exact_iqm():
    paired = chronological_pairs((0, 1, 2, 3, 4))
    assert paired.pairs == ((0, 1), (2, 3))
    assert paired.odd_tail == 4
    assert five_seed_iqm({0: Decimal("5"), 1: Decimal("1"), 2: Decimal("3"), 3: Decimal("2"), 4: Decimal("4")}) == Decimal("3.0")


def test_decimal_accounting_stop_ridge_random_and_shuffled_controls():
    assert PRIMARY_COST == Decimal("0.0023")
    assert replay_fixed_notional(((SlotOutcome("000001", "FILLED", Decimal("0.0100")),),)) == (Decimal("60038500.000000"),)
    assert stop_baseline(2) == ((), ())
    assert select_top_positive({"000002": Decimal("1"), "000001": Decimal("1"), "000003": Decimal("0")}) == ("000001", "000002")
    ridge = RidgeBaseline.fit([((0.0,) * 7, (0,) * 7, Decimal("0.0123")), ((1.0,) * 7, (0,) * 7, Decimal("0.0223"))])
    assert ridge.predict((0.0,) * 7, (0,) * 7).is_finite()
    available = (("000001", "000002"), ("000003",))
    assert random_baseline(available, replications=2, seed=0) == random_baseline(available, replications=2, seed=0)
    matched = exposure_matched_random(available, (1, 1), replications=2, seed=0)
    assert all(len(pair) == count for draw in matched for pair, count in zip(draw, (1, 1)))
    shuffled = shuffled_returns((Decimal("1"), None, Decimal("2"), Decimal("3")), seed=0)
    assert shuffled[1] is None and sorted(item for item in shuffled if item is not None) == [Decimal("1"), Decimal("2"), Decimal("3")]


def test_bootstrap_mutation_invariance_and_closed_failure_semantics():
    samples = circular_moving_block_bootstrap([Decimal("1"), Decimal("2")], replications=3, block_length_pairs=1, seed=0)
    assert samples == circular_moving_block_bootstrap([Decimal("1"), Decimal("2")], replications=3, block_length_pairs=1, seed=0)
    low, high = bootstrap_confidence_interval(samples)
    assert low <= high
    normalizer = TrainOnlyNormalizer.fit([_row(date(2018, 1, 2), "000001", ["0"] * 7), _row(date(2018, 1, 3), "000002", ["2"] * 7)])
    assert_validation_mutation_invariant(b"model", normalizer, b"model", normalizer)
    with pytest.raises(ProtocolError):
        assert_validation_mutation_invariant(b"model", normalizer, b"changed", normalizer)
    assert blocked_failure("schema error").execution_status.value == "BLOCK"
    assert blocked_failure("schema error").verdict.value == "NO_GO"
    assert completed_no_go("fresh OOS untouched").verdict.value == "NO_GO"


def test_public_row_accepts_canonical_key_order():
    row = {
        "decision_date": "2018-01-02",
        "symbol": "000250",
        "features": dict(sorted({
            "ret_1d_prev": "1",
            "ret_5d_prev": "1",
            "ret_20d_prev": "1",
            "vol_z_20": "1",
            "foreign_ratio_prev": "1",
            "foreign_ratio_delta_5": "1",
            "inst_netbuy_norm_5": "1",
        }.items())),
        "gross_return": "0.01",
        "entry_available": True,
    }
    assert public_row_from_mapping(row).symbol == "000250"

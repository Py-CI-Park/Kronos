from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from stom_rl.daily_close_research.offline_data import OfflineTransition
from stom_rl.daily_market_rl_contract import base_cost_config
from stom_rl.daily_market_rl_dataset import (
    MarketDay,
    fit_train_score_scale,
    prepare_market_data,
)
from stom_rl.daily_market_rl_trajectory import (
    build_behavior_transitions,
    build_model_observation,
    select_non_overlapping_days,
    shuffle_transition_actions,
    shuffle_transition_rewards,
)
from stom_rl.daily_market_score_dataset import CausalMarketScoreDay, DailyMarketScoreDataset
from stom_rl.daily_market_state_dataset import (
    CAUSAL_FEATURE_COLUMNS,
    CausalMarketStateDay,
    DailyMarketStateDataset,
    FeatureStatistic,
)
from stom_rl.daily_market_transition_contract import (
    DailyMarketCandidate,
    DailyMarketScore,
    SplitName,
    market_score_hash,
)


def _scores(decision: date, split: SplitName, *, offset: float = 0.0) -> tuple[DailyMarketScore, ...]:
    return tuple(
        DailyMarketScore(
            decision_date=decision,
            code=f"{index:06d}",
            score=offset + float(10 - index),
            split=split,
        )
        for index in range(1, 11)
    )


def _score_day(decision: date, split: SplitName, *, offset: float = 0.0) -> CausalMarketScoreDay:
    scores = _scores(decision, split, offset=offset)
    return CausalMarketScoreDay(
        decision_date=decision,
        split=split,
        scores=scores,
        day_hash=market_score_hash(scores),
    )


def _score_dataset() -> DailyMarketScoreDataset:
    train = _score_day(date(2026, 1, 2), "TRAIN")
    validation = _score_day(date(2026, 1, 5), "VALIDATION", offset=10_000.0)
    return DailyMarketScoreDataset(
        schema_version="kronos_daily_market_score_dataset.v1",
        days=(train, validation),
        dataset_hash="1" * 64,
        source_candidate_csv_sha256="2" * 64,
        source_manifest_sha256="3" * 64,
        source_fill_mode="close_to_next_close_research_label",
        target_fill_mode="D_CLOSE_DECISION_D1_OPEN_ENTRY_D2_OPEN_EXIT",
        day_count=2,
        scored_row_count=20,
        selected_score_count=20,
        excluded_missing_score_rows=0,
        excluded_ineligible_rows=0,
        split_day_counts={"TRAIN": 1, "VALIDATION": 1},
        blockers=("TEST_BLOCKER",),
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def _market_day(
    decision: date,
    *,
    split: SplitName = "TRAIN",
    entry_offset: int = 1,
    exit_offset: int = 2,
) -> MarketDay:
    score_day = _score_day(decision, split)
    state_day = CausalMarketStateDay(
        decision_date=decision.isoformat(),
        split=split,
        score_day_hash=score_day.day_hash,
        feature_vector=tuple(float(index) / 100.0 for index in range(160)),
        missing_feature_count=0,
        feature_hash="4" * 64,
    )
    candidates = tuple(
        DailyMarketCandidate(
            decision_date=score.decision_date,
            code=score.code,
            score=score.score,
            split=score.split,
            market_prefix=score.market_prefix,
            entry_date=decision + timedelta(days=entry_offset),
            exit_date=decision + timedelta(days=exit_offset),
            entry_open_krw=Decimal("10000"),
            exit_open_krw=Decimal("10100"),
        )
        for score in score_day.scores
    )
    return MarketDay(score_day=score_day, state_day=state_day, candidates=candidates)


def _single_score_dataset() -> DailyMarketScoreDataset:
    source = _score_dataset()
    return source.model_copy(
        update={
            "days": (source.days[0],),
            "day_count": 1,
            "scored_row_count": 10,
            "selected_score_count": 10,
            "split_day_counts": {"TRAIN": 1},
        }
    )


def _state_dataset(score_dataset: DailyMarketScoreDataset) -> DailyMarketStateDataset:
    market_day = _market_day(date(2026, 1, 2))
    statistics = tuple(
        FeatureStatistic(
            feature=feature,
            mean=0.0,
            standard_deviation=1.0,
            scaling_denominator=1.0,
            observed_count=10,
            fitted_split="TRAIN",
        )
        for feature in CAUSAL_FEATURE_COLUMNS
    )
    return DailyMarketStateDataset(
        schema_version="kronos_daily_market_state_dataset.v1",
        score_dataset_hash=score_dataset.dataset_hash,
        source_panel_sha256="5" * 64,
        state_dataset_hash="6" * 64,
        feature_columns=CAUSAL_FEATURE_COLUMNS,
        preprocessing="TRAIN_MEAN_IMPUTE_TRAIN_ZSCORE_WITH_MISSING_MASK",
        statistics=statistics,
        days=(market_day.state_day,),
        day_count=1,
        training_selected_rows=10,
        feature_vector_size=160,
        blockers=("TEST_BLOCKER",),
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def _daily_db(path: Path, *, missing_last_exit: bool) -> Path:
    with sqlite3.connect(path) as connection:
        for index in range(1, 11):
            table = f"A{index:06d}"
            _ = connection.execute(f'CREATE TABLE "{table}" (date INTEGER, open REAL)')
            rows = [(20260102, 10_000.0), (20260105, 10_000.0), (20260106, 10_100.0)]
            if missing_last_exit and index == 10:
                rows = rows[:-1]
            _ = connection.executemany(f'INSERT INTO "{table}" VALUES (?, ?)', rows)
    return path


def test_score_scale_and_observation_use_train_only_causal_values() -> None:
    # Given: one ordinary TRAIN day and a massively shifted VALIDATION day.
    dataset = _score_dataset()
    day = _market_day(date(2026, 1, 2))

    # When: score scaling and one model observation are built.
    scale = fit_train_score_scale(dataset)
    observation = build_model_observation(
        day,
        scale,
        previous_exposure_ratio=Decimal("0.5"),
        previous_drawdown=Decimal("-0.1"),
    )

    # Then: validation values cannot affect the scale and the state is exactly 172-D.
    assert scale.mean == 4.5
    assert scale.observed_count == 10
    assert len(observation) == 172
    assert observation[-2:] == (0.5, -0.1)


def test_non_overlapping_schedule_waits_until_the_previous_exit_open() -> None:
    # Given: three decisions where the middle decision occurs before the first exit.
    days = (
        _market_day(date(2026, 1, 2), exit_offset=4),
        _market_day(date(2026, 1, 5)),
        _market_day(date(2026, 1, 6)),
    )

    # When: the causal non-overlapping schedule is selected.
    selected = select_non_overlapping_days(days, split="TRAIN")

    # Then: the overlapping middle decision is excluded, while exit-day close is allowed.
    assert tuple(day.decision_date for day in selected) == (date(2026, 1, 2), date(2026, 1, 6))


def test_behavior_dataset_records_real_costed_transitions_and_terminal_boundaries() -> None:
    # Given: two non-overlapping market days and two exploratory behavior seeds.
    dataset = _score_dataset()
    scale = fit_train_score_scale(dataset)
    days = (
        _market_day(date(2026, 1, 2)),
        _market_day(date(2026, 1, 5)),
    )

    # When: the offline behavior data is generated through the real accounting engine.
    transitions = build_behavior_transitions(
        days,
        scale,
        behavior_seeds=(7, 8),
        cost_config=base_cost_config(),
    )

    # Then: each trajectory has two decisions, a terminal marker, and 172-D states.
    assert len(transitions) == 4
    assert sum(item.done for item in transitions) == 2
    assert all(len(item.state) == 172 and len(item.next_state) == 172 for item in transitions)
    assert {item.action for item in transitions}.issubset({0, 1})
    assert any(item.reward != 0.0 for item in transitions)


def test_negative_controls_shuffle_only_the_registered_field() -> None:
    # Given: an intentionally ordered offline transition sequence.
    source = tuple(
        OfflineTransition(index, (float(index),), index // 2, float(index + 1), (0.0,), index == 3)
        for index in range(4)
    )

    # When: reward and action falsification controls are constructed.
    reward_shuffled = shuffle_transition_rewards(source, seed=19)
    action_shuffled = shuffle_transition_actions(source, seed=23)

    # Then: each control preserves every non-target field and the original multisets.
    assert sorted(item.reward for item in reward_shuffled) == sorted(item.reward for item in source)
    assert sorted(item.action for item in action_shuffled) == sorted(item.action for item in source)
    assert tuple(item.action for item in reward_shuffled) == tuple(item.action for item in source)
    assert tuple(item.reward for item in action_shuffled) == tuple(item.reward for item in source)
    assert reward_shuffled != source
    assert action_shuffled != source


def test_market_preparation_uses_real_read_only_sqlite_reward_adapter(tmp_path: Path) -> None:
    # Given: one frozen score/state day and ten SQLite tables with exact next opens.
    score_dataset = _single_score_dataset()
    state_dataset = _state_dataset(score_dataset)
    database = _daily_db(tmp_path / "daily.db", missing_last_exit=False)

    # When: reward-only candidates are attached after the causal state is frozen.
    prepared = prepare_market_data(score_dataset, state_dataset, db_path=database)

    # Then: all ten candidates are available and no day is silently omitted.
    assert len(prepared.days) == 1
    assert len(prepared.days[0].candidates) == 10
    assert prepared.blocked_days == ()


def test_market_preparation_preserves_right_censored_day_as_blocked(tmp_path: Path) -> None:
    # Given: the last selected symbol has no exact exit open.
    score_dataset = _single_score_dataset()
    state_dataset = _state_dataset(score_dataset)
    database = _daily_db(tmp_path / "daily.db", missing_last_exit=True)

    # When: the reward horizon is prepared.
    prepared = prepare_market_data(score_dataset, state_dataset, db_path=database)

    # Then: the whole day is blocked visibly instead of filtering one future-missing stock.
    assert prepared.days == ()
    assert len(prepared.blocked_days) == 1
    assert prepared.blocked_days[0].reason == "000010:MISSING_EXIT_OPEN"

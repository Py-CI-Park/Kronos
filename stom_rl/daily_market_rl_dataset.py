"""Causal actual-market observations and exploratory offline trajectories."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from .daily_market_errors import DailyMarketDataError
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_score_dataset import CausalMarketScoreDay, DailyMarketScoreDataset
from .daily_market_state_dataset import (
    CausalMarketStateDay,
    DailyMarketStateDataset,
)
from .daily_market_transition_contract import (
    DailyMarketCandidate,
    SplitName,
)
from .daily_market_transition_db import load_daily_market_candidates
from .daily_ohlcv_db import DEFAULT_DAILY_DB_PATH

SCORE_COUNT: Final = 10


@dataclass(frozen=True, slots=True)
class TrainScoreScale:
    """Top-10 score normalization fitted exclusively on TRAIN days."""

    mean: float
    standard_deviation: float
    scaling_denominator: float
    observed_count: int


@dataclass(frozen=True, slots=True)
class MarketDay:
    """One causal state paired with reward-only exact-open candidates."""

    score_day: CausalMarketScoreDay
    state_day: CausalMarketStateDay
    candidates: tuple[DailyMarketCandidate, ...]

    def __post_init__(self) -> None:
        if self.state_day.decision_date != self.score_day.decision_date.isoformat():
            raise DailyMarketRlContractError("STATE_SCORE_DATE_MISMATCH")
        if self.state_day.split != self.score_day.split:
            raise DailyMarketRlContractError("STATE_SCORE_SPLIT_MISMATCH")
        if self.state_day.score_day_hash != self.score_day.day_hash:
            raise DailyMarketRlContractError("STATE_SCORE_HASH_MISMATCH")
        if len(self.candidates) != SCORE_COUNT:
            raise DailyMarketRlContractError("MARKET_DAY_REQUIRES_10_CANDIDATES")
        if len({row.entry_date for row in self.candidates}) != 1:
            raise DailyMarketRlContractError("MARKET_DAY_ENTRY_DATE_MISMATCH")
        if len({row.exit_date for row in self.candidates}) != 1:
            raise DailyMarketRlContractError("MARKET_DAY_EXIT_DATE_MISMATCH")

    @property
    def decision_date(self) -> date:
        return self.score_day.decision_date

    @property
    def split(self) -> SplitName:
        return self.score_day.split

    @property
    def entry_date(self) -> date:
        return self.candidates[0].entry_date

    @property
    def exit_date(self) -> date:
        return self.candidates[0].exit_date


@dataclass(frozen=True, slots=True)
class BlockedMarketDay:
    """A frozen day whose exact reward horizon is unavailable."""

    decision_date: date
    split: SplitName
    day_hash: str
    reason: str


@dataclass(frozen=True, slots=True)
class PreparedMarketData:
    """Parsed actual-market days with visible fail-closed omissions."""

    score_dataset_hash: str
    state_dataset_hash: str
    score_scale: TrainScoreScale
    days: tuple[MarketDay, ...]
    blocked_days: tuple[BlockedMarketDay, ...]


def fit_train_score_scale(dataset: DailyMarketScoreDataset) -> TrainScoreScale:
    """Fit score statistics without reading validation or test values."""
    values = tuple(score.score for day in dataset.days if day.split == "TRAIN" for score in day.scores)
    if not values:
        raise DailyMarketRlContractError("TRAIN_SCORE_VALUES_MISSING")
    mean = sum(values) / len(values)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    return TrainScoreScale(mean, deviation, deviation if deviation > 0 else 1.0, len(values))


def prepare_market_data(
    score_dataset: DailyMarketScoreDataset,
    state_dataset: DailyMarketStateDataset,
    *,
    db_path: Path | str = DEFAULT_DAILY_DB_PATH,
) -> PreparedMarketData:
    """Attach reward-only prices after state identity has been frozen."""
    if state_dataset.score_dataset_hash != score_dataset.dataset_hash:
        raise DailyMarketRlContractError("STATE_SCORE_DATASET_HASH_MISMATCH")
    states = {(day.decision_date, day.split): day for day in state_dataset.days}
    days: list[MarketDay] = []
    blocked: list[BlockedMarketDay] = []
    for score_day in score_dataset.days:
        state_day = states.get((score_day.decision_date.isoformat(), score_day.split))
        if state_day is None:
            raise DailyMarketRlContractError("CAUSAL_STATE_DAY_MISSING", score_day.decision_date.isoformat())
        try:
            batch = load_daily_market_candidates(score_day.scores, db_path=db_path)
        except DailyMarketDataError as exc:
            blocked.append(
                BlockedMarketDay(
                    score_day.decision_date,
                    score_day.split,
                    score_day.day_hash,
                    str(exc),
                )
            )
            continue
        if batch.split_hash != score_day.day_hash:
            raise DailyMarketRlContractError("REWARD_SCORE_HASH_MISMATCH")
        days.append(MarketDay(score_day, state_day, batch.candidates))
    return PreparedMarketData(
        score_dataset.dataset_hash,
        state_dataset.state_dataset_hash,
        fit_train_score_scale(score_dataset),
        tuple(days),
        tuple(blocked),
    )


__all__ = [
    "BlockedMarketDay",
    "MarketDay",
    "PreparedMarketData",
    "TrainScoreScale",
    "fit_train_score_scale",
    "prepare_market_data",
]

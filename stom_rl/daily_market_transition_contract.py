"""Typed contract for the daily-close binary market transition research lane."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

SplitName = Literal["TRAIN", "VALIDATION", "TEST", "FRESH_OOS"]
ActionName = Literal["CASH", "INVEST_TOP10_EQUAL_SLOT"]
PositiveMoney = Annotated[Decimal, Field(gt=0)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0)]


class BinaryAction(IntEnum):
    CASH = 0
    INVEST_TOP10_EQUAL_SLOT = 1


class DailyMarketScore(BaseModel):
    """One causal D-close score; safe to use for state and ranking."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision_date: date
    code: str = Field(pattern=r"^[0-9]{6}$")
    score: float
    split: SplitName
    market_prefix: Literal["A", "Q"] = "A"

    @property
    def table(self) -> str:
        return f"{self.market_prefix}{self.code}"


class DailyMarketCandidate(DailyMarketScore):
    """Causal score plus future prices reserved exclusively for reward."""

    entry_date: date
    exit_date: date
    entry_open_krw: PositiveMoney
    exit_open_krw: PositiveMoney

    @model_validator(mode="after")
    def validate_horizon(self) -> DailyMarketCandidate:
        if not self.decision_date < self.entry_date < self.exit_date:
            raise ValueError("expected decision_date < entry_date < exit_date")
        return self


@dataclass(frozen=True, slots=True)
class MarketTransitionConfig:
    initial_capital_krw: Decimal = Decimal("60000000")
    stock_exposure_cap_krw: Decimal = Decimal("50000000")
    cash_reserve_floor_krw: Decimal = Decimal("10000000")
    max_slots: int = 10
    buy_commission_percent: Decimal = Decimal("0.015")
    sell_commission_percent: Decimal = Decimal("0.015")
    sell_tax_percent: Decimal = Decimal("0.200")
    buy_slippage_percent: Decimal = Decimal("0")
    sell_slippage_percent: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.initial_capital_krw <= 0 or self.max_slots != 10:
            raise ValueError("market transition requires positive capital and exactly 10 slots")
        if self.stock_exposure_cap_krw + self.cash_reserve_floor_krw > self.initial_capital_krw:
            raise ValueError("exposure cap plus cash reserve exceeds initial capital")
        costs = (
            self.buy_commission_percent,
            self.sell_commission_percent,
            self.sell_tax_percent,
            self.buy_slippage_percent,
            self.sell_slippage_percent,
        )
        if any(value < 0 for value in costs):
            raise ValueError("cost percentages must be nonnegative")

    @property
    def round_trip_cost_percent(self) -> Decimal:
        return (
            self.buy_commission_percent
            + self.sell_commission_percent
            + self.sell_tax_percent
            + self.buy_slippage_percent
            + self.sell_slippage_percent
        )


class MarketState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision_date: date
    split: SplitName
    feature_vector: tuple[float, ...]
    previous_exposure_ratio: Annotated[Decimal, Field(ge=0, le=1)]
    previous_drawdown: Annotated[Decimal, Field(ge=-1, le=0)]
    candidate_tables: tuple[str, ...]
    candidate_codes: tuple[str, ...]
    candidate_scores: tuple[float, ...]
    state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SlotTransition(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    slot: int = Field(ge=0, lt=10)
    table: str = Field(pattern=r"^[AQ][0-9]{6}$")
    code: str = Field(pattern=r"^[0-9]{6}$")
    shares: int = Field(gt=0)
    entry_open_krw: PositiveMoney
    exit_open_krw: PositiveMoney
    entry_notional_krw: PositiveMoney
    exit_notional_krw: PositiveMoney
    buy_cost_krw: NonNegativeMoney
    sell_cost_krw: NonNegativeMoney
    gross_pnl_krw: Decimal
    net_pnl_krw: Decimal


class BinaryMarketTransition(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_transition.v1"]
    state_hash: str
    requested_action: ActionName
    executed_action: ActionName
    action_recorded: Literal[True]
    execution_reason: str
    previous_nav_krw: PositiveMoney
    previous_peak_nav_krw: PositiveMoney
    final_nav_krw: PositiveMoney
    peak_nav_krw: PositiveMoney
    cash_after_entry_krw: NonNegativeMoney
    deployed_at_entry_krw: NonNegativeMoney
    gross_pnl_krw: Decimal
    total_cost_krw: NonNegativeMoney
    net_pnl_krw: Decimal
    economic_return_fraction: Decimal
    reward_log_nav: Decimal
    drawdown_fraction: Annotated[Decimal, Field(ge=-1, le=0)]
    round_trip_cost_percent: NonNegativeMoney
    filled_slots: int = Field(ge=0, le=10)
    ledger: tuple[SlotTransition, ...]
    reward_kind: Literal["log_nav_return"]
    reward_unit: Literal["fraction"]
    equity_kind: Literal["krw_nav"]
    equity_unit: Literal["krw"]
    research_scope: Literal["LOCAL_RETROSPECTIVE_RESEARCH"]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def _state_digest(payload: JsonValue) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def rank_market_scores(candidates: Sequence[DailyMarketScore]) -> tuple[DailyMarketScore, ...]:
    if not candidates:
        raise ValueError("market state requires candidates")
    decision_date = candidates[0].decision_date
    split: SplitName = candidates[0].split
    if any(
        candidate.decision_date != decision_date or candidate.split != split
        for candidate in candidates
    ):
        raise ValueError("all candidates must share one decision date and split")
    if split == "FRESH_OOS":
        raise ValueError("FRESH_OOS remains sealed until preregistration and human approval")
    if len({candidate.code for candidate in candidates}) != len(candidates):
        raise ValueError("candidate codes must be unique within one decision date")
    return tuple(sorted(candidates, key=lambda candidate: (-candidate.score, candidate.code))[:10])


def market_score_hash(candidates: Sequence[DailyMarketScore]) -> str:
    """Hash only causal score inputs after deterministic top-10 selection."""
    ranked = rank_market_scores(candidates)
    return _state_digest(
        {
            "scores": [
                {
                    "decision_date": candidate.decision_date.isoformat(),
                    "split": candidate.split,
                    "market_prefix": candidate.market_prefix,
                    "code": candidate.code,
                    "score": repr(candidate.score),
                }
                for candidate in ranked
            ]
        }
    )


def build_market_state(
    candidates: Sequence[DailyMarketScore],
    *,
    feature_vector: tuple[float, ...],
    previous_exposure_ratio: Decimal,
    previous_drawdown: Decimal,
) -> MarketState:
    if not feature_vector:
        raise ValueError("market state requires causal features")
    ranked = rank_market_scores(candidates)
    decision_date = ranked[0].decision_date
    split = ranked[0].split
    candidate_codes = tuple(candidate.code for candidate in ranked)
    candidate_scores = tuple(candidate.score for candidate in ranked)
    candidate_tables = tuple(candidate.table for candidate in ranked)
    digest_payload: dict[str, JsonValue] = {
        "decision_date": decision_date.isoformat(),
        "split": split,
        "feature_vector": list(feature_vector),
        "previous_exposure_ratio": str(previous_exposure_ratio),
        "previous_drawdown": str(previous_drawdown),
        "candidate_tables": list(candidate_tables),
        "candidate_codes": list(candidate_codes),
        "candidate_scores": list(candidate_scores),
    }
    return MarketState(
        decision_date=decision_date,
        split=split,
        feature_vector=feature_vector,
        previous_exposure_ratio=previous_exposure_ratio,
        previous_drawdown=previous_drawdown,
        candidate_tables=candidate_tables,
        candidate_codes=candidate_codes,
        candidate_scores=candidate_scores,
        state_hash=_state_digest(digest_payload),
    )


__all__ = [
    "BinaryAction",
    "ActionName",
    "BinaryMarketTransition",
    "DailyMarketCandidate",
    "DailyMarketScore",
    "MarketState",
    "MarketTransitionConfig",
    "SplitName",
    "SlotTransition",
    "build_market_state",
    "market_score_hash",
    "rank_market_scores",
]

"""Fail-closed reward-availability audit for daily market score days."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_errors import DailyMarketInvariantError
from .daily_market_score_dataset import DailyMarketScoreDataset
from .daily_market_transition_contract import SplitName
from .daily_market_transition_db import load_daily_market_candidates
from .daily_ohlcv_db import DEFAULT_DAILY_DB_PATH


class DailyMarketRewardAuditRow(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    decision_date: str
    split: SplitName
    day_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASS", "BLOCKED"]
    reason: str
    split_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class DailyMarketRewardAudit(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_reward_audit.v1"]
    score_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_days: int = Field(gt=0)
    passed_days: int = Field(ge=0)
    blocked_days: int = Field(ge=0)
    split_pass_counts: dict[str, int]
    reason_counts: dict[str, int]
    rows: tuple[DailyMarketRewardAuditRow, ...]
    status: Literal["RESEARCH_REWARDS_AVAILABLE", "RESEARCH_REWARDS_INCOMPLETE"]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def _reason_code(reason: str) -> str:
    if ":" in reason:
        return reason.split(":", maxsplit=1)[1]
    return reason


def audit_daily_market_rewards(
    dataset: DailyMarketScoreDataset,
    *,
    db_path: Path | str = DEFAULT_DAILY_DB_PATH,
) -> DailyMarketRewardAudit:
    """Audit every frozen day; blocked days remain visible and are never dropped."""
    rows: list[DailyMarketRewardAuditRow] = []
    split_pass_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for day in dataset.days:
        try:
            batch = load_daily_market_candidates(day.scores, db_path=db_path)
        except ValueError as exc:
            reason = str(exc)
            reason_counts[_reason_code(reason)] += 1
            rows.append(
                DailyMarketRewardAuditRow(
                    decision_date=day.decision_date.isoformat(),
                    split=day.split,
                    day_hash=day.day_hash,
                    status="BLOCKED",
                    reason=reason,
                )
            )
            continue
        if batch.split_hash != day.day_hash:
            raise DailyMarketInvariantError("MARKET_REWARD_SPLIT_HASH_MISMATCH")
        split_pass_counts[day.split] += 1
        rows.append(
            DailyMarketRewardAuditRow(
                decision_date=day.decision_date.isoformat(),
                split=day.split,
                day_hash=day.day_hash,
                status="PASS",
                reason="EXACT_NEXT_TWO_OPENS_AVAILABLE",
                split_hash=batch.split_hash,
            )
        )
    passed = sum(row.status == "PASS" for row in rows)
    blocked = len(rows) - passed
    return DailyMarketRewardAudit(
        schema_version="kronos_daily_market_reward_audit.v1",
        score_dataset_hash=dataset.dataset_hash,
        total_days=len(rows),
        passed_days=passed,
        blocked_days=blocked,
        split_pass_counts=dict(split_pass_counts),
        reason_counts=dict(reason_counts),
        rows=tuple(rows),
        status="RESEARCH_REWARDS_AVAILABLE" if blocked == 0 else "RESEARCH_REWARDS_INCOMPLETE",
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = ["DailyMarketRewardAudit", "DailyMarketRewardAuditRow", "audit_daily_market_rewards"]

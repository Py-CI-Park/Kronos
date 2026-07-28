"""Torch-free strict expansion of the frozen D1 synthetic fixture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from stom_rl.daily_type1_contract import (
    EXECUTION_PROXY,
    FEATURES,
    FRESH_OOS_ACCESS_ALLOWED,
    MISSING_ENTRY_POLICY,
    OFFICIAL_CLOSE,
    PARTITION_LABEL,
    PROXY_TIME,
    PROXY_TIMEZONE,
    RESEARCH_SPLIT_LABEL,
)
from stom_rl.daily_type1_env import STABLE_SLOTS


class _CompactPair(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    signal_slot: int | None = Field(default=None, ge=0, lt=8)


class _CompactFixture(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    label: str
    partition: str
    pair_count: int
    symbols: tuple[str, ...]
    pairs: tuple[_CompactPair, ...]

    @model_validator(mode="after")
    def validate_frozen_shape(self) -> _CompactFixture:
        if self.schema_version != 1:
            raise ValueError("D1 fixture schema version must be 1")
        if self.label != "TRAIN_ONLY_SYNTHETIC_WIRING" or self.partition != "TRAIN_ONLY":
            raise ValueError("D1 fixture must be explicitly train-only")
        if self.pair_count != 64 or len(self.pairs) != 64:
            raise ValueError("D1 fixture must contain exactly 64 pairs")
        if len(self.symbols) != 8 or len(set(self.symbols)) != 8:
            raise ValueError("D1 fixture must contain eight unique symbols")
        if any(len(symbol) != 6 or not symbol.isdigit() for symbol in self.symbols):
            raise ValueError("D1 symbols must preserve six-digit string identity")
        for index, pair in enumerate(self.pairs):
            if (pair.signal_slot is None) != (index % 4 == 0):
                raise ValueError("D1 fixture must preserve the ordinal-mod-4 no-trade layout")
        return self


def load_d1_fixture(path: Path) -> Sequence[Mapping[str, Any]]:
    """Expand the compact fixture without importing Torch or training modules."""

    compact = _CompactFixture.model_validate(json.loads(path.read_text(encoding="utf-8")))
    stable_symbols = [f"{slot:06d}" for slot in range(1, STABLE_SLOTS + 1)]
    stable_symbols[: len(compact.symbols)] = compact.symbols
    expanded: list[dict[str, Any]] = []
    for index, pair in enumerate(compact.pairs):
        decision_date = date(2020, 1, 3) + timedelta(days=index * 4)
        values = np.zeros((STABLE_SLOTS, len(FEATURES)), dtype=np.float32)
        missing = np.zeros_like(values, dtype=np.int8)
        availability = np.zeros(STABLE_SLOTS, dtype=np.int8)
        entry_available = np.zeros(STABLE_SLOTS, dtype=np.int8)
        fill_available = np.ones(STABLE_SLOTS, dtype=np.int8)
        gross_returns: list[str | None] = [None] * STABLE_SLOTS
        for slot in range(len(compact.symbols)):
            availability[slot] = entry_available[slot] = 1
            values[slot, 0] = 10.0 if slot == pair.signal_slot else -10.0
            gross_returns[slot] = "0.0200" if slot == pair.signal_slot else "-0.0100"
        expanded.append(
            {
                "candidate_values": values,
                "candidate_missing": missing,
                "availability_mask": availability,
                "symbols": stable_symbols,
                "gross_returns": gross_returns,
                "entry_available": entry_available,
                "post_decision_fill_available": fill_available,
                "decision_date": decision_date.isoformat(),
                "settlement_date": (decision_date + timedelta(days=1)).isoformat(),
                "observation_cutoff_d1": (decision_date - timedelta(days=1)).isoformat(),
                "observation_cutoff_d2": (decision_date - timedelta(days=2)).isoformat(),
                "split_label": RESEARCH_SPLIT_LABEL,
                "partition_label": PARTITION_LABEL,
                "fresh_oos_access_allowed": FRESH_OOS_ACCESS_ALLOWED,
                "execution_proxy": EXECUTION_PROXY,
                "proxy_time": PROXY_TIME,
                "proxy_timezone": PROXY_TIMEZONE,
                "official_close": OFFICIAL_CLOSE,
                "missing_entry_policy": MISSING_ENTRY_POLICY,
            }
        )
    return tuple(expanded)

"""Bounded adapter from frozen public rows to five-candidate D3 episodes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from stom_rl.daily_type1_contract import FEATURES
from stom_rl.rl_discovery.d2_data import D2DataError
from stom_rl.rl_discovery.d3_env import Candidate, D3Episode


class D3FeatureRow(BaseModel):
    """Typed observable feature payload at the public-row boundary."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ret_1d_prev: float | None = None
    ret_5d_prev: float | None = None
    ret_20d_prev: float | None = None
    vol_z_20: float | None = None
    foreign_ratio_prev: float | None = None
    foreign_ratio_delta_5: float | None = None
    inst_netbuy_norm_5: float | None = None

    def ordered(self) -> tuple[float | None, ...]:
        return (
            self.ret_1d_prev,
            self.ret_5d_prev,
            self.ret_20d_prev,
            self.vol_z_20,
            self.foreign_ratio_prev,
            self.foreign_ratio_delta_5,
            self.inst_netbuy_norm_5,
        )


class D3SourceRow(BaseModel):
    """Parsed train-row contract consumed by D3 episode construction."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    decision_date: str
    symbol: str | None = None
    split: str | None = None
    features: D3FeatureRow | None = None
    gross_return: float | None = None
    entry_available: bool | None = None


def build_top_k_episodes(
    rows: Iterable[D3SourceRow],
    *,
    scales: Sequence[tuple[float, float]],
    limit: int,
) -> tuple[D3Episode, ...]:
    """Build the chronological train prefix using observable top-five ranking."""

    if len(scales) != len(FEATURES) or not 1 <= limit <= 2000:
        raise D2DataError("D3 scale or normalizer width is invalid")
    episodes: list[D3Episode] = []
    current_date: str | None = None
    group: list[D3SourceRow] = []
    for row in rows:
        decision_date = row.decision_date
        if current_date is not None and decision_date != current_date:
            episode = _episode_from_group(current_date, group, scales, len(episodes), limit)
            if episode is not None:
                episodes.append(episode)
            if len(episodes) == limit:
                break
            group = []
        current_date = decision_date
        group.append(row)
        if len(group) > 500:
            raise D2DataError("one D3 session cannot exceed 500 rows")
    else:
        if current_date is not None and len(episodes) < limit:
            episode = _episode_from_group(current_date, group, scales, len(episodes), limit)
            if episode is not None:
                episodes.append(episode)
    if len(episodes) != limit:
        raise D2DataError(f"expected {limit} eligible D3 sessions, found {len(episodes)}")
    return tuple(episodes)


def _episode_from_group(
    decision_date: str,
    rows: Sequence[D3SourceRow],
    scales: Sequence[tuple[float, float]],
    index: int,
    limit: int,
) -> D3Episode | None:
    eligible: list[Candidate] = []
    normalized_rows: list[tuple[float, ...]] = []
    for row in rows:
        if row.split != "train" or row.entry_available is not True:
            continue
        symbol, gross, features = row.symbol, row.gross_return, row.features
        if symbol is None or gross is None or features is None:
            continue
        values = features.ordered()
        raw = tuple(float(value) if value is not None else 0.0 for value in values)
        missing = tuple(float(value is None) for value in values)
        normalized = tuple(float(np.clip((value - center) / scale, -10, 10)) for value, (center, scale) in zip(raw, scales, strict=True))
        normalized_rows.append(normalized)
        eligible.append((symbol, normalized + missing, float(gross)))
    if len(eligible) < 5:
        return None
    selected = tuple(sorted(eligible, key=lambda item: (-item[1][0], item[0]))[:5])
    matrix = np.asarray(normalized_rows, dtype=np.float64)
    context = tuple(float(value) for value in (*np.clip(matrix.mean(axis=0), -10, 10), *np.clip(matrix.std(axis=0), 0, 10)))
    progress = 0.0 if limit == 1 else index / (limit - 1)
    return D3Episode(decision_date, selected, context, progress)

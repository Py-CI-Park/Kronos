"""Reused-validation episode materialization for D6."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import fmean, pstdev

from stom_rl.daily_type1_contract import FEATURES
from stom_rl.rl_discovery.d3_data import D3SourceRow
from stom_rl.rl_discovery.d3_env import Candidate, D3Episode


class D6DataError(ValueError):
    """The frozen reused-validation rows cannot satisfy the D6 contract."""


def build_reused_validation_episodes(
    rows: Iterable[D3SourceRow],
    *,
    scales: Sequence[tuple[float, float]],
    limit: int,
) -> tuple[D3Episode, ...]:
    """Build the fixed chronological reused-validation prefix."""

    if len(scales) != len(FEATURES) or not 1 <= limit <= 2_000:
        raise D6DataError("D6 scale width or episode limit is invalid")
    episodes: list[D3Episode] = []
    current_date: str | None = None
    group: list[D3SourceRow] = []
    for row in rows:
        if current_date is not None and row.decision_date != current_date:
            episode = _episode_from_group(current_date, group, scales, len(episodes), limit)
            if episode is not None:
                episodes.append(episode)
            if len(episodes) == limit:
                break
            group = []
        current_date = row.decision_date
        group.append(row)
        if len(group) > 500:
            raise D6DataError("one D6 session cannot exceed 500 rows")
    else:
        if current_date is not None and len(episodes) < limit:
            episode = _episode_from_group(current_date, group, scales, len(episodes), limit)
            if episode is not None:
                episodes.append(episode)
    if len(episodes) != limit:
        raise D6DataError(f"expected {limit} reused-validation sessions, found {len(episodes)}")
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
        if row.split != "reused_validation" or row.entry_available is not True:
            continue
        if row.symbol is None or row.gross_return is None or row.features is None:
            continue
        values = row.features.ordered()
        raw = tuple(float(value) if value is not None else 0.0 for value in values)
        missing = tuple(float(value is None) for value in values)
        normalized = tuple(
            max(-10.0, min(10.0, (value - center) / scale))
            for value, (center, scale) in zip(raw, scales, strict=True)
        )
        normalized_rows.append(normalized)
        eligible.append((row.symbol, normalized + missing, float(row.gross_return)))
    if len(eligible) < 5:
        return None
    selected = tuple(sorted(eligible, key=lambda item: (-item[1][0], item[0]))[:5])
    columns = tuple(zip(*normalized_rows, strict=True))
    context = tuple(
        max(-10.0, min(10.0, fmean(column))) for column in columns
    ) + tuple(
        max(0.0, min(10.0, pstdev(column))) for column in columns
    )
    progress = 0.0 if limit == 1 else index / (limit - 1)
    return D3Episode(decision_date, selected, context, progress)

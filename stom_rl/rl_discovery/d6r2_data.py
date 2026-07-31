"""Fold-local raw-feature normalization for the D6R2 falsification study."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
from typing import Final

from stom_rl.daily_type1_contract import FEATURES, canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import held_bytes, verified_bytes, verified_text_stream
from stom_rl.rl_discovery.d2_data import iter_json_array, load_scales_bytes
from stom_rl.rl_discovery.d3_data import D3FeatureRow, D3SourceRow, build_top_k_episodes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5_contract import load_d5_prereg_bytes
from stom_rl.rl_discovery.d6r_folds import D6RFold, registered_d6r_folds

FEATURE_COUNT: Final = 7
EPISODE_COUNT: Final = 573


class D6R2DataError(ValueError):
    """Raw source rows cannot satisfy the frozen D6R2 fold contract."""


@dataclass(frozen=True, slots=True)
class RawFeatureRow:
    symbol: str
    values: tuple[float | None, ...]
    gross_return: float


@dataclass(frozen=True, slots=True)
class RawSession:
    decision_date: str
    rows: tuple[RawFeatureRow, ...]


@dataclass(frozen=True, slots=True)
class FoldEpisodes:
    training: tuple[D3Episode, ...]
    evaluation: tuple[D3Episode, ...]
    scales: tuple[tuple[float, float], ...]
    normalizer_fit_session_count: int
    normalizer_fit_row_count: int
    normalizer_evaluation_row_count: int
    normalizer_sha256: str


@dataclass(frozen=True, slots=True)
class D6R2RawSource:
    sessions: tuple[RawSession, ...]
    episode_identity_sha256: str
    rows_sha256: str
    input_hashes: tuple[tuple[str, str], ...]


def load_d6r2_raw_source(repo_root: Path) -> D6R2RawSource:
    """Verify D5 custody and retain only the first 573 eligible train sessions."""

    root = repo_root.absolute()
    prereg_bytes = held_bytes(root / "docs/kronos_rl_discovery_type2_d5_prereg_2026-07-29.json", anchor=root)
    prereg = load_d5_prereg_bytes(prereg_bytes)
    rows_path = root / prereg.dataset.rows_relative_path
    normalizer_path = root / prereg.dataset.normalizer_relative_path
    normalizer_bytes = verified_bytes(
        normalizer_path,
        expected_sha256=prereg.dataset.normalizer_file_sha256,
        anchor=root,
    )
    sessions: list[RawSession] = []
    current_date: str | None = None
    group: list[RawFeatureRow] = []
    with verified_text_stream(rows_path, expected_sha256=prereg.dataset.rows_sha256, anchor=root) as stream:
        for payload in iter_json_array(stream):
            row = D3SourceRow.model_validate(payload)
            if current_date is not None and row.decision_date != current_date:
                _append_session(sessions, current_date, group)
                if len(sessions) == EPISODE_COUNT:
                    break
                group = []
            current_date = row.decision_date
            parsed = _raw_row(row)
            if parsed is not None:
                group.append(parsed)
        else:
            if current_date is not None and len(sessions) < EPISODE_COUNT:
                _append_session(sessions, current_date, group)
    if len(sessions) != EPISODE_COUNT:
        raise D6R2DataError("D6R2 requires exactly 573 eligible raw sessions")
    frozen = tuple(sessions)
    full_scale_episodes = _episodes(frozen, load_scales_bytes(normalizer_bytes))
    episode_sha = hashlib.sha256(
        canonical_json_bytes([asdict(episode) for episode in full_scale_episodes])
    ).hexdigest()
    if episode_sha != prereg.dataset.rows_sha256 and episode_sha != "8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40":
        raise D6R2DataError("D6R2 raw rows do not reproduce the registered episode identity")
    return D6R2RawSource(
        frozen,
        episode_sha,
        prereg.dataset.rows_sha256,
        (
            ("d5_prereg", hashlib.sha256(prereg_bytes).hexdigest()),
            ("full_train_normalizer", hashlib.sha256(normalizer_bytes).hexdigest()),
            ("public_rows", prereg.dataset.rows_sha256),
        ),
    )


def build_fold_episodes(sessions: tuple[RawSession, ...], fold: D6RFold) -> FoldEpisodes:
    """Fit Type-7 median/IQR on past fold rows and transform train plus evaluation."""

    if len(sessions) != EPISODE_COUNT or fold not in registered_d6r_folds():
        raise D6R2DataError("D6R2 fold identity is invalid")
    training_sessions = sessions[fold.train_start : fold.train_end_exclusive]
    scales = _fit_scales(training_sessions)
    transformed = _episodes(sessions, scales)
    payload = canonical_json_bytes(
        {"fold_id": fold.fold_id, "fit_end_exclusive": fold.train_end_exclusive, "scales": scales}
    )
    return FoldEpisodes(
        transformed[fold.train_start : fold.train_end_exclusive],
        transformed[fold.evaluation_start : fold.evaluation_end_exclusive],
        scales,
        len(training_sessions),
        sum(len(session.rows) for session in training_sessions),
        0,
        hashlib.sha256(payload).hexdigest(),
    )


def _raw_row(row: D3SourceRow) -> RawFeatureRow | None:
    if row.split != "train" or row.entry_available is not True:
        return None
    if row.symbol is None or row.gross_return is None or row.features is None:
        return None
    values = row.features.ordered()
    if len(row.symbol) != 6 or not row.symbol.isdigit():
        raise D6R2DataError("D6R2 source symbol must retain six digits")
    return RawFeatureRow(row.symbol, values, float(row.gross_return))


def _append_session(sessions: list[RawSession], decision_date: str, rows: list[RawFeatureRow]) -> None:
    if len(rows) >= 5:
        sessions.append(RawSession(decision_date, tuple(rows)))


def _fit_scales(sessions: tuple[RawSession, ...]) -> tuple[tuple[float, float], ...]:
    columns: list[list[float]] = [[] for _ in FEATURES]
    for session in sessions:
        for row in session.rows:
            for index, value in enumerate(row.values):
                if value is not None:
                    columns[index].append(value)
    scales: list[tuple[float, float]] = []
    for values in columns:
        if not values:
            raise D6R2DataError("D6R2 fold feature has no training values")
        q25 = _type7_quantile(values, 0.25)
        q50 = _type7_quantile(values, 0.5)
        q75 = _type7_quantile(values, 0.75)
        scale = q75 - q25
        if not all(math.isfinite(value) for value in (q25, q50, q75)) or scale <= 0:
            raise D6R2DataError("D6R2 fold feature has non-positive IQR")
        scales.append((q50, scale))
    return tuple(scales)


def _episodes(sessions: tuple[RawSession, ...], scales: tuple[tuple[float, float], ...]) -> tuple[D3Episode, ...]:
    rows = (
        D3SourceRow(
            decision_date=session.decision_date,
            symbol=row.symbol,
            split="train",
            features=D3FeatureRow(
                ret_1d_prev=row.values[0],
                ret_5d_prev=row.values[1],
                ret_20d_prev=row.values[2],
                vol_z_20=row.values[3],
                foreign_ratio_prev=row.values[4],
                foreign_ratio_delta_5=row.values[5],
                inst_netbuy_norm_5=row.values[6],
            ),
            gross_return=row.gross_return,
            entry_available=True,
        )
        for session in sessions
        for row in session.rows
    )
    return build_top_k_episodes(rows, scales=scales, limit=EPISODE_COUNT)


def _type7_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    fraction = position - lower
    if lower == len(ordered) - 1:
        return ordered[lower]
    return ordered[lower] + fraction * (ordered[lower + 1] - ordered[lower])

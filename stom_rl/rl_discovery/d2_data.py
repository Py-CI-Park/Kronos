"""Bounded streaming adapter from frozen public rows to D2 episodes."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
import json
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from stom_rl.daily_type1_contract import FEATURES
from stom_rl.rl_discovery.d2_env import HistoricalEpisode


class D2DataError(ValueError):
    """Frozen historical input is malformed or unsafe."""


def iter_json_array(source: Path | TextIO, *, chunk_size: int = 1 << 20) -> Iterator[Mapping[str, Any]]:
    """Stream a top-level JSON array without retaining the 438MB source."""

    if isinstance(source, Path):
        with source.open("r", encoding="utf-8") as handle:
            yield from iter_json_array(handle, chunk_size=chunk_size)
        return
    decoder = json.JSONDecoder()
    handle = source
    if not handle.readable():
        raise D2DataError("public rows stream must be readable")
    maximum_buffer = max(chunk_size * 8, 8 << 20)
    with _borrowed_stream(handle):
        buffer = ""
        started = False
        finished = False
        expect_value = True
        allow_end = True
        while not finished:
            chunk = handle.read(chunk_size)
            buffer += chunk
            if len(buffer) > maximum_buffer:
                raise D2DataError("public row token exceeds the bounded stream buffer")
            cursor = 0
            while True:
                while cursor < len(buffer) and buffer[cursor].isspace():
                    cursor += 1
                if not started:
                    if cursor >= len(buffer):
                        break
                    if buffer[cursor] != "[":
                        raise D2DataError("public rows must be a JSON array")
                    started = True
                    cursor += 1
                    continue
                while cursor < len(buffer) and buffer[cursor].isspace():
                    cursor += 1
                if cursor >= len(buffer):
                    break
                if not expect_value:
                    if buffer[cursor] == "]":
                        finished = True
                        cursor += 1
                        break
                    if buffer[cursor] != ",":
                        raise D2DataError("public rows require a comma between objects")
                    cursor += 1
                    expect_value = True
                    allow_end = False
                    continue
                if buffer[cursor] == "]":
                    if not allow_end:
                        raise D2DataError("public rows cannot end after a comma")
                    finished = True
                    cursor += 1
                    break
                try:
                    value, end = decoder.raw_decode(buffer, cursor)
                except json.JSONDecodeError:
                    break
                if not isinstance(value, Mapping):
                    raise D2DataError("public row must be an object")
                yield value
                cursor = end
                expect_value = False
                allow_end = True
            buffer = buffer[cursor:]
            if not chunk and not finished:
                raise D2DataError("public rows JSON ended before closing array")
        if buffer.strip():
            raise D2DataError("public rows JSON has trailing content")


class _borrowed_stream:
    """Keep a caller-owned stream open while sharing one parser implementation."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def __enter__(self) -> TextIO:
        return self._stream

    def __exit__(self, *_: object) -> None:
        return None


def load_scales_bytes(payload: bytes) -> tuple[tuple[float, float], ...]:
    """Load the custody-bound Type-7 normalizer."""

    value = json.loads(payload)
    if not isinstance(value, Mapping) or value.get("kind") != "market_type7_train_only":
        raise D2DataError("normalizer kind is not train-only Type-7")
    raw = value.get("scales")
    if not isinstance(raw, list) or len(raw) != len(FEATURES):
        raise D2DataError("normalizer scale schema is malformed")
    scales = tuple((float(item["center"]), float(item["scale"])) for item in raw)
    if any(not np.isfinite(pair).all() or pair[1] <= 0 for pair in map(np.asarray, scales)):
        raise D2DataError("normalizer scales must be finite and positive")
    return scales


def build_historical_episodes(
    rows: Iterable[Mapping[str, Any]],
    *,
    scales: Sequence[tuple[float, float]],
    limit: int,
) -> tuple[HistoricalEpisode, ...]:
    """Build the first eligible chronological train sessions without look-ahead ranking."""

    if len(scales) != len(FEATURES) or not 1 <= limit <= 128:
        raise D2DataError("D2 scale or normalizer width is invalid")
    episodes: list[HistoricalEpisode] = []
    current_date: str | None = None
    group: list[Mapping[str, Any]] = []
    for row in rows:
        decision_date = row.get("decision_date")
        if not isinstance(decision_date, str):
            raise D2DataError("decision_date must be a string")
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
            raise D2DataError("one D2 session cannot exceed 500 stable-symbol rows")
    else:
        if current_date is not None and len(episodes) < limit:
            episode = _episode_from_group(current_date, group, scales, len(episodes), limit)
            if episode is not None:
                episodes.append(episode)
    if len(episodes) != limit:
        raise D2DataError(f"expected {limit} eligible train sessions, found {len(episodes)}")
    return tuple(episodes)


def _episode_from_group(
    decision_date: str,
    rows: Sequence[Mapping[str, Any]],
    scales: Sequence[tuple[float, float]],
    index: int,
    limit: int,
) -> HistoricalEpisode | None:
    eligible: list[tuple[str, tuple[float, ...], tuple[float, ...], float]] = []
    for row in rows:
        if row.get("split") != "train" or row.get("entry_available") is not True:
            continue
        symbol, gross, features = row.get("symbol"), row.get("gross_return"), row.get("features")
        if not isinstance(symbol, str) or gross is None or not isinstance(features, Mapping):
            continue
        raw = tuple(float(features[name]) if features.get(name) is not None else 0.0 for name in FEATURES)
        missing = tuple(float(features.get(name) is None) for name in FEATURES)
        normalized = tuple(np.clip((value - center) / scale, -10, 10) for value, (center, scale) in zip(raw, scales, strict=True))
        eligible.append((symbol, normalized, missing, float(gross)))
    if not eligible:
        return None
    selected = sorted(eligible, key=lambda item: (-item[1][0], item[0]))[0]
    matrix = np.asarray([item[1] for item in eligible], dtype=np.float64)
    aggregate = tuple(np.clip(matrix.mean(axis=0), -10, 10)) + tuple(np.clip(matrix.std(axis=0), 0, 10))
    progress = 0.0 if limit == 1 else index / (limit - 1)
    observation = selected[1] + selected[2] + aggregate + (progress,)
    return HistoricalEpisode(decision_date, selected[0], tuple(float(value) for value in observation), selected[3])

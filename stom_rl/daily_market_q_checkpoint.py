"""Pickle-free binary custody for actual-market Q-network weights."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Final

import numpy as np
from pydantic import TypeAdapter, ValidationError

from .daily_market_path_custody import has_reparse_component
from .daily_market_q_network import FloatArray, MarketQNetwork
from .daily_market_rl_contract import DailyMarketRlContractError

MAGIC: Final = b"KRONOSQ1"
SHAPE_ADAPTER: Final = TypeAdapter(tuple[tuple[int, ...], ...])
MAX_CHECKPOINT_BYTES: Final = 64 * 1024 * 1024


def _arrays(network: MarketQNetwork) -> tuple[FloatArray, ...]:
    return (
        network.first_weight,
        network.first_bias,
        network.second_weight,
        network.second_bias,
        network.output_weight,
        network.output_bias,
    )


def _payload_bytes(shapes: tuple[tuple[int, ...], ...]) -> int:
    total = sum(math.prod(shape) * 8 for shape in shapes)
    if total > MAX_CHECKPOINT_BYTES:
        raise DailyMarketRlContractError("MODEL_CHECKPOINT_SIZE_INVALID")
    return total


def save_network(network: MarketQNetwork, path: Path) -> None:
    """Write a bounded JSON shape header followed by raw float64 arrays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if has_reparse_component(path.parent):
        raise DailyMarketRlContractError("MODEL_CHECKPOINT_OUTPUT_UNTRUSTED")
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    arrays = _arrays(network)
    shapes = tuple(tuple(value.shape) for value in arrays)
    _ = _payload_bytes(shapes)
    if any(not bool(np.isfinite(value).all()) for value in arrays):
        raise DailyMarketRlContractError("MODEL_CHECKPOINT_NONFINITE")
    header = json.dumps([list(value.shape) for value in arrays], separators=(",", ":")).encode("ascii")
    with temporary.open("wb") as handle:
        _ = handle.write(MAGIC)
        _ = handle.write(len(header).to_bytes(4, byteorder="big", signed=False))
        _ = handle.write(header)
        for value in arrays:
            _ = handle.write(np.asarray(value, dtype="<f8").tobytes(order="C"))
    _ = temporary.replace(path)


def load_network(
    path: Path,
    expected_shapes: tuple[tuple[int, ...], ...],
) -> MarketQNetwork:
    """Parse numeric arrays without executing serialized code."""
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketRlContractError("MODEL_CHECKPOINT_UNTRUSTED", str(path))
    with path.open("rb") as handle:
        if handle.read(len(MAGIC)) != MAGIC:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_MAGIC_MISMATCH")
        encoded_header_size = handle.read(4)
        if len(encoded_header_size) != 4:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_HEADER_INVALID")
        header_size = int.from_bytes(encoded_header_size, byteorder="big", signed=False)
        if not 2 <= header_size <= 4_096:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_HEADER_INVALID")
        encoded_shapes = handle.read(header_size)
        if len(encoded_shapes) != header_size:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_HEADER_INVALID")
        try:
            shapes = SHAPE_ADAPTER.validate_json(encoded_shapes)
        except ValidationError as error:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_HEADER_INVALID") from error
        if shapes != expected_shapes:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_SHAPE_MISMATCH")
        payload_bytes = _payload_bytes(shapes)
        expected_size = len(MAGIC) + 4 + header_size + payload_bytes
        actual_size = path.stat().st_size
        if actual_size < expected_size:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_TRUNCATED")
        if actual_size > expected_size:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_TRAILING_BYTES")
        arrays: list[FloatArray] = []
        for shape in shapes:
            byte_count = math.prod(shape) * 8
            payload = handle.read(byte_count)
            if len(payload) != byte_count:
                raise DailyMarketRlContractError("MODEL_CHECKPOINT_TRUNCATED")
            array = np.frombuffer(payload, dtype="<f8").copy().reshape(shape)
            if not bool(np.isfinite(array).all()):
                raise DailyMarketRlContractError("MODEL_CHECKPOINT_NONFINITE")
            arrays.append(array)
    first_weight, first_bias, second_weight, second_bias, output_weight, output_bias = arrays
    return MarketQNetwork(
        first_weight,
        first_bias,
        second_weight,
        second_bias,
        output_weight,
        output_bias,
    )


__all__ = ["load_network", "save_network"]

"""Pickle-free binary custody for actual-market Q-network weights."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Final

import numpy as np
from pydantic import TypeAdapter

from .daily_market_q_network import FloatArray, MarketQNetwork
from .daily_market_rl_contract import DailyMarketRlContractError

MAGIC: Final = b"KRONOSQ1"
SHAPE_ADAPTER: Final = TypeAdapter(tuple[tuple[int, ...], ...])


def _arrays(network: MarketQNetwork) -> tuple[FloatArray, ...]:
    return (
        network.first_weight,
        network.first_bias,
        network.second_weight,
        network.second_bias,
        network.output_weight,
        network.output_bias,
    )


def save_network(network: MarketQNetwork, path: Path) -> None:
    """Write a bounded JSON shape header followed by raw float64 arrays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    arrays = _arrays(network)
    header = json.dumps([list(value.shape) for value in arrays], separators=(",", ":")).encode("ascii")
    with temporary.open("wb") as handle:
        _ = handle.write(MAGIC)
        _ = handle.write(len(header).to_bytes(4, byteorder="big", signed=False))
        _ = handle.write(header)
        for value in arrays:
            _ = handle.write(np.asarray(value, dtype="<f8").tobytes(order="C"))
    _ = temporary.replace(path)


def load_network(path: Path) -> MarketQNetwork:
    """Parse numeric arrays without executing serialized code."""
    with path.open("rb") as handle:
        if handle.read(len(MAGIC)) != MAGIC:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_MAGIC_MISMATCH")
        header_size = int.from_bytes(handle.read(4), byteorder="big", signed=False)
        if not 2 <= header_size <= 4_096:
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_HEADER_INVALID")
        shapes = SHAPE_ADAPTER.validate_json(handle.read(header_size))
        if len(shapes) != 6 or any(not shape or any(axis < 1 for axis in shape) for shape in shapes):
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_SHAPES_INVALID")
        arrays: list[FloatArray] = []
        for shape in shapes:
            byte_count = math.prod(shape) * 8
            payload = handle.read(byte_count)
            if len(payload) != byte_count:
                raise DailyMarketRlContractError("MODEL_CHECKPOINT_TRUNCATED")
            arrays.append(np.frombuffer(payload, dtype="<f8").copy().reshape(shape))
        if handle.read(1):
            raise DailyMarketRlContractError("MODEL_CHECKPOINT_TRAILING_BYTES")
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

from __future__ import annotations

import json
import math
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from pydantic import TypeAdapter

from stom_rl.daily_close_research.offline_data import OfflineTransition
from stom_rl.daily_market_offline_q import load_market_q, train_market_q
from stom_rl.daily_market_q_checkpoint import MAGIC, save_network
from stom_rl.daily_market_q_network import MarketQNetwork
from stom_rl.daily_market_rl_contract import (
    DailyMarketRlContractError,
    MarketAlgorithm,
    MarketTrainingConfig,
)
from stom_rl.daily_market_transition_contract import BinaryAction

SHAPES_ADAPTER = TypeAdapter(list[list[int]])


def _known_signal_transitions() -> tuple[OfflineTransition, ...]:
    rows: list[OfflineTransition] = []
    zero_tail = (0.0,) * 171
    for index in range(400):
        signal = -1.0 if index % 2 == 0 else 1.0
        action = (index // 2) % 2
        correct = (signal < 0 and action == 0) or (signal > 0 and action == 1)
        state = (signal, *zero_tail)
        rows.append(
            OfflineTransition(
                sequence=index,
                state=state,
                action=action,
                reward=1.0 if correct else -1.0,
                next_state=(0.0,) * 172,
                done=True,
            )
        )
    return tuple(rows)


def _fast_config(algorithm: MarketAlgorithm) -> MarketTrainingConfig:
    return replace(
        MarketTrainingConfig.registered(algorithm=algorithm, seed=11),
        hidden_dimensions=(32, 16),
        learning_rate=0.003,
        discount=0.0,
        cql_alpha=0.1 if algorithm is not MarketAlgorithm.DQN else 0.0,
        reward_scale=1.0,
        batch_size=64,
        gradient_steps=250,
        target_update_interval=20,
    )


def _write_checkpoint(path: Path, config: MarketTrainingConfig) -> None:
    network = MarketQNetwork.initialize(
        config.input_dimension,
        config.hidden_dimensions,
        config.action_count,
        np.random.default_rng(7),
    )
    save_network(network, path)


def _replace_shape(path: Path, index: int, shape: tuple[int, ...]) -> None:
    content = path.read_bytes()
    header_start = len(MAGIC) + 4
    header_size = int.from_bytes(content[len(MAGIC) : header_start], byteorder="big")
    payload = content[header_start + header_size :]
    shapes = SHAPES_ADAPTER.validate_json(
        content[header_start : header_start + header_size]
    )
    shapes[index] = list(shape)
    header = json.dumps(shapes, separators=(",", ":")).encode("ascii")
    path.write_bytes(
        MAGIC + len(header).to_bytes(4, byteorder="big") + header + payload
    )


def test_cql_learns_known_binary_policy_and_round_trips_safe_weights(
    tmp_path: Path,
) -> None:
    # Given: full action coverage for a known two-state reward function.
    transitions = _known_signal_transitions()
    config = _fast_config(MarketAlgorithm.CQL)
    checkpoint = tmp_path / "market_cql.kq"

    # When: CQL is trained and restored from weights-only safetensors.
    trained = train_market_q(transitions, config, checkpoint_path=checkpoint)
    restored = load_market_q(checkpoint, config)

    # Then: both in-memory and restored policies choose the known optimal action.
    negative = (-1.0, *((0.0,) * 171))
    positive = (1.0, *((0.0,) * 171))
    assert trained.policy.greedy_action(negative) is BinaryAction.CASH
    assert (
        trained.policy.greedy_action(positive) is BinaryAction.INVEST_TOP10_EQUAL_SLOT
    )
    assert restored.greedy_action(negative) is BinaryAction.CASH
    assert restored.greedy_action(positive) is BinaryAction.INVEST_TOP10_EQUAL_SLOT
    assert checkpoint.is_file()
    assert trained.checkpoint_sha256 is not None


def test_dqn_training_produces_finite_loss_history() -> None:
    # Given: the same known-signal offline data and the DQN control arm.
    # When: the fixed-step optimizer runs.
    trained = train_market_q(
        _known_signal_transitions(), _fast_config(MarketAlgorithm.DQN)
    )

    # Then: every recorded optimization loss is finite and nonnegative.
    assert len(trained.losses) == 250
    assert all(0.0 <= loss < float("inf") for loss in trained.losses)


def test_training_rejects_transition_state_dimension_mismatch() -> None:
    # Given: a transition that does not satisfy the preregistered 172-D contract.
    invalid = (OfflineTransition(0, (1.0,), 1, 1.0, (0.0,), True),)

    # When / Then: the typed boundary rejects it before Torch tensor construction.
    with pytest.raises(
        DailyMarketRlContractError, match="TRAINING_STATE_DIMENSION_MISMATCH"
    ):
        _ = train_market_q(invalid, _fast_config(MarketAlgorithm.CQL))


@pytest.mark.parametrize(
    ("shape_index", "invalid_shape"),
    (
        (0, (172, 31)),
        (1, (32, 1)),
        (2, (32, 15)),
        (3, (16, 1)),
        (4, (16, 3)),
        (5, (2, 1)),
        (0, (999_999_999, 32)),
    ),
)
def test_checkpoint_rejects_every_unregistered_shape_before_payload_read(
    tmp_path: Path,
    shape_index: int,
    invalid_shape: tuple[int, ...],
) -> None:
    config = _fast_config(MarketAlgorithm.CQL)
    checkpoint = tmp_path / f"bad-shape-{shape_index}.kq"
    _write_checkpoint(checkpoint, config)
    _replace_shape(checkpoint, shape_index, invalid_shape)

    with pytest.raises(
        DailyMarketRlContractError, match="MODEL_CHECKPOINT_SHAPE_MISMATCH"
    ):
        _ = load_market_q(checkpoint, config)


def test_checkpoint_rejects_nonfinite_numeric_payload(tmp_path: Path) -> None:
    config = _fast_config(MarketAlgorithm.CQL)
    checkpoint = tmp_path / "nonfinite.kq"
    _write_checkpoint(checkpoint, config)
    content = bytearray(checkpoint.read_bytes())
    header_size = int.from_bytes(content[len(MAGIC) : len(MAGIC) + 4], byteorder="big")
    payload_start = len(MAGIC) + 4 + header_size
    content[payload_start : payload_start + 8] = struct.pack("<d", math.nan)
    checkpoint.write_bytes(content)

    with pytest.raises(DailyMarketRlContractError, match="MODEL_CHECKPOINT_NONFINITE"):
        _ = load_market_q(checkpoint, config)


def test_checkpoint_writer_never_overwrites_completed_weights(tmp_path: Path) -> None:
    config = _fast_config(MarketAlgorithm.CQL)
    checkpoint = tmp_path / "immutable.kq"
    _write_checkpoint(checkpoint, config)
    original = checkpoint.read_bytes()

    with pytest.raises(
        DailyMarketRlContractError,
        match="MODEL_CHECKPOINT_ALREADY_EXISTS",
    ):
        _write_checkpoint(checkpoint, config)

    assert checkpoint.read_bytes() == original

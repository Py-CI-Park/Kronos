"""Reduced-action Type2-D1 train-only environment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import IntEnum
from typing import Any

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from stom_rl.daily_type1_env import STOP, Type1ClosingEnv
from stom_rl.rl_discovery.d1_contract import D1RewardKind


class BinaryAction(IntEnum):
    """D1 reduced action head."""

    STOP = 0
    SELECT_TOP_OBSERVED = 1


class D1EnvironmentStateError(RuntimeError):
    """Raised when the D1 environment lifecycle is used out of order."""


class BinaryCandidateEnv(gym.Env[NDArray[np.float32], int]):
    """Map a two-action policy onto the frozen Type1 candidate environment."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        pairs: Sequence[Mapping[str, Any]],
        *,
        reward_kind: D1RewardKind,
    ) -> None:
        super().__init__()
        self._base = Type1ClosingEnv(pairs)
        self._reward_kind = reward_kind
        self._raw_observation: Mapping[str, NDArray[np.generic]] | None = None
        self.action_space = gym.spaces.Discrete(len(BinaryAction))
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (6,), np.float32)

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[NDArray[np.float32], dict[str, Any]]:
        raw, info = self._base.reset(seed=seed, options=options)
        self._raw_observation = raw
        return self._encode(raw), info

    def action_masks(self) -> NDArray[np.bool_]:
        base_mask = self._base.action_masks()
        return np.asarray([bool(base_mask[STOP]), bool(base_mask[1:].any())], dtype=np.bool_)

    def step(
        self,
        action: int,
    ) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        binary = BinaryAction(action)
        raw = self._require_observation()
        call_index = int(round(float(raw["portfolio_state"][0]) * 10))
        top_score = self._top_score(raw)
        decoded = STOP if binary is BinaryAction.STOP else self._decode_select(raw)
        next_raw, native_reward, terminated, truncated, raw_info = self._base.step(decoded)
        training_reward = self._training_reward(
            binary=binary,
            call_index=call_index,
            top_score=top_score,
            native_reward=float(native_reward),
        )
        self._raw_observation = next_raw
        info = dict(raw_info)
        info.update(
            {
                "binary_action": int(binary),
                "decoded_action": decoded,
                "native_economic_reward": float(native_reward),
                "training_reward": training_reward,
            }
        )
        return self._encode(next_raw), training_reward, terminated, truncated, info

    def _training_reward(
        self,
        *,
        binary: BinaryAction,
        call_index: int,
        top_score: float,
        native_reward: float,
    ) -> float:
        if self._reward_kind is not D1RewardKind.FIRST_DECISION_DIAGNOSTIC:
            return native_reward
        if call_index != 0:
            return 0.0
        expected = BinaryAction.SELECT_TOP_OBSERVED if top_score > 0 else BinaryAction.STOP
        return 1.0 if binary is expected else -1.0

    def _decode_select(self, raw: Mapping[str, NDArray[np.generic]]) -> int:
        mask = self._base.action_masks()[1:]
        candidates = np.flatnonzero(mask)
        if not len(candidates):
            return STOP
        scores = np.asarray(raw["candidate_values"][:, 0], dtype=np.float32)
        return int(candidates[int(np.argmax(scores[candidates]))]) + 1

    @staticmethod
    def _top_score(raw: Mapping[str, NDArray[np.generic]]) -> float:
        availability = np.asarray(raw["availability_mask"], dtype=np.bool_)
        selected = np.asarray(raw["current_selection_mask"], dtype=np.bool_)
        candidates = np.flatnonzero(availability & ~selected)
        if not len(candidates):
            return -10.0
        scores = np.asarray(raw["candidate_values"][:, 0], dtype=np.float32)
        return float(scores[candidates].max())

    def _require_observation(self) -> Mapping[str, NDArray[np.generic]]:
        if self._raw_observation is None:
            raise D1EnvironmentStateError("reset must be called before step")
        return self._raw_observation

    @classmethod
    def _encode(cls, raw: Mapping[str, NDArray[np.generic]]) -> NDArray[np.float32]:
        portfolio = np.asarray(raw["portfolio_state"], dtype=np.float32)
        score = cls._top_score(raw)
        return np.asarray(
            [score / 10.0, float(score > 0), portfolio[1], portfolio[0], portfolio[3] / 10.0, portfolio[4] / 10.0],
            dtype=np.float32,
        )

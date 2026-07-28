"""Small real-history close-trading environment for the D2 capacity ladder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray


OBSERVATION_WIDTH = 29


class D2Action(IntEnum):
    STOP = 0
    BUY = 1


@dataclass(frozen=True, slots=True)
class HistoricalEpisode:
    """One observable decision and its post-decision reward."""

    decision_date: str
    symbol: str
    observation: tuple[float, ...]
    gross_return: float

    def __post_init__(self) -> None:
        if len(self.observation) != OBSERVATION_WIDTH:
            raise ValueError("historical observation must contain 29 values")
        if len(self.symbol) != 6 or not self.symbol.isdigit():
            raise ValueError("historical symbol must preserve six digits")
        values = np.asarray((*self.observation, self.gross_return), dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError("historical episode values must be finite")


class HistoricalCloseEnv(gym.Env[NDArray[np.float32], int]):
    """Binary daily decision sequence; future return is used only after action."""

    metadata = {"render_modes": []}

    def __init__(self, episodes: tuple[HistoricalEpisode, ...], *, cost_bp: int) -> None:
        super().__init__()
        if not episodes:
            raise ValueError("historical environment requires episodes")
        if cost_bp < 0:
            raise ValueError("cost_bp must be non-negative")
        self._episodes = episodes
        self._cost = cost_bp / 10_000.0
        self._index = 0
        self._terminated = False
        self.action_space = gym.spaces.Discrete(len(D2Action))
        self.observation_space = gym.spaces.Box(-10.0, 10.0, (OBSERVATION_WIDTH,), np.float32)

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[NDArray[np.float32], dict[str, Any]]:
        super().reset(seed=seed)
        self._index = 0
        self._terminated = False
        return self._observation(), {}

    def action_masks(self) -> NDArray[np.bool_]:
        return np.asarray([True, True], dtype=np.bool_)

    def step(
        self,
        action: int,
    ) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        if self._terminated:
            raise RuntimeError("cannot step after terminal state")
        try:
            selected = D2Action(action)
        except ValueError as exc:
            raise ValueError("action must be STOP or BUY") from exc
        episode = self._episodes[self._index]
        reward = episode.gross_return - self._cost if selected is D2Action.BUY else 0.0
        self._index += 1
        self._terminated = self._index == len(self._episodes)
        observation = self._terminal_observation() if self._terminated else self._observation()
        return observation, reward, self._terminated, False, {
            "decision_date": episode.decision_date,
            "symbol": episode.symbol,
            "action": int(selected),
            "gross_return": episode.gross_return,
            "cost_bp": int(round(self._cost * 10_000)),
        }

    def _observation(self) -> NDArray[np.float32]:
        return np.asarray(self._episodes[self._index].observation, dtype=np.float32)

    @staticmethod
    def _terminal_observation() -> NDArray[np.float32]:
        return np.zeros(OBSERVATION_WIDTH, dtype=np.float32)

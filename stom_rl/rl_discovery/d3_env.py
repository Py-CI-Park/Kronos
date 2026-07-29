"""Top-k daily-close action environment and registered D3 representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, assert_never

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_contract import D3PolicyArmId


Candidate = tuple[str, tuple[float, ...], float]


class D3EnvironmentError(ValueError):
    """A D3 episode, action, or environment contract is invalid."""


class D3TerminatedError(RuntimeError):
    """A caller attempted to step an already terminated D3 episode sequence."""


@dataclass(frozen=True, slots=True)
class D3Episode:
    """One date with five observable ranked candidates and post-action rewards."""

    decision_date: str
    candidates: tuple[Candidate, ...]
    market_context: tuple[float, ...]
    progress: float

    def __post_init__(self) -> None:
        if len(self.candidates) != 5 or len(self.market_context) != 14:
            raise D3EnvironmentError("D3 episode requires five candidates and 14 context values")
        if any(len(symbol) != 6 or not symbol.isdigit() or len(features) != 14 for symbol, features, _ in self.candidates):
            raise D3EnvironmentError("D3 candidates must retain six-digit symbols and 14 features")
        values = [self.progress, *self.market_context]
        for _, features, gross_return in self.candidates:
            values.extend((*features, gross_return))
        if not np.isfinite(np.asarray(values, dtype=np.float64)).all():
            raise D3EnvironmentError("D3 episode values must be finite")


@dataclass(frozen=True, slots=True)
class D3Representation:
    """Observation and action contract for one preregistered policy arm."""

    arm: D3PolicyArmId
    candidate_count: int
    include_market_context: bool

    @classmethod
    def for_arm(cls, arm: D3PolicyArmId) -> D3Representation:
        match arm:
            case D3PolicyArmId.TOP1_CONTEXT_1X:
                return cls(arm, 1, True)
            case D3PolicyArmId.TOP5_PLAIN_1X:
                return cls(arm, 5, False)
            case D3PolicyArmId.TOP5_CONTEXT_1X | D3PolicyArmId.TOP5_CONTEXT_4X:
                return cls(arm, 5, True)
            case unreachable:
                assert_never(unreachable)

    @property
    def action_count(self) -> int:
        return self.candidate_count + 1

    @property
    def observation_width(self) -> int:
        return self.candidate_count * 14 + (14 if self.include_market_context else 0) + 1

    def observation(self, episode: D3Episode) -> tuple[float, ...]:
        candidates = tuple(value for _, features, _ in episode.candidates[: self.candidate_count] for value in features)
        context = episode.market_context if self.include_market_context else ()
        return candidates + context + (episode.progress,)


class HistoricalTopKEnv(gym.Env[NDArray[np.float32], int]):
    """Daily STOP/top-k selection sequence; returns remain hidden until action."""

    metadata = {"render_modes": []}

    def __init__(self, episodes: tuple[D3Episode, ...], *, representation: D3Representation, cost_bp: int) -> None:
        super().__init__()
        if not episodes or cost_bp < 0:
            raise D3EnvironmentError("D3 environment requires episodes and non-negative cost")
        self._episodes = episodes
        self._representation = representation
        self._cost = cost_bp / 10_000
        self._index = 0
        self._terminated = False
        self.action_space = gym.spaces.Discrete(representation.action_count)
        self.observation_space = gym.spaces.Box(-10.0, 10.0, (representation.observation_width,), np.float32)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[NDArray[np.float32], dict[str, Any]]:
        super().reset(seed=seed)
        self._index = 0
        self._terminated = False
        return self._observation(), {}

    def action_masks(self) -> NDArray[np.bool_]:
        return np.ones(self._representation.action_count, dtype=np.bool_)

    def step(self, action: int) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        if self._terminated:
            raise D3TerminatedError("cannot step after terminal state")
        if not 0 <= action < self._representation.action_count:
            raise D3EnvironmentError("D3 action is outside the registered candidate set")
        episode = self._episodes[self._index]
        symbol = None
        gross_return = 0.0
        if action > 0:
            symbol, _, gross_return = episode.candidates[action - 1]
        reward = gross_return - self._cost if action > 0 else 0.0
        self._index += 1
        self._terminated = self._index == len(self._episodes)
        observation = np.zeros(self._representation.observation_width, np.float32) if self._terminated else self._observation()
        return observation, reward, self._terminated, False, {
            "decision_date": episode.decision_date,
            "symbol": symbol,
            "action": action,
            "gross_return": gross_return,
            "cost_bp": round(self._cost * 10_000),
        }

    def _observation(self) -> NDArray[np.float32]:
        return np.asarray(self._representation.observation(self._episodes[self._index]), dtype=np.float32)

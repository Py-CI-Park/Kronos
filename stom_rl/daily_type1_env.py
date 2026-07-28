"""Deterministic Type 1 closing-price Gymnasium environment.

A decision pair is represented by a mapping with point-in-time observation arrays and
post-commitment ``gross_returns``.  The latter is deliberately never used to build
an observation or action mask.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from typing import Any, Mapping, Sequence

import gymnasium as gym
import numpy as np

from stom_rl.daily_type1_accounting import PortfolioState, SlotOutcome, settle_session
from stom_rl.daily_type1_contract import (
    EXECUTION_PROXY,
    FEATURES,
    FRESH_OOS_END_DATE,
    FRESH_OOS_START_DATE,
    FRESH_OOS_ACCESS_ALLOWED,
    INITIAL_NAV_KRW,
    MAX_SLOTS,
    MISSING_ENTRY_POLICY,
    OFFICIAL_CLOSE,
    PARTITION_LABEL,
    PROXY_TIME,
    PROXY_TIMEZONE,
    RESEARCH_SPLIT_LABEL,
    SLOT_NOTIONAL_KRW,
    STABLE_SLOTS,
)

STOP = 0
ACTION_COUNT = STABLE_SLOTS + 1
EXTRACTOR_WIDTH = STABLE_SLOTS * len(FEATURES) * 2 + STABLE_SLOTS * 3 + 14
# Ten fixed 5M slots retain 10M of the 60M NAV.  The reserve prevents a
# non-self-financing eleventh selection; MAX_SLOTS is therefore the feasibility
# boundary, not merely an action-space preference.
_RESERVE_KRW = INITIAL_NAV_KRW - MAX_SLOTS * SLOT_NOTIONAL_KRW
if _RESERVE_KRW != 2 * SLOT_NOTIONAL_KRW:
    raise RuntimeError("frozen Type 1 cash reserve must be 10M KRW")

# These are the complete frozen input keys.  Post-decision fill availability is
# separate from decision-time eligibility and must be supplied explicitly so a
# missing execution record cannot become an optimistic fill.
_REQUIRED_PAIR_KEYS = frozenset((
    "decision_date", "settlement_date", "observation_cutoff_d1", "observation_cutoff_d2",
    "split_label", "partition_label", "fresh_oos_access_allowed", "execution_proxy",
    "proxy_time", "proxy_timezone", "official_close", "missing_entry_policy",
    "candidate_values", "candidate_missing", "availability_mask", "symbols",
    "gross_returns", "entry_available", "post_decision_fill_available",
))


def _binary_array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    """Validate 0/1 values before narrowing them to the frozen int8 schema."""
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a binary array of shape {shape}") from exc
    if array.shape != shape or array.dtype.kind not in "biuf":
        raise ValueError(f"{name} must be a binary array of shape {shape}")
    if array.dtype.kind == "f" and not np.isfinite(array).all():
        raise ValueError(f"{name} must be a binary array of shape {shape}")
    if not np.all((array == 0) | (array == 1)):
        raise ValueError(f"{name} must be a binary array of shape {shape}")
    return array.astype(np.int8, copy=True)


def _values(value: Any) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.shape != (STABLE_SLOTS, len(FEATURES)) or not np.isfinite(array).all():
        raise ValueError("candidate_values must be finite float32-compatible (500, 7)")
    if np.any(array < -10) or np.any(array > 10):
        raise ValueError("candidate_values must be normalized and clipped to [-10, 10]")
    return array.copy()


def _return_value(value: Any, slot: int) -> Decimal | None:
    """Parse an absent settlement distinctly from a malformed supplied value."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"gross_returns[{slot}] must be a finite Decimal-compatible value or None")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(f"gross_returns[{slot}] must be a finite Decimal-compatible value or None") from exc
    if not result.is_finite():
        raise ValueError(f"gross_returns[{slot}] must be a finite Decimal-compatible value or None")
    return result


def _pair_value(pair: Mapping[str, Any], name: str) -> Any:
    if name not in pair:
        raise ValueError(f"pair is missing {name}")
    return pair[name]


def _session_date(value: Any, name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 session date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 session date") from exc


def _normalize_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(pair, Mapping):
        raise TypeError("pairs must contain mappings")
    keys = set(pair)
    if keys != _REQUIRED_PAIR_KEYS:
        raise ValueError("pair has missing or unknown frozen-schema keys")
    decision_date = _session_date(_pair_value(pair, "decision_date"), "decision_date")
    settlement_date = _session_date(_pair_value(pair, "settlement_date"), "settlement_date")
    cutoff_d1 = _session_date(_pair_value(pair, "observation_cutoff_d1"), "observation_cutoff_d1")
    cutoff_d2 = _session_date(_pair_value(pair, "observation_cutoff_d2"), "observation_cutoff_d2")
    if not cutoff_d2 < cutoff_d1 < decision_date < settlement_date:
        raise ValueError("pair must order D-2 < D-1 < decision_date < settlement_date")
    fresh_oos_start = _session_date(FRESH_OOS_START_DATE, "fresh OOS start")
    fresh_oos_end = _session_date(FRESH_OOS_END_DATE, "fresh OOS end")
    if decision_date <= fresh_oos_end and settlement_date >= fresh_oos_start:
        raise ValueError("pair dates overlap the forbidden fresh OOS window")
    if pair["split_label"] != RESEARCH_SPLIT_LABEL or pair["partition_label"] != PARTITION_LABEL:
        raise ValueError("pair must be research-only historical-secondary, never fresh OOS")
    if pair["fresh_oos_access_allowed"] is not FRESH_OOS_ACCESS_ALLOWED:
        raise ValueError("pair must explicitly deny fresh OOS access")
    if pair["execution_proxy"] != EXECUTION_PROXY or pair["proxy_time"] != PROXY_TIME or pair["proxy_timezone"] != PROXY_TIMEZONE:
        raise ValueError("pair must use the exact 15:20 Asia/Seoul proxy")
    if pair["official_close"] is not OFFICIAL_CLOSE:
        raise ValueError("pair must explicitly reject official-close pricing")
    if pair["missing_entry_policy"] != MISSING_ENTRY_POLICY:
        raise ValueError("pair missing entries must be NO_FILL without fallback")
    values = _values(pair["candidate_values"])
    missing = _binary_array(pair["candidate_missing"], values.shape, "candidate_missing")
    availability = _binary_array(pair["availability_mask"], (STABLE_SLOTS,), "availability_mask")
    entry_available = _binary_array(pair["entry_available"], (STABLE_SLOTS,), "entry_available")
    if not np.array_equal(availability, entry_available):
        raise ValueError("availability_mask and entry_available must agree at the 15:20 decision")
    post_decision_fill_available = _binary_array(
        pair["post_decision_fill_available"],
        (STABLE_SLOTS,),
        "post_decision_fill_available",
    )
    symbols = pair["symbols"]
    if len(symbols) != STABLE_SLOTS or any(not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isdigit() for symbol in symbols):
        raise ValueError("symbols must contain exactly 500 six-digit strings")
    if len(set(symbols)) != STABLE_SLOTS:
        raise ValueError("symbols must be unique stable slots")
    raw_returns = pair["gross_returns"]
    try:
        if len(raw_returns) != STABLE_SLOTS:
            raise ValueError("gross_returns must contain exactly 500 slot values")
        gross_returns = tuple(_return_value(value, slot) for slot, value in enumerate(raw_returns))
    except TypeError as exc:
        raise ValueError("gross_returns must contain exactly 500 slot values") from exc
    return {
        "decision_date": decision_date,
        "settlement_date": settlement_date,
        "observation_cutoff_d1": cutoff_d1,
        "observation_cutoff_d2": cutoff_d2,
        "candidate_values": values,
        "candidate_missing": missing,
        "availability_mask": availability,
        "symbols": tuple(symbols),
        "gross_returns": gross_returns,
        "entry_available": entry_available,
        "post_decision_fill_available": post_decision_fill_available,
    }


def validate_type1_pairs(pairs: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Validate point-in-time, no-fresh-OOS pair inputs before an episode exists."""
    normalized = tuple(_normalize_pair(pair) for pair in pairs)
    if not normalized:
        raise ValueError("at least one two-session pair is required")
    symbols = normalized[0]["symbols"]
    previous_settlement: date | None = None
    for pair in normalized:
        if pair["symbols"] != symbols:
            raise ValueError("stable 500-slot symbol mapping must not change across pairs")
        if previous_settlement is not None and pair["decision_date"] <= previous_settlement:
            raise ValueError("pairs must not overlap: each decision follows the prior settlement")
        previous_settlement = pair["settlement_date"]
    return normalized


def decode_action(action: Any) -> int:
    """Validate the shared STOP/slot encoding and return its zero-based slot."""
    if isinstance(action, bool) or not isinstance(action, (int, np.integer)):
        raise ValueError("action must be an integer")
    value = int(action)
    if value < STOP or value >= ACTION_COUNT:
        raise ValueError("action must be STOP (0) or a stable slot (1..500)")
    return value - 1
def flatten_observation(observation: Mapping[str, np.ndarray]) -> np.ndarray:
    """Flatten the frozen Dict observation in extractor order without reordering slots."""
    expected = (
        "candidate_values",
        "candidate_missing",
        "availability_mask",
        "current_selection_mask",
        "prior_selection_mask",
        "portfolio_state",
    )
    if tuple(observation) != expected:
        raise ValueError("observation keys must use the frozen Type 1 insertion order")
    result = np.concatenate((
        np.asarray(observation["candidate_values"], dtype=np.float32).reshape(-1),
        np.asarray(observation["candidate_missing"], dtype=np.float32).reshape(-1),
        np.asarray(observation["availability_mask"], dtype=np.float32).reshape(-1),
        np.asarray(observation["current_selection_mask"], dtype=np.float32).reshape(-1),
        np.asarray(observation["prior_selection_mask"], dtype=np.float32).reshape(-1),
        np.asarray(observation["portfolio_state"], dtype=np.float32).reshape(-1),
    ))
    if result.shape != (EXTRACTOR_WIDTH,):
        raise ValueError("observation does not have the frozen 8514-wide Type 1 shape")
    return result


class Type1DictExtractor:
    """Parameterless frozen-order extractor shared by Type 1 policy wiring."""

    features_dim = EXTRACTOR_WIDTH

    def __call__(self, observation: Mapping[str, np.ndarray]) -> np.ndarray:
        return flatten_observation(observation)



class Type1ClosingEnv(gym.Env[dict[str, np.ndarray], int]):
    """One non-overlapping decision/fill/settlement pair per ten action calls."""

    metadata = {"render_modes": []}

    def __init__(self, pairs: Sequence[Mapping[str, Any]]) -> None:
        super().__init__()
        self._pairs = validate_type1_pairs(pairs)
        self.action_space = gym.spaces.Discrete(ACTION_COUNT)
        self.observation_space = gym.spaces.Dict({
            "candidate_values": gym.spaces.Box(-10, 10, (STABLE_SLOTS, len(FEATURES)), np.float32),
            "candidate_missing": gym.spaces.Box(0, 1, (STABLE_SLOTS, len(FEATURES)), np.int8),
            "availability_mask": gym.spaces.Box(0, 1, (STABLE_SLOTS,), np.int8),
            "current_selection_mask": gym.spaces.Box(0, 1, (STABLE_SLOTS,), np.int8),
            "prior_selection_mask": gym.spaces.Box(0, 1, (STABLE_SLOTS,), np.int8),
            "portfolio_state": gym.spaces.Box(
                np.array([0, 0, 1 / 6, -10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
                np.array([1, 1, 1, 10, 10, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=np.float32),
                dtype=np.float32,
            ),
        })
        self._state = PortfolioState()
        self._pair_index = 0
        self._call_index = 0
        self._selected: list[int] = []
        self._stop_latched = False
        self._prior_selected: list[int] = []
        self._prior_counts = (0, 0, 0)
        self._terminated = False
        self._terminal_observation: dict[str, np.ndarray] | None = None

    @property
    def extractor_width(self) -> int:
        return EXTRACTOR_WIDTH

    def action_masks(self) -> np.ndarray:
        mask = np.zeros(ACTION_COUNT, dtype=bool)
        if self._terminated:
            return mask
        mask[STOP] = True
        if not self._stop_latched and len(self._selected) < MAX_SLOTS:
            available = self._pairs[self._pair_index]["availability_mask"]
            for slot in np.flatnonzero(available):
                if int(slot) not in self._selected:
                    mask[int(slot) + 1] = True
        return mask

    def _progress(self) -> float:
        return 0.0 if len(self._pairs) == 1 else self._pair_index / (len(self._pairs) - 1)

    def _portfolio(self, *, terminal: bool = False, terminal_counts: tuple[int, int, int] = (0, 0, 0), call: int | None = None, progress: float | None = None) -> np.ndarray:
        nav_ratio = float(self._state.nav / Decimal(INITIAL_NAV_KRW))
        raw_drawdown = max(Decimal("0"), Decimal("1") - self._state.nav / self._state.high_water_nav)
        drawdown = float(raw_drawdown)
        navc, ddc = float(np.clip(nav_ratio, -10, 10)), float(np.clip(drawdown, 0, 10))
        clipped = float(nav_ratio != navc or drawdown != ddc)
        selected = len(self._selected)
        return np.asarray([
            (self._call_index if call is None else call) / MAX_SLOTS,
            selected / MAX_SLOTS,
            1.0 if terminal else (INITIAL_NAV_KRW - SLOT_NOTIONAL_KRW * selected) / INITIAL_NAV_KRW,
            navc, ddc,
            self._prior_counts[0] / MAX_SLOTS, self._prior_counts[1] / MAX_SLOTS, self._prior_counts[2] / MAX_SLOTS,
            terminal_counts[0] / MAX_SLOTS, terminal_counts[1] / MAX_SLOTS, terminal_counts[2] / MAX_SLOTS,
            self._progress() if progress is None else progress, clipped, float(terminal),
        ], dtype=np.float32)

    def _copy_terminal_observation(self) -> dict[str, np.ndarray]:
        if self._terminal_observation is None:
            raise RuntimeError("terminal observation was not frozen")
        return {name: value.copy() for name, value in self._terminal_observation.items()}

    def _freeze_terminal_observation(self, observation: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        self._terminal_observation = {name: value.copy() for name, value in observation.items()}
        return self._copy_terminal_observation()

    def _observation(self) -> dict[str, np.ndarray]:
        if self._terminated:
            if self._terminal_observation is not None:
                return self._copy_terminal_observation()
            zeros_values = np.zeros((STABLE_SLOTS, len(FEATURES)), dtype=np.float32)
            zeros_mask = np.zeros(STABLE_SLOTS, dtype=np.int8)
            prior = zeros_mask.copy()
            prior[self._prior_selected] = 1
            return {"candidate_values": zeros_values, "candidate_missing": np.zeros_like(zeros_values, dtype=np.int8),
                    "availability_mask": zeros_mask, "current_selection_mask": zeros_mask, "prior_selection_mask": prior,
                    "portfolio_state": self._portfolio(terminal=True)}
        pair = self._pairs[self._pair_index]
        current = np.zeros(STABLE_SLOTS, dtype=np.int8)
        current[self._selected] = 1
        prior = np.zeros(STABLE_SLOTS, dtype=np.int8)
        prior[self._prior_selected] = 1
        return {"candidate_values": pair["candidate_values"].copy(), "candidate_missing": pair["candidate_missing"].copy(),
                "availability_mask": pair["availability_mask"].copy(), "current_selection_mask": current,
                "prior_selection_mask": prior, "portfolio_state": self._portfolio()}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._state = PortfolioState()
        self._pair_index = self._call_index = 0
        self._selected, self._prior_selected = [], []
        self._prior_counts = (0, 0, 0)
        self._stop_latched = self._terminated = False
        self._terminal_observation = None
        return self._observation(), {}

    def _block(self, reason: str, *, trace_call: int | None = None) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        if self._terminated:
            return self._copy_terminal_observation(), -1.0, True, False, {
                "status": "BLOCK", "reason": reason, "event_reward": "-1.000000000000", "economic_reward": None,
            }
        pre_call, selected = self._call_index, len(self._selected)
        progress = self._progress()
        self._terminated = True
        observation = self._observation()
        observation["portfolio_state"] = self._portfolio(
            terminal=True,
            call=min(MAX_SLOTS, pre_call + 1 if trace_call is None else trace_call),
            progress=progress,
        )
        observation["portfolio_state"][1] = np.float32(selected / MAX_SLOTS)
        return self._freeze_terminal_observation(observation), -1.0, True, False, {
            "status": "BLOCK", "reason": reason, "event_reward": "-1.000000000000", "economic_reward": None,
        }

    def step(self, action: int):
        if self._terminated:
            return self._block("step_after_terminal")
        try:
            slot = decode_action(action)
        except ValueError as exc:
            return self._block(str(exc))
        if not self.action_masks()[int(action)]:
            return self._block("invalid_action")
        if action == STOP:
            self._stop_latched = True
        else:
            self._selected.append(slot)
        self._call_index += 1
        if self._call_index < MAX_SLOTS:
            return self._observation(), 0.0, False, False, {"status": "PENDING", "event_reward": "0.000000000000"}

        pair = self._pairs[self._pair_index]
        outcomes: list[SlotOutcome] = []
        for slot in self._selected:
            gross_return = pair["gross_returns"][slot]
            if not pair["post_decision_fill_available"][slot]:
                outcomes.append(SlotOutcome(pair["symbols"][slot], "NO_FILL"))
            elif gross_return is None:
                return self._block("missing_settlement", trace_call=MAX_SLOTS)
            else:
                outcomes.append(SlotOutcome(pair["symbols"][slot], "FILLED", gross_return))
        settlement = settle_session(self._state, outcomes)
        self._state = settlement.state
        counts = (len(outcomes), settlement.filled_slots, settlement.no_fill_slots)
        self._prior_selected, self._prior_counts = self._selected.copy(), counts
        final = self._pair_index == len(self._pairs) - 1
        if final:
            self._terminated = True
            observation = self._observation()
            observation["portfolio_state"] = self._portfolio(terminal=True, terminal_counts=counts, call=MAX_SLOTS, progress=1.0)
            observation["portfolio_state"][1] = np.float32(counts[0] / MAX_SLOTS)
            observation = self._freeze_terminal_observation(observation)
            return observation, float(settlement.reward), True, False, {"status": "SETTLED", "settlement": settlement, "event_reward": format(settlement.reward, "f"), "economic_reward": format(settlement.reward, "f")}
        self._pair_index += 1
        self._call_index, self._selected, self._stop_latched = 0, [], False
        return self._observation(), float(settlement.reward), False, False, {"status": "SETTLED", "settlement": settlement, "event_reward": format(settlement.reward, "f"), "economic_reward": format(settlement.reward, "f")}


def build_observation(env: Type1ClosingEnv) -> dict[str, np.ndarray]:
    """Expose the current immutable observation without offering an alternate path."""
    if not isinstance(env, Type1ClosingEnv):
        raise TypeError("env must be a Type1ClosingEnv")
    return env._observation()


def action_masks(env: Type1ClosingEnv) -> np.ndarray:
    """Shared train/evaluation action-mask adapter."""
    if not isinstance(env, Type1ClosingEnv):
        raise TypeError("env must be a Type1ClosingEnv")
    return env.action_masks()

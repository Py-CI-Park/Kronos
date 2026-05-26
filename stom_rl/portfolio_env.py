"""Fixed-shape portfolio environment for STOM RL candidates.

The first portfolio action contract is deliberately discrete and slot-based:

* ``0``: hold
* ``1..top_k_candidates``: buy the candidate slot
* ``top_k_candidates+1..top_k_candidates+max_positions``: sell the holding slot

Candidate and holding masks make padded slots explicit.  Invalid actions are
logged with reason codes and penalized instead of silently mutating the action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from .accounting import FLOAT_TOLERANCE, PortfolioAccount
from .trading_env import BoxSpace, DiscreteSpace


ACTION_HOLD = 0


def _float_or_zero(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class PortfolioEnvConfig:
    candidate_path: Optional[str] = None
    top_k_candidates: int = 3
    max_positions: int = 2
    initial_cash: float = 1_000_000.0
    buy_fraction: float = 0.25
    cost_bps: float = 25.0
    slippage_bps: float = 0.0
    invalid_action_penalty: float = 0.001
    seed: int = 100
    feature_columns: Optional[Tuple[str, ...]] = None


def synthetic_candidates() -> pd.DataFrame:
    """Small deterministic fixture used by smoke commands and contract tests."""

    base = pd.Timestamp("2025-01-03 09:00:00")
    rows: List[Dict[str, Any]] = []
    symbols = ["000001", "000002", "000003"]
    for t in range(8):
        for rank, symbol in enumerate(symbols):
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(seconds=t)).isoformat(),
                    "symbol": symbol,
                    "condition_id": "synthetic_momentum",
                    "passed": True,
                    "rank_score": float(3 - rank + t * 0.01),
                    "price": float(100 + rank * 5 + t * (rank + 1)),
                    "feature_momentum": float(t - rank),
                    "feature_liquidity": float(1000 - rank * 100),
                }
            )
    return pd.DataFrame(rows)


class PortfolioEnv:
    """Dependency-light portfolio RL environment over condition candidates."""

    metadata: ClassVar[Dict[str, Any]] = {"render_modes": []}

    def __init__(
        self,
        config: Optional[PortfolioEnvConfig] = None,
        *,
        candidates: Optional[pd.DataFrame] = None,
        **overrides: Any,
    ) -> None:
        if config is not None and overrides:
            raise ValueError("Pass either config or keyword overrides, not both.")
        self.config = config or PortfolioEnvConfig(**overrides)
        if self.config.top_k_candidates <= 0:
            raise ValueError("top_k_candidates must be positive")
        if self.config.max_positions <= 0:
            raise ValueError("max_positions must be positive")
        if not (0 < self.config.buy_fraction <= 1):
            raise ValueError("buy_fraction must be in (0, 1]")

        self.candidates = self._load_candidates(candidates)
        self.feature_columns = list(self.config.feature_columns or self._infer_feature_columns(self.candidates))
        self.candidate_width = 3 + len(self.feature_columns)
        self.holding_width = 4
        self.account_width = 3
        obs_width = (
            self.config.top_k_candidates * self.candidate_width
            + self.config.max_positions * self.holding_width
            + self.account_width
        )
        self.observation_space = BoxSpace((obs_width,), dtype=np.float32)
        self.action_space = DiscreteSpace(1 + self.config.top_k_candidates + self.config.max_positions)
        self._rng = np.random.default_rng(self.config.seed)
        self.timestamps: List[pd.Timestamp] = []
        self.current_step = 0
        self.account = PortfolioAccount(
            initial_cash=self.config.initial_cash,
            cost_bps=self.config.cost_bps,
            slippage_bps=self.config.slippage_bps,
        )
        self.last_prices: Dict[str, float] = {}
        self.peak_nav = float(self.config.initial_cash)
        self.invalid_actions: List[Dict[str, Any]] = []
        self.trade_log: List[Dict[str, Any]] = []
        self.nav_log: List[Dict[str, Any]] = []
        self.action_log: List[Dict[str, Any]] = []

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        del options
        self.timestamps = sorted(pd.Timestamp(ts) for ts in self.candidates["timestamp"].dropna().unique())
        if not self.timestamps:
            raise ValueError("candidate data has no timestamps")
        self.current_step = 0
        self.account = PortfolioAccount(
            initial_cash=self.config.initial_cash,
            cost_bps=self.config.cost_bps,
            slippage_bps=self.config.slippage_bps,
        )
        self.last_prices = {}
        self.peak_nav = float(self.config.initial_cash)
        self.invalid_actions = []
        self.trade_log = []
        self.nav_log = []
        self.action_log = []
        self._update_last_prices(self._current_candidates())
        info = self._info(event="reset")
        self.nav_log.append(self._nav_row(info))
        return self._observation(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action {action!r}; expected action < {self.action_space.n}.")
        if not self.timestamps:
            raise RuntimeError("Call reset() before step().")
        if self.current_step >= len(self.timestamps):
            raise RuntimeError("Episode is already terminated; call reset().")

        action = int(action)
        candidates = self._current_candidates()
        self._update_last_prices(candidates)
        prices_before = self._mark_prices(candidates)
        nav_before = self.account.nav(prices_before)
        action_mask = self.action_mask(candidates)
        invalid = not bool(action_mask[action])
        blocked_reason = "" if not invalid else self._blocked_reason(action, candidates)
        fill = None
        decoded = self.decode_action(action)

        if not invalid and action != ACTION_HOLD:
            if decoded["type"] == "buy":
                row = candidates.iloc[int(decoded["slot"])]
                symbol = str(row["symbol"])
                price = float(row["price"])
                max_notional = float(self.account.cash or 0.0) / (1.0 + self.account.cost_pct)
                notional = min(nav_before * float(self.config.buy_fraction), max_notional)
                fill = self.account.buy(
                    symbol=symbol,
                    price=price,
                    notional=notional,
                    timestamp=self._timestamp().isoformat(),
                )
            elif decoded["type"] == "sell":
                holdings = self._holding_symbols()
                symbol = holdings[int(decoded["slot"])]
                price = float(prices_before[symbol])
                fill = self.account.sell(
                    symbol=symbol,
                    price=price,
                    timestamp=self._timestamp().isoformat(),
                )
            if fill:
                self.trade_log.append(fill.to_dict())
        elif invalid:
            event = {
                "timestamp": self._timestamp().isoformat(),
                "action": action,
                "reason": blocked_reason,
                "decoded": decoded,
            }
            self.invalid_actions.append(event)

        self.current_step += 1
        terminated = self.current_step >= len(self.timestamps)
        next_candidates = self._current_candidates() if not terminated else candidates
        self._update_last_prices(next_candidates)
        prices_after = self._mark_prices(next_candidates)
        nav_after = self.account.nav(prices_after)
        self.peak_nav = max(self.peak_nav, nav_after)
        reward = (nav_after - nav_before) / max(nav_before, FLOAT_TOLERANCE)
        if invalid:
            reward -= float(self.config.invalid_action_penalty)
        info = self._info(
            event="step",
            action=action,
            decoded=decoded,
            invalid_action=invalid,
            blocked_reason=blocked_reason,
            reward=reward,
            nav_before=nav_before,
            nav_after=nav_after,
            terminated=terminated,
        )
        self.nav_log.append(self._nav_row(info))
        self.action_log.append(
            {
                "timestamp": info["timestamp"],
                "action": action,
                "action_type": decoded["type"],
                "slot": decoded.get("slot"),
                "invalid_action": invalid,
                "blocked_reason": blocked_reason,
                "reward": float(reward),
                "nav_after": nav_after,
            }
        )
        return self._observation(), float(reward), terminated, False, info

    def decode_action(self, action: int) -> Dict[str, Any]:
        if action == ACTION_HOLD:
            return {"type": "hold"}
        buy_end = self.config.top_k_candidates
        if 1 <= action <= buy_end:
            return {"type": "buy", "slot": action - 1}
        return {"type": "sell", "slot": action - buy_end - 1}

    def action_mask(self, candidates: Optional[pd.DataFrame] = None) -> np.ndarray:
        candidates = self._current_candidates() if candidates is None else candidates
        mask = np.zeros(self.action_space.n, dtype=np.int8)
        mask[ACTION_HOLD] = 1
        can_add_position = len(self.account.positions) < self.config.max_positions
        buy_cash = float(self.account.cash or 0.0) > FLOAT_TOLERANCE
        for slot in range(self.config.top_k_candidates):
            if slot < len(candidates):
                symbol = str(candidates.iloc[slot]["symbol"])
                if can_add_position and buy_cash and symbol not in self.account.positions:
                    mask[1 + slot] = 1
        holdings = self._holding_symbols()
        sell_offset = 1 + self.config.top_k_candidates
        for slot in range(min(len(holdings), self.config.max_positions)):
            mask[sell_offset + slot] = 1
        return mask

    def _load_candidates(self, candidates: Optional[pd.DataFrame]) -> pd.DataFrame:
        if candidates is None:
            if self.config.candidate_path:
                candidates = pd.read_csv(self.config.candidate_path, encoding="utf-8-sig")
            else:
                candidates = synthetic_candidates()
        required = {"timestamp", "symbol", "rank_score", "price"}
        missing = sorted(required - set(candidates.columns))
        if missing:
            raise ValueError(f"Portfolio candidates missing required columns: {missing}")
        frame = candidates.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame["symbol"] = frame["symbol"].astype(str)
        frame["rank_score"] = pd.to_numeric(frame["rank_score"], errors="coerce").fillna(0.0)
        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
        frame = frame.dropna(subset=["timestamp", "symbol", "price"])
        frame = frame[frame["price"] > 0].sort_values(["timestamp", "rank_score", "symbol"], ascending=[True, False, True])
        if frame.empty:
            raise ValueError("Portfolio candidates contain no valid rows")
        return frame.reset_index(drop=True)

    def _infer_feature_columns(self, frame: pd.DataFrame) -> Tuple[str, ...]:
        features = [column for column in frame.columns if column.startswith("feature_")]
        if "rank_score" not in features:
            features.insert(0, "rank_score")
        return tuple(features)

    def _timestamp(self) -> pd.Timestamp:
        idx = min(self.current_step, len(self.timestamps) - 1)
        return self.timestamps[idx]

    def _current_candidates(self) -> pd.DataFrame:
        if not self.timestamps:
            return pd.DataFrame(columns=self.candidates.columns)
        timestamp = self._timestamp()
        rows = self.candidates[self.candidates["timestamp"] == timestamp]
        return rows.sort_values(["rank_score", "symbol"], ascending=[False, True]).head(self.config.top_k_candidates).reset_index(drop=True)

    def _update_last_prices(self, candidates: pd.DataFrame) -> None:
        for _, row in candidates.iterrows():
            self.last_prices[str(row["symbol"])] = float(row["price"])

    def _mark_prices(self, candidates: pd.DataFrame) -> Dict[str, float]:
        prices = dict(self.last_prices)
        for _, row in candidates.iterrows():
            prices[str(row["symbol"])] = float(row["price"])
        for symbol, position in self.account.positions.items():
            prices.setdefault(symbol, position.average_price)
        return prices

    def _holding_symbols(self) -> List[str]:
        return sorted(self.account.positions)

    def _blocked_reason(self, action: int, candidates: pd.DataFrame) -> str:
        decoded = self.decode_action(action)
        if decoded["type"] == "buy":
            slot = int(decoded["slot"])
            if slot >= len(candidates):
                return "candidate_padding_slot"
            symbol = str(candidates.iloc[slot]["symbol"])
            if symbol in self.account.positions:
                return "already_holding_symbol"
            if len(self.account.positions) >= self.config.max_positions:
                return "max_positions_reached"
            if float(self.account.cash or 0.0) <= FLOAT_TOLERANCE:
                return "insufficient_cash"
        if decoded["type"] == "sell":
            slot = int(decoded["slot"])
            if slot >= len(self._holding_symbols()):
                return "holding_padding_slot"
        return "masked_action"

    def _observation(self) -> np.ndarray:
        candidates = self._current_candidates()
        prices = self._mark_prices(candidates)
        candidate_values: List[float] = []
        for slot in range(self.config.top_k_candidates):
            if slot < len(candidates):
                row = candidates.iloc[slot]
                price = float(row["price"])
                candidate_values.extend([1.0, price / 100_000.0, float(row["rank_score"])])
                for column in self.feature_columns:
                    candidate_values.append(_float_or_zero(row.get(column, 0.0)))
            else:
                candidate_values.extend([0.0] * self.candidate_width)

        holding_values: List[float] = []
        nav = self.account.nav(prices)
        for slot in range(self.config.max_positions):
            holdings = self._holding_symbols()
            if slot < len(holdings):
                symbol = holdings[slot]
                position = self.account.positions[symbol]
                price = float(prices[symbol])
                market_value = position.market_value(price)
                unrealized = (price - position.average_price) / position.average_price if position.average_price else 0.0
                holding_values.extend([1.0, position.quantity, unrealized, market_value / max(nav, FLOAT_TOLERANCE)])
            else:
                holding_values.extend([0.0] * self.holding_width)
        account_values = [
            float(self.account.cash or 0.0) / float(self.config.initial_cash),
            nav / float(self.config.initial_cash),
            (nav / max(self.peak_nav, FLOAT_TOLERANCE)) - 1.0,
        ]
        obs = np.asarray(candidate_values + holding_values + account_values, dtype=np.float32)
        return np.nan_to_num(obs, nan=0.0, posinf=10.0, neginf=-10.0)

    def _info(self, *, event: str, **extra: Any) -> Dict[str, Any]:
        candidates = self._current_candidates()
        prices = self._mark_prices(candidates)
        candidate_mask = [1 if slot < len(candidates) else 0 for slot in range(self.config.top_k_candidates)]
        holding_count = len(self._holding_symbols())
        holding_mask = [1 if slot < holding_count else 0 for slot in range(self.config.max_positions)]
        nav = self.account.nav(prices)
        info: Dict[str, Any] = {
            "event": event,
            "timestamp": self._timestamp().isoformat(),
            "current_step": int(self.current_step),
            "config": asdict(self.config),
            "candidate_mask": candidate_mask,
            "holding_mask": holding_mask,
            "action_mask": self.action_mask(candidates).tolist(),
            "nav": nav,
            "cash": float(self.account.cash or 0.0),
            "positions": self.account.snapshot(prices)["positions"],
            "trade_count": int(self.account.trade_count),
            "invalid_action_count": len(self.invalid_actions),
        }
        info.update(extra)
        return info

    def _nav_row(self, info: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "timestamp": info["timestamp"],
            "step": info["current_step"],
            "nav": info["nav"],
            "cash": info["cash"],
            "position_count": len(info["positions"]),
        }

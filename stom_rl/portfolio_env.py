"""Fixed-shape portfolio environment for STOM RL candidates.

The first portfolio action contract is deliberately discrete and slot-based:

* ``0``: hold
* ``1..top_k_candidates``: buy the candidate slot
* ``top_k_candidates+1..top_k_candidates+max_positions``: sell the holding slot

Candidate and holding masks make padded slots explicit.  Invalid raw actions are
logged, counted, and executed as HOLD/no-fill while the clock still advances.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import warnings
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from .accounting import (
    FLOAT_TOLERANCE,
    LEGACY_SCALAR_COST_MODEL,
    PortfolioAccount,
    V5_SIDE_COMPONENT_COST_MODEL,
)
from .symbol_norm import normalize_symbol_series, read_candidates_csv
from .trading_env import BoxSpace, DiscreteSpace
from .v5_accounting import scenario_for_cost



ACTION_HOLD = 0
SB3_ACCOUNTING_HORIZON = "SB3_T_DECIDE_T1_FILL_STATEFUL_V1"
SB3_LEGACY_SCALAR_ACCOUNTING_HORIZON = "SB3_LEGACY_SCALAR_T_DECIDE_T1_FILL_V0"
SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON = "SB3_SYNTHETIC_SAME_BAR_FILL_LEGACY_V0"

REWARD_MODE_SHAPED = "shaped"
REWARD_MODE_ECONOMIC_ONLY = "economic_only"
VALID_REWARD_MODES = {REWARD_MODE_SHAPED, REWARD_MODE_ECONOMIC_ONLY}
MONEY_QUANT = Decimal("0.000001")


def _float_or_zero(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_bool(value: Any) -> bool:
    """Coerce CSV/JSON truthy markers (``True``/``"true"``/``1``) to ``bool``."""

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _legacy_scalar_cost_label(config: "PortfolioEnvConfig") -> str:
    total_bp = float(config.cost_bps) + float(config.slippage_bps)
    if config.legacy_scalar_cost_label:
        label = str(config.legacy_scalar_cost_label)
        if label in {"zero_control_0bp", "base_23bp", "stress_46bp"}:
            raise ValueError("legacy scalar cost labels cannot reuse V5 component scenario ids")
        return label
    return f"legacy_scalar_split_{total_bp:g}bp_round_trip"


def _account_cost_kwargs(config: "PortfolioEnvConfig") -> Dict[str, Any]:
    if config.accounting_horizon == SB3_ACCOUNTING_HORIZON and float(config.slippage_bps) == 0.0:
        try:
            scenario = scenario_for_cost(config.cost_bps, config.cost_scenario_id)
        except ValueError:
            scenario = None
        if scenario is not None:
            return {
                "cost_bps": float(scenario.total_bp),
                "slippage_bps": 0.0,
                "cost_scenario_id": scenario.scenario_id,
                "cost_model": V5_SIDE_COMPONENT_COST_MODEL,
                "accounting_horizon": SB3_ACCOUNTING_HORIZON,
                "sell_tax_bps": float(scenario.sell_tax_bp),
                "buy_commission_bps": float(scenario.buy_commission_bp),
                "sell_commission_bps": float(scenario.sell_commission_bp),
                "buy_slippage_bps": float(scenario.buy_slippage_bp),
                "sell_slippage_bps": float(scenario.sell_slippage_bp),
            }
    if config.cost_scenario_id is not None:
        raise ValueError("cost_scenario_id requires a V5 0/23/46 component schedule with slippage_bps=0.0")
    return {
        "cost_bps": float(config.cost_bps) / 2.0,
        "slippage_bps": float(config.slippage_bps) / 2.0,
        "cost_scenario_id": _legacy_scalar_cost_label(config),
        "cost_model": LEGACY_SCALAR_COST_MODEL,
        "accounting_horizon": (
            config.accounting_horizon
            if config.accounting_horizon != SB3_ACCOUNTING_HORIZON
            else SB3_LEGACY_SCALAR_ACCOUNTING_HORIZON
        ),
    }


def canonical_money(value: Any) -> str:
    """Canonical six-decimal money string with signed zero normalized away."""

    amount = Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    if amount == 0:
        amount = abs(amount)
    return str(amount)


def _money_decimal(value: Any) -> Decimal:
    return Decimal(canonical_money(value))


def _canonical_float(value: Any) -> float:
    result = float(value)
    return 0.0 if canonical_money(result) == "0.000000" else result


def _fill_row(fill: Any, *, terminal_liquidation: bool) -> Dict[str, Any]:
    row = fill.to_dict()
    for key in (
        "price",
        "quantity",
        "gross_value",
        "cost",
        "cash_after",
        "realized_pnl",
        "sell_tax_bp",
        "buy_commission_bp",
        "sell_commission_bp",
        "buy_slippage_bp",
        "sell_slippage_bp",
        "sell_tax_krw",
        "buy_commission_krw",
        "sell_commission_krw",
        "buy_slippage_krw",
        "sell_slippage_krw",
        "total_cost_krw",
    ):
        if key in row:
            row[key] = _canonical_float(row[key])

    row["terminal_liquidation"] = bool(terminal_liquidation)
    return row


@dataclass(frozen=True)
class PortfolioEnvConfig:
    candidate_path: Optional[str] = None
    top_k_candidates: int = 3
    max_positions: int = 2
    initial_cash: float = 1_000_000.0
    buy_fraction: float = 0.25
    cost_bps: float = 23.0
    slippage_bps: float = 0.0
    invalid_action_penalty: float = 0.001
    # SB3_T_DECIDE_T1_FILL_STATEFUL_V1 reward:
    #   economic nav return includes execution costs in cash/NAV;
    #   shaped reward = nav_return - turnover_penalty_lambda * turnover_ratio
    #                   - invalid_action_penalty * invalid.

    turnover_penalty_lambda: float = 0.001
    reward_mode: str = REWARD_MODE_SHAPED
    terminal_liquidation: bool = True
    cost_scenario_id: Optional[str] = None
    legacy_scalar_cost_label: Optional[str] = None
    accounting_horizon: str = SB3_ACCOUNTING_HORIZON
    allow_legacy_same_bar_fill: bool = False
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
                    "fill_price": float(100 + rank * 5 + (t + 1) * (rank + 1)) if t + 1 < 8 else np.nan,
                    "fillable": t + 1 < 8,
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
        if self.config.reward_mode not in VALID_REWARD_MODES:
            raise ValueError(f"reward_mode must be one of: {sorted(VALID_REWARD_MODES)}")

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
        self.account = self._new_account()

        self.last_prices: Dict[str, float] = {}
        self.peak_nav = float(self.config.initial_cash)
        self.invalid_actions: List[Dict[str, Any]] = []
        self.trade_log: List[Dict[str, Any]] = []
        self.nav_log: List[Dict[str, Any]] = []
        self.action_log: List[Dict[str, Any]] = []

    def _new_account(self) -> PortfolioAccount:
        return PortfolioAccount(
            initial_cash=self.config.initial_cash,
            **_account_cost_kwargs(self.config),
        )

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
        self.account = self._new_account()
        self.last_prices = {}
        self.peak_nav = float(self.config.initial_cash)
        self.invalid_actions = []
        self.trade_log = []
        self.nav_log = []
        self.action_log = []
        self._update_last_prices(self._current_frame())
        info = self._info(event="reset")
        self.nav_log.append(self._nav_row(info))
        return self._observation(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if not self.timestamps:
            raise RuntimeError("Call reset() before step().")
        if self.current_step >= len(self.timestamps):
            raise RuntimeError("Episode is already terminated; call reset().")

        try:
            action_int = int(np.asarray(action).item())
        except (TypeError, ValueError):
            action_int = -1
        decision_timestamp = self._timestamp().isoformat()
        current_frame = self._current_frame()
        candidates = self._current_candidates()
        self._update_last_prices(current_frame)
        prices_before = self._mark_prices(current_frame)
        nav_before = self.account.nav(prices_before)
        action_mask = self.action_mask(candidates)
        in_space = self.action_space.contains(action_int)
        decoded = self.decode_action(action_int) if in_space else {"type": "unknown", "raw_action": action_int}
        invalid = (not in_space) or not bool(action_mask[action_int])
        blocked_reason = ""
        if invalid:
            blocked_reason = "action_out_of_space" if not in_space else self._blocked_reason(action_int, candidates)
        executed_action = ACTION_HOLD if invalid else action_int
        executed_decoded = {"type": "hold"} if invalid else decoded
        fills: List[Dict[str, Any]] = []

        if not invalid and action_int != ACTION_HOLD:
            # T+1 fill contract: the decision uses the close at T (observation /
            # `prices_before`), but the order fills at the next-bar `fill_price`.
            fill = None
            if decoded["type"] == "buy":
                row = candidates.iloc[int(decoded["slot"])]
                symbol = str(row["symbol"])
                fill_price = self._execution_fill_price_for(
                    symbol,
                    row,
                    float(row["price"]),
                )
                if fill_price is None:
                    raise ValueError(f"Missing T+1 fill_price for buy fill: {symbol}")

                if self._uses_official_v5_stateful_components():
                    quantity = self._official_v5_buy_quantity(
                        price=fill_price,
                        nav_before=nav_before,
                    )
                    if quantity <= 0:
                        raise ValueError(
                            f"Insufficient cash for one V5 buy lot: {symbol}"
                        )
                    fill = self.account.buy(
                        symbol=symbol,
                        price=fill_price,
                        quantity=float(quantity),
                        timestamp=decision_timestamp,
                    )
                elif self._uses_legacy_scalar_costs():
                    notional = self._legacy_scalar_buy_notional(
                        nav_before=nav_before
                    )
                    if notional <= FLOAT_TOLERANCE:
                        raise ValueError(
                            f"Insufficient cash for legacy scalar buy: {symbol}"
                        )
                    fill = self.account.buy(
                        symbol=symbol,
                        price=fill_price,
                        notional=notional,
                        timestamp=decision_timestamp,
                    )
                else:
                    max_notional = float(self.account.cash or 0.0) / (
                        1.0 + self.account.cost_pct
                    )
                    notional = min(
                        nav_before * float(self.config.buy_fraction),
                        max_notional,
                    )
                    fill = self.account.buy(
                        symbol=symbol,
                        price=fill_price,
                        notional=notional,
                        timestamp=decision_timestamp,
                    )
            elif decoded["type"] == "sell":
                holdings = self._holding_symbols()
                symbol = holdings[int(decoded["slot"])]
                fill_price = self._execution_fill_price_for(symbol, self._candidate_row_for(symbol, current_frame), float(prices_before[symbol]))
                if fill_price is None:
                    raise ValueError(f"Missing T+1 fill_price for sell fill: {symbol}")

                fill = self.account.sell(
                    symbol=symbol,
                    price=fill_price,
                    timestamp=decision_timestamp,
                )
            if fill:
                row = _fill_row(fill, terminal_liquidation=False)
                fills.append(row)
                self.trade_log.append(row)
        elif invalid:
            event = {
                "timestamp": decision_timestamp,
                "raw_action": action_int,
                "action": action_int,
                "executed_action": ACTION_HOLD,
                "reason": blocked_reason,
                "decoded": decoded,
            }
            self.invalid_actions.append(event)

        self.current_step += 1
        terminated = self.current_step >= len(self.timestamps)
        next_frame = self._current_frame() if not terminated else current_frame
        self._update_last_prices(next_frame)
        prices_after = self._mark_prices(next_frame)
        terminal_fills: List[Dict[str, Any]] = []
        if terminated and self.config.terminal_liquidation and self.account.positions:
            terminal_fills = self._liquidate_positions(prices_after, self._timestamp().isoformat())
            fills.extend(terminal_fills)
            self.trade_log.extend(terminal_fills)
            prices_after = self._mark_prices(next_frame)
        nav_after = self.account.nav(prices_after)
        self.peak_nav = max(self.peak_nav, nav_after)
        nav_return = (nav_after - nav_before) / max(nav_before, FLOAT_TOLERANCE)
        turnover_krw = sum(float(row.get("gross_value", 0.0)) for row in fills)
        turnover_ratio = turnover_krw / max(nav_before, FLOAT_TOLERANCE)
        execution_cost = sum(float(row.get("cost", 0.0)) for row in fills)
        reward = nav_return
        if self.config.reward_mode == REWARD_MODE_SHAPED:
            reward -= float(self.config.turnover_penalty_lambda) * turnover_ratio

            if invalid:
                reward -= float(self.config.invalid_action_penalty)

        info = self._info(
            event="step",
            action=action_int,
            raw_action=action_int,
            decoded=decoded,
            executed_action=executed_action,
            executed_decoded=executed_decoded,
            invalid_action=invalid,
            blocked_reason=blocked_reason,
            reward=reward,
            reward_mode=self.config.reward_mode,
            accounting_horizon=self.account.accounting_horizon,

            nav_before=nav_before,
            nav_after=nav_after,
            nav_return=nav_return,
            turnover_krw=turnover_krw,
            turnover_ratio=turnover_ratio,

            execution_cost=execution_cost,
            fills=fills,
            terminal_liquidation_count=len(terminal_fills),
            terminated=terminated,
        )
        self.nav_log.append(self._nav_row(info))
        self.action_log.append(
            {
                "timestamp": info["timestamp"],
                "raw_action": action_int,
                "action": executed_action,
                "requested_action": action_int,
                "action_type": executed_decoded["type"],
                "slot": executed_decoded.get("slot"),
                "invalid_action": invalid,
                "blocked_reason": blocked_reason,
                "reward": float(reward),
                "nav_after": nav_after,
                "turnover_krw": turnover_krw,
                "turnover_ratio": turnover_ratio,
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
        current_frame = self._current_frame()
        nav_before = (
            self.account.nav(self._mark_prices(current_frame))
            if self._uses_cost_reserved_buy_sizing()
            else None
        )
        for slot in range(self.config.top_k_candidates):
            if slot < len(candidates):
                row = candidates.iloc[slot]
                symbol = str(row["symbol"])
                # Only enable a buy slot with a real T+1 fill price unless the
                # caller explicitly selected the synthetic same-bar legacy horizon.
                fill_price = self._execution_fill_price_for(
                    symbol,
                    row,
                    float(row["price"]),
                )
                fillable = fill_price is not None
                affordable_buy = True
                if fillable and nav_before is not None:
                    if self._uses_official_v5_stateful_components():
                        affordable_buy = self._official_v5_buy_quantity(
                            price=float(fill_price),
                            nav_before=float(nav_before),
                        ) > 0
                    elif self._uses_legacy_scalar_costs():
                        affordable_buy = (
                            self._legacy_scalar_buy_notional(
                                nav_before=float(nav_before)
                            )
                            > FLOAT_TOLERANCE
                        )
                if (
                    can_add_position
                    and buy_cash
                    and fillable
                    and affordable_buy
                    and symbol not in self.account.positions
                ):
                    mask[1 + slot] = 1
        holdings = self._holding_symbols()
        sell_offset = 1 + self.config.top_k_candidates
        for slot, symbol in enumerate(holdings[: self.config.max_positions]):
            row = self._candidate_row_for(symbol, current_frame)
            if row is not None:
                mark_price = float(row["price"])
            else:
                mark_price = self.last_prices.get(symbol)
            if (
                self._execution_fill_price_for(symbol, row, mark_price)
                is not None
            ):
                mask[sell_offset + slot] = 1
        return mask


    def _load_candidates(self, candidates: Optional[pd.DataFrame]) -> pd.DataFrame:
        if candidates is None:
            if self.config.candidate_path:
                candidates = read_candidates_csv(self.config.candidate_path)
            else:
                candidates = synthetic_candidates()
        required = {"timestamp", "symbol", "rank_score", "price"}
        missing = sorted(required - set(candidates.columns))
        if missing:
            raise ValueError(f"Portfolio candidates missing required columns: {missing}")
        frame = candidates.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        # Canonical symbol form (6-digit zero-pad for all-digit Korean codes;
        # non-numeric synthetic symbols left unchanged) so the holding key,
        # sell-lookup and mask all match regardless of whether candidates came
        # from a CSV (int-stripped) or in-memory.
        frame["symbol"] = normalize_symbol_series(frame["symbol"])
        frame["rank_score"] = pd.to_numeric(frame["rank_score"], errors="coerce").fillna(0.0)
        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
        # T+1 fill contract (Page 9/10): `price` is the decision-bar close at T;
        # trades fill at `fill_price` (the next-bar close). Official/stateful
        # candidates must carry this column. Same-bar fallback is allowed only
        # for callers that explicitly select the synthetic legacy horizon.

        if "fill_price" in frame.columns:
            frame["fill_price"] = pd.to_numeric(frame["fill_price"], errors="coerce")
            if "fillable" in frame.columns:
                frame["fillable"] = frame["fillable"].map(_as_bool).astype(bool)
            else:
                frame["fillable"] = frame["fill_price"].notna()
            # Unfillable rows have no real T+1 price; never fabricate one.
            frame.loc[~frame["fillable"], "fill_price"] = np.nan
            bad_fillable = frame["fillable"] & frame["fill_price"].isna()
            if bool(bad_fillable.any()):
                raise ValueError("Portfolio candidates mark fillable rows without a T+1 fill_price")
        else:
            if not (
                self.config.allow_legacy_same_bar_fill
                and self.config.accounting_horizon == SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON
            ):
                raise ValueError(
                    "Portfolio candidates require a 'fill_price' column for "
                    f"{SB3_ACCOUNTING_HORIZON}; use the explicit synthetic legacy "
                    "horizon only for deterministic same-bar fixtures."
                )
            warnings.warn(
                "Portfolio candidates lack a 'fill_price' column; using explicit "
                "synthetic legacy same-bar fills. This horizon cannot claim V5 "
                "T+1 stateful accounting.",
                RuntimeWarning,
                stacklevel=2,
            )
            frame["fill_price"] = frame["price"]
            frame["fillable"] = frame["price"] > 0

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

    def _current_frame(self) -> pd.DataFrame:
        if not self.timestamps:
            return pd.DataFrame(columns=self.candidates.columns)
        timestamp = self._timestamp()
        rows = self.candidates[self.candidates["timestamp"] == timestamp]
        return rows.sort_values(["rank_score", "symbol"], ascending=[False, True]).reset_index(drop=True)

    def _current_candidates(self) -> pd.DataFrame:
        return self._current_frame().head(self.config.top_k_candidates).reset_index(drop=True)

    def _candidate_row_for(self, symbol: str, candidates: pd.DataFrame) -> Optional[pd.Series]:
        """Return the current-timestamp candidate row for ``symbol`` if present."""

        if candidates.empty:
            return None
        matches = candidates[candidates["symbol"].astype(str) == str(symbol)]
        if matches.empty:
            return None
        return matches.iloc[0]

    def _fill_price_for(self, symbol: str, row: Optional[pd.Series]) -> Optional[float]:
        """T+1 fill price for ``symbol`` from a candidate ``row``.

        Returns the row's ``fill_price`` when present and fillable, otherwise
        ``None``. Official stateful callers must not replace ``None`` with the
        decision-bar mark.

        """

        del symbol  # kept for call-site readability; lookup is row-scoped
        if row is None:
            return None
        if "fillable" in row.index and not _as_bool(row.get("fillable", True)):
            return None
        fill_value = row.get("fill_price") if "fill_price" in row.index else None
        if fill_value is None or pd.isna(fill_value):
            return None
        fill_price = float(fill_value)
        return fill_price if fill_price > 0 else None

    def _uses_legacy_same_bar_fill(self) -> bool:
        return bool(
            self.config.allow_legacy_same_bar_fill
            and self.config.accounting_horizon == SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON
        )

    def _execution_fill_price_for(
        self,
        symbol: str,
        row: Optional[pd.Series],
        mark_price: Optional[float],
    ) -> Optional[float]:
        fill_price = self._fill_price_for(symbol, row)
        if fill_price is not None:
            return fill_price
        if not self._uses_legacy_same_bar_fill() or mark_price is None:
            return None
        mark = float(mark_price)
        return mark if mark > 0 else None

    def _uses_official_v5_stateful_components(self) -> bool:
        return (
            self.account.accounting_horizon == SB3_ACCOUNTING_HORIZON
            and self.account.cost_model == V5_SIDE_COMPONENT_COST_MODEL
        )

    def _uses_legacy_scalar_costs(self) -> bool:
        return self.account.cost_model == LEGACY_SCALAR_COST_MODEL

    def _uses_cost_reserved_buy_sizing(self) -> bool:
        return (
            self._uses_official_v5_stateful_components()
            or self._uses_legacy_scalar_costs()
        )

    def _buy_side_rate(self) -> Decimal:
        components = self.account.cost_component_bps()
        return (
            Decimal(str(components["buy_commission_bp"]))
            + Decimal(str(components["buy_slippage_bp"]))
        ) / Decimal("10000")

    def _buy_cash_needed_for_gross(self, gross: Decimal) -> Decimal:
        components = self.account.cost_component_bps()
        buy_commission = _money_decimal(
            gross
            * Decimal(str(components["buy_commission_bp"]))
            / Decimal("10000")
        )
        buy_slippage = _money_decimal(
            gross
            * Decimal(str(components["buy_slippage_bp"]))
            / Decimal("10000")
        )
        return gross + buy_commission + buy_slippage

    def _official_v5_buy_cash_needed(
        self,
        *,
        price: float,
        quantity: int,
    ) -> Decimal:
        gross = Decimal(str(float(price) * float(quantity)))
        return self._buy_cash_needed_for_gross(gross)

    def _official_v5_buy_quantity(self, *, price: float, nav_before: float) -> int:
        if price <= 0:
            return 0
        price_dec = Decimal(str(price))
        cash_dec = Decimal(str(float(self.account.cash or 0.0)))
        target_notional = Decimal(str(nav_before)) * Decimal(
            str(self.config.buy_fraction)
        )
        target_quantity = (
            int(target_notional / price_dec) if target_notional > 0 else 0
        )
        buy_rate = self._buy_side_rate()
        affordable_quantity = (
            int(cash_dec / (price_dec * (Decimal("1") + buy_rate)))
            if cash_dec > 0
            else 0
        )
        quantity = min(target_quantity, affordable_quantity)
        tolerance = Decimal(str(FLOAT_TOLERANCE))
        while (
            quantity > 0
            and self._official_v5_buy_cash_needed(price=price, quantity=quantity)
            > cash_dec + tolerance
        ):
            quantity -= 1
        return max(0, quantity)

    def _legacy_scalar_buy_notional(self, *, nav_before: float) -> float:
        cash_dec = Decimal(str(float(self.account.cash or 0.0)))
        target_notional = Decimal(str(nav_before)) * Decimal(
            str(self.config.buy_fraction)
        )
        buy_rate = self._buy_side_rate()
        affordable_notional = (
            cash_dec / (Decimal("1") + buy_rate)
            if cash_dec > 0
            else Decimal("0")
        )
        notional = min(target_notional, affordable_notional)
        tolerance = Decimal(str(FLOAT_TOLERANCE))
        while (
            notional > 0
            and self._buy_cash_needed_for_gross(notional) > cash_dec + tolerance
        ):
            notional -= MONEY_QUANT
        return float(max(Decimal("0"), notional))


    def _update_last_prices(self, candidates: pd.DataFrame) -> None:
        for _, row in candidates.iterrows():
            self.last_prices[str(row["symbol"])] = float(row["price"])

    def _mark_prices(self, candidates: pd.DataFrame) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for _, row in candidates.iterrows():
            prices[str(row["symbol"])] = float(row["price"])
        missing = [symbol for symbol, position in self.account.positions.items() if position.quantity > FLOAT_TOLERANCE and symbol not in prices]
        if missing:
            raise KeyError(f"Missing mark price for held symbol(s): {', '.join(sorted(missing))}")
        return prices

    def _holding_symbols(self) -> List[str]:
        return sorted(self.account.positions)

    def _liquidate_positions(self, prices: Mapping[str, float], timestamp: str) -> List[Dict[str, Any]]:
        fills: List[Dict[str, Any]] = []
        for symbol in self._holding_symbols():
            if symbol not in prices:
                raise KeyError(f"Missing mark price for held symbol: {symbol}")
            fill = self.account.sell(symbol=symbol, price=float(prices[symbol]), timestamp=timestamp)
            fills.append(_fill_row(fill, terminal_liquidation=True))
        return fills

    def _blocked_reason(self, action: int, candidates: pd.DataFrame) -> str:
        decoded = self.decode_action(action)
        if decoded["type"] == "buy":
            slot = int(decoded["slot"])
            if slot >= len(candidates):
                return "candidate_padding_slot"
            row = candidates.iloc[slot]
            symbol = str(row["symbol"])
            if symbol in self.account.positions:
                return "already_holding_symbol"
            if len(self.account.positions) >= self.config.max_positions:
                return "max_positions_reached"
            if float(self.account.cash or 0.0) <= FLOAT_TOLERANCE:
                return "insufficient_cash"
            fill_price = self._execution_fill_price_for(
                symbol,
                row,
                float(row["price"]),
            )
            if fill_price is None:
                return "unfillable_no_t1"
            if self._uses_official_v5_stateful_components():
                nav_before = self.account.nav(
                    self._mark_prices(self._current_frame())
                )
                if (
                    self._official_v5_buy_quantity(
                        price=fill_price,
                        nav_before=nav_before,
                    )
                    <= 0
                ):
                    return "insufficient_cash_for_lot"
            elif self._uses_legacy_scalar_costs():
                nav_before = self.account.nav(
                    self._mark_prices(self._current_frame())
                )
                if (
                    self._legacy_scalar_buy_notional(nav_before=nav_before)
                    <= FLOAT_TOLERANCE
                ):
                    return "insufficient_cash"

        if decoded["type"] == "sell":
            slot = int(decoded["slot"])
            if slot >= len(self._holding_symbols()):
                return "holding_padding_slot"
            holdings = self._holding_symbols()
            symbol = holdings[slot]
            row = self._candidate_row_for(symbol, self._current_frame())
            if row is not None:
                mark_price = float(row["price"])
            else:
                mark_price = self.last_prices.get(symbol)
            if self._execution_fill_price_for(symbol, row, mark_price) is None:
                return "unfillable_no_t1"
        return "masked_action"

    def _observation(self) -> np.ndarray:
        candidates = self._current_candidates()
        prices = self._mark_prices(self._current_frame())
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
        prices = self._mark_prices(self._current_frame())
        candidate_mask = [1 if slot < len(candidates) else 0 for slot in range(self.config.top_k_candidates)]
        holding_count = len(self._holding_symbols())
        holding_mask = [1 if slot < holding_count else 0 for slot in range(self.config.max_positions)]
        nav = _canonical_float(self.account.nav(prices))
        cash = _canonical_float(self.account.cash or 0.0)
        snapshot = self.account.snapshot(prices)
        config_payload = asdict(self.config)
        config_payload["configured_accounting_horizon"] = config_payload.get("accounting_horizon")
        config_payload["accounting_horizon"] = self.account.accounting_horizon
        config_payload["cost_scenario_id"] = self.account.effective_cost_scenario_id
        config_payload["cost_model"] = self.account.cost_model

        info: Dict[str, Any] = {
            "event": event,
            "timestamp": self._timestamp().isoformat(),
            "current_step": int(self.current_step),
            "config": config_payload,
            "candidate_mask": candidate_mask,
            "holding_mask": holding_mask,
            "action_mask": self.action_mask(candidates).tolist(),
            "nav": nav,
            "nav_money": canonical_money(nav),
            "cash": cash,
            "cash_money": canonical_money(cash),
            "positions": snapshot["positions"],
            "trade_count": int(self.account.trade_count),
            "invalid_action_count": len(self.invalid_actions),
            "accounting_horizon": self.account.accounting_horizon,
            "cost_scenario_id": self.account.effective_cost_scenario_id,
            "cost_model": self.account.cost_model,
            "cost_components": self.account.cost_component_bps(),
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

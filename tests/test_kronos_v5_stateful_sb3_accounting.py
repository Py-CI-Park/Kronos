from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stom_rl import portfolio_sb3_train as trainer
from stom_rl.portfolio_env import (
    SB3_ACCOUNTING_HORIZON,
    SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON,
    PortfolioEnv,
    PortfolioEnvConfig,
    canonical_money,
)


_ORACLE_PATH = Path(__file__).with_name("oracles") / "v5_stateful_sb3_oracle.py"
_ORACLE_SPEC = importlib.util.spec_from_file_location("v5_stateful_sb3_oracle", _ORACLE_PATH)
assert _ORACLE_SPEC and _ORACLE_SPEC.loader
oracle = importlib.util.module_from_spec(_ORACLE_SPEC)
_ORACLE_SPEC.loader.exec_module(oracle)

ACTIONS = [1, 2, 99, 4, 0]
_COMPONENT_KEYS = (
    "buy_commission_krw",
    "buy_slippage_krw",
    "sell_tax_krw",
    "sell_commission_krw",
    "sell_slippage_krw",
)


def _sum_fill_money(step_fills: list[dict[str, object]], key: str) -> str:
    return canonical_money(sum(float(fill.get(key, 0.0)) for fill in step_fills))



def _stateful_candidates() -> pd.DataFrame:
    base = pd.Timestamp("2026-07-01 15:30:00")
    price_plan = {
        "000003": [100, 110, 120, 130, 140],
        "000001": [200, 220, 230, 240, 250],
        "000002": [300, 330, 340, 350, 360],
    }
    ranks = {"000003": 3.0, "000001": 2.0, "000002": 1.0}
    rows = []
    for symbol, prices in price_plan.items():
        for step, price in enumerate(prices):
            fill_price = prices[step + 1] if step + 1 < len(prices) else None
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(days=step)).isoformat(),
                    "symbol": symbol,
                    "condition_id": "stateful_sb3_fixture",
                    "passed": True,
                    "rank_score": ranks[symbol] - step * 0.01,
                    "price": float(price),
                    "fill_price": None if fill_price is None else float(fill_price),
                    "fillable": fill_price is not None,
                    "feature_rank": ranks[symbol],
                }
            )
    return pd.DataFrame(rows)

def _affordability_boundary_candidates() -> pd.DataFrame:
    base = pd.Timestamp("2026-07-10 15:30:00")
    return pd.DataFrame(
        [
            {
                "timestamp": base.isoformat(),
                "symbol": "000123",
                "condition_id": "stateful_sb3_affordability_boundary",
                "passed": True,
                "rank_score": 1.0,
                "price": 100.0,
                "fill_price": 100.0,
                "fillable": True,
                "feature_rank": 1.0,
            },
            {
                "timestamp": (base + pd.Timedelta(days=1)).isoformat(),
                "symbol": "000123",
                "condition_id": "stateful_sb3_affordability_boundary",
                "passed": True,
                "rank_score": 1.0,
                "price": 100.0,
                "fill_price": None,
                "fillable": False,
                "feature_rank": 1.0,
            },
        ]
    )



def _actual_rows(cost_bps: float) -> list[dict[str, object]]:
    env = PortfolioEnv(
        PortfolioEnvConfig(
            top_k_candidates=3,
            max_positions=2,
            initial_cash=1000.0,
            buy_fraction=0.5,
            cost_bps=cost_bps,
            invalid_action_penalty=0.001,
            turnover_penalty_lambda=0.001,
            seed=7,
        ),
        candidates=_stateful_candidates(),
    )
    _observation, _info = env.reset(seed=7)
    output: list[dict[str, object]] = []
    for step, action in enumerate(ACTIONS):
        fill_start = len(env.trade_log)
        _observation, reward, _terminated, _truncated, info = env.step(action)
        step_fills = env.trade_log[fill_start:]
        output.append(
            {
                "step": step,
                "raw_action": info["raw_action"],
                "executed_action": info["executed_action"],
                "invalid_action": bool(info["invalid_action"]),
                "cash": canonical_money(info["cash"]),
                "nav": canonical_money(info["nav"]),
                "nav_return": canonical_money(info["nav_return"]),
                "turnover_krw": canonical_money(info["turnover_krw"]),
                "turnover_ratio": canonical_money(info["turnover_ratio"]),
                "cost_scenario_id": info["cost_scenario_id"],
                **{key: _sum_fill_money(step_fills, key) for key in _COMPONENT_KEYS},
                "total_cost_krw": _sum_fill_money(step_fills, "total_cost_krw"),

                "reward": canonical_money(reward),
                "terminal_liquidation_count": int(info["terminal_liquidation_count"]),
                "positions": {row["symbol"]: canonical_money(row["quantity"]) for row in info["positions"]},
            }
        )
    return output


@pytest.mark.parametrize("cost_bps", [0.0, 23.0, 46.0])
def test_stateful_sb3_rows_match_independent_decimal_oracle(cost_bps):
    expected = oracle.simulate_stateful_sb3(
        _stateful_candidates().to_dict("records"),
        ACTIONS,
        initial_cash="1000",
        buy_fraction="0.5",
        cost_bps=str(cost_bps),
        top_k=3,
        max_positions=2,
        turnover_penalty="0.001",
        invalid_penalty="0.001",
    )

    actual = _actual_rows(cost_bps)

    assert actual == expected
    assert actual[2]["raw_action"] == 99
    assert actual[2]["executed_action"] == 0
    assert actual[2]["invalid_action"] is True
    assert actual[2]["total_cost_krw"] == "0.000000"
    assert actual[2]["turnover_krw"] == "0.000000"
    assert actual[2]["turnover_ratio"] == "0.000000"
    assert actual[2]["terminal_liquidation_count"] == 0
    assert actual[-1]["terminal_liquidation_count"] == 1

@pytest.mark.parametrize(
    ("cost_bps", "initial_cash", "insufficient_cash"),
    [
        (0.0, "299.999999", 99.999999),
        (23.0, "300.044999", 100.014999),
        (46.0, "300.389999", 100.129999),
    ],
)
def test_stateful_v5_buy_sizing_uses_exact_component_affordability_boundary(
    cost_bps,
    initial_cash,
    insufficient_cash,
):
    candidates = _affordability_boundary_candidates()
    env = PortfolioEnv(
        PortfolioEnvConfig(
            top_k_candidates=1,
            max_positions=1,
            initial_cash=float(initial_cash),
            buy_fraction=1.0,
            cost_bps=cost_bps,
            invalid_action_penalty=0.001,
            turnover_penalty_lambda=0.001,
            seed=7,
        ),
        candidates=candidates,
    )
    _observation, reset_info = env.reset(seed=7)

    assert reset_info["action_mask"][1] == 1

    _observation, reward, _terminated, _truncated, info = env.step(1)
    expected = oracle.simulate_stateful_sb3(
        candidates.to_dict("records"),
        [1],
        initial_cash=initial_cash,
        buy_fraction="1.0",
        cost_bps=str(cost_bps),
        top_k=1,
        max_positions=1,
        turnover_penalty="0.001",
        invalid_penalty="0.001",
    )[0]
    fill = env.trade_log[0]
    actual = {
        "cash": canonical_money(info["cash"]),
        "turnover_krw": canonical_money(info["turnover_krw"]),
        "turnover_ratio": canonical_money(info["turnover_ratio"]),
        "buy_commission_krw": _sum_fill_money([fill], "buy_commission_krw"),
        "buy_slippage_krw": _sum_fill_money([fill], "buy_slippage_krw"),
        "total_cost_krw": _sum_fill_money([fill], "total_cost_krw"),
        "reward": canonical_money(reward),
        "positions": {
            row["symbol"]: canonical_money(row["quantity"])
            for row in info["positions"]
        },
    }

    assert canonical_money(fill["quantity"]) == "2.000000"
    assert canonical_money(fill["gross_value"]) == "200.000000"
    assert actual == {
        "cash": expected["cash"],
        "turnover_krw": expected["turnover_krw"],
        "turnover_ratio": expected["turnover_ratio"],
        "buy_commission_krw": expected["buy_commission_krw"],
        "buy_slippage_krw": expected["buy_slippage_krw"],
        "total_cost_krw": expected["total_cost_krw"],
        "reward": expected["reward"],
        "positions": expected["positions"],
    }

    poor_env = PortfolioEnv(
        PortfolioEnvConfig(
            top_k_candidates=1,
            max_positions=1,
            initial_cash=insufficient_cash,
            buy_fraction=1.0,
            cost_bps=cost_bps,
            seed=7,
        ),
        candidates=candidates,
    )
    _observation, poor_reset_info = poor_env.reset(seed=7)
    assert poor_reset_info["action_mask"][1] == 0

    _observation, _reward, _terminated, _truncated, poor_info = poor_env.step(1)
    assert poor_info["raw_action"] == 1
    assert poor_info["executed_action"] == 0
    assert poor_info["invalid_action"] is True
    assert poor_info["blocked_reason"] == "insufficient_cash_for_lot"
    assert poor_info["turnover_krw"] == pytest.approx(0.0)



def test_negative_zero_money_serialization_is_normalized_on_both_boundaries():
    assert canonical_money("-0.000000") == "0.000000"
    assert canonical_money("-0.0000004") == "0.000000"
    assert oracle.q("-0.000000") == "0.000000"
    assert oracle.q("-0.0000004") == "0.000000"
    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=3, max_positions=2, initial_cash=1000.0),
        candidates=_stateful_candidates(),
    )
    env.reset(seed=7)
    env.account.cash = -0.0
    info = env._info(event="negative_zero_probe")  # noqa: SLF001 - serialization probe
    assert info["cash"] == 0.0
    assert info["cash_money"] == "0.000000"


def test_stateful_sb3_missing_mark_for_held_symbol_fails_closed():
    candidates = _stateful_candidates()
    second_timestamp = sorted(candidates["timestamp"].unique())[1]
    broken = candidates[~((candidates["timestamp"] == second_timestamp) & (candidates["symbol"] == "000003"))]
    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=3, max_positions=2, initial_cash=1000.0, buy_fraction=0.5, cost_bps=23.0),
        candidates=broken,
    )
    env.reset(seed=7)

    with pytest.raises(KeyError, match="Missing mark price"):
        env.step(1)


def test_stateful_sb3_missing_fill_price_column_fails_closed():
    candidates = _stateful_candidates().drop(columns=["fill_price", "fillable"])

    with pytest.raises(ValueError, match="fill_price"):
        PortfolioEnv(
            PortfolioEnvConfig(top_k_candidates=3, max_positions=2, initial_cash=1000.0),
            candidates=candidates,
        )


def test_explicit_synthetic_legacy_same_bar_fallback_cannot_claim_v5():
    candidates = _stateful_candidates().drop(columns=["fill_price", "fillable"])

    with pytest.warns(RuntimeWarning, match="synthetic legacy"):
        env = PortfolioEnv(
            PortfolioEnvConfig(
                top_k_candidates=3,
                max_positions=2,
                initial_cash=1000.0,
                cost_bps=23.0,
                legacy_scalar_cost_label="legacy_scalar_23bp_synthetic_fixture",
                accounting_horizon=SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON,
                allow_legacy_same_bar_fill=True,
            ),
            candidates=candidates,
        )
    _observation, info = env.reset(seed=7)

    assert info["accounting_horizon"] == SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON
    assert info["accounting_horizon"] != SB3_ACCOUNTING_HORIZON
    assert info["cost_scenario_id"] == "legacy_scalar_23bp_synthetic_fixture"
    assert info["config"]["accounting_horizon"] == SB3_LEGACY_SYNTHETIC_ACCOUNTING_HORIZON
    assert info["cost_model"] == "legacy_scalar_per_fill"
    assert info["action_mask"][1] == 1


class _RecordingModel:
    def __init__(self, action: int) -> None:
        self.action = int(action)
        self.deterministic_calls: list[bool] = []

    def predict(self, observation, deterministic: bool = True):
        self.deterministic_calls.append(bool(deterministic))
        return np.asarray(self.action), None


def test_validation_eval_uses_deterministic_raw_action_without_substitution():
    model = _RecordingModel(action=99)
    config = trainer.PortfolioSb3TrainConfig(
        total_timesteps=8,
        max_eval_steps=3,
        top_k_candidates=3,
        max_positions=2,
        initial_cash=1000.0,
        buy_fraction=0.5,
        cost_bps=23.0,
        write_artifacts=False,
        write_training_events=False,
    )

    metrics = trainer._evaluate_model_on_candidates(
        model,
        config,
        _stateful_candidates(),
        fold_index=0,
        cost_label="base_23bp",
    )

    assert model.deterministic_calls == [True, True, True]
    assert metrics["reward_mode"] == "economic_only"
    assert metrics["raw_invalid_action_count"] == metrics["steps"] == 3
    assert metrics["executed_invalid_action_count"] == 3
    assert metrics["trade_count"] == 0
    assert metrics["turnover_krw"] == pytest.approx(0.0)
    assert metrics["turnover_ratio"] == pytest.approx(0.0)
    assert "turnover" not in metrics
    assert metrics["cost_scenario_id"] == "base_23bp"
    assert metrics["final_nav"] == pytest.approx(1000.0)


def test_predict_action_exposes_stochastic_training_flag_and_deterministic_eval_flag():
    model = _RecordingModel(action=0)
    observation = np.zeros((4,), dtype=np.float32)

    assert trainer._predict_action(model, observation, deterministic=False) == 0
    assert trainer._predict_action(model, observation, deterministic=True) == 0
    assert model.deterministic_calls == [False, True]

import json
from pathlib import Path

import pandas as pd
import pytest

from stom_rl.condition_screener import (
    ConditionRule,
    SafeExpression,
    load_rules,
    screen_frame,
    write_candidates,
)

RULES_DIR = Path(__file__).resolve().parents[1] / "stom_rl" / "rules"
REAL_RULE_FILES = ("buy_widev1", "buy_widev2", "buy_demand_pressure")


def _demand_frame() -> pd.DataFrame:
    """Tiny in-memory fixture (no DB dependency) covering pass and fail rows."""

    return pd.DataFrame(
        {
            "timestamp": [
                "2025-01-03 09:00:00",
                "2025-01-03 09:00:00",
                "2025-01-03 09:00:01",
            ],
            "symbol": ["000001", "000002", "000001"],
            "close": [100.0, 200.0, 101.0],
            "amount": [150, 50, 200],
            "trade_strength": [120, 90, 130],
            "buy_qty_1s": [10, 1, 8],
            "sell_qty_1s": [2, 5, 3],
            "net_buy_qty_1s": [8, -4, 5],
            "bid_ask_imbalance": [0.6, 0.4, 0.7],
        }
    )


def test_safe_expression_rejects_forbidden_tokens_and_unknowns():
    with pytest.raises(ValueError, match="Forbidden"):
        SafeExpression("__import__('os')", allowed_names=["close"])
    with pytest.raises(ValueError, match="Unknown"):
        SafeExpression("missing > 0", allowed_names=["close"])


def test_condition_screener_emits_deterministic_candidate_schema(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "timestamp": ["2025-01-03 09:00:00", "2025-01-03 09:00:00", "2025-01-03 09:00:01"],
            "symbol": ["000001", "000002", "000001"],
            "close": [100.0, 200.0, 101.0],
            "rank_score": [0.5, 0.2, 0.7],
            "buy_qty_1s": [10, 0, 5],
            "sell_qty_1s": [2, 5, 1],
        }
    )
    candidates = screen_frame(
        frame,
        [ConditionRule(condition_id="net_buy", expression="buy_qty_1s > sell_qty_1s", rank_expression="rank_score")],
    )

    assert list(candidates[["timestamp", "symbol", "condition_id", "passed", "rank_score", "price"]].columns)
    assert candidates["symbol"].tolist() == ["000001", "000001"]
    assert candidates["timestamp"].is_monotonic_increasing
    output = tmp_path / "candidates.jsonl"
    write_candidates(output, candidates)
    assert output.read_text(encoding="utf-8-sig").count("\n") == 2


def test_buy_screener_rejects_sell_only_variables():
    frame = pd.DataFrame({"timestamp": ["2025-01-03"], "symbol": ["000001"], "close": [100], "holding_qty": [1]})
    with pytest.raises(ValueError, match="sell-only"):
        screen_frame(frame, [ConditionRule(condition_id="bad", expression="holding_qty > 0")])


@pytest.mark.parametrize("rule_name", REAL_RULE_FILES)
def test_real_buy_rule_json_loads(rule_name: str):
    rules = load_rules(RULES_DIR / f"{rule_name}.json")
    assert len(rules) == 1
    rule = rules[0]
    assert rule.condition_id == rule_name
    assert rule.side == "buy"
    assert rule.expression  # non-empty whitelisted expression


@pytest.mark.parametrize(
    "rule_name, expected_rank",
    [
        ("buy_widev1", [120.0, 130.0]),
        ("buy_widev2", [8.0, 5.0]),
        ("buy_demand_pressure", [72.0, 91.0]),
    ],
)
def test_real_buy_rule_screens_deterministically(rule_name: str, expected_rank: list[float]):
    rules = load_rules(RULES_DIR / f"{rule_name}.json")
    candidates = screen_frame(_demand_frame(), rules, strategy_side="buy")
    # 000002 fails every filter (low amount, weak trade strength, net selling, bid-light book).
    assert candidates["symbol"].tolist() == ["000001", "000001"]
    assert candidates["condition_id"].tolist() == [rule_name, rule_name]
    assert candidates["timestamp"].is_monotonic_increasing
    assert candidates["rank_score"].tolist() == expected_rank
    # Determinism: a second screen of the same frame yields identical output.
    again = screen_frame(_demand_frame(), rules, strategy_side="buy")
    assert again["rank_score"].tolist() == candidates["rank_score"].tolist()


def test_real_buy_rules_use_only_whitelisted_canonical_features():
    canonical = {
        "open", "high", "low", "close", "volume", "amount", "trade_strength",
        "buy_qty_1s", "sell_qty_1s", "net_buy_qty_1s", "bid_ask_imbalance",
        "spread_ticks", "amount_delta", "turnover_rate", "rank_score",
    }
    for rule_name in REAL_RULE_FILES:
        rules = load_rules(RULES_DIR / f"{rule_name}.json")
        for rule in rules:
            expr = SafeExpression(rule.expression, allowed_names=canonical)
            # Every referenced name maps to a canonical feature (no hallucinated vars).
            assert expr.referenced_names <= canonical
            ranker = SafeExpression(rule.rank_expression, allowed_names=canonical)
            assert ranker.referenced_names <= canonical


def test_screener_rejects_forbidden_tokens_in_rule_expression():
    forbidden_rule = ConditionRule(condition_id="evil", expression="__import__('os') and close > 0")
    with pytest.raises(ValueError, match="Forbidden"):
        screen_frame(_demand_frame(), [forbidden_rule], strategy_side="buy")


def test_screener_rejects_unknown_variable_in_rule_expression():
    unknown_rule = ConditionRule(condition_id="hallucinated", expression="시가총액 > 100")
    with pytest.raises(ValueError, match="Unknown"):
        screen_frame(_demand_frame(), [unknown_rule], strategy_side="buy")


def test_screener_rejects_sell_only_variable_in_buy_rule():
    frame = _demand_frame().assign(position_weight=0.0)
    sell_var_rule = ConditionRule(condition_id="leak", expression="position_weight > 0 and close > 0")
    with pytest.raises(ValueError, match="sell-only"):
        screen_frame(frame, [sell_var_rule], strategy_side="buy")


def test_real_buy_rule_json_has_no_forbidden_or_sell_only_tokens():
    sell_only_korean = ("수익률", "보유시간", "매수가", "보유수량", "수익금", "최고수익률")
    for rule_name in REAL_RULE_FILES:
        text = (RULES_DIR / f"{rule_name}.json").read_text(encoding="utf-8-sig")
        payload = json.loads(text)
        for rule in payload["rules"]:
            assert rule["side"] == "buy"
            lowered = rule["expression"].lower()
            assert "import" not in lowered and "eval" not in lowered and "__" not in lowered
            assert "open(" not in lowered and "compile" not in lowered
            for token in sell_only_korean:
                assert token not in rule["expression"]

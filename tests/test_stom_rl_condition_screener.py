from pathlib import Path

import pandas as pd
import pytest

from stom_rl.condition_screener import ConditionRule, SafeExpression, screen_frame, write_candidates


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

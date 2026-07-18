from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import pytest

from stom_rl.daily_v51_causal_panel import build_causal_panel as _build_causal_panel, _panel_digest
from stom_rl.daily_v51_evaluator import (
    MISSING_1520_ENTRY_BAR,
    MISSING_1520_EXIT_BAR,
    PRIMARY_VARIANT_ID,
    VALIDATION_VARIANT_IDS,
    VARIANT_ORDER,
    V51EvaluationError,
    canonical_manifest_sha256,
    evaluate_v51_horizon_variants,
    freeze_v51_horizon_variants,
)

_SOURCE_DB_PATH = "D:/Kronos/_database/Stock_Database_ohlcv_5min.db"
_DAILY_DB_PATH = "D:/Kronos/_database/Stock_Database_ohlcv_1day.db"
_SOURCE_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_SOURCE_DB_SHA256 = "0123456789abcdef" * 4
_SOURCE_IDENTITY: Mapping[str, object] = {
    "schema_version": "kronos_daily_1520_source.v1",
    "source_db_path": _SOURCE_DB_PATH,
    "source_db_sha256": _SOURCE_DB_SHA256,
}
_SESSIONS = ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]
_SPLIT_IDENTITY: Mapping[str, object] = {
    "split_id": "krx-v51-split-001",
    "train_split_id": "train-2023",
    "validation_split_id": "validation-2024q1",
    "untouched_test_split_id": "untouched-test-2024q2",
    "oos_split_id": "fresh-oos-status-only",
    "horizon_choice_source": "train_validation_only",
    "used_untouched_test_for_horizon_choice": False,
    "used_oos_for_horizon_choice": False,
    "post_hoc_retune": False,
}


@dataclass(frozen=True)
class Exact1520Fixture:
    schema_version: str
    session_date: str
    date: str
    timestamp_kst: str
    timestamp_yyyymmddhhmm: str
    symbol: str
    table: str
    open: float
    high: float
    low: float
    close: float
    price_1520_close_proxy: float
    bar_volume_1520: int
    bar_volume_status: str
    volume_to_1520: None
    volume_to_1520_status: str
    cumulative_volume_to_1520: None
    cumulative_volume_to_1520_status: str
    amount_to_1520: None
    amount_to_1520_status: str
    tradable: bool
    exclusion_reason: str | None
    official_close: bool
    price_basis: str
    causal_cutoff_kst: str
    source_db_path: str
    source_table: str
    source_columns: tuple[str, ...]
    source_timestamp_column: str
    source_price_column: str
    source_volume_column: str


_FAKE_COST_SCENARIO_BP = {
    "zero_control_0bp": 0,
    "base_23bp": 23,
    "stress_46bp": 46,
}
_FAKE_ACCOUNT_NAV_BY_SCENARIO = {
    "zero_control_0bp": "61000000.000000",
    "base_23bp": "60000000.000000",
    "stress_46bp": "59000000.000000",
}


class FakeV51Accounting:
    def __init__(
        self,
        *,
        mutate_before_digest: Callable[[dict[str, Any]], None] | None = None,
        mutate_after_digest: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._mutate_before_digest = mutate_before_digest
        self._mutate_after_digest = mutate_after_digest

    def __call__(self, rows: Sequence[Mapping[str, Any]], horizon_id: str) -> dict[str, Any]:
        selected = [dict(row) for row in rows]
        horizon = self._horizon(horizon_id)
        self.calls.append({"selected_rows": selected, "horizon_id": horizon_id})
        scenario_manifests = {
            scenario_id: self._scenario_manifest(selected, horizon=horizon, scenario_id=scenario_id)
            for scenario_id in _FAKE_COST_SCENARIO_BP
        }
        primary = scenario_manifests["base_23bp"]
        manifest: dict[str, Any] = {
            "schema_version": "kronos_v51_slot_accounting.v1",
            "v5_schema_version": 1,
            "horizon_id": horizon["horizon_id"],
            "accounting_horizon_id": horizon["horizon_id"],
            "horizon_days": horizon["horizon_days"],
            "label_column": horizon["label_column"],
            "supported_horizon_ids": ["H1", "H3", "H5"],
            "price_basis": "15:20_bar_close_proxy",
            "official_close": False,
            "causal_cutoff_kst": "15:20:00",
            "total_capital_krw": 60000000.0,
            "total_capital_krw_decimal": "60000000.000000",
            "slot_count": 10,
            "slot_buy_budget_krw": 5000000.0,
            "slot_buy_budget_krw_decimal": "5000000.000000",
            "max_deployed_principal_krw": 50000000.0,
            "max_deployed_principal_krw_decimal": "50000000.000000",
            "reserve_cash_krw": 10000000.0,
            "reserve_cash_krw_decimal": "10000000.000000",
            "selected_count": len(selected),
            "symbols": [row["symbol"] for row in selected],
            "cost_scenario_ids": list(_FAKE_COST_SCENARIO_BP),
            "primary_cost_scenario_id": "base_23bp",
            "cost_scenarios": [
                {"scenario_id": scenario_id, "total_bp": round_trip_bp}
                for scenario_id, round_trip_bp in _FAKE_COST_SCENARIO_BP.items()
            ],
            "scenario_manifests": scenario_manifests,
            "primary_accounting": primary,
            "account_nav_krw_decimal": primary["account_nav_krw_decimal"],
            "deployed_principal_krw_decimal": primary["deployed_principal_krw_decimal"],
            "blockers": [],
            "false_locks": {
                "broker_integration": False,
                "full_day_daily_ohlcv": False,
                "live_trading": False,
                "official_close": False,
                "paper_trading": False,
                "profit_claim": False,
            },
            "promotion_claims": {
                "broker_integration": False,
                "live_trading": False,
                "paper_trading": False,
                "profit": False,
            },
            "no_claims": [
                "NO_LIVE_TRADING",
                "NO_BROKER_INTEGRATION",
                "NO_PAPER_TRADING",
                "NO_PROFIT_CLAIM",
            ],
        }
        if self._mutate_before_digest is not None:
            self._mutate_before_digest(manifest)
        manifest["accounting_manifest_sha256"] = canonical_manifest_sha256(
            manifest,
            digest_field="accounting_manifest_sha256",
        )
        if self._mutate_after_digest is not None:
            self._mutate_after_digest(manifest)
        return manifest

    @staticmethod
    def _horizon(horizon_id: str) -> dict[str, Any]:
        horizon_days = {"H1": 1, "H3": 3, "H5": 5}[horizon_id]
        label_column = {
            "H1": "future_return_h1_1520_proxy",
            "H3": "future_return_h3_1520_proxy",
            "H5": "future_return_h5_1520_proxy",
        }[horizon_id]
        return {"horizon_id": horizon_id, "horizon_days": horizon_days, "label_column": label_column}

    @staticmethod
    def _slot_payload(
        slot: int,
        *,
        row: Mapping[str, Any] | None,
        horizon: Mapping[str, Any],
        scenario_id: str,
    ) -> dict[str, Any]:
        filled = row is not None
        entry_mark = row["entry_1520"] if row is not None else None
        exit_mark = row["exit_1520_by_label"][horizon["label_column"]] if row is not None else None
        return {
            "slot": slot,
            "symbol": row["symbol"] if row is not None else None,
            "code": row["symbol"] if row is not None else None,
            "side": "buy" if filled else None,
            "quantity": row["quantity"] if row is not None else 0,
            "status": "filled" if filled else "unfilled",
            "slot_state": "filled" if filled else "cash_hold",
            "blocked": False,
            "horizon_id": horizon["horizon_id"],
            "horizon_days": horizon["horizon_days"],
            "label_column": horizon["label_column"],
            "price_basis": "15:20_bar_close_proxy",
            "official_close": False,
            "cost_scenario_id": scenario_id,
            "cost_application_count": 1,
            "entry_mark_krw_decimal": str(entry_mark["price_1520_close_proxy"]) if filled else None,
            "exit_mark_krw_decimal": str(exit_mark["price_1520_close_proxy"]) if filled else None,
            "deployed_principal_krw_decimal": "5000000.000000" if filled else "0.000000",
        }

    def _scenario_manifest(
        self,
        selected: Sequence[Mapping[str, Any]],
        *,
        horizon: Mapping[str, Any],
        scenario_id: str,
    ) -> dict[str, Any]:
        ledger = [
            self._slot_payload(index, row=row, horizon=horizon, scenario_id=scenario_id)
            for index, row in enumerate(selected)
        ]
        while len(ledger) < 10:
            ledger.append(self._slot_payload(len(ledger), row=None, horizon=horizon, scenario_id=scenario_id))
        deployed = f"{5_000_000 * len(selected)}.000000"
        round_trip_bp = _FAKE_COST_SCENARIO_BP[scenario_id]
        return {
            "schema_version": "kronos_v51_slot_accounting.v1",
            "horizon_id": horizon["horizon_id"],
            "accounting_horizon_id": horizon["horizon_id"],
            "horizon_days": horizon["horizon_days"],
            "label_column": horizon["label_column"],
            "cost_scenario_id": scenario_id,
            "cost_scenario": {"scenario_id": scenario_id, "total_bp": round_trip_bp},
            "round_trip_cost_bp": round_trip_bp,
            "cost_application_count": 1,
            "total_capital_krw": 60000000.0,
            "total_capital_krw_decimal": "60000000.000000",
            "slot_count": 10,
            "slot_buy_budget_krw": 5000000.0,
            "slot_buy_budget_krw_decimal": "5000000.000000",
            "max_deployed_principal_krw": 50000000.0,
            "max_deployed_principal_krw_decimal": "50000000.000000",
            "reserve_cash_krw": 10000000.0,
            "filled_slots": len(selected),
            "unfilled_slots": 10 - len(selected),
            "hold_cash_slots": 10 - len(selected),
            "deployed_principal_krw_decimal": deployed,
            "reserve_cash_krw_decimal": "10000000.000000",
            "account_nav_krw_decimal": _FAKE_ACCOUNT_NAV_BY_SCENARIO[scenario_id],
            "ledger": ledger,
            "blockers": [],
        }


def _observation(symbol: str = "005930", session: str = _SESSIONS[0]) -> dict[str, object]:
    return {
        "symbol": symbol,
        "session": session,
        "timestamp": f"{session}T15:20:00+09:00",
        "max_source_timestamp": f"{session}T15:20:00+09:00",
        "feature_score": 1.25,
        "source_db_path": _SOURCE_DB_PATH,
    }


def _exact(symbol: str, session: str, close: float, *, source_db_path: str = _SOURCE_DB_PATH) -> Exact1520Fixture:
    table = f"A{symbol}"
    return Exact1520Fixture(
        schema_version="kronos_daily_1520_source.v1",
        session_date=session,
        date=session,
        timestamp_kst=f"{session}T15:20:00+09:00",
        timestamp_yyyymmddhhmm=session.replace("-", "") + "1520",
        symbol=symbol,
        table=table,
        open=close - 1.0,
        high=close + 2.0,
        low=close - 2.0,
        close=close,
        price_1520_close_proxy=close,
        bar_volume_1520=1234,
        bar_volume_status="SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY",
        volume_to_1520=None,
        volume_to_1520_status="NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
        cumulative_volume_to_1520=None,
        cumulative_volume_to_1520_status="NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
        amount_to_1520=None,
        amount_to_1520_status="NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME",
        tradable=True,
        exclusion_reason=None,
        official_close=False,
        price_basis="15:20_bar_close_proxy",
        causal_cutoff_kst="15:20:00",
        source_db_path=source_db_path,
        source_table=table,
        source_columns=_SOURCE_COLUMNS,
        source_timestamp_column="date",
        source_price_column="close",
        source_volume_column="volume",
    )


def _panel(*, exact_sessions: Sequence[str] | None = None, symbol: str = "005930") -> dict[str, object]:
    closes = {
        _SESSIONS[0]: 100.0,
        _SESSIONS[1]: 110.0,
        _SESSIONS[2]: 130.0,
        _SESSIONS[3]: 160.0,
        _SESSIONS[4]: 200.0,
        _SESSIONS[5]: 260.0,
    }
    sessions = list(_SESSIONS if exact_sessions is None else exact_sessions)
    return _build_causal_panel(
        [_observation(symbol, _SESSIONS[0])],
        [_exact(symbol, session, closes[session]) for session in sessions],
        source_calendar=_SESSIONS,
        source_identity=_SOURCE_IDENTITY,
    )


def _selections(symbol: str = "005930") -> dict[str, list[dict[str, object]]]:
    return {
        PRIMARY_VARIANT_ID: [{"symbol": symbol, "session": _SESSIONS[0], "rank": 1}],
        VALIDATION_VARIANT_IDS[0]: [{"symbol": symbol, "session": _SESSIONS[0], "rank": 1}],
        VALIDATION_VARIANT_IDS[1]: [{"symbol": symbol, "session": _SESSIONS[0], "rank": 1}],
    }


def _freeze(
    panel: Mapping[str, Any],
    selections: Mapping[str, Sequence[Any]] | None = None,
    *,
    cost_scenario_bp: int = 23,
) -> dict[str, Any]:
    return freeze_v51_horizon_variants(
        panel,
        _selections() if selections is None else selections,
        split_identity=_SPLIT_IDENTITY,
        selection_sequence=7,
        cost_scenario_bp=cost_scenario_bp,
    )


def test_evaluator_produces_primary_h1_and_validation_h3_h5_results_from_accounting_helper() -> None:
    panel = _panel()
    freeze = _freeze(panel)
    accounting = FakeV51Accounting()

    result = evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting, cost_scenario_bp=23)

    assert result["manifest_sha256"] == canonical_manifest_sha256(result)
    assert result["price_basis"] == "15:20_bar_close_proxy"
    assert result["primary_variant_id"] == PRIMARY_VARIANT_ID
    assert tuple(result["variant_order"]) == VARIANT_ORDER
    assert [call["horizon_id"] for call in accounting.calls] == ["H1", "H3", "H5"]
    assert [
        call["selected_rows"][0]["exit_1520_by_label"][call["selected_rows"][0]["label_column"]][
            "price_1520_close_proxy"
        ]
        for call in accounting.calls
    ] == [110.0, 160.0, 260.0]
    for call in accounting.calls:
        selected_row = call["selected_rows"][0]
        assert set(selected_row["exit_1520_by_label"]) == {selected_row["label_column"]}
        assert {"entry_mark", "exit_mark", "entry_price", "exit_price"}.isdisjoint(selected_row)
        assert isinstance(selected_row["quantity"], int) and selected_row["quantity"] > 0
    assert result["horizon_results"][0]["role"] == "primary"
    assert [item["role"] for item in result["horizon_results"][1:]] == ["validation", "validation"]
    assert result["metrics_by_variant"][PRIMARY_VARIANT_ID]["account_nav"] == "60000000.000000"
    assert result["metrics_by_variant"][PRIMARY_VARIANT_ID]["cost_scenario_id"] == "base_23bp"
    assert result["metrics_by_variant"][PRIMARY_VARIANT_ID]["round_trip_cost_bp"] == 23
    primary_accounting = result["horizon_results"][0]["accounting"]
    assert primary_accounting["cost_scenario_id"] == "base_23bp"
    assert primary_accounting["round_trip_cost_bp"] == 23
    assert primary_accounting["slots"][0]["cost_scenario_id"] == "base_23bp"
    assert result["gates_by_variant"][PRIMARY_VARIANT_ID]["status"] == "PASS"


def test_evaluator_calls_default_v5_accounting_helper_for_h1_h3_h5() -> None:
    panel = _panel()
    freeze = _freeze(panel)

    result = evaluate_v51_horizon_variants(panel, freeze, cost_scenario_bp=23)

    assert [item["horizon_id"] for item in result["horizon_results"]] == ["H1", "H3", "H5"]
    for horizon_result in result["horizon_results"]:
        accounting_row = horizon_result["accounting_input_rows"][0]
        label_column = horizon_result["label_column"]
        assert accounting_row["side"] == "buy"
        assert accounting_row["entry_1520"]["price_basis"] == "15:20_bar_close_proxy"
        assert accounting_row["entry_1520"]["official_close"] is False
        assert set(accounting_row["exit_1520_by_label"]) == {label_column}
        assert accounting_row["exit_1520_by_label"][label_column]["price_basis"] == "15:20_bar_close_proxy"
        assert accounting_row["exit_1520_by_label"][label_column]["official_close"] is False
        assert {"entry_mark", "exit_mark", "entry_price", "exit_price"}.isdisjoint(accounting_row)
        assert accounting_row["horizon_id"] == horizon_result["horizon_id"]
        assert accounting_row["horizon_days"] == horizon_result["horizon_days"]
        assert accounting_row["source_db_sha256"] == _SOURCE_DB_SHA256
        assert horizon_result["accounting"]["slots"][0]["status"] == "filled"
        assert horizon_result["accounting"]["slots"][0]["horizon_id"] == horizon_result["horizon_id"]
        assert horizon_result["gate"]["status"] == "PASS"


@pytest.mark.parametrize(
    ("cost_bp", "scenario_id", "account_nav"),
    [
        (0, "zero_control_0bp", "61000000.000000"),
        (46, "stress_46bp", "59000000.000000"),
    ],
)
def test_evaluator_selects_frozen_non_23_accounting_scenario(
    cost_bp: int,
    scenario_id: str,
    account_nav: str,
) -> None:
    panel = _panel()
    freeze = _freeze(panel, cost_scenario_bp=cost_bp)
    accounting = FakeV51Accounting()

    result = evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting, cost_scenario_bp=cost_bp)

    metrics = result["metrics_by_variant"][PRIMARY_VARIANT_ID]
    primary_accounting = result["horizon_results"][0]["accounting"]
    assert metrics["cost_scenario_id"] == scenario_id
    assert metrics["round_trip_cost_bp"] == cost_bp
    assert metrics["account_nav"] == account_nav
    assert primary_accounting["cost_scenario_id"] == scenario_id
    assert primary_accounting["round_trip_cost_bp"] == cost_bp
    assert primary_accounting["slots"][0]["cost_scenario_id"] == scenario_id


def test_missing_accounting_manifest_digest_is_rejected() -> None:
    panel = _panel()
    freeze = _freeze(panel)
    accounting = FakeV51Accounting(
        mutate_after_digest=lambda manifest: manifest.pop("accounting_manifest_sha256"),
    )

    with pytest.raises(V51EvaluationError, match="accounting_manifest_sha256"):
        evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting)


def test_tampered_accounting_manifest_digest_is_rejected() -> None:
    panel = _panel()
    freeze = _freeze(panel)
    accounting = FakeV51Accounting(
        mutate_after_digest=lambda manifest: manifest.__setitem__("accounting_manifest_sha256", "0" * 64),
    )

    with pytest.raises(V51EvaluationError, match="accounting_manifest_sha256"):
        evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting)


def test_accounting_true_promotion_claim_is_rejected() -> None:
    def promote_profit(manifest: dict[str, Any]) -> None:
        manifest["promotion_claims"]["profit"] = True

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="promotion_claims"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=promote_profit),
        )


def test_accounting_missing_false_lock_key_is_rejected() -> None:
    def remove_lock(manifest: dict[str, Any]) -> None:
        manifest["false_locks"].pop("official_close")

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="false_locks"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=remove_lock),
        )


def test_accounting_extra_false_lock_key_is_rejected() -> None:
    def add_lock(manifest: dict[str, Any]) -> None:
        manifest["false_locks"]["unexpected_false_lock"] = False

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="false_locks"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=add_lock),
        )


def test_accounting_true_false_lock_value_is_rejected() -> None:
    def unlock_profit(manifest: dict[str, Any]) -> None:
        manifest["false_locks"]["profit_claim"] = True

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="false_locks"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=unlock_profit),
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("total_capital_krw", 59000000.0),
        ("slot_count", 9),
        ("slot_buy_budget_krw", 4000000.0),
        ("max_deployed_principal_krw", 49000000.0),
        ("reserve_cash_krw", 9000000.0),
    ],
)
def test_accounting_manifest_capital_envelope_drift_is_rejected(field: str, bad_value: object) -> None:
    def drift_capital(manifest: dict[str, Any]) -> None:
        manifest[field] = bad_value

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match=field):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=drift_capital),
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("total_capital_krw", 59000000.0),
        ("slot_count", 9),
        ("slot_buy_budget_krw", 4000000.0),
        ("max_deployed_principal_krw", 49000000.0),
        ("reserve_cash_krw", 9000000.0),
    ],
)
def test_accounting_scenario_capital_envelope_drift_is_rejected(field: str, bad_value: object) -> None:
    def drift_capital(manifest: dict[str, Any]) -> None:
        manifest["scenario_manifests"]["base_23bp"][field] = bad_value

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match=field):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=drift_capital),
        )


def test_accounting_missing_no_claim_label_is_rejected() -> None:
    def remove_profit_label(manifest: dict[str, Any]) -> None:
        manifest["no_claims"].remove("NO_PROFIT_CLAIM")

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="exactly match required no-claim labels"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=remove_profit_label),
        )


def test_accounting_extra_no_claim_label_is_rejected() -> None:
    def add_unexpected_label(manifest: dict[str, Any]) -> None:
        manifest["no_claims"].append("NO_UNREGISTERED_CLAIM")

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="exactly match required no-claim labels"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=add_unexpected_label),
        )


def test_accounting_price_basis_drift_is_rejected() -> None:
    def drift_price_basis(manifest: dict[str, Any]) -> None:
        manifest["price_basis"] = "official_close"
        manifest["official_close"] = True

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="price_basis"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=drift_price_basis),
        )


def test_nested_accounting_round_trip_cost_drift_is_rejected() -> None:
    def drift_round_trip_bp(manifest: dict[str, Any]) -> None:
        manifest["scenario_manifests"]["stress_46bp"]["round_trip_cost_bp"] = 23

    panel = _panel()
    freeze = _freeze(panel)

    with pytest.raises(V51EvaluationError, match="round_trip_cost_bp"):
        evaluate_v51_horizon_variants(
            panel,
            freeze,
            accounting_helper=FakeV51Accounting(mutate_before_digest=drift_round_trip_bp),
        )


def test_missing_entry_bar_fails_closed_before_accounting() -> None:
    panel = _panel(exact_sessions=_SESSIONS[1:])
    freeze = _freeze(panel)
    accounting = FakeV51Accounting()

    with pytest.raises(V51EvaluationError, match=MISSING_1520_ENTRY_BAR):
        evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting)

    assert accounting.calls == []


def test_missing_exit_bar_fails_closed_before_accounting() -> None:
    panel = _panel(exact_sessions=[_SESSIONS[0]])
    freeze = _freeze(panel)
    accounting = FakeV51Accounting()

    with pytest.raises(V51EvaluationError, match=MISSING_1520_EXIT_BAR):
        evaluate_v51_horizon_variants(panel, freeze, accounting_helper=accounting)

    assert accounting.calls == []


def test_altered_freeze_manifest_is_rejected_by_deterministic_hash() -> None:
    panel = _panel()
    freeze = _freeze(panel)
    tampered = copy.deepcopy(freeze)
    tampered["horizon_manifests"][0]["selected_rows"][0]["symbol"] = "000660"

    with pytest.raises(V51EvaluationError, match="manifest_sha256"):
        evaluate_v51_horizon_variants(panel, tampered, accounting_helper=FakeV51Accounting())


def test_horizon_mixing_is_rejected_at_freeze() -> None:
    panel = _panel()
    selections = _selections()
    selections[PRIMARY_VARIANT_ID][0]["label_column"] = "future_return_h3_1520_proxy"

    with pytest.raises(V51EvaluationError, match="mixes immutable horizon"):
        _freeze(panel, selections)


def test_test_or_oos_driven_retuning_is_rejected_before_freeze() -> None:
    panel = _panel()
    split_identity = dict(_SPLIT_IDENTITY)
    split_identity["used_untouched_test_for_horizon_choice"] = True

    with pytest.raises(V51EvaluationError, match="test/OOS-driven horizon choice"):
        freeze_v51_horizon_variants(
            panel,
            _selections(),
            split_identity=split_identity,
            selection_sequence=7,
        )


def test_duplicate_selected_symbols_are_rejected_per_horizon_variant() -> None:
    panel = _panel()
    selections = _selections()
    selections[PRIMARY_VARIANT_ID].append({"symbol": "005930", "session": _SESSIONS[0], "rank": 2})

    with pytest.raises(V51EvaluationError, match="duplicate selected symbol"):
        _freeze(panel, selections)


def test_legacy_future_return_1d_and_noncausal_daily_source_inputs_are_rejected() -> None:
    panel = _panel()
    freeze = _freeze(panel)
    legacy = copy.deepcopy(panel)
    legacy["rows"][0]["future_return_1d"] = 0.01

    with pytest.raises(V51EvaluationError, match="future_return_1d"):
        evaluate_v51_horizon_variants(legacy, freeze, accounting_helper=FakeV51Accounting())

    alias_selection = _selections()
    alias_selection[PRIMARY_VARIANT_ID][0]["label_column"] = "future_return_1d"
    with pytest.raises(V51EvaluationError, match="future_return_1d"):
        _freeze(panel, alias_selection)

    noncausal = copy.deepcopy(panel)
    noncausal["rows"][0]["observations"][0]["source_db_path"] = _DAILY_DB_PATH
    noncausal["panel_sha256"] = _panel_digest(noncausal)
    with pytest.raises(ValueError, match="forbidden or unapproved causal source"):
        evaluate_v51_horizon_variants(noncausal, freeze, accounting_helper=FakeV51Accounting())

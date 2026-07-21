from stom_rl.daily_v6_train import CAPITAL, PRIMARY_COST, SLOT_BUDGET
from stom_rl.daily_v8_m3e import (
    SEEDS,
    _select,
    build_manifest,
    decide_verdict,
    evaluate_ensemble,
    evaluate_scores,
    fit_evaluate,
)


def row(symbol, session=20240102, *, ret1=0.0, label=0.0):
    return {
        "symbol": symbol,
        "session_yyyymmdd": session,
        "ret_1d_prev": ret1,
        "ret_5d_prev": ret1,
        "ret_20d_prev": 0.0,
        "vol_z_20": 0.0,
        "foreign_ratio_prev": 0.0,
        "foreign_ratio_delta_5": 0.0,
        "inst_netbuy_norm_5": 0.0,
        "future_return_h1_1520_proxy": label,
    }


def members(*thetas):
    return [{"seed": index, "theta": list(theta), "member_hash": str(index)} for index, theta in enumerate(thetas)]


def baselines(nav=CAPITAL):
    return {name: {"nav": nav} for name in ("rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")}


def metrics(nav):
    return {"nav": nav}


def test_raw_member_scores_are_averaged_before_ranking():
    rows = [row("0001", ret1=1.0), row("0002", ret1=0.0)]
    # Member 1 prefers 0001; member 2 prefers 0002.  Their raw mean only admits 0002.
    result = evaluate_ensemble(rows, members([10, 0, 0, 0, 0, 0, 0, 0], [-12, 0, 0, 0, 0, 0, 0, 2]))
    assert result["pick_counts"] == [1]
    assert result["metrics"]["trade_count"] == 1
    assert result["scores"] == [0.0, 1.0]


def test_ties_break_by_ascending_string_symbol_including_leading_zeroes():
    rows = [row("0002"), row("0001")]
    assert _select(rows, [1.0, 1.0]) == [1, 0]


def test_zero_or_negative_scores_produce_no_picks():
    result, pick_counts = evaluate_scores([row("0001", label=0.9), row("0002", label=0.9)], [0.0, -1.0])
    assert pick_counts == [0]
    assert result["nav"] == CAPITAL
    assert result["trade_count"] == 0


def test_distinct_symbols_and_ten_slot_limit_are_enforced():
    rows = [row(f"{index:04d}", label=0.01) for index in range(11)]
    rows.append(row("0000", label=0.01))
    result, pick_counts = evaluate_scores(rows, [2.0] * len(rows))
    assert pick_counts == [10]
    assert result["trade_count"] == 10
    assert result["max_positions_per_session"] == 10
    assert result["max_invested_krw"] == 50_000_000.0


def test_primary_accounting_charges_exactly_23bp_per_selected_slot():
    result, _ = evaluate_scores([row("0001", label=0.0)], [1.0])
    assert result["nav"] == CAPITAL - SLOT_BUDGET * PRIMARY_COST
    assert result["cost_scenario_navs"]["0.0023"] == CAPITAL - 11_500.0


def test_fit_evaluate_returns_five_members_full_and_leave_one_out_ensembles():
    train = [row("0001", 20230102, ret1=1.0, label=0.03), row("0002", 20230103, ret1=-1.0, label=-0.01)]
    validation = [row("0001", 20240102, ret1=1.0, label=0.01), row("0002", 20240103, ret1=-1.0, label=-0.01)]
    result = fit_evaluate(train, validation)
    assert [member["seed"] for member in result["members"]] == list(SEEDS)
    assert len({member["member_hash"] for member in result["members"]}) >= 1
    assert len(result["ensemble"]["member_hashes"]) == 5
    assert set(result["jackknives"]) == {str(seed) for seed in SEEDS}
    assert all(len(value["member_hashes"]) == 4 for value in result["jackknives"].values())
    assert set(result["shuffled_label_ensemble"]["jackknives"]) == {str(seed) for seed in SEEDS}


def test_control_failure_forces_no_go():
    verdict, _, _ = decide_verdict(metrics(CAPITAL + 2), {"0": {"metrics": metrics(CAPITAL + 2)}}, baselines(), {"full": {"control_fails": True}})
    assert verdict == "NO_GO"


def test_verdict_eligible_requires_full_and_four_jackknives():
    jackknives = {str(seed): {"metrics": metrics(CAPITAL + 1 if seed < 4 else CAPITAL)} for seed in SEEDS}
    verdict, _, passed = decide_verdict(metrics(CAPITAL + 1), jackknives, baselines(), {"full": {"control_fails": False}})
    assert verdict == "OOS_OPEN_ELIGIBLE_REUSED_VALIDATION_SCREEN"
    assert passed == ["0", "1", "2", "3"]


def test_verdict_inconclusive_for_one_to_three_passing_jackknives():
    jackknives = {str(seed): {"metrics": metrics(CAPITAL + 1 if seed < 2 else CAPITAL)} for seed in SEEDS}
    verdict, _, passed = decide_verdict(metrics(CAPITAL + 1), jackknives, baselines(), {"full": {"control_fails": False}})
    assert verdict == "INCONCLUSIVE"
    assert passed == ["0", "1"]


def test_verdict_no_go_when_full_screen_fails_and_manifest_locks_test():
    jackknives = {str(seed): {"metrics": metrics(CAPITAL + 1)} for seed in SEEDS}
    verdict, _, _ = decide_verdict(metrics(CAPITAL), jackknives, baselines(), {"full": {"control_fails": False}})
    manifest = build_manifest({"verdict": {"value": verdict}})
    assert verdict == "NO_GO"
    assert manifest["test"] == {"state": "NOT_RUN"}
    assert not any(manifest["false_research_locks"].values())

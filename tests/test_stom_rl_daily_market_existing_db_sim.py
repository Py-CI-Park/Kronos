from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from stom_rl.daily_market_allocation_contract import AllocationAction
from stom_rl.daily_market_authority_contract import AuthorityFileIdentity
from stom_rl.daily_market_existing_db_sim_artifacts import (
    write_existing_db_simulation_artifacts,
)
from stom_rl.daily_market_existing_db_sim_contract import (
    ExistingDbSimulationReceipt,
    ExistingDbSimulationStep,
    ExistingDbSimulationWindow,
)
from stom_rl.daily_market_existing_db_sim_engine import (
    ConstantSimulationPolicy,
    NamedModelPolicy,
    RandomSimulationPolicy,
    paired_shuffle_policy,
    simulate_existing_db_policy,
)
from stom_rl.daily_market_existing_db_sim_gate import build_existing_db_simulation_gate
from stom_rl.daily_market_existing_db_sim_inputs import ExistingDbSimulationPaths
from stom_rl.daily_market_existing_db_sim_runner import (
    main,
    run_existing_db_policy_matrix,
)
from stom_rl.daily_market_rl_contract import (
    DailyMarketRlContractError,
    base_cost_config,
)
from stom_rl.daily_market_rl_dataset import MarketDay, TrainScoreScale
from stom_rl.daily_market_score_dataset import CausalMarketScoreDay
from stom_rl.daily_market_state_dataset import CausalMarketStateDay
from stom_rl.daily_market_transition_contract import (
    DailyMarketCandidate,
    DailyMarketScore,
    market_score_hash,
)
from webui.v6_daily_market_publication import observe_daily_market_publication
from webui import v6_existing_db_sim_publication


def _market_day(decision: date, return_ratio: Decimal | None = None) -> MarketDay:
    selected_return = return_ratio or Decimal("1.01")
    scores = tuple(
        DailyMarketScore(
            decision_date=decision,
            code=f"{index:06d}",
            score=float(11 - index),
            split="TEST",
        )
        for index in range(1, 11)
    )
    day_hash = market_score_hash(scores)
    state = CausalMarketStateDay(
        decision_date=decision.isoformat(),
        split="TEST",
        score_day_hash=day_hash,
        feature_vector=(0.0,) * 160,
        missing_feature_count=0,
        feature_hash="7" * 64,
    )
    candidates = tuple(
        DailyMarketCandidate(
            decision_date=decision,
            code=score.code,
            score=score.score,
            split="TEST",
            entry_date=decision + timedelta(days=1),
            exit_date=decision + timedelta(days=2),
            entry_open_krw=Decimal("10000"),
            exit_open_krw=Decimal("10000") * selected_return,
        )
        for score in scores
    )
    return MarketDay(
        CausalMarketScoreDay(
            decision_date=decision,
            split="TEST",
            scores=scores,
            day_hash=day_hash,
        ),
        state,
        candidates,
    )


def _scale() -> TrainScoreScale:
    return TrainScoreScale(5.5, 2.872281323, 2.872281323, 80)


def _days() -> tuple[MarketDay, ...]:
    start = date(2026, 3, 9)
    return tuple(_market_day(start + timedelta(days=index * 2)) for index in range(4))


def test_simulation_engine_accounts_for_costs_and_preserves_shuffle_histogram() -> None:
    policy = ConstantSimulationPolicy(
        "RULE_ALWAYS_TOP5", "RULE", AllocationAction.INVEST_TOP5_EQUAL_SLOT
    )

    metrics, steps = simulate_existing_db_policy(
        _days(), _scale(), policy, scenario="BASE_23BP", config=base_cost_config()
    )
    shuffled = paired_shuffle_policy("SHUFFLE_SEED_0", 0, steps)
    shuffled_metrics, shuffled_steps = simulate_existing_db_policy(
        _days(), _scale(), shuffled, scenario="BASE_23BP", config=base_cost_config()
    )

    assert metrics.decision_count == 4
    assert metrics.round_trip_cost_bps == 23
    assert metrics.action_counts == (0, 0, 4, 0)
    assert metrics.total_cost_krw > 0
    assert sorted(step.action for step in shuffled_steps) == sorted(
        step.action for step in steps
    )
    assert shuffled_metrics.action_counts == metrics.action_counts


def test_random_policy_is_date_seed_deterministic() -> None:
    policy = RandomSimulationPolicy("RANDOM_SEED_2", 2)

    first = tuple(policy.action((0.0,), day) for day in _days())
    second = tuple(policy.action((1.0,), day) for day in reversed(_days()))

    assert first == tuple(reversed(second))
    assert all(action in AllocationAction for action in first)


def test_complete_policy_matrix_and_gate_are_deterministic() -> None:
    delegates = (
        AllocationAction.CASH,
        AllocationAction.INVEST_TOP3_EQUAL_SLOT,
        AllocationAction.INVEST_TOP5_EQUAL_SLOT,
        AllocationAction.INVEST_TOP10_EQUAL_SLOT,
        AllocationAction.INVEST_TOP3_EQUAL_SLOT,
    )
    policies = tuple(
        NamedModelPolicy(
            f"CQL_SEED_{seed}",
            seed,
            ConstantSimulationPolicy(f"D{seed}", "CONTROL", action),
        )
        for seed, action in enumerate(delegates)
    )

    metrics, steps = run_existing_db_policy_matrix(_days(), _scale(), policies)
    gate = build_existing_db_simulation_gate(metrics)

    assert len(metrics) == 34
    assert len(steps) == 34 * 4
    assert sum(row.policy_kind == "RL" for row in metrics) == 10
    assert sum(row.policy_kind == "RANDOM" for row in metrics) == 10
    assert sum(row.policy_kind == "SHUFFLE" for row in metrics) == 10
    assert gate.failed_checks == tuple(
        check.check_id for check in gate.checks if not check.passed
    )


def _identity(name: str, value: str) -> AuthorityFileIdentity:
    return AuthorityFileIdentity(
        path_suffix=name,
        size_bytes=10,
        modified_at_utc="2026-08-14T00:00:00+00:00",
        sha256=value * 64,
    )


def _receipt() -> tuple[
    ExistingDbSimulationReceipt, tuple[ExistingDbSimulationStep, ...]
]:
    policies = tuple(
        NamedModelPolicy(
            f"CQL_SEED_{seed}",
            seed,
            ConstantSimulationPolicy(
                f"D{seed}", "CONTROL", AllocationAction.INVEST_TOP3_EQUAL_SLOT
            ),
        )
        for seed in range(5)
    )
    metrics, steps = run_existing_db_policy_matrix(_days(), _scale(), policies)
    receipt = ExistingDbSimulationReceipt(
        schema_version="kronos_existing_db_60_historical_simulation.v1",
        research_id="DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001",
        verdict="HISTORICAL_SIMULATION_ONLY_NO_PROMOTION",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        source_git_sha="f" * 40,
        daily_database=_identity("daily.db", "a"),
        score_dataset_hash="b" * 64,
        state_dataset_hash="c" * 64,
        allocation_receipt=_identity("allocation.json", "d"),
        checkpoint_identities=tuple(
            _identity(f"seed-{seed}.kq", str(seed + 1)) for seed in range(5)
        ),
        window=ExistingDbSimulationWindow(
            selection_rule="LAST_60_REGISTERED_SCORE_DAYS",
            requested_score_days=60,
            start_decision_date=date(2026, 3, 9),
            end_decision_date=date(2026, 6, 11),
            validation_score_days=14,
            test_score_days=46,
            available_reward_days=59,
            blocked_reward_days=1,
            non_overlapping_decisions=4,
        ),
        blocked_days=("2026-06-11:MISSING_EXIT_OPEN",),
        metrics=metrics,
        gate=build_existing_db_simulation_gate(metrics),
        historical_state="VALIDATION_AND_TEST_ALREADY_CONSUMED_CONTAMINATED",
        future_data_used=False,
        local_db_fresh_holdout_read=False,
        independent_oos_claim_allowed=False,
        profitability_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )
    return receipt, steps


def test_artifacts_are_create_exclusive_and_keep_no_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, steps = _receipt()
    output = tmp_path / "DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001"

    paths = write_existing_db_simulation_artifacts(receipt, steps, output)
    manifest_sha256 = hashlib.sha256(paths.bundle_manifest.read_bytes()).hexdigest()
    monkeypatch.setattr(
        v6_existing_db_sim_publication,
        "EXPECTED_MANIFEST_SHA256",
        manifest_sha256,
    )

    assert paths.receipt.is_file()
    assert paths.ledger.read_text(encoding="utf-8").count("\n") == len(steps)
    assert '"future_data_used": false' in paths.summary.read_text(encoding="utf-8")
    assert observe_daily_market_publication(output).state == "VALID"
    with pytest.raises(
        DailyMarketRlContractError, match="HISTORICAL_SIMULATION_OUTPUT_UNTRUSTED"
    ):
        _ = write_existing_db_simulation_artifacts(receipt, steps, output)

    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    forged_receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
    manifest = json.loads(paths.bundle_manifest.read_text(encoding="utf-8"))
    summary["technical_gate_passed"] = True
    forged_receipt["gate"]["technical_gate_passed"] = True
    for path, payload in (
        (paths.summary, summary),
        (paths.receipt, forged_receipt),
    ):
        _ = path.write_text(
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
            encoding="utf-8",
        )
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        payload = path.read_bytes()
        artifact["size_bytes"] = len(payload)
        artifact["sha256"] = hashlib.sha256(payload).hexdigest()
    _ = paths.bundle_manifest.write_text(
        f"{json.dumps(manifest, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
    assert observe_daily_market_publication(output).state == "INVALID"


def test_window_and_cli_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="window drifted"):
        _ = ExistingDbSimulationWindow(
            selection_rule="LAST_60_REGISTERED_SCORE_DAYS",
            requested_score_days=60,
            start_decision_date=date(2026, 3, 10),
            end_decision_date=date(2026, 6, 11),
            validation_score_days=14,
            test_score_days=46,
            available_reward_days=59,
            blocked_reward_days=1,
            non_overlapping_decisions=30,
        )
    with pytest.raises(
        DailyMarketRlContractError, match="HISTORICAL_SIMULATION_REQUIRES_ROOT"
    ):
        _ = main(())
    assert ExistingDbSimulationPaths.registered(
        tmp_path
    ).output_directory.name.endswith("2026_08_14_001")

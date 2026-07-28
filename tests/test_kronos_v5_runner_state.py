"""Synthetic runner-state tests for the G008 daily Portfolio SB3 protocol slice."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from stom_rl import daily_portfolio_sb3_protocol as protocol
from stom_rl import daily_portfolio_sb3_events as events
from stom_rl import daily_portfolio_sb3_runner as runner
from stom_rl import daily_portfolio_sb3_state as state


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_v5_runner_state_fixture.json").read_text(encoding="utf-8"))


def test_exact_cpu_resume_snapshot_contract_is_semantically_valid_not_hash_only() -> None:
    snapshot = deepcopy(FIXTURE["exact_resume_snapshot"])
    parsed = state.ResumeSnapshot.from_mapping(snapshot)
    candidate = state.ResumeSnapshot.from_mapping(deepcopy(snapshot))

    decision = state.decide_resume(
        parsed,
        candidate,
        expected_protocol_sha256=FIXTURE["protocol_sha256"],
        expected_event_seq=snapshot["event_seq"],
        expected_config=snapshot["config"],
    )

    assert parsed.to_mapping() == candidate.to_mapping()
    assert parsed.fingerprint() == candidate.fingerprint()
    assert decision.exact is True
    assert decision.action == "RESUME_EXACT"
    assert decision.reason_code == "EXACT_CPU_SNAPSHOT"
    assert decision.new_attempt_required is False



def test_malformed_equal_resume_snapshots_do_not_exact_resume() -> None:
    previous = deepcopy(FIXTURE["exact_resume_snapshot"])
    candidate = deepcopy(previous)
    malformed_cases = [
        ("model", "weights_sha256"),
        ("torch_rng", "cpu_state_sha256"),
        ("deps", "state_sha256"),
        ("config", "no_heavy_compute"),
        ("protocol", "protocol_sha256"),
    ]

    for section, key in malformed_cases:
        broken_previous = deepcopy(previous)
        broken_candidate = deepcopy(candidate)
        del broken_previous[section][key]
        del broken_candidate[section][key]

        with pytest.raises(state.ResumeSnapshotError):
            state.ResumeSnapshot.from_mapping(broken_previous)
        decision = state.decide_resume(broken_previous, broken_candidate)

        assert decision.exact is False
        assert decision.action == "RESTART_NEW_ATTEMPT"
        assert decision.reason_code == "MISSING_RESUME_SECTION"
        assert decision.new_attempt_required is True

def test_non_exact_resume_inputs_restart_with_new_attempt_not_config_retry() -> None:
    previous = deepcopy(FIXTURE["exact_resume_snapshot"])
    cuda = deepcopy(previous)
    cuda["device"] = {"kind": "cuda", "torch_device": "cuda:0"}
    midrollout = deepcopy(previous)
    midrollout["rollout"]["midrollout"] = True
    missing = deepcopy(previous)
    del missing["torch_rng"]
    mismatch = deepcopy(previous)
    mismatch["model"]["weights_sha256"] = "0101010101010101010101010101010101010101010101010101010101010101"

    assert state.decide_resume(previous, cuda).reason_code == "CUDA_SNAPSHOT"
    assert state.decide_resume(previous, midrollout).reason_code == "MIDROLLOUT_SNAPSHOT"
    assert state.decide_resume(previous, missing).reason_code == "MISSING_RESUME_SECTION"
    mismatch_decision = state.decide_resume(previous, mismatch)
    assert mismatch_decision.reason_code == "SNAPSHOT_MISMATCH"
    assert mismatch_decision.new_attempt_required is True

    run_state = state.start_cell(state.build_initial_state(), FIXTURE["first_cell_uid"])
    restarted = state.start_new_attempt(run_state, FIXTURE["first_cell_uid"], mismatch_decision)
    restarted_cell = restarted.cell_by_uid(FIXTURE["first_cell_uid"])

    assert restarted_cell.cell_uid == FIXTURE["first_cell_uid"]
    assert restarted_cell.attempt_number == 2
    assert restarted_cell.attempt_uid != FIXTURE["first_attempt_uid"]
    assert restarted_cell.status == "PENDING"

    checkpoint_ref = state.snapshot_artifact(
        FIXTURE["exact_resume_snapshot"],
        uri="kronos-run://fixture/restart-checkpoint-10240",
    ).ref
    checkpointed_source = state.record_checkpoint(
        state.start_cell(state.build_initial_state(), FIXTURE["first_cell_uid"]),
        FIXTURE["first_cell_uid"],
        step=state.CHECKPOINT_INTERVAL_STEPS,
        snapshot_ref=checkpoint_ref,
    )
    checkpoint_restarted = state.start_new_attempt(
        checkpointed_source,
        FIXTURE["first_cell_uid"],
        mismatch_decision,
    )
    assert checkpoint_restarted.cell_by_uid(FIXTURE["first_cell_uid"]).attempt_number == 2
    with pytest.raises(state.DailyPortfolioSb3StateError, match="pending"):
        state.start_new_attempt(state.build_initial_state(), FIXTURE["first_cell_uid"], mismatch_decision)

    completed_source = state.complete_cell(
        state.start_cell(state.build_initial_state(), FIXTURE["first_cell_uid"]),
        FIXTURE["first_cell_uid"],
        step=1,
    )
    with pytest.raises(state.DailyPortfolioSb3StateError, match="completed"):
        state.start_new_attempt(completed_source, FIXTURE["first_cell_uid"], mismatch_decision)

    exact_decision = state.decide_resume(previous, previous)
    with pytest.raises(state.DailyPortfolioSb3StateError, match="non-exact"):
        state.start_new_attempt(run_state, FIXTURE["first_cell_uid"], exact_decision)

    bad_reason = state.ResumeDecision(
        exact=False,
        action="RESTART_NEW_ATTEMPT",
        reason_code="UNRECOGNIZED_RESTART",
        previous_sha256=None,
        candidate_sha256=None,
        new_attempt_required=True,
    )
    with pytest.raises(state.DailyPortfolioSb3StateError, match="reason"):
        state.start_new_attempt(run_state, FIXTURE["first_cell_uid"], bad_reason)
    with pytest.raises(state.DailyPortfolioSb3StateError, match="config retry"):
        state.start_new_attempt(run_state, FIXTURE["first_cell_uid"], mismatch_decision, config_overrides={"n_steps": 257})
    with pytest.raises(state.DailyPortfolioSb3StateError, match="config retry"):
        state.request_config_retry()


def test_terminal_artifacts_are_emitted_and_terminal_state_is_immutable() -> None:
    restart_decision = state.ResumeDecision(False, "RESTART_NEW_ATTEMPT", "SNAPSHOT_MISMATCH", None, None, True)

    stopped = state.stop_run(
        state.build_initial_state(),
        stop_codes=["D0_PRICE_BASIS_NOT_VERIFIED", "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED"],
        reason_code="AUTHORITY_BLOCK",
        stopped_at="2026-07-15T00:00:00Z",
    )
    assert stopped.state.status == "STOPPED"
    assert stopped.artifact.payload["terminal_status"] == "STOPPED"
    assert stopped.artifact.ref["sha256"] == protocol.sha256_hex(stopped.artifact.raw)
    assert stopped.artifact.payload["claims"]["training_allowed"] is False
    with pytest.raises(state.DailyPortfolioSb3StateError, match="immutable"):
        state.start_cell(stopped.state, FIXTURE["first_cell_uid"])
    with pytest.raises(state.DailyPortfolioSb3StateError, match="immutable"):
        state.start_new_attempt(stopped.state, FIXTURE["first_cell_uid"], restart_decision)

    failed = state.fail_run(state.build_initial_state(), reason_code="SYNTHETIC_EXECUTOR_FAILURE", failed_at="2026-07-15T00:00:01Z")
    assert failed.state.status == "FAILED"
    assert failed.artifact.payload["terminal_status"] == "FAILED"
    with pytest.raises(state.DailyPortfolioSb3StateError, match="immutable"):
        state.start_new_attempt(failed.state, FIXTURE["first_cell_uid"], restart_decision)

    completed = runner.SyntheticDailyPortfolioSb3Runner().run(
        runner.SyntheticRunnerConfig(max_cells=50, steps_per_cell=3),
        completed_at="2026-07-15T00:00:02Z",
    )
    assert completed.state.status == "COMPLETED"
    assert completed.terminal_artifact is not None
    assert completed.terminal_artifact.payload["terminal_status"] == "COMPLETED"
    assert completed.terminal_artifact.payload["cell_counts"] == {"COMPLETED": 50}
    with pytest.raises(state.DailyPortfolioSb3StateError, match="immutable"):
        state.fail_run(completed.state, reason_code="LATE_FAILURE", failed_at="2026-07-15T00:00:03Z")
    with pytest.raises(state.DailyPortfolioSb3StateError, match="immutable"):
        state.start_new_attempt(completed.state, FIXTURE["first_cell_uid"], restart_decision)


def test_test_oos_read_requires_authority_and_consumes_capability_before_reader() -> None:
    class ReaderProbe:
        def __init__(self) -> None:
            self.calls = 0
            self.receipts: list[dict] = []

        def __call__(self, receipt: dict) -> dict:
            assert receipt["capability_consumed_before_read"] is True
            self.calls += 1
            self.receipts.append(dict(receipt))
            return {"read": "ok", "receipt": receipt}

    probe = ReaderProbe()
    blocked_store = state.InMemoryCapabilityConsumptionStore()
    with pytest.raises(state.AuthorityGateError, match="D0_PRICE_BASIS_NOT_VERIFIED"):
        state.read_partition_after_authority(
            "historical_secondary_only",
            FIXTURE["blocked_authority"],
            blocked_store,
            probe,
            consumed_at="2026-07-15T00:00:00Z",
            protocol_sha256=FIXTURE["protocol_sha256"],
        )
    assert probe.calls == 0
    assert blocked_store.consumed == frozenset()


    safe_receipt = state.authorize_partition_read(
        "Validation",
        FIXTURE["blocked_authority"],
        state.InMemoryCapabilityConsumptionStore(),
        consumed_at="2026-07-15T00:00:00Z",
        protocol_sha256=FIXTURE["protocol_sha256"],
    )
    assert safe_receipt["partition"] == "validation"
    assert safe_receipt["protected_read"] is False

    for alias in ("test_oos", "official_test_oos", "historical-test-oos-secondary-only", "fresh-oos", "oos"):
        alias_store = state.InMemoryCapabilityConsumptionStore()
        with pytest.raises(state.AuthorityGateError, match="FRESH_OOS_ACCESS_REQUESTED|TEST_OOS_ALIAS_DENIED"):
            state.read_partition_after_authority(
                alias,
                FIXTURE["blocked_authority"],
                alias_store,
                probe,
                consumed_at="2026-07-15T00:00:00Z",
                protocol_sha256=FIXTURE["protocol_sha256"],
            )
        assert alias_store.consumed == frozenset()
    assert probe.calls == 0
    unknown_store = state.InMemoryCapabilityConsumptionStore()
    with pytest.raises(state.AuthorityGateError, match="PARTITION_READ_NOT_ALLOWLISTED"):
        state.read_partition_after_authority(
            "research",
            FIXTURE["blocked_authority"],
            unknown_store,
            probe,
            consumed_at="2026-07-15T00:00:00Z",
            protocol_sha256=FIXTURE["protocol_sha256"],
        )
    assert unknown_store.consumed == frozenset()
    assert probe.calls == 0
    verified_store = state.InMemoryCapabilityConsumptionStore()
    result = state.read_partition_after_authority(
        "historical_secondary_only",
        FIXTURE["verified_authority"],
        verified_store,
        probe,
        consumed_at="2026-07-15T00:00:01Z",
        protocol_sha256=FIXTURE["protocol_sha256"],
    )
    assert result["read"] == "ok"
    assert probe.calls == 1
    consumed_key = (FIXTURE["verified_authority"]["capability_sha256"], FIXTURE["verified_authority"]["nonce_sha256"])
    assert consumed_key in verified_store.consumed

    with pytest.raises(state.AuthorityGateError, match="ALREADY_CONSUMED"):
        state.read_partition_after_authority(
            "historical_secondary_only",
            FIXTURE["verified_authority"],
            verified_store,
            probe,
            consumed_at="2026-07-15T00:00:02Z",
            protocol_sha256=FIXTURE["protocol_sha256"],
        )
    with pytest.raises(state.AuthorityGateError, match="FRESH_OOS_ACCESS_REQUESTED"):
        state.read_partition_after_authority(
            "fresh_oos",
            FIXTURE["verified_authority"],
            verified_store,
            probe,
            consumed_at="2026-07-15T00:00:03Z",
            protocol_sha256=FIXTURE["protocol_sha256"],
        )
    assert probe.calls == 1


def test_checkpoint_interval_stop_order_and_matrix_state_transitions() -> None:
    initial = state.build_initial_state()
    assert len(initial.cells) == 50
    assert initial.phase == FIXTURE["matrix_transitions"][0]
    assert initial.cells[0].cell_uid == FIXTURE["first_cell_uid"]
    assert tuple(state.STOP_PREDICATE_CODES) == tuple(FIXTURE["stop_predicate_order"])

    all_stop_codes = state.evaluate_stop_predicates(
        missing_session=True,
        label_leakage_past_fit=True,
        alias_variant=True,
        protocol_drift=True,
        noncanonical_code_or_hash=True,
        fresh_oos_access_requested=True,
        unsupported_compute=True,
        d0_status="BLOCKED",
        d1_status="WATCH",
        require_fresh_oos_for_claim=True,
        fresh_oos_status="FRESH_OOS_NOT_RUN",
        metric_values=[float("nan")],
        invalid_action_rate=0.051,
    )
    assert all_stop_codes == tuple(FIXTURE["stop_predicate_order"])
    with pytest.raises(state.DailyPortfolioSb3StateError, match="order"):
        state.ordered_stop_codes(["D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED", "D0_PRICE_BASIS_NOT_VERIFIED"])

    running = state.start_cell(initial, FIXTURE["first_cell_uid"])
    assert running.phase == FIXTURE["matrix_transitions"][1]
    assert state.checkpoint_due(FIXTURE["checkpoint_interval_steps"])
    snapshot_ref = state.snapshot_artifact(FIXTURE["exact_resume_snapshot"], uri="kronos-run://fixture/checkpoint-10240").ref
    with pytest.raises(state.DailyPortfolioSb3StateError, match="10240"):
        state.record_checkpoint(running, FIXTURE["first_cell_uid"], step=10_239, snapshot_ref=snapshot_ref)
    checkpointed = state.record_checkpoint(running, FIXTURE["first_cell_uid"], step=10_240, snapshot_ref=snapshot_ref)
    checkpointed_cell = checkpointed.cell_by_uid(FIXTURE["first_cell_uid"])
    assert checkpointed_cell.next_checkpoint_step == 20_480
    assert checkpointed_cell.checkpoint_refs == (snapshot_ref,)
    with pytest.raises(state.DailyPortfolioSb3StateError, match="checkpoint due"):
        state.complete_cell(checkpointed, FIXTURE["first_cell_uid"], step=20_480)
    cell_done = state.complete_cell(checkpointed, FIXTURE["first_cell_uid"], step=10_241)
    assert cell_done.phase == FIXTURE["matrix_transitions"][2]

    completed = runner.SyntheticDailyPortfolioSb3Runner().run(runner.SyntheticRunnerConfig(max_cells=50, steps_per_cell=3))
    assert completed.state.phase == FIXTURE["matrix_transitions"][3]
    assert completed.state.matrix_counts() == {"COMPLETED": 50}
    events.validate_event_stream(completed.event_stream)
    replayed = events.replay_event_stream(completed.event_stream)
    assert completed.event_stream["events"][-1]["event"]["event_kind"] == "STOP"
    assert replayed["stream"]["event_count"] == completed.event_stream["event_count"]
    with pytest.raises(runner.SyntheticRunnerError, match="heavy"):
        runner.SyntheticDailyPortfolioSb3Runner().run(runner.SyntheticRunnerConfig(max_cells=1, steps_per_cell=state.MAX_SYNTHETIC_STEPS_PER_CELL + 1))
    with pytest.raises(runner.SyntheticRunnerError, match="synthetic"):
        runner.SyntheticDailyPortfolioSb3Runner().run(runner.SyntheticRunnerConfig(max_cells=1, synthetic_verification_only=False))

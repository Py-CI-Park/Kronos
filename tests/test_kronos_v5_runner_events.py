from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import stom_rl.daily_portfolio_sb3_events as events
import stom_rl.daily_portfolio_sb3_runner as runner


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_daily_sb3_events.v1.schema.json"
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_daily_sb3_events_fixture.json").read_text(encoding="utf-8"))
EXPECTED_LIFECYCLE = (
    "ADVANCING",
    "STALLED",
    "RESUMED",
    "RESTARTED_NON_EXACT",
    "STOPPED",
    "FAILED",
    "COMPLETED",
    "CONFLICT_BLOCKED",
    "NOT_RUN",
)


def _stream() -> dict:
    return deepcopy(events.build_fixture_stream())


def _rehash_chain(stream: dict) -> None:
    previous = events.ZERO_SHA256
    for record in stream["events"]:
        record["event"]["previous_event_sha256"] = previous
        digest = events.event_sha256(record["event"])
        record["event_sha256"] = digest
        previous = digest
    stream["final_event_sha256"] = previous


def _reject(stream: dict) -> None:
    with pytest.raises(events.DailySb3EventsError):
        events.validate_event_stream(stream)


def test_schema_fixture_and_replay_state_are_deterministic() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    stream = events.build_fixture_stream()
    Draft202012Validator(schema).validate(stream)
    events.validate_event_stream(stream)
    state = events.replay_event_stream(stream)

    assert events.LIFECYCLE_STATES == EXPECTED_LIFECYCLE
    assert schema["$defs"]["event"]["properties"]["lifecycle_state"]["enum"] == list(EXPECTED_LIFECYCLE)
    assert schema["$defs"]["event"]["properties"]["attempt_number"] == {"$ref": "#/$defs/attemptNumber"}
    assert events.fixture_summary(stream) == FIXTURE
    assert events.build_fixture_stream() == stream
    assert events.state_sha256(state) == FIXTURE["state_sha256"]
    assert state["protocol"]["cell_count"] == 50
    assert state["locks"] == events.FALSE_LOCKS

    active = [cell for cell in state["cells"] if cell["run_uid"] is not None]
    assert len(active) == 1
    assert active[0]["lifecycle_state"] == "STOPPED"
    assert active[0]["last_step"] == 1
    assert active[0]["attempt_number"] == 2
    assert active[0]["heartbeat_count"] == 0
    assert active[0]["resume_count"] == 2
    assert active[0]["liveness"] == {"live": False, "basis": "TERMINAL"}
    assert all("payload" not in record["event"] for record in stream["events"])
    assert all(ref["byte_length"] <= 8192 for record in stream["events"] for ref in record["event"]["artifact_refs"])


def test_append_only_validation_rejects_gap_fork_tamper_and_non_monotonic_time() -> None:
    gap = _stream()
    gap["events"][3]["event"]["global_sequence"] = 9
    _rehash_chain(gap)
    _reject(gap)

    fork = _stream()
    fork["events"][3]["event"]["previous_event_sha256"] = fork["events"][0]["event_sha256"]
    fork["events"][3]["event_sha256"] = events.event_sha256(fork["events"][3]["event"])
    _reject(fork)

    tamper = _stream()
    tamper["events"][-1]["event"]["stop"]["reason_code"] = "SYNTHETIC_FAILURE"
    _reject(tamper)

    chronology = _stream()
    chronology["events"][2]["event"]["occurred_at"] = "2026-07-14T23:59:59Z"
    _rehash_chain(chronology)
    _reject(chronology)

def test_terminal_run_cell_stream_is_immutable_after_stop_completed_and_failed() -> None:
    empty_state = events.replay_event_stream(events.start_event_stream(created_at="2026-07-15T00:00:00Z"))
    first_cell_uid = empty_state["cells"][0]["cell_uid"]
    other_cell_uid = empty_state["cells"][1]["cell_uid"]

    def make_terminal_stream(lifecycle_state: str, reason_code: str, run_suffix: str) -> dict:
        run_uid = f"kdp1-run-{run_suffix * 32}"
        report = events.artifact_ref(
            f"agent://kronos-v5/stop-reports/{run_uid}/{reason_code.lower()}",
            "kronos_daily_sb3_stop_report.v1",
            "synthetic_stop_report",
            {"schema": "kronos_daily_sb3_stop_report.v1", "run_uid": run_uid, "reason_code": reason_code},
        )
        stream = events.start_event_stream(created_at="2026-07-15T00:00:00Z")
        stream = events.append_event(
            stream,
            run_uid=run_uid,
            cell_uid=first_cell_uid,
            occurred_at="2026-07-15T00:00:00Z",
            event_kind="RUN_CREATED",
            phase="PREREGISTERED",
            lifecycle_state="NOT_RUN",
            step=0,
            total_steps=1,
        )
        return events.append_event(
            stream,
            run_uid=run_uid,
            cell_uid=first_cell_uid,
            occurred_at="2026-07-15T00:00:01Z",
            event_kind="STOP",
            phase="STOP" if lifecycle_state == "STOPPED" else "TERMINAL",
            lifecycle_state=lifecycle_state,
            step=0,
            total_steps=1,
            artifact_refs=[report],
            stop_reason_code=reason_code,
        )

    stopped = events.build_fixture_stream()
    stopped_terminal = stopped["events"][-1]["event"]
    stopped_common = {
        "run_uid": stopped_terminal["run_uid"],
        "cell_uid": stopped_terminal["cell"]["cell_uid"],
        "occurred_at": "2026-07-15T00:00:10Z",
        "total_steps": stopped_terminal["progress"]["total_steps"],
    }
    with pytest.raises(events.DailySb3EventsError, match="immutable"):
        events.append_event(
            stopped,
            **stopped_common,
            event_kind="HEARTBEAT",
            phase="SYNTHETIC_TRAIN",
            lifecycle_state="STALLED",
            step=stopped_terminal["progress"]["step"],
            heartbeat_observed=True,
        )
    with pytest.raises(events.DailySb3EventsError, match="immutable"):
        events.append_event(
            stopped,
            **stopped_common,
            event_kind="PROGRESS",
            phase="SYNTHETIC_TRAIN",
            lifecycle_state="ADVANCING",
            step=stopped_terminal["progress"]["step"] + 1,
        )
    with pytest.raises(events.DailySb3EventsError, match="immutable"):
        events.append_event(
            stopped,
            **stopped_common,
            event_kind="STOP",
            phase=stopped_terminal["phase"],
            lifecycle_state=stopped_terminal["lifecycle_state"],
            step=stopped_terminal["progress"]["step"],
            artifact_refs=stopped_terminal["artifact_refs"],
            stop_reason_code=stopped_terminal["stop"]["reason_code"],
        )

    for lifecycle_state, reason_code, run_suffix in (
        ("STOPPED", "USER_REQUESTED_STOP", "4"),
        ("COMPLETED", "SYNTHETIC_COMPLETE", "2"),
        ("FAILED", "SYNTHETIC_FAILURE", "3"),
    ):
        terminal_stream = make_terminal_stream(lifecycle_state, reason_code, run_suffix)
        terminal = terminal_stream["events"][-1]["event"]
        with pytest.raises(events.DailySb3EventsError, match="immutable"):
            events.append_event(
                terminal_stream,
                run_uid=terminal["run_uid"],
                cell_uid=other_cell_uid,
                occurred_at="2026-07-15T00:00:02Z",
                event_kind="HEARTBEAT",
                phase="SYNTHETIC_TRAIN",
                lifecycle_state="STALLED",
                step=terminal["progress"]["step"],
                total_steps=terminal["progress"]["total_steps"],
                heartbeat_observed=True,
            )


def test_identity_and_liveness_semantics_fail_closed() -> None:
    bad_protocol = _stream()
    bad_protocol["events"][0]["event"]["protocol_sha256"] = "0" * 64
    _rehash_chain(bad_protocol)
    _reject(bad_protocol)

    bad_source = _stream()
    bad_source["events"][0]["event"]["source_ref"]["sha256"] = "0" * 64
    _rehash_chain(bad_source)
    _reject(bad_source)

    bad_cell = _stream()
    last_cell = events.replay_event_stream(_stream())["cells"][-1]
    bad_cell["events"][0]["event"]["cell"]["cell_uid"] = last_cell["cell_uid"]
    _rehash_chain(bad_cell)
    _reject(bad_cell)

    heartbeat_live = _stream()
    heartbeat_live["events"][2]["event"]["liveness"]["live"] = True
    _rehash_chain(heartbeat_live)
    _reject(heartbeat_live)

    heartbeat_advancing = _stream()
    heartbeat_advancing["events"][2]["event"]["lifecycle_state"] = "ADVANCING"
    _rehash_chain(heartbeat_advancing)
    _reject(heartbeat_advancing)

    progress_without_step_increase = _stream()
    progress_without_step_increase["events"][5]["event"]["progress"] = {"step": 1, "total_steps": 3, "percent_complete": "33.333333"}
    _rehash_chain(progress_without_step_increase)
    _reject(progress_without_step_increase)


def test_exact_and_nonexact_resume_attempt_transitions_replay() -> None:
    stream = events.build_fixture_stream()
    replayed = events.replay_event_stream(stream)
    resume_events = [record["event"] for record in stream["events"] if record["event"]["event_kind"] == "RESUME"]

    assert [event["lifecycle_state"] for event in resume_events] == ["RESUMED", "RESTARTED_NON_EXACT"]
    assert [event["attempt_number"] for event in resume_events] == [1, 2]
    assert replayed["cells"][0]["attempt_number"] == 2
    assert replayed["cells"][0]["attempt_uid"] == resume_events[-1]["attempt_uid"]

    jump = _stream()
    jump["events"][7]["event"]["attempt_number"] = 3
    jump["events"][7]["event"]["attempt_uid"] = f"kdp1-attempt-{events.sha256_hex({'bad': 'attempt'})[:32]}"
    _rehash_chain(jump)
    _reject(jump)


def test_resume_requires_prior_matching_eligible_checkpoint() -> None:
    cell_uid = events.replay_event_stream(events.start_event_stream())["cells"][0]["cell_uid"]
    run_uid = "kdp1-run-55555555555555555555555555555555"
    pending_checkpoint = events.artifact_ref(
        f"agent://kronos-v5/checkpoints/{run_uid}/{cell_uid}/pending-step-0",
        "kronos_daily_sb3_checkpoint_ref.v1",
        "synthetic_checkpoint",
        {"schema": "kronos_daily_sb3_checkpoint_ref.v1", "run_uid": run_uid, "cell_uid": cell_uid, "attempt_number": 1, "step": 0},
    )
    stream = events.start_event_stream(created_at="2026-07-15T00:00:00Z")
    stream = events.append_event(
        stream,
        run_uid=run_uid,
        cell_uid=cell_uid,
        occurred_at="2026-07-15T00:00:00Z",
        event_kind="RUN_CREATED",
        phase="PREREGISTERED",
        lifecycle_state="NOT_RUN",
        step=0,
        total_steps=3,
    )
    stream = events.append_event(
        stream,
        run_uid=run_uid,
        cell_uid=cell_uid,
        occurred_at="2026-07-15T00:00:01Z",
        event_kind="CHECKPOINT",
        phase="CHECKPOINT",
        lifecycle_state="STALLED",
        step=0,
        total_steps=3,
        artifact_refs=[pending_checkpoint],
        checkpoint_ref=pending_checkpoint,
    )
    for resume_exact, lifecycle_state in ((True, "RESUMED"), (False, "RESTARTED_NON_EXACT")):
        with pytest.raises(events.DailySb3EventsError, match="prior matching eligible CHECKPOINT"):
            events.append_event(
                stream,
                run_uid=run_uid,
                cell_uid=cell_uid,
                occurred_at="2026-07-15T00:00:02Z",
                event_kind="RESUME",
                phase="RESUME",
                lifecycle_state=lifecycle_state,
                step=0,
                total_steps=3,
                resume_from_checkpoint_ref=pending_checkpoint,
                resume_exact=resume_exact,
            )

    for resume_index in (4, 7):
        arbitrary_resume = _stream()
        resume_event = arbitrary_resume["events"][resume_index]["event"]
        arbitrary_checkpoint = events.artifact_ref(
            f"agent://kronos-v5/checkpoints/{resume_event['run_uid']}/{resume_event['cell']['cell_uid']}/arbitrary-{resume_index}",
            "kronos_daily_sb3_checkpoint_ref.v1",
            "synthetic_checkpoint",
            {"schema": "kronos_daily_sb3_checkpoint_ref.v1", "run_uid": resume_event["run_uid"], "cell_uid": resume_event["cell"]["cell_uid"], "attempt_number": 1, "step": 2, "arbitrary": True},
        )
        resume_event["resume"]["from_checkpoint_ref"] = arbitrary_checkpoint
        _rehash_chain(arbitrary_resume)
        _reject(arbitrary_resume)


def test_runner_emits_canonical_chained_event_stream_for_exact_and_nonexact_resume() -> None:
    exact = runner.SyntheticDailyPortfolioSb3Runner().run(
        runner.SyntheticRunnerConfig(max_cells=1, steps_per_cell=3, resume_mode="exact")
    )
    nonexact = runner.SyntheticDailyPortfolioSb3Runner().run(
        runner.SyntheticRunnerConfig(max_cells=1, steps_per_cell=3, resume_mode="non_exact")
    )

    for result, expected_attempt in ((exact, 1), (nonexact, 2)):
        events.validate_event_stream(result.event_stream)
        replayed = events.replay_event_stream(result.event_stream)
        active = [cell for cell in replayed["cells"] if cell["run_uid"] is not None]
        resume_event = [record["event"] for record in result.event_stream["events"] if record["event"]["event_kind"] == "RESUME"][0]
        event_kinds = [record["event"]["event_kind"] for record in result.event_stream["events"]]

        assert result.to_mapping()["event_stream"] == result.event_stream
        assert active[0]["attempt_number"] == expected_attempt
        assert active[0]["attempt_uid"] == resume_event["attempt_uid"]
        assert resume_event["lifecycle_state"] == ("RESUMED" if expected_attempt == 1 else "RESTARTED_NON_EXACT")
        assert event_kinds.index("CHECKPOINT") < event_kinds.index("RESUME")
        assert all(record["schema"] == events.EVENT_RECORD_SCHEMA for record in result.events)


def test_heartbeat_only_stream_replays_stalled_not_live() -> None:
    cell_uid = events.build_fixture_stream()["events"][0]["event"]["cell"]["cell_uid"]
    run_uid = "kdp1-run-11111111111111111111111111111111"
    stream = events.start_event_stream(created_at="2026-07-15T00:00:00Z")
    stream = events.append_event(
        stream,
        run_uid=run_uid,
        cell_uid=cell_uid,
        occurred_at="2026-07-15T00:00:00Z",
        event_kind="RUN_CREATED",
        phase="PREREGISTERED",
        lifecycle_state="NOT_RUN",
        step=0,
        total_steps=2,
    )
    stream = events.append_event(
        stream,
        run_uid=run_uid,
        cell_uid=cell_uid,
        occurred_at="2026-07-15T00:00:01Z",
        event_kind="HEARTBEAT",
        phase="SYNTHETIC_TRAIN",
        lifecycle_state="STALLED",
        step=0,
        total_steps=2,
        heartbeat_observed=True,
    )

    state = events.replay_event_stream(stream)
    active = [cell for cell in state["cells"] if cell["run_uid"] == run_uid]
    assert len(active) == 1
    assert active[0]["lifecycle_state"] == "STALLED"
    assert active[0]["liveness"] == {"live": False, "basis": "HEARTBEAT_ONLY"}
    assert active[0]["last_live_at"] is None
    assert active[0]["last_progress_at"] is None
    assert active[0]["heartbeat_count"] == 1

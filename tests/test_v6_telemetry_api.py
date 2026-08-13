"""HTTP contract coverage for the V6 telemetry API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from webui.v6_research_api import create_v6_research_blueprint
from webui.v6_telemetry_api import create_v6_telemetry_blueprint
from webui.v6_run_telemetry import read_telemetry


def _client(tmp_path: Path):
    run = tmp_path / "daily_close_dqn"
    run.mkdir()
    events = tuple(
        {
            "global_step": step,
            "phase": "train",
            "reward": 0.04,
            "equity": 1.02,
            "telemetry_live_stream": True,
            "telemetry_producer_state": "RUNNING",
            "info": {
                "reward_kind": "return_fraction",
                "reward_unit": "fraction",
                "equity_kind": "normalized_nav",
                "equity_unit": "normalized",
                "action_recorded": False,
            },
        }
        for step in (7, 8)
    )
    (run / "rl_live_events.jsonl").write_text(
        "".join(f"{json.dumps(event)}\n" for event in events),
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_telemetry_blueprint(runs_root=tmp_path))
    app.config.update(TESTING=True)
    return app.test_client()


def test_telemetry_api_lists_runs_and_returns_bounded_points(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When
    listing = client.get("/api/v6/telemetry-runs")
    telemetry = client.get("/api/v6/research-runs/daily_close_dqn/telemetry?limit=120")

    # Then
    assert listing.status_code == 200
    assert listing.get_json()["items"][0]["run_id"] == "daily_close_dqn"
    assert telemetry.status_code == 200
    payload = telemetry.get_json()
    assert payload["follow_mode"] == "HISTORICAL_SNAPSHOT"
    assert payload["points"] == [
        {
            "step": step,
            "phase": "train",
            "reward": 0.04,
            "equity": 1.02,
            "loss": None,
            "exploration": None,
            "action_name": "MISSING",
            "timestamp": "MISSING",
            "decision_timestamp": None,
            "reward_observed_at": None,
            "reward_kind": "return_fraction",
            "reward_unit": "fraction",
            "equity_kind": "normalized_nav",
            "equity_unit": "normalized",
            "action_recorded": False,
            "telemetry_live_stream": True,
            "telemetry_producer_state": "RUNNING",
        }
        for step in (7, 8)
    ]


def test_telemetry_api_does_not_infer_units_for_legacy_events(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "legacy_dqn"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        json.dumps({"global_step": 1, "reward": 2.0, "equity": 1.1}) + "\n",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_telemetry_blueprint(runs_root=tmp_path))

    # When
    with app.test_client() as client:
        payload = client.get("/api/v6/research-runs/legacy_dqn/telemetry").get_json()

    # Then
    assert (
        payload["points"][0]
        | {
            "reward_kind": None,
            "reward_unit": None,
            "equity_kind": None,
            "equity_unit": None,
            "action_recorded": None,
            "telemetry_live_stream": None,
            "telemetry_producer_state": None,
        }
        == payload["points"][0]
    )


def test_recent_historical_replay_never_claims_a_live_stream(tmp_path: Path) -> None:
    # Given: a newly written validation replay explicitly declares it is historical.
    run = tmp_path / "validation_replay"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        json.dumps(
            {
                "global_step": 1,
                "phase": "VALIDATION_REPLAY",
                "reward": 0.01,
                "telemetry_live_stream": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_telemetry_blueprint(runs_root=tmp_path))

    # When: it is queried while its filesystem mtime is still fresh.
    with app.test_client() as client:
        payload = client.get(
            "/api/v6/research-runs/validation_replay/telemetry"
        ).get_json()

    # Then: event semantics override recency and the API remains fail-closed.
    assert payload["follow_mode"] == "HISTORICAL_SNAPSHOT"
    assert payload["claims"]["live_stream"] is False


def test_telemetry_preserves_decision_and_reward_observation_times(
    tmp_path: Path,
) -> None:
    run = tmp_path / "allocation_replay"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        json.dumps(
            {
                "global_step": 1,
                "phase": "VALIDATION_REPLAY",
                "timestamp": "2026-01-19T09:00:00+09:00",
                "decision_timestamp": "2026-01-15T15:30:00+09:00",
                "reward_observed_at": "2026-01-19T09:00:00+09:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    point = read_telemetry(run).points[0]

    assert point.decision_timestamp == "2026-01-15T15:30:00+09:00"
    assert point.reward_observed_at == "2026-01-19T09:00:00+09:00"
    assert point.timestamp == point.reward_observed_at


def test_telemetry_rejects_growth_during_a_bounded_read(tmp_path: Path) -> None:
    run = tmp_path / "growing"
    run.mkdir()
    event_path = run / "rl_live_events.jsonl"
    event_path.write_text("{}\n", encoding="utf-8")
    real_fstat = os.fstat
    calls = 0

    def grow_after_first_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        observed = real_fstat(descriptor)
        if calls == 0:
            with event_path.open("ab") as stream:
                _ = stream.write(b"x" * (5 * 1024 * 1024))
        calls += 1
        return observed

    with (
        patch(
            "webui.v6_telemetry_file_custody.os.fstat",
            side_effect=grow_after_first_fstat,
        ),
        pytest.raises(OSError, match="changed during bounded read"),
    ):
        _ = read_telemetry(run)


def test_static_running_file_requires_cross_poll_step_advancement(
    tmp_path: Path,
) -> None:
    run = tmp_path / "declared_running"
    run.mkdir()
    event_path = run / "rl_live_events.jsonl"
    events = (
        {
            "global_step": step,
            "phase": "train",
            "telemetry_live_stream": True,
            "telemetry_producer_state": "RUNNING",
        }
        for step in (1, 2)
    )
    event_path.write_text(
        "".join(f"{json.dumps(event)}\n" for event in events),
        encoding="utf-8",
    )

    first = read_telemetry(run)
    unchanged = read_telemetry(run)
    with event_path.open("a", encoding="utf-8") as handle:
        _ = handle.write(
            json.dumps(
                {
                    "global_step": 3,
                    "phase": "train",
                    "telemetry_live_stream": True,
                    "telemetry_producer_state": "RUNNING",
                }
            )
            + "\n"
        )
    advanced = read_telemetry(run)

    assert first.follow_mode == "HISTORICAL_SNAPSHOT"
    assert unchanged.follow_mode == "HISTORICAL_SNAPSHOT"
    assert advanced.follow_mode == "FOLLOWING_FILE"


def test_invalid_event_line_prevents_live_follow_claim(tmp_path: Path) -> None:
    run = tmp_path / "invalid_live_stream"
    run.mkdir()
    event_path = run / "rl_live_events.jsonl"
    valid = {
        "phase": "train",
        "telemetry_live_stream": True,
        "telemetry_producer_state": "RUNNING",
    }
    event_path.write_text(
        f"{json.dumps({**valid, 'global_step': 1})}\n"
        "not-json\n"
        f"{json.dumps({**valid, 'global_step': 2})}\n",
        encoding="utf-8",
    )
    _ = read_telemetry(run)
    with event_path.open("a", encoding="utf-8") as handle:
        _ = handle.write(f"{json.dumps({**valid, 'global_step': 3})}\n")

    observed = read_telemetry(run)

    assert observed.invalid_lines == 1
    assert observed.follow_mode == "HISTORICAL_SNAPSHOT"


def test_head_tail_sample_never_claims_every_event_is_live(tmp_path: Path) -> None:
    run = tmp_path / "sampled_live_stream"
    run.mkdir()
    event_path = run / "rl_live_events.jsonl"
    lines: list[str] = []
    for step in range(1, 50_002):
        lines.append(
            json.dumps(
                {
                    "global_step": step,
                    "phase": "train",
                    "telemetry_live_stream": step != 25_000,
                    "telemetry_producer_state": "RUNNING",
                    "padding": "x" * 32,
                }
            )
        )
    event_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    first = read_telemetry(run)
    with event_path.open("a", encoding="utf-8") as handle:
        _ = handle.write(
            json.dumps(
                {
                    "global_step": 50_002,
                    "phase": "train",
                    "telemetry_live_stream": True,
                    "telemetry_producer_state": "RUNNING",
                }
            )
            + "\n"
        )

    advanced = read_telemetry(run)

    assert first.sampling == "HEAD_TAIL_SAMPLE"
    assert advanced.sampling == "HEAD_TAIL_SAMPLE"
    assert advanced.follow_mode == "HISTORICAL_SNAPSHOT"


def test_telemetry_reader_rejects_a_symlinked_event_file(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "symlinked"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text("{}\n", encoding="utf-8")

    # When / Then
    with (
        patch.object(Path, "is_symlink", return_value=True),
        pytest.raises(FileNotFoundError),
    ):
        read_telemetry(run)


def test_integrated_research_and_telemetry_routes_do_not_collide(
    tmp_path: Path,
) -> None:
    # Given
    run = tmp_path / "daily_close_dqn"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        json.dumps({"global_step": 1, "reward": 0.1}) + "\n",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(
        create_v6_research_blueprint(runs_root=tmp_path, name="integrated_research")
    )
    app.register_blueprint(
        create_v6_telemetry_blueprint(runs_root=tmp_path, name="integrated_telemetry")
    )

    # When
    with app.test_client() as client:
        response = client.get(
            "/api/v6/research-runs/daily_close_dqn/telemetry?limit=20"
        )

    # Then
    assert response.status_code == 200
    assert response.get_json()["schema_version"] == "kronos_v6_run_telemetry.v1"


def test_telemetry_api_lists_event_files_inside_generic_run_groups(
    tmp_path: Path,
) -> None:
    # Given
    grouped = tmp_path / "daily_close_slot_train" / "market_cql_seed0"
    grouped.mkdir(parents=True)
    (grouped / "rl_live_events.jsonl").write_text(
        json.dumps({"global_step": 3, "phase": "train", "action_name": "CASH"}) + "\n",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(create_v6_telemetry_blueprint(runs_root=tmp_path))

    # When
    with app.test_client() as client:
        payload = client.get("/api/v6/telemetry-runs").get_json()

    # Then
    assert [row["run_id"] for row in payload["items"]] == [
        "daily_close_slot_train/market_cql_seed0"
    ]


def test_telemetry_api_rejects_invalid_limit_path_and_method(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When / Then
    assert (
        client.get(
            "/api/v6/research-runs/daily_close_dqn/telemetry?limit=2"
        ).status_code
        == 400
    )
    assert client.get("/api/v6/research-runs/..%2Fsecret/telemetry").status_code == 400
    assert client.get("/api/v6/research-runs/missing/telemetry").status_code == 404
    post = client.post("/api/v6/telemetry-runs")
    assert post.status_code == 405
    assert post.headers["Allow"] == "GET"


def test_official_dashboard_registers_telemetry_routes() -> None:
    # Given
    from webui.app import app as dashboard_app

    # When
    routes = {rule.rule for rule in dashboard_app.url_map.iter_rules()}

    # Then
    assert "/api/v6/telemetry-runs" in routes
    assert "/api/v6/research-runs/<path:run_id>/telemetry" in routes

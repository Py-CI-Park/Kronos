from dataclasses import asdict
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d6_source import load_d6_recovery_validation


def test_d6_recovery_reuses_typed_snapshot_from_terminal_failed_run(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "runs/failed-d6"
    inputs = run / "inputs"
    inputs.mkdir(parents=True)
    prereg_bytes = b'{"frozen":true}'
    _ = (inputs / "prereg.json").write_bytes(prereg_bytes)
    features = (0.0,) * 14
    episode = D3Episode(
        "20260102",
        tuple((f"{index:06d}", features, 0.01) for index in range(5)),
        features,
        0.0,
    )
    snapshot = canonical_json_bytes([asdict(episode)])
    _ = (inputs / "validation_episodes.json").write_bytes(snapshot)
    _ = (run / "terminal_receipt.json").write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "kronos.rl-discovery.d6.receipt.v1",
                "profile": "PRIMARY",
                "status": "FAILED",
                "verdict": "NO_GO",
                "error_type": "PolicyLoadError",
                "reused_validation": "FAILED",
                "fresh_oos": "NOT_RUN_NO_READ",
                "live_broker_order_allowed": False,
            }
        )
    )

    # When
    episodes, recovered_bytes = load_d6_recovery_validation(
        tmp_path,
        run,
        prereg_bytes=prereg_bytes,
        episode_count=1,
    )

    # Then
    assert episodes == (episode,)
    assert recovered_bytes == snapshot

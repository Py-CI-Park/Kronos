from pathlib import Path

from stom_rl.rl_discovery.d5_contract import load_d5_prereg_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_d5_contract_freezes_full_train_cost_matrix() -> None:
    prereg = load_d5_prereg_bytes((ROOT / "docs/kronos_rl_discovery_type2_d5_prereg_2026-07-29.json").read_bytes())
    assert prereg.episode_count == 573
    assert prereg.seeds == (0, 1, 2, 3, 4)
    assert prereg.algorithm.training_steps == 200_000
    assert prereg.costs.training_round_trip_bp == 23
    assert len(prereg.reward_arms) * len(prereg.seeds) == 10
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"
    assert prereg.claims_boundary.reused_validation == "NOT_RUN_NO_READ"

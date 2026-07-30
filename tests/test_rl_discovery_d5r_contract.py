from pathlib import Path

from stom_rl.rl_discovery.d5r_contract import load_d5r_prereg_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_d5r_contract_freezes_diagnostic_and_capacity_boundaries() -> None:
    prereg = load_d5r_prereg_bytes(
        (ROOT / "docs/kronos_rl_discovery_type2_d5r_prereg_2026-07-30.json").read_bytes()
    )

    assert prereg.source_run.episode_count == 573
    assert prereg.d5r_1_diagnostic.near_optimal_tolerance_bp == (5, 10, 25)
    assert prereg.d5r_1_diagnostic.capacity_required_when.median_native_near_optimal_25bp_below == 0.85
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d5r_source_loads_exact_authenticated_ten_unit_matrix() -> None:
    from stom_rl.rl_discovery.d5r_source import load_d5r_source

    source = load_d5r_source(ROOT)

    assert len(source.episodes) == 573
    assert len(source.units) == 10
    assert {(unit.reward_arm, unit.seed) for unit in source.units} == {
        (reward_arm, seed)
        for reward_arm in ("NATIVE", "SHUFFLED")
        for seed in range(5)
    }
    assert all(len(unit.events) == 573 for unit in source.units)

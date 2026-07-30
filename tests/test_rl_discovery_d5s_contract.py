from pathlib import Path

from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_d5s_contract_freezes_stability_selection_and_claim_boundaries() -> None:
    prereg = load_d5s_prereg_bytes(
        (ROOT / "docs/kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json").read_bytes()
    )

    assert prereg.execution.checkpoint_total_steps == (
        50_000,
        100_000,
        150_000,
        200_000,
        300_000,
        400_000,
    )
    assert prereg.selection.per_seed_or_per_arm_checkpoint_selection_allowed is False
    assert prereg.gate.maximum_400k_reward_ratio_degradation_from_selected == 0.05
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d5s_source_binds_d5r_primary_and_d5_baselines() -> None:
    from stom_rl.rl_discovery.d5s_source import load_d5s_source

    source = load_d5s_source(ROOT)

    assert len(source.episodes) == 573
    assert len(source.baselines) == 3
    assert {row.seed for row in source.baselines} == {0, 1, 2}
    assert source.prereg.source_run.verdict == "D5R_CAPACITY_NOT_CONFIRMED"

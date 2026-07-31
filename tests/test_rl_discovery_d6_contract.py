from pathlib import Path

from stom_rl.rl_discovery.d6_contract import load_d6_prereg_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_d6_contract_freezes_models_validation_and_claim_boundaries() -> None:
    # Given
    payload = (ROOT / "docs/kronos_rl_discovery_type2_d6_prereg_2026-07-31.json").read_bytes()

    # When
    prereg = load_d6_prereg_bytes(payload)

    # Then
    assert prereg.source_run.selected_steps == 100_000
    assert len(prereg.source_run.models) == 6
    assert prereg.dataset.partition == "REUSED_VALIDATION"
    assert prereg.execution.retraining_allowed is False
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"

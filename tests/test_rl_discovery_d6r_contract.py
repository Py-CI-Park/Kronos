from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.rl_discovery.d6r_contract import load_d6r_prereg_bytes


PREREG = Path("docs/kronos_rl_discovery_type2_d6r_prereg_2026-07-31.json")


def test_d6r_contract_freezes_the_exact_train_only_matrix() -> None:
    # Given
    payload = PREREG.read_bytes()

    # When
    contract = load_d6r_prereg_bytes(payload)

    # Then
    assert contract.execution.primary_unit_count == 60
    assert contract.execution.total_primary_rl_steps == 3_000_000
    assert contract.execution.primary_profile == "TURNOVER_10BP"
    assert len(contract.folds) == 5
    assert contract.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d6r_contract_rejects_validation_read_permission() -> None:
    # Given
    payload = PREREG.read_bytes().replace(
        b'"d6_validation_read_allowed": false',
        b'"d6_validation_read_allowed": true',
    )

    # When / Then
    with pytest.raises(ValidationError):
        load_d6r_prereg_bytes(payload)

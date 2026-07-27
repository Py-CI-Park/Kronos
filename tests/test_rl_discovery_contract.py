from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery import contract


def _write_prereg(path: Path, *, status: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "kronos.rl-discovery.prereg.v1",
                "status": status,
                "experiment_id": "type2-d0-ppo-attribution-v0",
                "claims_boundary": {
                    "research_only": True,
                    "profitability_claim_allowed": False,
                    "fresh_oos": "NOT_RUN_NO_READ",
                },
                "arms": [
                    {"id": "A_PPO_ONLY", "oracle_bc_before_ppo": False, "ppo": True, "reward": "NATIVE"},
                    {"id": "B_BC_THEN_PPO", "oracle_bc_before_ppo": True, "ppo": True, "reward": "NATIVE"},
                    {"id": "C_BC_ONLY", "oracle_bc_before_ppo": True, "ppo": False, "reward": "NATIVE"},
                    {"id": "D_SHUFFLED_REWARD_PPO", "oracle_bc_before_ppo": False, "ppo": True, "reward": "SHUFFLED"},
                ],
                "seeds": [0, 1, 2],
                "training": {
                    "smoke_timesteps": 256,
                    "primary_timesteps": 104000,
                    "smoke_seeds": [0],
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_prereg_parses_the_executable_type2_contract(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "prereg.json"
    _write_prereg(path, status="APPROVED_EXECUTABLE")

    # When
    prereg = contract.load_prereg(path)

    # Then
    assert prereg.experiment_id == "type2-d0-ppo-attribution-v0"
    assert tuple(arm.id.value for arm in prereg.arms) == (
        "A_PPO_ONLY",
        "B_BC_THEN_PPO",
        "C_BC_ONLY",
        "D_SHUFFLED_REWARD_PPO",
    )
    assert prereg.training.smoke_timesteps == 256
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_load_prereg_blocks_a_draft_from_execution(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "draft.json"
    _write_prereg(path, status="DRAFT_NOT_EXECUTABLE")

    # When / Then
    with pytest.raises(contract.DraftPreregistrationError, match="not executable"):
        contract.load_prereg(path)

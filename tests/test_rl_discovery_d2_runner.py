from __future__ import annotations

from stom_rl.rl_discovery.d2_contract import D2ArmId
from stom_rl.rl_discovery.d2_runner import _model_arm_id
from stom_rl.rl_discovery.storage import contained_path


def test_d2_model_arm_id_is_one_safe_storage_segment(tmp_path) -> None:
    arm_id = _model_arm_id(1, D2ArmId.NATIVE)

    assert arm_id == "count-1__A_NATIVE"
    assert contained_path(tmp_path, "models", arm_id).parent == tmp_path / "models"

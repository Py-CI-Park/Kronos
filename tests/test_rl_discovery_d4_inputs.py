from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery.d4_inputs import load_d4_inputs


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_d4_inputs_reuse_the_exact_d3_episode_snapshot_without_fresh_oos() -> None:
    # Given/When: D4 rebuilds its custody-bound train-only inputs.
    bundle = load_d4_inputs(REPO_ROOT)

    # Then: the frozen D3 episode identity and claims boundary are unchanged.
    assert len(bundle.episodes) == 128
    assert bundle.episode_sha256 == "50170682d245f4c85ca9a93dc0704d8417d6d852ee66a98e063ee9979dccda52"
    assert bundle.prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"

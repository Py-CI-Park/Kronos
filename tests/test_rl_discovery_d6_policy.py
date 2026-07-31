from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_d6_policy_loads_frozen_dqn_without_training() -> None:
    # Given
    source = "; ".join(
        (
            "from pathlib import Path",
            "from stom_rl.rl_discovery.d6_source import D6ModelArtifact",
            "from stom_rl.rl_discovery.d6_policy import load_d6_policy",
            "root = Path.cwd()",
            "path = root / 'webui/rl_runs/rl_discovery/type2-d5s-primary-20260730-001/models/NATIVE/seed-0/steps-100000/model.zip'",
            "model = D6ModelArtifact('NATIVE', 0, path, '40dcd57e81af5e4e7d9a64276fd4dc2b893e3212352bb89dd5ef5948b0d918cf')",
            "policy = load_d6_policy(model, repo_root=root)",
            "print(type(policy.model).__name__)",
        )
    )

    # When
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.stdout.strip().endswith("DQN")

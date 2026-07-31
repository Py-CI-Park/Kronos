from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r2_gate import D6R2GateThresholds, D6R2UnitOutcome, evaluate_d6r2_gate


def _metric(ratio: float) -> D3Metrics:
    return D3Metrics(0.4, ratio, ratio, 1.0, 0.4, 0.4, 0)


def test_d6r2_gate_accepts_exact_passing_matrix() -> None:
    rows: list[D6R2UnitOutcome] = []
    for algorithm in ("DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL"):
        for arm in ("NATIVE", "SHUFFLED"):
            for seed in range(3):
                for fold in range(5):
                    ratio = 0.4 if algorithm == "DQN_GAMMA_0_CONTEXTUAL" and arm == "NATIVE" else 0.1
                    rows.append(D6R2UnitOutcome(algorithm, arm, seed, fold, _metric(ratio), 0.1, 0))
    for arm in ("NATIVE", "SHUFFLED"):
        for fold in range(5):
            rows.append(D6R2UnitOutcome("RIDGE_REWARD_CEILING", arm, 0, fold, _metric(0.3 if arm == "NATIVE" else 0.1), 0.1, 0))

    result = evaluate_d6r2_gate(tuple(rows), thresholds=D6R2GateThresholds.registered())

    assert result.verdict == "D6R2_CONTEXTUAL_CANDIDATE"
    assert result.passed_gate_count == result.total_gate_count


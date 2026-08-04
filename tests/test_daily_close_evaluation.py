from __future__ import annotations

from stom_rl.daily_close_research.evaluation import bootstrap_interval, interquartile_mean, run_synthetic_calibration


def test_interquartile_mean_reduces_outlier_influence() -> None:
    values = (-100.0, 1.0, 2.0, 3.0, 100.0)

    assert interquartile_mean(values) == 2.0


def test_bootstrap_interval_is_deterministic_and_ordered() -> None:
    first = bootstrap_interval((0.1, 0.2, 0.3, 0.4), seed=9, resamples=200)
    second = bootstrap_interval((0.1, 0.2, 0.3, 0.4), seed=9, resamples=200)

    assert first == second
    assert first.low <= first.estimate <= first.high


def test_cql_calibration_beats_random_and_shuffled_reward_controls() -> None:
    receipt = run_synthetic_calibration(seeds=(0, 1, 2), epochs=120)

    assert receipt.verdict == "PASS_SYNTHETIC_OFFLINE_RL"
    assert receipt.cql.positive_seed_count == 3
    assert receipt.cql.iqm_return > receipt.random_policy_iqm_return
    assert receipt.cql.iqm_return > receipt.shuffled_cql.iqm_return


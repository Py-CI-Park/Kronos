"""Seed-robust synthetic calibration and compact uncertainty estimates."""

from __future__ import annotations

import random
from dataclasses import dataclass
from statistics import fmean

from .models import OfflineAlgorithm, QPolicy, TrainingConfig, train_offline_q
from .offline_data import shuffled_rewards, synthetic_market_dataset, synthetic_reward


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    estimate: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class AlgorithmSummary:
    name: str
    per_seed_returns: tuple[float, ...]
    iqm_return: float
    positive_seed_count: int
    confidence: ConfidenceInterval


@dataclass(frozen=True, slots=True)
class CalibrationReceipt:
    verdict: str
    dqn: AlgorithmSummary
    cql: AlgorithmSummary
    shuffled_cql: AlgorithmSummary
    random_policy_iqm_return: float


def interquartile_mean(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    trim = int(len(ordered) * 0.25)
    kept = ordered[trim : len(ordered) - trim] if trim else ordered
    return fmean(kept)


def bootstrap_interval(
    values: tuple[float, ...],
    *,
    seed: int,
    resamples: int = 1_000,
) -> ConfidenceInterval:
    if not values or resamples < 1:
        raise ValueError("bootstrap requires values and positive resamples")
    generator = random.Random(seed)
    estimates = sorted(
        interquartile_mean(tuple(generator.choice(values) for _ in values))
        for _ in range(resamples)
    )
    low_index = int((len(estimates) - 1) * 0.025)
    high_index = int((len(estimates) - 1) * 0.975)
    return ConfidenceInterval(interquartile_mean(values), estimates[low_index], estimates[high_index])


def run_synthetic_calibration(*, seeds: tuple[int, ...], epochs: int) -> CalibrationReceipt:
    dqn_returns: list[float] = []
    cql_returns: list[float] = []
    shuffled_returns: list[float] = []
    random_returns: list[float] = []
    for seed in seeds:
        dataset = synthetic_market_dataset(seed=seed, episode_count=30, episode_length=20)
        dqn = train_offline_q(dataset, TrainingConfig.registered(algorithm=OfflineAlgorithm.DQN, seed=seed, epochs=epochs))
        cql = train_offline_q(dataset, TrainingConfig.registered(algorithm=OfflineAlgorithm.CQL, seed=seed, epochs=epochs))
        shuffled = train_offline_q(
            shuffled_rewards(dataset, seed=seed + 100),
            TrainingConfig.registered(algorithm=OfflineAlgorithm.CQL, seed=seed, epochs=epochs),
        )
        evaluation_seed = seed + 10_000
        dqn_returns.append(_policy_return(dqn.model, evaluation_seed))
        cql_returns.append(_policy_return(cql.model, evaluation_seed))
        shuffled_returns.append(_policy_return(shuffled.model, evaluation_seed))
        random_returns.append(_random_policy_return(evaluation_seed))
    dqn_summary = _summary("DQN", tuple(dqn_returns), 101)
    cql_summary = _summary("CQL", tuple(cql_returns), 102)
    shuffled_summary = _summary("SHUFFLED_CQL", tuple(shuffled_returns), 103)
    random_iqm = interquartile_mean(tuple(random_returns))
    passed = (
        cql_summary.positive_seed_count == len(seeds)
        and cql_summary.iqm_return > random_iqm
        and cql_summary.iqm_return > shuffled_summary.iqm_return
    )
    return CalibrationReceipt(
        "PASS_SYNTHETIC_OFFLINE_RL" if passed else "NO_GO_SYNTHETIC_OFFLINE_RL",
        dqn_summary,
        cql_summary,
        shuffled_summary,
        random_iqm,
    )


def _summary(name: str, values: tuple[float, ...], bootstrap_seed: int) -> AlgorithmSummary:
    return AlgorithmSummary(
        name,
        values,
        interquartile_mean(values),
        sum(value > 0 for value in values),
        bootstrap_interval(values, seed=bootstrap_seed, resamples=300),
    )


def _policy_return(policy: QPolicy, seed: int, episode_count: int = 20, length: int = 30) -> float:
    generator = random.Random(seed)
    totals: list[float] = []
    for _ in range(episode_count):
        position = 0
        total = 0.0
        for _ in range(length):
            signal = generator.choice((-1, 1))
            action = policy.action((float(signal), float(position)))
            total += synthetic_reward(signal, position, action)
            position = action
        totals.append(total)
    return fmean(totals)


def _random_policy_return(seed: int, episode_count: int = 20, length: int = 30) -> float:
    generator = random.Random(seed)
    totals: list[float] = []
    for _ in range(episode_count):
        position = 0
        total = 0.0
        for _ in range(length):
            signal = generator.choice((-1, 1))
            action = generator.choice((0, 1))
            total += synthetic_reward(signal, position, action)
            position = action
        totals.append(total)
    return fmean(totals)


"""Typed offline transitions and deterministic calibration datasets."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class OfflineTransition:
    sequence: int
    state: tuple[float, ...]
    action: int
    reward: float
    next_state: tuple[float, ...]
    done: bool


@dataclass(frozen=True, slots=True)
class OfflineSplit:
    fold_id: int
    train: tuple[OfflineTransition, ...]
    validation: tuple[OfflineTransition, ...]


def synthetic_market_dataset(
    *,
    seed: int,
    episode_count: int,
    episode_length: int,
) -> tuple[OfflineTransition, ...]:
    """Create an action-dependent two-state market with a known optimal policy."""
    if episode_count < 1 or episode_length < 2:
        raise ValueError("synthetic dataset requires positive episodes of length >= 2")
    generator = random.Random(seed)
    transitions: list[OfflineTransition] = []
    sequence = 0
    for _ in range(episode_count):
        position = 0
        signal = generator.choice((-1, 1))
        for step in range(episode_length):
            action = generator.choice((0, 1))
            next_signal = generator.choice((-1, 1))
            done = step == episode_length - 1
            transitions.append(
                OfflineTransition(
                    sequence=sequence,
                    state=(float(signal), float(position)),
                    action=action,
                    reward=synthetic_reward(signal, position, action),
                    next_state=(float(next_signal), float(action)),
                    done=done,
                )
            )
            sequence += 1
            signal = next_signal
            position = action
    return tuple(transitions)


def synthetic_reward(signal: int, previous_position: int, action: int) -> float:
    market_return = float(signal) * 0.01 if action == 1 else 0.0
    switching_cost = 0.0023 if action != previous_position else 0.0
    return market_return - switching_cost


def shuffled_rewards(
    transitions: tuple[OfflineTransition, ...],
    *,
    seed: int,
) -> tuple[OfflineTransition, ...]:
    generator = random.Random(seed)
    rewards = [transition.reward for transition in transitions]
    generator.shuffle(rewards)
    return tuple(replace(transition, reward=reward) for transition, reward in zip(transitions, rewards, strict=True))


def chronological_splits(
    transitions: tuple[OfflineTransition, ...],
    *,
    validation_fold_count: int,
) -> tuple[OfflineSplit, ...]:
    if validation_fold_count < 1:
        raise ValueError("validation_fold_count must be positive")
    ordered = tuple(sorted(transitions, key=lambda item: item.sequence))
    bucket_count = validation_fold_count + 1
    buckets: list[list[OfflineTransition]] = [[] for _ in range(bucket_count)]
    for index, transition in enumerate(ordered):
        bucket = min(bucket_count - 1, index * bucket_count // max(1, len(ordered)))
        buckets[bucket].append(transition)
    return tuple(
        OfflineSplit(
            fold_id=fold_id,
            train=tuple(item for bucket in buckets[:fold_id] for item in bucket),
            validation=tuple(buckets[fold_id]),
        )
        for fold_id in range(1, bucket_count)
        if buckets[fold_id]
    )

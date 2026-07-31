"""Chronological TRAIN_ONLY folds for D6R."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from stom_rl.rl_discovery.d3_env import D3Episode


@dataclass(frozen=True, slots=True)
class D6RFold:
    fold_id: int
    train_start: int
    train_end_exclusive: int
    evaluation_start: int
    evaluation_end_exclusive: int


EPISODE_COUNT: Final = 573


class D6RFoldError(ValueError):
    """The D6R source cannot satisfy the registered fold identity."""


def registered_d6r_folds() -> tuple[D6RFold, ...]:
    return tuple(
        D6RFold(
            fold_id=fold_id,
            train_start=0,
            train_end_exclusive=323 + fold_id * 50,
            evaluation_start=323 + fold_id * 50,
            evaluation_end_exclusive=373 + fold_id * 50,
        )
        for fold_id in range(5)
    )


def split_d6r_fold(
    episodes: tuple[D3Episode, ...],
    fold: D6RFold,
) -> tuple[tuple[D3Episode, ...], tuple[D3Episode, ...]]:
    if len(episodes) != EPISODE_COUNT or fold not in registered_d6r_folds():
        raise D6RFoldError("D6R requires 573 episodes and one registered fold")
    training = episodes[fold.train_start : fold.train_end_exclusive]
    evaluation = episodes[fold.evaluation_start : fold.evaluation_end_exclusive]
    if not training or len(evaluation) != 50:
        raise D6RFoldError("D6R fold slices are incomplete")
    return training, evaluation

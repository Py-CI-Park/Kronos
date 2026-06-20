"""Chronological walk-forward folds over session dates for the model factory.

Honesty guardrails: research-only tooling, no profit claim. Folds are built
on session-date strings only; OOS sessions must never be used for tuning,
and no alpha claim is permitted from ``n_folds < 5`` or from a single
favorable split (see ``stom_rl/AGENTS.md``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

GUARDRAIL = "OOS sessions must never be used for tuning"
MIN_FOLDS_FOR_CLAIMS = 5
DEFAULT_MIN_OOS_TRADES = 100
VERDICT_GO = "GO_CANDIDATE"
VERDICT_NO_GO_FOLDS = "NO-GO_FOLDS"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"


class WalkForwardError(ValueError):
    """Raised when fold construction would violate walk-forward guardrails."""


@dataclass(frozen=True)
class Fold:
    """One expanding-window fold of chronologically ordered session dates."""

    fold_id: int
    train_sessions: tuple[str, ...]
    validation_sessions: tuple[str, ...]
    oos_sessions: tuple[str, ...]


def _normalize_sessions(sessions: Sequence[str]) -> tuple[str, ...]:
    """Sort, dedupe, and validate 'YYYYMMDD' session-date strings."""
    cleaned: set[str] = set()
    for session in sessions:
        if not isinstance(session, str):
            raise WalkForwardError(
                f"session dates must be strings (got {type(session).__name__}); "
                "never coerce symbol/date codes to int"
            )
        if len(session) != 8 or not session.isdigit():
            raise WalkForwardError(f"session date must be 'YYYYMMDD': {session!r}")
        cleaned.add(session)
    return tuple(sorted(cleaned))


def _contiguous_blocks(ordered: tuple[str, ...], n_blocks: int) -> list[tuple[str, ...]]:
    """Split ordered sessions into ``n_blocks`` contiguous chronological blocks.

    Remainder sessions are assigned to the earliest blocks, deterministically.
    """
    total = len(ordered)
    base, remainder = divmod(total, n_blocks)
    blocks: list[tuple[str, ...]] = []
    start = 0
    for index in range(n_blocks):
        size = base + (1 if index < remainder else 0)
        blocks.append(ordered[start : start + size])
        start += size
    return blocks


def chronological_folds(
    sessions: Sequence[str],
    *,
    n_folds: int = 5,
    validation_fraction: float = 0.2,
    allow_few_folds: bool = False,
) -> list[Fold]:
    """Build expanding-window chronological folds from session-date strings.

    The deduped, ascending timeline is split into ``n_folds + 1`` contiguous
    blocks. Fold ``k`` (0-based) uses blocks ``0..k`` as train+validation
    (the trailing ``validation_fraction`` of those sessions, at least 1,
    becomes validation; the rest train) and block ``k + 1`` as OOS. Every
    fold's OOS sessions are therefore strictly later than all of its
    train/validation sessions.

    Raises ``WalkForwardError`` when ``n_folds < 5`` (repo rule: no alpha
    claims from ``n_folds < 5``) unless ``allow_few_folds=True`` is passed
    explicitly for smoke tests, or when the sessions are too few to give
    every fold non-empty train/validation/OOS sets.
    """
    if n_folds < 1:
        raise WalkForwardError(f"n_folds must be >= 1 (got {n_folds})")
    if n_folds < MIN_FOLDS_FOR_CLAIMS and not allow_few_folds:
        raise WalkForwardError(
            f"n_folds={n_folds} < {MIN_FOLDS_FOR_CLAIMS}: repo rule forbids alpha claims "
            "from n_folds < 5; pass allow_few_folds=True only for smoke tests"
        )
    if not 0.0 < validation_fraction < 1.0:
        raise WalkForwardError(
            f"validation_fraction must be in (0, 1) (got {validation_fraction})"
        )

    ordered = _normalize_sessions(sessions)
    n_blocks = n_folds + 1
    # Fold 0 needs >= 2 sessions in block 0 (>=1 train, >=1 validation) and
    # every block must be non-empty.
    if len(ordered) < n_blocks + 1:
        raise WalkForwardError(
            f"need at least {n_blocks + 1} distinct sessions for n_folds={n_folds} "
            f"(got {len(ordered)})"
        )

    blocks = _contiguous_blocks(ordered, n_blocks)
    folds: list[Fold] = []
    for fold_id in range(n_folds):
        train_val: tuple[str, ...] = tuple(
            session for block in blocks[: fold_id + 1] for session in block
        )
        oos = blocks[fold_id + 1]
        n_validation = max(1, int(len(train_val) * validation_fraction))
        train = train_val[: len(train_val) - n_validation]
        validation = train_val[len(train_val) - n_validation :]
        if not train or not validation or not oos:
            raise WalkForwardError(
                f"fold {fold_id} has an empty split "
                f"(train={len(train)}, validation={len(validation)}, oos={len(oos)}); "
                "provide more sessions"
            )
        folds.append(
            Fold(
                fold_id=fold_id,
                train_sessions=train,
                validation_sessions=validation,
                oos_sessions=oos,
            )
        )
    return folds


def fold_manifest(folds: Sequence[Fold], *, split_seed: int | None = None) -> dict:
    """Build a JSON-safe manifest describing the folds.

    ``split_hash`` is the sha256 of the ordered per-fold session lists,
    truncated to 16 hex characters, so identical splits hash identically
    and any session change alters the hash.
    """
    ordered_lists = [
        [list(fold.train_sessions), list(fold.validation_sessions), list(fold.oos_sessions)]
        for fold in folds
    ]
    payload = json.dumps(ordered_lists, separators=(",", ":"), ensure_ascii=True)
    split_hash = hashlib.sha256(payload.encode("ascii")).hexdigest()[:16]
    return {
        "n_folds": len(folds),
        "split_seed": split_seed,
        "split_hash": split_hash,
        "guardrail": GUARDRAIL,
        "folds": [
            {
                "fold_id": fold.fold_id,
                "train_count": len(fold.train_sessions),
                "validation_count": len(fold.validation_sessions),
                "oos_count": len(fold.oos_sessions),
                "train_start": fold.train_sessions[0],
                "train_end": fold.train_sessions[-1],
                "validation_start": fold.validation_sessions[0],
                "validation_end": fold.validation_sessions[-1],
                "oos_start": fold.oos_sessions[0],
                "oos_end": fold.oos_sessions[-1],
            }
            for fold in folds
        ],
    }


def enforce_sample_power(oos_trade_count: int, *, min_required: int = DEFAULT_MIN_OOS_TRADES) -> dict:
    """Force ``INCONCLUSIVE`` when OOS trade count is below ``min_required``."""
    sufficient = oos_trade_count >= min_required
    return {
        "oos_trades": int(oos_trade_count),
        "min_required": int(min_required),
        "sufficient": sufficient,
        "forced_verdict": "" if sufficient else VERDICT_INCONCLUSIVE,
    }


def synthesize_fold_verdicts(fold_verdicts: Sequence[str]) -> str:
    """Synthesize a single verdict from per-fold verdicts.

    Exact rule, in order:
    1. Empty input -> ``'INCONCLUSIVE'``.
    2. Any verdict starting with ``'NO-GO'`` -> ``'NO-GO_FOLDS'``.
    3. Any verdict equal to ``'INCONCLUSIVE'`` -> ``'INCONCLUSIVE'``.
    4. All verdicts equal to ``'GO_CANDIDATE'`` -> ``'GO_CANDIDATE'``.
    5. Anything else (unknown labels) -> ``'INCONCLUSIVE'``.

    Only a clean sweep of ``GO_CANDIDATE`` folds yields ``GO_CANDIDATE``.
    """
    if not fold_verdicts:
        return VERDICT_INCONCLUSIVE
    if any(verdict.startswith("NO-GO") for verdict in fold_verdicts):
        return VERDICT_NO_GO_FOLDS
    if any(verdict == VERDICT_INCONCLUSIVE for verdict in fold_verdicts):
        return VERDICT_INCONCLUSIVE
    if all(verdict == VERDICT_GO for verdict in fold_verdicts):
        return VERDICT_GO
    return VERDICT_INCONCLUSIVE

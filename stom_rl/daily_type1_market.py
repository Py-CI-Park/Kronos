"""Pure public-train/reused-validation primitives for the frozen Type 1 G002 protocol.

This module deliberately has no filesystem, dataset, fresh-OOS, or M3E dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext, Context, ROUND_HALF_EVEN
from enum import Enum
import hashlib
import random
import re
import struct
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

from stom_rl.daily_type1_accounting import PortfolioState, SlotOutcome, settle_session
from stom_rl.daily_type1_contract import FEATURES, INITIAL_NAV_KRW, MAX_SLOTS, SEEDS, SLOT_NOTIONAL_KRW, canonical_json_bytes

TRAIN_START = date(2018, 1, 2)
TRAIN_END = date(2023, 12, 29)
REUSED_VALIDATION_START = date(2024, 1, 2)
REUSED_VALIDATION_END = date(2025, 6, 30)
PRIMARY_COST = Decimal("0.0023")
_SYMBOL_RE = re.compile(r"^\d{6}$")
_DECIMAL_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
T = TypeVar("T")


class ProtocolError(ValueError):
    """A closed public-protocol validation or integrity failure."""


class ExecutionStatus(str, Enum):
    BLOCK = "BLOCK"
    COMPLETE = "COMPLETE"


class Verdict(str, Enum):
    NO_GO = "NO_GO"


@dataclass(frozen=True)
class FailureOutcome:
    execution_status: ExecutionStatus
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class PublicMarketRow:
    """One public daily candidate. Raw features remain Decimal until normalization."""

    decision_date: date
    symbol: str
    features: tuple[Decimal | None, ...]
    gross_return: Decimal | None
    entry_available: bool

    def __post_init__(self) -> None:
        if not isinstance(self.decision_date, date):
            raise ProtocolError("decision_date must be an ISO date")
        if not isinstance(self.symbol, str) or not _SYMBOL_RE.fullmatch(self.symbol):
            raise ProtocolError("symbol must be a six-digit string")
        if len(self.features) != len(FEATURES):
            raise ProtocolError("features must match the frozen Type1 feature schema")
        for value in self.features:
            _require_decimal_or_null(value, "feature")
        _require_decimal_or_null(self.gross_return, "gross_return")
        if type(self.entry_available) is not bool:
            raise ProtocolError("entry_available must be boolean")
        if not self.entry_available and self.gross_return is not None:
            raise ProtocolError("unavailable entries must have null gross_return")


@dataclass(frozen=True)
class ChronologicalPairs:
    pairs: tuple[tuple[T, T], ...]
    odd_tail: T | None


@dataclass(frozen=True)
class FeatureScale:
    center: Decimal
    scale: Decimal


@dataclass(frozen=True)
class TrainOnlyNormalizer:
    """Type-7 train-only feature scaler with float32, clipped transformed values."""

    scales: tuple[FeatureScale, ...]

    @classmethod
    def fit(cls, rows: Sequence[PublicMarketRow]) -> "TrainOnlyNormalizer":
        checked = validate_public_rows(rows, split="train")
        if not checked:
            raise ProtocolError("normalizer requires at least one training row")
        scales: list[FeatureScale] = []
        for column in range(len(FEATURES)):
            values = [row.features[column] for row in checked if row.features[column] is not None]
            if not values:
                raise ProtocolError(f"feature {FEATURES[column]} has no train values")
            q25 = type7_quantile(values, Decimal("0.25"))
            q50 = type7_quantile(values, Decimal("0.5"))
            q75 = type7_quantile(values, Decimal("0.75"))
            scale = q75 - q25
            if scale <= 0:
                raise ProtocolError(f"feature {FEATURES[column]} has non-positive IQR")
            scales.append(FeatureScale(center=q50, scale=scale))
        return cls(tuple(scales))

    def transform(self, values: Sequence[Decimal | None]) -> tuple[tuple[float, ...], tuple[int, ...]]:
        if len(values) != len(FEATURES):
            raise ProtocolError("feature values must match the frozen Type1 feature schema")
        if len(self.scales) != len(FEATURES):
            raise ProtocolError("normalizer schema is malformed")
        normalized: list[float] = []
        missing: list[int] = []
        for value, scale in zip(values, self.scales, strict=True):
            _require_decimal_or_null(value, "feature")
            if value is None:
                normalized.append(_float32(0.0))
                missing.append(1)
                continue
            with localcontext(_DECIMAL_CONTEXT):
                raw = (value - scale.center) / scale.scale
            clipped = min(Decimal("10"), max(Decimal("-10"), raw))
            normalized.append(_float32(float(clipped)))
            missing.append(0)
        return tuple(normalized), tuple(missing)

    def digest(self) -> str:
        return sha256_digest(self.scales)


def _float32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]


def _require_decimal_or_null(value: Decimal | None, field: str) -> None:
    if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
        raise ProtocolError(f"{field} must be a finite Decimal or null")


def _decimal_string(value: Any, field: str, *, nullable: bool) -> Decimal | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ProtocolError(f"{field} must be a Decimal string" + (" or null" if nullable else ""))
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ProtocolError(f"{field} is malformed") from exc
    if not result.is_finite():
        raise ProtocolError(f"{field} must be finite")
    return result


def public_row_from_mapping(value: Mapping[str, Any]) -> PublicMarketRow:
    """Parse the sole accepted public-row JSON schema without coercing symbols."""
    required = {"decision_date", "symbol", "features", "gross_return", "entry_available"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ProtocolError("public row must have exactly the frozen public schema fields")
    raw_features = value["features"]
    if not isinstance(raw_features, Mapping) or set(raw_features) != set(FEATURES):
        raise ProtocolError("features must contain exactly the frozen feature names")
    try:
        decision = date.fromisoformat(value["decision_date"])
    except (TypeError, ValueError) as exc:
        raise ProtocolError("decision_date must be ISO-8601") from exc
    features = tuple(_decimal_string(raw_features[name], name, nullable=True) for name in FEATURES)
    return PublicMarketRow(
        decision_date=decision,
        symbol=value["symbol"],
        features=features,
        gross_return=_decimal_string(value["gross_return"], "gross_return", nullable=True),
        entry_available=value["entry_available"],
    )


def validate_public_rows(rows: Sequence[PublicMarketRow], *, split: str) -> tuple[PublicMarketRow, ...]:
    """Validate one public split and reject dates outside its exact inclusive boundary."""
    if split == "train":
        start, end = TRAIN_START, TRAIN_END
    elif split == "reused_validation":
        start, end = REUSED_VALIDATION_START, REUSED_VALIDATION_END
    else:
        raise ProtocolError("split must be train or reused_validation; fresh OOS is forbidden")
    result = tuple(rows)
    previous: tuple[date, str] | None = None
    seen: set[tuple[date, str]] = set()
    for row in result:
        if not isinstance(row, PublicMarketRow):
            raise ProtocolError("rows must contain PublicMarketRow values")
        if not start <= row.decision_date <= end:
            raise ProtocolError("row date is outside the exact public split boundary")
        key = (row.decision_date, row.symbol)
        if key in seen or (previous is not None and key < previous):
            raise ProtocolError("rows must be unique and chronological by date then symbol")
        seen.add(key)
        previous = key
    return result


def type7_quantile(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    """Hyndman-Fan Type-7 quantile, using only finite Decimal inputs."""
    if not isinstance(probability, Decimal) or not Decimal("0") <= probability <= Decimal("1"):
        raise ProtocolError("probability must be a Decimal in [0, 1]")
    ordered = sorted(values)
    if not ordered or any(not isinstance(item, Decimal) or not item.is_finite() for item in ordered):
        raise ProtocolError("quantile values must be non-empty finite Decimals")
    if len(ordered) == 1:
        return ordered[0]
    with localcontext(_DECIMAL_CONTEXT):
        position = (Decimal(len(ordered) - 1) * probability)
        lower = int(position)
        fraction = position - Decimal(lower)
        return ordered[lower] + fraction * (ordered[lower + 1] - ordered[lower])


def chronological_pairs(items: Sequence[T]) -> ChronologicalPairs[T]:
    """Pair already canonical chronological items as (0,1), (2,3), recording odd tail."""
    frozen = tuple(items)
    pair_count = len(frozen) // 2
    return ChronologicalPairs(tuple((frozen[index * 2], frozen[index * 2 + 1]) for index in range(pair_count)), frozen[-1] if len(frozen) % 2 else None)


def five_seed_iqm(values: Mapping[int, Decimal] | Sequence[Decimal]) -> Decimal:
    """Exact frozen five-member IQM: .3*x1 + .4*x2 + .3*x3 after sorting."""
    if isinstance(values, Mapping):
        if set(values) != set(SEEDS):
            raise ProtocolError("IQM requires exactly seeds 0, 1, 2, 3, and 4")
        ordered = sorted(values.values())
    else:
        ordered = sorted(values)
        if len(ordered) != 5:
            raise ProtocolError("IQM requires exactly five values")
    if any(not isinstance(item, Decimal) or not item.is_finite() for item in ordered):
        raise ProtocolError("IQM values must be finite Decimals")
    with localcontext(_DECIMAL_CONTEXT):
        return Decimal("0.3") * ordered[1] + Decimal("0.4") * ordered[2] + Decimal("0.3") * ordered[3]


def replay_fixed_notional(pair_outcomes: Sequence[Sequence[SlotOutcome]]) -> tuple[Decimal, ...]:
    """Independent public Decimal replay; each filled slot pays exactly 23bp."""
    state = PortfolioState()
    navs: list[Decimal] = []
    for outcomes in pair_outcomes:
        settlement = settle_session(state, outcomes, cost_bp=23)
        state = settlement.state
        navs.append(state.nav)
    return tuple(navs)


def stop_baseline(pair_count: int) -> tuple[tuple[str, ...], ...]:
    if type(pair_count) is not int or pair_count < 0:
        raise ProtocolError("pair_count must be a non-negative integer")
    return tuple(() for _ in range(pair_count))


def select_top_positive(scores: Mapping[str, Decimal], *, maximum_slots: int = MAX_SLOTS) -> tuple[str, ...]:
    """Frozen selection ordering for ridge: score descending, six-digit symbol ascending."""
    if type(maximum_slots) is not int or not 0 <= maximum_slots <= MAX_SLOTS:
        raise ProtocolError("maximum_slots must be an integer between zero and ten")
    checked: list[tuple[str, Decimal]] = []
    for symbol, score in scores.items():
        if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
            raise ProtocolError("score symbols must be six-digit strings")
        if not isinstance(score, Decimal) or not score.is_finite():
            raise ProtocolError("scores must be finite Decimals")
        if score > 0:
            checked.append((symbol, score))
    return tuple(symbol for symbol, _ in sorted(checked, key=lambda item: (-item[1], item[0]))[:maximum_slots])


@dataclass(frozen=True)
class RidgeBaseline:
    """Untuned alpha=1 ridge on seven normalized values then seven missing indicators."""

    coefficients: tuple[Decimal, ...]
    intercept: Decimal

    @classmethod
    def fit(cls, samples: Sequence[tuple[Sequence[float], Sequence[int], Decimal]]) -> "RidgeBaseline":
        if not samples:
            raise ProtocolError("ridge requires training samples")
        width = len(FEATURES) * 2
        design: list[list[Decimal]] = []
        targets: list[Decimal] = []
        for values, missing, gross_return in samples:
            if len(values) != len(FEATURES) or len(missing) != len(FEATURES):
                raise ProtocolError("ridge sample schema is malformed")
            if not isinstance(gross_return, Decimal) or not gross_return.is_finite():
                raise ProtocolError("ridge targets must be finite Decimals")
            numeric = [Decimal(str(value)) for value in values] + [Decimal(int(item)) for item in missing]
            if any(not item.is_finite() for item in numeric) or any(item not in {Decimal(0), Decimal(1)} for item in numeric[len(FEATURES):]):
                raise ProtocolError("ridge inputs are malformed")
            design.append(numeric + [Decimal(1)])
            targets.append(gross_return - PRIMARY_COST)
        # Normal equations with alpha=1 on features only; intercept remains unpenalized.
        dimension = width + 1
        matrix = [[Decimal(0) for _ in range(dimension + 1)] for _ in range(dimension)]
        for row, target in zip(design, targets, strict=True):
            for i in range(dimension):
                matrix[i][-1] += row[i] * target
                for j in range(dimension):
                    matrix[i][j] += row[i] * row[j]
        for i in range(width):
            matrix[i][i] += Decimal(1)
        solution = _solve_linear_system(matrix)
        return cls(tuple(solution[:width]), solution[width])

    def predict(self, values: Sequence[float], missing: Sequence[int]) -> Decimal:
        if len(values) != len(FEATURES) or len(missing) != len(FEATURES) or len(self.coefficients) != len(FEATURES) * 2:
            raise ProtocolError("ridge prediction schema is malformed")
        inputs = [Decimal(str(value)) for value in values] + [Decimal(int(item)) for item in missing]
        if any(not item.is_finite() for item in inputs):
            raise ProtocolError("ridge prediction inputs must be finite")
        with localcontext(_DECIMAL_CONTEXT):
            return self.intercept + sum((coefficient * item for coefficient, item in zip(self.coefficients, inputs, strict=True)), Decimal(0))


def _solve_linear_system(matrix: Sequence[Sequence[Decimal]]) -> list[Decimal]:
    work = [list(row) for row in matrix]
    size = len(work)
    with localcontext(_DECIMAL_CONTEXT):
        for column in range(size):
            pivot = next((row for row in range(column, size) if work[row][column] != 0), None)
            if pivot is None:
                raise ProtocolError("ridge normal equations are singular")
            work[column], work[pivot] = work[pivot], work[column]
            divisor = work[column][column]
            work[column] = [value / divisor for value in work[column]]
            for row in range(size):
                if row == column:
                    continue
                factor = work[row][column]
                if factor:
                    work[row] = [value - factor * base for value, base in zip(work[row], work[column], strict=True)]
    return [row[-1] for row in work]


def random_baseline(available_symbols: Sequence[Sequence[str]], *, replications: int = 10_000, seed: int = 0, counts: Sequence[int] | None = None) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Deterministic distinct-symbol random portfolios; optional exact exposure matching."""
    if type(replications) is not int or not 1 <= replications <= 10_000:
        raise ProtocolError("replications must be between one and 10000")
    if type(seed) is not int:
        raise ProtocolError("seed must be an integer")
    slots = tuple(tuple(pair) for pair in available_symbols)
    if counts is None:
        counts = tuple(min(MAX_SLOTS, len(pair)) for pair in slots)
    if len(counts) != len(slots):
        raise ProtocolError("exposure counts must match pair count")
    for pair, count in zip(slots, counts, strict=True):
        if len(set(pair)) != len(pair) or any(not _SYMBOL_RE.fullmatch(symbol) for symbol in pair):
            raise ProtocolError("available symbols must be unique six-digit strings")
        if type(count) is not int or not 0 <= count <= min(MAX_SLOTS, len(pair)):
            raise ProtocolError("exposure count is unavailable or exceeds ten slots")
    rng = random.Random(seed)
    return tuple(tuple(tuple(sorted(rng.sample(pair, count))) for pair, count in zip(slots, counts, strict=True)) for _ in range(replications))


def exposure_matched_random(available_symbols: Sequence[Sequence[str]], selected_counts: Sequence[int], *, replications: int = 10_000, seed: int = 0) -> tuple[tuple[tuple[str, ...], ...], ...]:
    return random_baseline(available_symbols, replications=replications, seed=seed, counts=selected_counts)


def shuffled_returns(returns: Sequence[Decimal | None], *, seed: int) -> tuple[Decimal | None, ...]:
    """Fisher-Yates permutation of filled returns only, preserving null positions."""
    if type(seed) is not int:
        raise ProtocolError("seed must be an integer")
    filled = [item for item in returns if item is not None]
    if any(not isinstance(item, Decimal) or not item.is_finite() for item in filled):
        raise ProtocolError("returns must be finite Decimals or null")
    rng = random.Random(seed)
    for index in range(len(filled) - 1, 0, -1):
        other = rng.randrange(index + 1)
        filled[index], filled[other] = filled[other], filled[index]
    iterator = iter(filled)
    return tuple(next(iterator) if item is not None else None for item in returns)


def circular_moving_block_bootstrap(differences: Sequence[Decimal], *, replications: int = 10_000, block_length_pairs: int = 20, seed: int = 0) -> tuple[Decimal, ...]:
    """Circular moving-block means over per-pair Decimal P&L differences."""
    if not differences or any(not isinstance(item, Decimal) or not item.is_finite() for item in differences):
        raise ProtocolError("differences must be non-empty finite Decimals")
    if type(replications) is not int or not 1 <= replications <= 10_000 or type(block_length_pairs) is not int or not 1 <= block_length_pairs <= 20 or type(seed) is not int:
        raise ProtocolError("bootstrap parameters exceed frozen bounds")
    size = len(differences)
    rng = random.Random(seed)
    samples: list[Decimal] = []
    for _ in range(replications):
        drawn: list[Decimal] = []
        while len(drawn) < size:
            start = rng.randrange(size)
            drawn.extend(differences[(start + offset) % size] for offset in range(block_length_pairs))
        with localcontext(_DECIMAL_CONTEXT):
            samples.append(sum(drawn[:size], Decimal(0)) / Decimal(size))
    return tuple(samples)


def bootstrap_confidence_interval(samples: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    return (type7_quantile(samples, Decimal("0.025")), type7_quantile(samples, Decimal("0.975")))


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def train_only_digest(model_bytes: bytes, normalizer: TrainOnlyNormalizer) -> str:
    if not isinstance(model_bytes, bytes):
        raise ProtocolError("model_bytes must be bytes")
    return hashlib.sha256(model_bytes + bytes.fromhex(normalizer.digest())).hexdigest()


def assert_validation_mutation_invariant(model_bytes: bytes, normalizer: TrainOnlyNormalizer, mutated_model_bytes: bytes, mutated_normalizer: TrainOnlyNormalizer) -> None:
    """Fail closed when a reused-validation mutation changes train-only artifacts."""
    if train_only_digest(model_bytes, normalizer) != train_only_digest(mutated_model_bytes, mutated_normalizer):
        raise ProtocolError("reused-validation mutation changed train-only artifacts")


def blocked_failure(reason: str) -> FailureOutcome:
    if not isinstance(reason, str) or not reason:
        raise ProtocolError("failure reason must be non-empty")
    return FailureOutcome(ExecutionStatus.BLOCK, Verdict.NO_GO, reason)


def completed_no_go(reason: str) -> FailureOutcome:
    if not isinstance(reason, str) or not reason:
        raise ProtocolError("failure reason must be non-empty")
    return FailureOutcome(ExecutionStatus.COMPLETE, Verdict.NO_GO, reason)

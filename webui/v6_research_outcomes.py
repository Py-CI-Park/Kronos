"""Bounded outcome extraction from one directly observed research summary."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Final, TypedDict

from pydantic import JsonValue, TypeAdapter, ValidationError

from webui.v6_research_metadata import MAX_SUMMARY_BYTES
from webui.v6_daily_market_publication import observe_daily_market_publication

MAX_OUTCOME_ROWS: Final = 16
MAX_REASONS: Final = 6
MAX_TEXT_LENGTH: Final = 400
NUMERIC_FIELDS: Final = (
    "date_count",
    "filled_slots",
    "total_net_pnl_krw",
    "net_pnl_krw",
    "total_cost_krw",
    "mean_reward",
    "cumulative_reward",
    "required_membership_pairs",
    "covered_membership_pairs",
    "coverage_percent",
)
JSON_OBJECT_ADAPTER: Final = TypeAdapter(dict[str, JsonValue])


class OutcomeSeriesOptional(TypedDict, total=False):
    state: str
    date_count: float
    filled_slots: float
    total_net_pnl_krw: float
    net_pnl_krw: float
    total_cost_krw: float
    mean_reward: float
    cumulative_reward: float
    required_membership_pairs: float
    covered_membership_pairs: float
    coverage_percent: float


class OutcomeSeriesPayload(OutcomeSeriesOptional):
    label: str


class ObservedOutcomePayload(TypedDict):
    scope: str
    source_file: str
    headline: str
    reasons: list[str]
    series: list[OutcomeSeriesPayload]


def _bounded_text(value: JsonValue | None) -> str | None:
    if type(value) is not str:
        return None
    normalized = value.strip()
    return normalized[:MAX_TEXT_LENGTH] if normalized else None


def _finite_number(value: JsonValue | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _headline(mapping: Mapping[str, JsonValue]) -> str:
    for key in ("primary_headline", "headline", "guardrail"):
        observed = _bounded_text(mapping.get(key))
        if observed is not None:
            return observed
    return "MISSING"


def _reasons(mapping: Mapping[str, JsonValue]) -> list[str]:
    rows: list[str] = []
    for key in (
        "reasons",
        "gate_validation_errors",
        "upstream_gate_blockers",
        "errors",
    ):
        values = mapping.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            observed = _bounded_text(value)
            if observed is not None and observed not in rows:
                rows.append(observed)
            if len(rows) >= MAX_REASONS:
                return rows
    return rows


def _series_row(
    mapping: Mapping[str, JsonValue], label: str
) -> OutcomeSeriesPayload | None:
    row: OutcomeSeriesPayload = {"label": label}
    state = _bounded_text(mapping.get("state"))
    if state is not None:
        row["state"] = state
    for field in NUMERIC_FIELDS:
        observed = _finite_number(mapping.get(field))
        if observed is None:
            continue
        match field:
            case "date_count":
                row["date_count"] = observed
            case "filled_slots":
                row["filled_slots"] = observed
            case "total_net_pnl_krw":
                row["total_net_pnl_krw"] = observed
            case "net_pnl_krw":
                row["net_pnl_krw"] = observed
            case "total_cost_krw":
                row["total_cost_krw"] = observed
            case "mean_reward":
                row["mean_reward"] = observed
            case "cumulative_reward":
                row["cumulative_reward"] = observed
            case "required_membership_pairs":
                row["required_membership_pairs"] = observed
            case "covered_membership_pairs":
                row["covered_membership_pairs"] = observed
            case "coverage_percent":
                row["coverage_percent"] = observed
    return row if len(row) > 1 else None


def _summary_rows(mapping: Mapping[str, JsonValue]) -> list[OutcomeSeriesPayload]:
    summary = mapping.get("summary")
    if not isinstance(summary, list):
        return []
    rows: list[OutcomeSeriesPayload] = []
    for index, value in enumerate(summary):
        if not isinstance(value, dict):
            continue
        label = next(
            (
                text
                for key in ("policy", "name", "scenario", "seed")
                if (text := _bounded_text(value.get(key))) is not None
            ),
            f"row-{index + 1}",
        )
        row = _series_row(value, label)
        if row is not None:
            rows.append(row)
        if len(rows) >= MAX_OUTCOME_ROWS:
            break
    return rows


def _split_rows(
    mapping: Mapping[str, JsonValue], available: int
) -> list[OutcomeSeriesPayload]:
    splits = mapping.get("primary_split_summary")
    if not isinstance(splits, dict) or available <= 0:
        return []
    rows: list[OutcomeSeriesPayload] = []
    for name, value in splits.items():
        if not isinstance(value, dict):
            continue
        row = _series_row(value, f"split:{name}")
        if row is not None:
            rows.append(row)
        if len(rows) >= available:
            break
    return rows


def _empty(source_file: str) -> ObservedOutcomePayload:
    return {
        "scope": "DIRECT_SUMMARY_NUMERIC_ONLY",
        "source_file": source_file,
        "headline": "MISSING",
        "reasons": [],
        "series": [],
    }


def observe_outcome(directory: Path, source_file: str) -> ObservedOutcomePayload:
    """Return only bounded scalar values from the direct metadata source file."""
    publication = observe_daily_market_publication(directory)
    if publication.state == "INVALID":
        return _empty(source_file)
    if source_file == "MISSING" or Path(source_file).name != source_file:
        return _empty(source_file)
    if publication.state == "VALID":
        if publication.source_file != source_file or publication.summary_bytes is None:
            return _empty(source_file)
        try:
            raw = JSON_OBJECT_ADAPTER.validate_json(publication.summary_bytes)
        except ValidationError:
            return _empty(source_file)
        rows = _summary_rows(raw)
        rows.extend(_split_rows(raw, MAX_OUTCOME_ROWS - len(rows)))
        return {
            "scope": "DIRECT_SUMMARY_NUMERIC_ONLY",
            "source_file": source_file,
            "headline": _headline(raw),
            "reasons": _reasons(raw),
            "series": rows,
        }
    source = directory / source_file
    try:
        if (
            source.is_symlink()
            or not source.is_file()
            or source.stat().st_size > MAX_SUMMARY_BYTES
        ):
            return _empty(source_file)
        raw = JSON_OBJECT_ADAPTER.validate_json(source.read_bytes())
    except (OSError, ValidationError):
        return _empty(source_file)
    rows = _summary_rows(raw)
    rows.extend(_split_rows(raw, MAX_OUTCOME_ROWS - len(rows)))
    return {
        "scope": "DIRECT_SUMMARY_NUMERIC_ONLY",
        "source_file": source_file,
        "headline": _headline(raw),
        "reasons": _reasons(raw),
        "series": rows,
    }


__all__ = ["observe_outcome"]

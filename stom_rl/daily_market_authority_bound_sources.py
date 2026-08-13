"""Parse small authority inputs from the exact bytes bound into a receipt."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .daily_market_authority_contract import (
    AuthorityInputBinding,
    AuthorityInputRole,
    DailyMarketAuthorityError,
    PitMembershipRecord,
    PriceProvenanceRecord,
)
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_candidate_eligibility import parse_candidate_eligibility
from .daily_market_path_custody import has_reparse_component

EvidenceState = Literal["PRESENT", "MISSING", "INVALID"]


def _bound_bytes(
    path: Path,
    role: AuthorityInputRole,
) -> tuple[EvidenceState, bytes | None, AuthorityInputBinding]:
    if not path.exists():
        return (
            "MISSING",
            None,
            AuthorityInputBinding(
                role=role,
                state="MISSING",
                identity=None,
            ),
        )
    if has_reparse_component(path) or not path.is_file():
        return (
            "INVALID",
            None,
            AuthorityInputBinding(
                role=role,
                state="INVALID",
                identity=None,
            ),
        )
    try:
        payload, identity = read_stable_file_bytes(path)
    except (OSError, DailyMarketAuthorityError):
        return (
            "INVALID",
            None,
            AuthorityInputBinding(
                role=role,
                state="INVALID",
                identity=None,
            ),
        )
    return (
        "PRESENT",
        payload,
        AuthorityInputBinding(
            role=role,
            state="PRESENT",
            identity=identity,
        ),
    )


def bound_candidate_pairs(
    path: Path,
) -> tuple[frozenset[tuple[str, str]], AuthorityInputBinding]:
    state, payload, binding = _bound_bytes(path, "CANDIDATE_SCORES")
    if state != "PRESENT" or payload is None:
        raise DailyMarketAuthorityError("CANDIDATE_SCORE_BINDING_INVALID")
    try:
        reader = csv.DictReader(StringIO(payload.decode("utf-8-sig"), newline=""))
        fields = frozenset(reader.fieldnames or ())
        if not {"date", "code", "eligible_for_selection"}.issubset(fields):
            raise DailyMarketAuthorityError("CANDIDATE_SCORE_SCHEMA_INVALID")
        pairs: set[tuple[str, str]] = set()
        for row in reader:
            try:
                eligible = parse_candidate_eligibility(
                    row.get("eligible_for_selection", "")
                )
            except ValueError as exc:
                raise DailyMarketAuthorityError(
                    "CANDIDATE_ELIGIBILITY_INVALID"
                ) from exc
            if not eligible:
                continue
            date_text = str(row.get("date", "")).replace("-", "")
            code = str(row.get("code", "")).zfill(6)
            if (
                len(date_text) != 8
                or len(code) != 6
                or not date_text.isdigit()
                or not code.isdigit()
            ):
                raise DailyMarketAuthorityError("CANDIDATE_MEMBERSHIP_KEY_INVALID")
            pairs.add((date_text, code))
    except UnicodeDecodeError as exc:
        raise DailyMarketAuthorityError("CANDIDATE_SCORE_ENCODING_INVALID") from exc
    if not pairs:
        raise DailyMarketAuthorityError("CANDIDATE_MEMBERSHIP_KEYS_MISSING")
    return frozenset(pairs), binding


def bound_price_provenance(
    path: Path,
) -> tuple[
    EvidenceState,
    PriceProvenanceRecord | None,
    AuthorityInputBinding,
]:
    state, payload, binding = _bound_bytes(path, "PRICE_PROVENANCE")
    if state != "PRESENT" or payload is None:
        return state, None, binding
    try:
        record = PriceProvenanceRecord.model_validate_json(payload)
    except ValidationError:
        return "INVALID", None, binding
    return "PRESENT", record, binding


def bound_current_metadata(
    path: Path,
) -> tuple[EvidenceState, tuple[str, ...], AuthorityInputBinding]:
    state, payload, binding = _bound_bytes(path, "CURRENT_OFFICIAL_METADATA")
    if state != "PRESENT" or payload is None:
        return state, (), binding
    required = {
        "code",
        "name",
        "market",
        "instrument_type",
        "available_at",
        "source_hash",
    }
    try:
        reader = csv.DictReader(StringIO(payload.decode("utf-8-sig"), newline=""))
        if not required.issubset(frozenset(reader.fieldnames or ())):
            return "INVALID", (), binding
        hashes: set[str] = set()
        observed = 0
        for row in reader:
            code = str(row.get("code", ""))
            market = str(row.get("market", ""))
            instrument_type = str(row.get("instrument_type", ""))
            available_at = str(row.get("available_at", ""))
            source_hash = str(row.get("source_hash", ""))
            if (
                len(code) != 6
                or not code.isdigit()
                or market not in {"KOSPI", "KOSDAQ", "KONEX"}
                or instrument_type != "common_equity"
                or len(available_at) != 8
                or not available_at.isdigit()
                or len(source_hash) != 64
                or any(character not in "0123456789abcdef" for character in source_hash)
            ):
                return "INVALID", (), binding
            hashes.add(source_hash)
            observed += 1
    except (csv.Error, UnicodeDecodeError):
        return "INVALID", (), binding
    return (
        ("PRESENT", tuple(sorted(hashes)), binding)
        if observed
        else ("INVALID", (), binding)
    )


def bound_pit_records(
    path: Path,
) -> tuple[EvidenceState, tuple[PitMembershipRecord, ...], AuthorityInputBinding]:
    state, payload, binding = _bound_bytes(path, "PIT_MEMBERSHIP")
    if state != "PRESENT" or payload is None:
        return state, (), binding
    required = {
        "code",
        "name",
        "market",
        "instrument_type",
        "effective_from",
        "effective_to",
        "available_at",
        "source_hash",
    }
    try:
        reader = csv.DictReader(StringIO(payload.decode("utf-8-sig"), newline=""))
        if not required.issubset(frozenset(reader.fieldnames or ())):
            return "INVALID", (), binding
        records = tuple(PitMembershipRecord.model_validate(row) for row in reader)
    except (csv.Error, UnicodeDecodeError, ValidationError):
        return "INVALID", (), binding
    return ("PRESENT", records, binding) if records else ("INVALID", (), binding)


__all__ = [
    "EvidenceState",
    "bound_candidate_pairs",
    "bound_current_metadata",
    "bound_pit_records",
    "bound_price_provenance",
]

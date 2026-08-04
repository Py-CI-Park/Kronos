"""Fail-closed audit of local Type1 authority evidence for daily-close research."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Literal, cast

from stom_rl.daily_type1_authority import INTEGRITY_LABEL, load_type1_authority

CodeDisposition = Literal[
    "STABLE_AT_ANCHOR",
    "ELIGIBLE_OUTSIDE_STABLE_TOP_500",
    "EXCLUDED_AT_ANCHOR",
    "NOT_CLASSIFIED",
]

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_EXTERNAL_BLOCKERS: Final = (
    "POINT_IN_TIME_UNIVERSE",
    "AVAILABLE_AT_PROVEN",
    "OFFICIAL_PRICE_IDENTITY",
    "CORPORATE_ACTION_CONTRACT",
)


class AuthorityAuditError(ValueError):
    """Local authority material is missing, malformed, or source-inconsistent."""


@dataclass(frozen=True, slots=True)
class RegisteredCodeFinding:
    code: str
    disposition: CodeDisposition
    reason: str


@dataclass(frozen=True, slots=True)
class LocalAuthorityAuditReceipt:
    authority_id: str
    authority_anchor_date: str
    authority_artifact_sha256: str
    authority_integrity_label: str
    evidence_scope: str
    source_identity_sha256: str
    source_identity_matched: bool
    registered_code_count: int
    stable_at_anchor_count: int
    eligible_outside_stable_count: int
    excluded_at_anchor_count: int
    not_classified_count: int
    code_findings: tuple[RegisteredCodeFinding, ...]
    external_attestation: bool
    point_in_time_universe_proven: bool
    available_at_proven: bool
    official_price_identity_proven: bool
    corporate_action_contract_proven: bool
    fresh_oos_state: str
    blockers: tuple[str, ...]
    verdict: str


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AuthorityAuditError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _as_sequence(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise AuthorityAuditError(f"{label} must be an array")
    return tuple(cast(list[object] | tuple[object, ...], value))


def _required_string(source: Mapping[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value:
        raise AuthorityAuditError(f"{key} must be a non-empty string")
    return value


def _row_symbols(value: object, label: str) -> set[str]:
    symbols: set[str] = set()
    for item in _as_sequence(value, label):
        row = _as_mapping(item, f"{label} row")
        symbols.add(_required_string(row, "symbol"))
    return symbols


def classify_registered_codes(
    authority: Mapping[str, object],
    codes: tuple[str, ...],
) -> tuple[RegisteredCodeFinding, ...]:
    stable_values = _as_sequence(authority.get("stable_symbols"), "stable_symbols")
    if not all(isinstance(value, str) for value in stable_values):
        raise AuthorityAuditError("stable_symbols must contain strings")
    stable = {cast(str, value) for value in stable_values}
    ranking = _as_mapping(authority.get("ranking"), "ranking")
    eligible = _row_symbols(ranking.get("rows"), "ranking.rows")
    excluded: dict[str, str] = {}
    for item in _as_sequence(authority.get("candidate_exclusions"), "candidate_exclusions"):
        row = _as_mapping(item, "candidate_exclusions row")
        excluded[_required_string(row, "symbol")] = _required_string(row, "reason")

    findings: list[RegisteredCodeFinding] = []
    for code in codes:
        if code in stable:
            findings.append(RegisteredCodeFinding(code, "STABLE_AT_ANCHOR", "top_500_by_anchor_liquidity"))
        elif code in eligible:
            findings.append(
                RegisteredCodeFinding(code, "ELIGIBLE_OUTSIDE_STABLE_TOP_500", "below_anchor_top_500")
            )
        elif code in excluded:
            findings.append(RegisteredCodeFinding(code, "EXCLUDED_AT_ANCHOR", excluded[code]))
        else:
            findings.append(RegisteredCodeFinding(code, "NOT_CLASSIFIED", "absent_from_local_anchor_authority"))
    return tuple(findings)


def _load_daily_identity(path: Path) -> str:
    try:
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityAuditError("source identity artifact is unreadable") from exc
    daily = _as_mapping(_as_mapping(payload, "source identity").get("daily"), "daily identity")
    digest = _required_string(daily, "sha256")
    if _SHA256.fullmatch(digest) is None:
        raise AuthorityAuditError("daily source identity sha256 is malformed")
    return digest


def audit_local_authority(
    authority_path: Path,
    source_identity_path: Path,
    *,
    database_sha256: str,
    codes: tuple[str, ...],
) -> LocalAuthorityAuditReceipt:
    if _SHA256.fullmatch(database_sha256) is None:
        raise AuthorityAuditError("database sha256 is malformed")
    authority = cast(Mapping[str, object], load_type1_authority(authority_path))
    identity_sha256 = _load_daily_identity(source_identity_path)
    if identity_sha256 != database_sha256:
        raise AuthorityAuditError("daily source identity does not match the research database")
    findings = classify_registered_codes(authority, codes)
    fresh_oos = _as_mapping(authority.get("fresh_oos"), "fresh_oos")
    if fresh_oos != {"status": "NOT_RUN", "no_read": True}:
        raise AuthorityAuditError("Fresh OOS state must remain NOT_RUN/no-read")

    def count(disposition: CodeDisposition) -> int:
        return sum(item.disposition == disposition for item in findings)

    return LocalAuthorityAuditReceipt(
        authority_id=_required_string(authority, "authority_id"),
        authority_anchor_date=_required_string(authority, "anchor_date"),
        authority_artifact_sha256=hashlib.sha256(authority_path.read_bytes()).hexdigest(),
        authority_integrity_label=INTEGRITY_LABEL,
        evidence_scope="LOCAL_2017_ANCHOR_CLASSIFICATION_ONLY",
        source_identity_sha256=identity_sha256,
        source_identity_matched=True,
        registered_code_count=len(codes),
        stable_at_anchor_count=count("STABLE_AT_ANCHOR"),
        eligible_outside_stable_count=count("ELIGIBLE_OUTSIDE_STABLE_TOP_500"),
        excluded_at_anchor_count=count("EXCLUDED_AT_ANCHOR"),
        not_classified_count=count("NOT_CLASSIFIED"),
        code_findings=findings,
        external_attestation=False,
        point_in_time_universe_proven=False,
        available_at_proven=False,
        official_price_identity_proven=False,
        corporate_action_contract_proven=False,
        fresh_oos_state="NOT_RUN_NO_READ",
        blockers=_EXTERNAL_BLOCKERS,
        verdict="AUDITED_LOCAL_ANCHOR_NO_GO_EXTERNAL_AUTHORITY",
    )


def write_authority_audit(receipt: LocalAuthorityAuditReceipt, output: Path) -> None:
    """Atomically persist a rebuildable authority audit receipt."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    _ = temporary.write_text(
        json.dumps(asdict(receipt), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _ = temporary.replace(output)

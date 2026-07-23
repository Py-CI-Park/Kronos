"""Immutable report authority for the replacement Type1 public run.

This module deliberately has no fresh-OOS inputs.  A report is a hash-addressed
revision, not a request for the latest report in a directory.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
AMENDMENT_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_recovery_amendment_v3_2026-07-24.json"
REPORT_ROOT = "type1_reports"
REVISION_SCHEMA = "kronos_type1_report_revision.v2"
MATERIALIZATION_SCHEMA = "kronos_type1_report_materialization.v2"
TIP_SCHEMA = "kronos_type1_committed_report_tip.v2"
BUILDER_VERSION = "kronos_type1_report_builder.v2"
REPLACEMENT_IDENTITY = {
    "authority_id": "type1-krx-authority-20260724-003",
    "dataset_id": "type1-close-20260803-004",
    "train_id": "type1-public-004",
    "train_run_id": "train_type1-public-004",
    "custody_uid": "type1-fresh-oos-20260803-004",
}
REPLACEMENT_OUTER_IDENTITY = {
    **REPLACEMENT_IDENTITY,
    "report_family": "kronos.type1.report.v1",
}
IDENTITY = {
    **REPLACEMENT_OUTER_IDENTITY,
    "domain": "kronos.type1",
    "algorithm_family": "MASKABLE_PPO",
}
POLICY = {"price_basis": "EXACT_15_20_BAR_CLOSE_PROXY", "official_close": False, "accounting": "FIXED_NOTIONAL_NON_SELF_FINANCING", "primary_cost_rate": "0.0023", "initial_nav_krw": "60000000", "slot_notional_krw": "5000000", "maximum_slots": 10, "seeds": [0, 1, 2, 3, 4], "checkpoint_selection": False, "synthetic_oracle_calibration": False}
LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
M3E_STATEMENT = "LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EVENT = re.compile(r"([0-9]{8})-([0-9a-f]{64})\.json\Z")
_OBJECT = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]{0,80})-([0-9a-f]{64})\.html\Z")
# Names are fixed; callers cannot substitute a path for any authority artifact.
_SOURCE_LOCAL_PATHS = {
    "type1_identity": Path("type1_identity.json"),
    "public_run_seal": Path("p6_public_run_seal.json"),
    "deployment_lock": Path("deployment_lock.json"),
    "attempt_parent": Path("attempt_parent.json"),
    "authority": Path("authority.json"),
    "dataset_manifest": Path("..") / "dataset_manifest.json",
    "public_rows": Path("..") / "public_rows.json",
    "run_manifest": Path("run_manifest.json"),
    "run_receipt": Path("receipt.json"),
    **{f"{kind}_seed_{seed}_{artifact}": Path(kind) / f"seed_{seed}" / filename
       for kind in ("primary", "shuffled_reward") for seed in range(5)
       for artifact, filename in (("model", "final_model.zip"), ("normalizer", "normalizer.pkl"))},
}

class Type1ReportError(ValueError):
    """Raised when a Type1 immutable report authority is invalid or blocked."""

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise Type1ReportError(f"{label} must be lowercase SHA-256")
    return value

def _is_reparse(path: Path) -> bool:
    try:
        mode = os.lstat(path).st_mode
        attrs = os.lstat(path).st_file_attributes if hasattr(os.lstat(path), "st_file_attributes") else 0
    except OSError as exc:
        raise Type1ReportError("authority path is unreadable") from exc
    return stat.S_ISLNK(mode) or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

def _safe_child(root: Path, relative: Path) -> Path:
    """Lexically contain a path and reject every symlink/junction component."""
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise Type1ReportError("authority path escapes fixed root")
    root = root.absolute()
    for ancestor in (root, *root.parents):
        if _is_reparse(ancestor):
            raise Type1ReportError("authority root contains a reparse point")
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.exists() and _is_reparse(candidate):
            raise Type1ReportError("authority path contains reparse point")
    try:
        candidate.absolute().relative_to(root)
    except ValueError as exc:
        raise Type1ReportError("authority path escapes fixed root") from exc
    return candidate

def _read_bytes(path: Path, label: str, *, maximum: int = 64 * 1024 * 1024) -> bytes:
    if _is_reparse(path) or not path.is_file():
        raise Type1ReportError(f"required report source is missing: {label}")
    try:
        size = path.stat().st_size
        if size < 0 or size > maximum:
            raise Type1ReportError(f"required report source is oversized: {label}")
        with path.open("rb") as handle:
            raw = handle.read(maximum + 1)
    except OSError as exc:
        raise Type1ReportError(f"required report source is unreadable: {label}") from exc
    if len(raw) != size or len(raw) > maximum:
        raise Type1ReportError(f"required report source changed while read: {label}")
    return raw

def _read_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = _read_bytes(path, label)
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, Type1ReportError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise Type1ReportError(f"{label} is not canonical JSON")
    return value, raw
def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_bytes(path, label).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, Type1ReportError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict):
        raise Type1ReportError(f"{label} is invalid")
    return value

def _write_new(path: Path, raw: bytes) -> None:
    """Create and durably write an immutable object; accept only an exact orphan retry."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    except FileExistsError:
        if _read_bytes(path, "existing immutable catalog entry", maximum=len(raw)) != raw:
            raise Type1ReportError("immutable catalog entry already exists")
        return
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    except Exception as exc:
        raise Type1ReportError("indeterminate immutable create; retry exact operation to recover") from exc

def _root(run_dir: str | Path, *, create: bool = False) -> Path:
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    root = _safe_child(directory, Path(REPORT_ROOT))
    if create:
        try:
            root.mkdir(exist_ok=True); _safe_child(root, Path("events")).mkdir(exist_ok=True); _safe_child(root, Path("objects")).mkdir(exist_ok=True)
        except OSError as exc:
            raise Type1ReportError("cannot create report catalog root") from exc
    if not root.is_dir() or _is_reparse(root):
        raise Type1ReportError("report catalog root is invalid")
    for name in ("events", "objects"):
        child = _safe_child(root, Path(name))
        if not child.is_dir() or _is_reparse(child):
            raise Type1ReportError("report catalog root is invalid")
    return root

def _mutex(root: Path) -> sqlite3.Connection:
    db = _safe_child(root, Path("current_parent.sqlite3"))
    if db.exists() and _is_reparse(db):
        raise Type1ReportError("current-parent authority is invalid")
    try:
        con = sqlite3.connect(str(db), timeout=30, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE IF NOT EXISTS current_parent (singleton INTEGER PRIMARY KEY CHECK(singleton=1), event_sha256 TEXT NOT NULL, state TEXT NOT NULL)")
        return con
    except sqlite3.Error as exc:
        raise Type1ReportError("current-parent authority is unavailable") from exc
def _identity_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = value.get("identity", value)
    if not isinstance(candidate, Mapping) or any(
        candidate.get(key) != expected for key, expected in REPLACEMENT_OUTER_IDENTITY.items()
    ):
        raise Type1ReportError("authority artifact does not bind exact replacement outer identity")
    return candidate


def _validate_authority_sources(fixed: Mapping[str, Mapping[str, Any]]) -> None:
    amendment = fixed["amendment"]
    if (
        amendment.get("schema_version") != "kronos.type1.g002-recovery-amendment.v3"
        or amendment.get("amendment_id") != "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-003"
        or amendment.get("supersedes") != "KRONOS-TYPE1-G002-RECOVERY-2026-07-23-002"
        or amendment.get("status") != "FROZEN_BEFORE_V4_MATERIALIZATION_OR_TRAINING"
        or amendment.get("replacement_identity") != REPLACEMENT_IDENTITY
    ):
        raise Type1ReportError("recovery amendment does not bind exact frozen v4 replacement identity")
    execution = amendment.get("execution_contract")
    fresh_oos = amendment.get("fresh_oos")
    preserved = amendment.get("preserved_aborted_evidence")
    expected_attempts = (
        ("type1-close-20260803-001", "type1-public-001", "train_type1-public-001", "INELIGIBLE_BLOCKED"),
        ("type1-close-20260803-002", "type1-public-002", "train_type1-public-002", "INELIGIBLE_BLOCKED"),
        ("type1-close-20260803-003", "type1-public-003", "train_type1-public-003", "NON_MATERIALIZED_INELIGIBLE"),
    )
    if (
        not isinstance(execution, Mapping)
        or execution.get("outcome") != "NO_GO_ONLY"
        or execution.get("cost_bps") != 23
        or execution.get("primary_seeds") != 5
        or execution.get("shuffled_seeds") != 5
        or not isinstance(fresh_oos, Mapping)
        or fresh_oos != {
            "custody_uid": REPLACEMENT_IDENTITY["custody_uid"],
            "status": "NOT_RUN",
            "no_read": True,
            "no_price_or_oos_query_after": "2025-06-30",
        }
        or not isinstance(preserved, list)
        or len(preserved) != len(expected_attempts)
    ):
        raise Type1ReportError("recovery amendment frozen no-go or aborted history is invalid")
    for evidence, (dataset_id, train_id, train_run_id, status) in zip(preserved, expected_attempts):
        if not isinstance(evidence, Mapping) or (
            evidence.get("dataset_id"),
            evidence.get("train_id"),
            evidence.get("train_run_id"),
            evidence.get("status"),
            evidence.get("models_created"),
        ) != (dataset_id, train_id, train_run_id, status, 0):
            raise Type1ReportError("recovery amendment aborted history is invalid")
    if preserved[2].get("fresh_oos") != {"status": "NOT_RUN", "no_read": True}:
        raise Type1ReportError("recovery amendment v3 fresh-OOS history is invalid")
    quarantined = amendment.get("quarantined_authorities")
    if quarantined != [{
        "authority_id": "type1-krx-authority-20260723-002",
        "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2",
        "status": "QUARANTINED",
        "models_created": 0,
        "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }]:
        raise Type1ReportError("recovery amendment does not quarantine the v2 authority")
    authority_contract = amendment.get("authority_contract")
    if not isinstance(authority_contract, Mapping) or (
        authority_contract.get("authority_metadata_cutoff"),
        authority_contract.get("authority_metadata_scope"),
    ) != (
        "2026-07-24",
        "MDCSTAT23801 instrument-master metadata only; this does not extend price, calendar, ranking, public-row, or fresh-OOS access beyond 2025-06-30.",
    ):
        raise Type1ReportError("recovery amendment authority metadata scope is invalid")

    protocol, preregistration = fixed["protocol"], fixed["preregistration"]
    if (protocol.get("protocol_id"), protocol.get("parent_prereg_id")) != (
        "KRONOS-TYPE1-G002-PUBLIC-2026-07-23", "KRONOS-TYPE1-CLOSING-2026-07-23",
    ):
        raise Type1ReportError("protocol ancestry is invalid")
    boundary, training = protocol.get("scientific_boundary"), protocol.get("training")
    if not isinstance(boundary, Mapping) or not isinstance(training, Mapping) or (
        boundary.get("price_basis"), boundary.get("primary_round_trip_cost_rate"),
        boundary.get("fresh_oos_state"), boundary.get("fresh_oos_read_performed"),
        training.get("seeds"), boundary.get("terminal_verdict"),
    ) != ("EXACT_15_20_BAR_CLOSE_PROXY", "0.0023", "NOT_RUN", False, [0, 1, 2, 3, 4], "NO_GO"):
        raise Type1ReportError("protocol Type1 boundary is invalid")
    m3e = preregistration.get("m3e_context")
    if preregistration.get("prereg_id") != "KRONOS-TYPE1-CLOSING-2026-07-23" or not isinstance(m3e, Mapping) or (
        m3e.get("classification"), m3e.get("verdict"), m3e.get("fresh_oos_status")
    ) != ("CONTEXTUAL_BANDIT_RESEARCH_EXPERIMENT", "NO_GO", "NOT_RUN"):
        raise Type1ReportError("preregistration M3E boundary is invalid")

    for label in ("type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "authority"):
        _identity_mapping(fixed[label])
    seal = fixed["public_run_seal"]
    fresh = seal.get("fresh_oos", seal)
    if not isinstance(fresh, Mapping) or (
        fresh.get("state", fresh.get("fresh_oos_state")), fresh.get("payload_read", fresh.get("fresh_oos_read_performed"))
    ) != ("NOT_RUN", False):
        raise Type1ReportError("P6 public run seal has unsafe fresh-OOS state")
    lock = fixed["deployment_lock"]
    if lock.get("false_research_locks", lock.get("locks")) != LOCKS:
        raise Type1ReportError("deployment lock does not preserve Type1 no-go locks")
    parent = fixed["attempt_parent"]
    prior = parent.get("parent_identity", parent.get("parent_attempt", parent.get("previous_attempt")))
    if not isinstance(prior, Mapping) or (
        prior.get("dataset_id"), prior.get("train_id"), prior.get("train_run_id")
    ) != ("type1-close-20260803-002", "type1-public-002", "train_type1-public-002"):
        raise Type1ReportError("attempt parent does not preserve aborted -002 ancestry")
    authority = fixed["authority"]
    if authority.get("authority_id", _identity_mapping(authority).get("authority_id")) != REPLACEMENT_OUTER_IDENTITY["authority_id"]:
        raise Type1ReportError("authority source does not bind replacement authority ID")

def report_source_sha256(run_dir: str | Path) -> dict[str, str]:
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    paths = {
        "amendment": _safe_child(REPO_ROOT, Path("docs") / AMENDMENT_PATH.name),
        "protocol": _safe_child(REPO_ROOT, Path("docs") / PROTOCOL_PATH.name),
        "preregistration": _safe_child(REPO_ROOT, Path("docs") / PREREG_PATH.name),
        "builder_source": _safe_child(REPO_ROOT, Path("stom_rl") / Path(__file__).name),
        **{label: _safe_child(directory, relative) for label, relative in _SOURCE_LOCAL_PATHS.items() if label not in {"dataset_manifest", "public_rows"}},
        "dataset_manifest": _safe_child(directory.parent, Path("dataset_manifest.json")),
        "public_rows": _safe_child(directory.parent, Path("public_rows.json")),
    }
    fixed = {label: (_read_json(paths[label], label) if label in {"amendment", "protocol", "preregistration"} else _read_canonical(paths[label], label)[0]) for label in ("amendment", "protocol", "preregistration", "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "authority")}
    _validate_authority_sources(fixed)
    return {label: _sha(_read_bytes(path, label)) for label, path in paths.items()}
def _verify_current_parent(root: Path, events: list[tuple[dict[str, Any], str]], state: str) -> None:
    db = _safe_child(root, Path("current_parent.sqlite3"))
    if not db.is_file() or _is_reparse(db):
        raise Type1ReportError("current-parent authority is missing")
    expected = events[-1][1] if events else None
    expected_state = "COMMITTED" if state == "COMMITTED" else ("MATERIALIZED" if events and len(events) % 2 == 0 else ("REVISION" if events else "EMPTY"))
    previous = events[-2][1] if len(events) > 1 else None
    previous_state = "MATERIALIZED" if len(events) > 1 and (len(events) - 1) % 2 == 0 else ("REVISION" if events else "EMPTY")
    try:
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT event_sha256,state FROM current_parent WHERE singleton=1").fetchone()
        # A fully validated final event/tip can outlive its SQLite parent update
        # after O_EXCL/fsync success. Recover only that immediate exact orphan.
        if expected and ((row is None and previous is None) or (row is not None and row == (previous, previous_state))):
            con.execute("INSERT OR REPLACE INTO current_parent(singleton,event_sha256,state) VALUES(1,?,?)", (expected, expected_state))
            con.commit()
            row = (expected, expected_state)
        con.close()
    except sqlite3.Error as exc:
        raise Type1ReportError("current-parent authority is unreadable") from exc
    if row is None or row[0] != expected or row[1] != expected_state:
        raise Type1ReportError("current-parent authority mismatch")

def _validate_revision(value: Mapping[str, Any]) -> None:
    required = {"schema_version", "revision_id", "revision_ordinal", "identity", "policy", "result", "source_sha256", "evidence", "false_research_locks", "claims", "catalog_ordinal", "previous_event_sha256", "previous_revision_event_sha256"}
    if set(value) != required or value.get("schema_version") != REVISION_SCHEMA or value.get("identity") != IDENTITY or value.get("policy") != POLICY:
        raise Type1ReportError("revision does not match frozen replacement Type1 contract")
    if not isinstance(value.get("revision_id"), str) or not re.fullmatch(r"type1-r[0-9]{4,}", value["revision_id"]): raise Type1ReportError("revision ID is invalid")
    if type(value.get("revision_ordinal")) is not int or value["revision_ordinal"] < 1: raise Type1ReportError("revision ordinal is invalid")
    result = value.get("result")
    states = {"COMPLETE", "FAILED", "BLOCKED", "NOT_RUN"}
    if not isinstance(result, Mapping) or result.get("run_state") not in states or result.get("training_state") not in states or result.get("reused_validation_state") not in states or result.get("verdict") != "NO_GO" or result.get("fresh_oos_state") not in {"NOT_RUN", "ACCUMULATING_NOT_RUN", "BLOCKED"} or result.get("fresh_oos_read_performed") is not False or not isinstance(result.get("failures"), list): raise Type1ReportError("revision result violates Type1 boundary")
    for state in ("run_state", "training_state", "reused_validation_state"):
        if result[state] in {"FAILED", "BLOCKED", "NOT_RUN"} and not result["failures"]: raise Type1ReportError("failed, blocked, or not-run state requires failure reason")
    sources, evidence = value.get("source_sha256"), value.get("evidence")
    required_evidence = {"type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "amendment", "protocol", "preregistration", "authority", "builder_source"}
    if not isinstance(sources, Mapping) or not isinstance(evidence, Mapping) or set(evidence) != required_evidence: raise Type1ReportError("replacement authority evidence is incomplete")
    for label, digest in sources.items():
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label): raise Type1ReportError("source label is invalid")
        _require_sha(digest, "source SHA")
    for label in required_evidence:
        if evidence[label] != sources.get(label): raise Type1ReportError("authority evidence does not bind fixed source")
    if value.get("false_research_locks") != LOCKS or not isinstance(value.get("claims"), Mapping): raise Type1ReportError("revision locks or claims are invalid")

def _render(revision: Mapping[str, Any], revision_sha: str) -> bytes:
    r = revision["result"]; failures = "".join(f"<li>{html.escape(str(x))}</li>" for x in r["failures"]) or "<li>None recorded.</li>"
    hashes = "".join(f"<li><code>{html.escape(k)}</code>: <code>{html.escape(v)}</code></li>" for k,v in sorted(revision["source_sha256"].items()))
    observed = f"<p>Observed completion — run: {html.escape(str(r['run_state']))}; training: {html.escape(str(r['training_state']))}; reused validation: {html.escape(str(r['reused_validation_state']))}.</p>"
    sections = (
        ("overview", "Overview", f"<p class=verdict>NO_GO</p>{observed}"),
        ("identity", "Type1 identity and scope", "<p>Replacement Type1 research-only evidence; not official close, alpha, profitability, paper, broker, live, or funded evidence.</p>"),
        ("protocol", "Protocol and accounting", "<p>Exact 15:20 close proxy and fixed-notional non-self-financing 23bp accounting.</p>"),
        ("training", "Training plan and observed completion", f"<p>Planned: five seeds × 200000 timesteps. This is a plan, not a completion claim.</p>{observed}"),
        ("validation", "Reused-validation controls", "<p>Reused validation can yield NO_GO only.</p>"),
        ("custody", "Fresh OOS and custody", f"<p>Fresh OOS: {html.escape(str(r['fresh_oos_state']))}; payload was not read.</p><p>M3E: {M3E_STATEMENT}</p>"),
        ("integrity", "Failures and integrity", f"<p>Revision SHA-256: <code>{revision_sha}</code></p><ul>{failures}</ul><ul>{hashes}</ul>"),
    )
    links = "".join(f'<a href="#{key}">{title}</a>' for key, title, _ in sections)
    body = "".join(f'<section id="{key}" aria-labelledby="{key}-heading"><h2 id="{key}-heading">{title}</h2>{content}</section>' for key, title, content in sections)
    text = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Type1 immutable report</title><style>'
        'body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem;line-height:1.5}'
        'nav{display:flex;gap:.7rem;flex-wrap:wrap}'
        'section{border-top:1px solid #cbd5e1;margin-top:1rem}'
        '.verdict{font-weight:bold;padding:.6rem;background:#7f1d1d;color:white}'
        'code{overflow-wrap:anywhere}'
        '@media(max-width:600px){body{margin:1rem}nav{display:grid;grid-template-columns:1fr}}'
        '</style></head><body><h1>Type1 immutable reused-validation evidence</h1>'
        f'<nav aria-label="Report sections">{links}</nav><main>{body}</main></body></html>'
    )
    return text.encode("utf-8")

def verify_report_catalog(run_dir: str | Path) -> dict[str, Any]:
    root=_root(run_dir); events_dir=_safe_child(root,Path("events")); objects_dir=_safe_child(root,Path("objects"))
    try: paths=list(events_dir.iterdir())
    except OSError as exc: raise Type1ReportError("events directory is unreadable") from exc
    if len(paths)>100000: raise Type1ReportError("event count exceeds bound")
    indexed=[]
    for p in paths:
        m=_EVENT.fullmatch(p.name)
        if not m or _is_reparse(p) or not p.is_file(): raise Type1ReportError("orphan or malformed event")
        indexed.append((int(m.group(1)),m.group(2),p))
    indexed.sort(); events=[]; revisions={}; materialized={}; previous=None
    for pos,(ordinal,name,p) in enumerate(indexed,1):
        if ordinal!=pos: raise Type1ReportError("event ordinal gap")
        event,raw=_read_canonical(p,"event"); digest=_sha(raw)
        if digest!=name or event.get("catalog_ordinal")!=ordinal or event.get("previous_event_sha256")!=previous: raise Type1ReportError("event identity or chain mismatch")
        if pos%2:
            _validate_revision(event)
            if event.get("previous_revision_event_sha256") != (events[-2][1] if len(events)>=2 else None) or event["revision_id"] in revisions or event["revision_ordinal"]!=(pos+1)//2: raise Type1ReportError("revision predecessor mismatch")
            if event["source_sha256"] != report_source_sha256(run_dir): raise Type1ReportError("revision source hashes differ from fixed evidence paths")
            revisions[event["revision_id"]]=(event,digest)
        else:
            required={"schema_version","catalog_ordinal","previous_event_sha256","revision_event_sha256","builder_version","builder_source_sha256","object_id","html_sha256","byte_size"}
            if set(event)!=required or event.get("schema_version")!=MATERIALIZATION_SCHEMA or event.get("revision_event_sha256")!=events[-1][1] or event.get("builder_version")!=BUILDER_VERSION or event.get("builder_source_sha256")!=report_source_sha256(run_dir)["builder_source"]: raise Type1ReportError("materialization does not bind preceding revision")
            oid=event.get("object_id"); _require_sha(event.get("html_sha256"),"HTML SHA")
            if not isinstance(oid,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}",oid) or oid in materialized or type(event.get("byte_size")) is not int or event["byte_size"]<1: raise Type1ReportError("materialization is invalid")
            materialized[oid]=(event,digest)
        events.append((event,digest)); previous=digest
    opaths=list(objects_dir.iterdir())
    if len(opaths)!=len(materialized): raise Type1ReportError("orphan or missing object")
    for p in opaths:
        m=_OBJECT.fullmatch(p.name)
        if not m or _is_reparse(p) or not p.is_file() or m.group(1) not in materialized: raise Type1ReportError("orphan or malformed object")
        event,_=materialized[m.group(1)]; raw=_read_bytes(p,"object")
        if m.group(2)!=event["html_sha256"] or _sha(raw)!=event["html_sha256"] or len(raw)!=event["byte_size"]: raise Type1ReportError("object hash mismatch")
    tip_path=_safe_child(root,Path("committed_report_tip.json"))
    if not tip_path.exists():
        if events:
            _verify_current_parent(root, events, "DRAFT")
        return {"state":"DRAFT","event_count":len(events),"events":events,"root":root,"revisions":revisions}
    tip,tip_raw=_read_canonical(tip_path,"committed tip")
    required={"schema_version","identity","event_count","final_event_sha256","latest_revision_event_sha256","materialization_event_sha256","object_id","html_sha256"}
    if set(tip)!=required or tip.get("schema_version")!=TIP_SCHEMA or tip.get("identity")!=IDENTITY or tip.get("event_count")!=len(events) or not events or len(events)%2 or tip.get("final_event_sha256")!=events[-1][1] or tip.get("latest_revision_event_sha256")!=events[-2][1] or tip.get("materialization_event_sha256")!=events[-1][1] or tip.get("object_id")!=events[-1][0].get("object_id") or tip.get("html_sha256")!=events[-1][0].get("html_sha256"): raise Type1ReportError("committed tip is invalid")
    _verify_current_parent(root, events, "COMMITTED")
    return {"state":"COMMITTED","event_count":len(events),"events":events,"root":root,"revisions":revisions,"tip":tip,"tip_sha256":_sha(tip_raw),"revision":events[-2][0],"materialization":events[-1][0]}

def _assert_parent(con: sqlite3.Connection, expected: str|None, state: str) -> None:
    row=con.execute("SELECT event_sha256,state FROM current_parent WHERE singleton=1").fetchone()
    if (row is None and expected is not None) or (row is not None and (row[0]!=expected or row[1]!=state)): raise Type1ReportError("current-parent authority mismatch")

def insert_report_revision(run_dir: str|Path, revision: Mapping[str,Any])->dict[str,Any]:
    root=_root(run_dir,create=True); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE"); snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or len(snap["events"])%2: raise Type1ReportError("catalog is not open for a revision")
        expected=snap["events"][-1][1] if snap["events"] else None; _assert_parent(con,expected,"MATERIALIZED" if expected else "EMPTY")
        event=dict(revision); event.update({"catalog_ordinal":len(snap["events"])+1,"previous_event_sha256":expected,"previous_revision_event_sha256":snap["events"][-2][1] if snap["events"] else None})
        if event.get("revision_ordinal")!=(len(snap["events"])//2)+1: raise Type1ReportError("revision ordinal does not match catalog")
        _validate_revision(event)
        if event["source_sha256"]!=report_source_sha256(run_dir): raise Type1ReportError("revision source hashes differ from fixed evidence paths")
        raw=_canonical(event); digest=_sha(raw); _write_new(_safe_child(root,Path("events")/f"{event['catalog_ordinal']:08d}-{digest}.json"),raw)
        con.execute("INSERT OR REPLACE INTO current_parent(singleton,event_sha256,state) VALUES(1,?,?)",(digest,"REVISION")); con.execute("COMMIT")
        return {"event_sha256":digest,"catalog_ordinal":event["catalog_ordinal"],"revision_id":event["revision_id"]}
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()

def materialize_report_revision(run_dir: str|Path, revision_event_sha256:str)->dict[str,Any]:
    _require_sha(revision_event_sha256,"revision event SHA"); root=_root(run_dir); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE"); snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or not snap["events"] or len(snap["events"])%2==0 or snap["events"][-1][1]!=revision_event_sha256: raise Type1ReportError("only current unmaterialized revision may be materialized")
        _assert_parent(con,revision_event_sha256,"REVISION"); revision=snap["events"][-1][0]; data=_render(revision,revision_event_sha256); h=_sha(data); oid=revision["revision_id"]
        _write_new(_safe_child(root,Path("objects")/f"{oid}-{h}.html"),data)
        event={"schema_version":MATERIALIZATION_SCHEMA,"catalog_ordinal":len(snap["events"])+1,"previous_event_sha256":revision_event_sha256,"revision_event_sha256":revision_event_sha256,"builder_version":BUILDER_VERSION,"builder_source_sha256":report_source_sha256(run_dir)["builder_source"],"object_id":oid,"html_sha256":h,"byte_size":len(data)}; raw=_canonical(event); digest=_sha(raw)
        _write_new(_safe_child(root,Path("events")/f"{event['catalog_ordinal']:08d}-{digest}.json"),raw); con.execute("UPDATE current_parent SET event_sha256=?,state=? WHERE singleton=1",(digest,"MATERIALIZED")); con.execute("COMMIT")
        return {"event_sha256":digest,"object_id":oid,"html_sha256":h,"byte_size":len(data)}
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()

def commit_report_tip(run_dir: str|Path, materialization_event_sha256:str)->dict[str,Any]:
    _require_sha(materialization_event_sha256,"materialization event SHA"); root=_root(run_dir); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE"); snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or not snap["events"] or len(snap["events"])%2 or snap["events"][-1][1]!=materialization_event_sha256: raise Type1ReportError("only current materialization may be committed")
        _assert_parent(con,materialization_event_sha256,"MATERIALIZED"); m=snap["events"][-1][0]
        tip={"schema_version":TIP_SCHEMA,"identity":IDENTITY,"event_count":len(snap["events"]),"final_event_sha256":materialization_event_sha256,"latest_revision_event_sha256":snap["events"][-2][1],"materialization_event_sha256":materialization_event_sha256,"object_id":m["object_id"],"html_sha256":m["html_sha256"]}; _write_new(_safe_child(root,Path("committed_report_tip.json")),_canonical(tip)); con.execute("UPDATE current_parent SET state='COMMITTED' WHERE singleton=1"); con.execute("COMMIT"); return dict(tip)
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()

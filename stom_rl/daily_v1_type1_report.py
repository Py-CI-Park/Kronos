"""Immutable Type1 reused-validation report catalog; it never reads fresh OOS data."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
REPORT_ROOT = "type1_reports"
REVISION_SCHEMA = "kronos_type1_report_revision.v1"
MATERIALIZATION_SCHEMA = "kronos_type1_report_materialization.v1"
TIP_SCHEMA = "kronos_type1_committed_report_tip.v1"
BUILDER_VERSION = "kronos_type1_report_builder.v1"
IDENTITY = {"report_family": "TYPE1", "dataset_id": "type1-close-20260803-001", "train_id": "type1-public-001", "train_run_id": "train_type1-public-001", "domain": "kronos.type1", "algorithm_family": "MASKABLE_PPO"}
POLICY = {"price_basis": "EXACT_15_20_BAR_CLOSE_PROXY", "official_close": False, "accounting": "FIXED_NOTIONAL_NON_SELF_FINANCING", "primary_cost_rate": "0.0023", "initial_nav_krw": "60000000", "slot_notional_krw": "5000000", "maximum_slots": 10, "seeds": [0, 1, 2, 3, 4], "checkpoint_selection": False, "synthetic_oracle_calibration": False}
LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EVENT = re.compile(r"([0-9]{8})-([0-9a-f]{64})\.json\Z")
_OBJECT = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]{0,80})-([0-9a-f]{64})\.html\Z")
_SOURCE_LOCAL_PATHS = {
    "dataset_manifest": Path("..") / "dataset_manifest.json",
    "public_rows": Path("..") / "public_rows.json",
    "run_manifest": Path("run_manifest.json"),
    "run_receipt": Path("receipt.json"),
    **{
        f"{kind}_seed_{seed}_{artifact}": Path(kind) / f"seed_{seed}" / filename
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
        for artifact, filename in (
            ("model", "final_model.zip"),
            ("normalizer", "normalizer.pkl"),
        )
    },
}


class Type1ReportError(ValueError):
    """Raised when the immutable Type1 report catalog is invalid or blocked."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise Type1ReportError(f"{label} must be lowercase SHA-256")
    return value


def _read_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise Type1ReportError(f"{label} is not canonical JSON")
    return value, raw


def _write_new(path: Path, raw: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    except FileExistsError as exc:
        raise Type1ReportError("immutable catalog entry already exists") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _root(run_dir: str | Path, *, create: bool = False) -> Path:
    directory = Path(run_dir)
    if not directory.is_dir() or directory.is_symlink():
        raise Type1ReportError("run directory is required")
    root = directory / REPORT_ROOT
    if create:
        root.mkdir(exist_ok=True)
        (root / "events").mkdir(exist_ok=True)
        (root / "objects").mkdir(exist_ok=True)
    if not root.is_dir() or root.is_symlink() or not (root / "events").is_dir() or not (root / "objects").is_dir():
        raise Type1ReportError("report catalog root is invalid")
    return root


def report_source_sha256(run_dir: str | Path) -> dict[str, str]:
    """Hash the exact fixed Type1 evidence paths; report input cannot choose paths."""
    directory = Path(run_dir)
    paths = {
        "protocol": PROTOCOL_PATH,
        "preregistration": PREREG_PATH,
        **{label: directory / relative for label, relative in _SOURCE_LOCAL_PATHS.items()},
    }
    hashes: dict[str, str] = {}
    for label, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise Type1ReportError(f"required report source is missing: {label}")
        try:
            hashes[label] = _sha(path.read_bytes())
        except OSError as exc:
            raise Type1ReportError(f"required report source is unreadable: {label}") from exc
    return hashes


def _validate_revision(value: Mapping[str, Any]) -> None:
    required = {"schema_version", "revision_id", "revision_ordinal", "identity", "policy", "result", "source_sha256", "false_research_locks", "claims", "catalog_ordinal", "previous_event_sha256", "previous_revision_event_sha256"}
    if set(value) != required:
        raise Type1ReportError("revision fields are not exact")
    if value.get("schema_version") != REVISION_SCHEMA or value.get("identity") != IDENTITY or value.get("policy") != POLICY:
        raise Type1ReportError("revision does not match frozen Type1 contract")
    if not isinstance(value.get("revision_id"), str) or not re.fullmatch(r"type1-r[0-9]{4,}", value["revision_id"]):
        raise Type1ReportError("revision ID is invalid")
    ordinal = value.get("revision_ordinal")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise Type1ReportError("revision ordinal is invalid")
    result = value.get("result")
    if not isinstance(result, Mapping) or result.get("run_state") not in {"COMPLETE", "FAILED", "BLOCKED"} or result.get("training_state") not in {"COMPLETE", "FAILED", "NOT_RUN"} or result.get("reused_validation_state") not in {"COMPLETE", "FAILED", "NOT_RUN"} or result.get("verdict") != "NO_GO" or result.get("fresh_oos_state") not in {"NOT_RUN", "ACCUMULATING_NOT_RUN", "BLOCKED"} or result.get("fresh_oos_read_performed") is not False or not isinstance(result.get("failures"), list):
        raise Type1ReportError("revision result violates Type1 research boundary")
    sources = value.get("source_sha256")
    if not isinstance(sources, Mapping) or not sources:
        raise Type1ReportError("revision source hashes are required")
    for label, digest in sources.items():
        if not isinstance(label, str) or not label or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label):
            raise Type1ReportError("source label is invalid")
        _require_sha(digest, "source SHA")
    if value.get("false_research_locks") != LOCKS or not isinstance(value.get("claims"), Mapping):
        raise Type1ReportError("revision locks or claims are invalid")


def _render(revision: Mapping[str, Any], revision_sha: str) -> bytes:
    result = revision["result"]
    failures = "".join(f"<li>{html.escape(str(item), quote=True)}</li>" for item in result["failures"]) or "<li>None recorded.</li>"
    hashes = "".join(f"<li><code>{html.escape(str(k), quote=True)}</code>: <code>{html.escape(str(v), quote=True)}</code></li>" for k, v in sorted(revision["source_sha256"].items()))
    sections = (
        ("overview", "Overview", f"<p class=\"verdict\">{html.escape(str(result['verdict']))}</p><p>Scientific state: {html.escape(str(result['run_state']))}. Reused-validation cannot yield GO.</p>"),
        ("identity", "Type1 identity and scope", "<p>Research-only MASKABLE_PPO evidence. This is not official close, daily, paper, broker, live, funded, investment advice, alpha, or profitability evidence.</p>"),
        ("protocol", "Protocol and accounting", "<p>EXACT_15_20_BAR_CLOSE_PROXY; two-session chronological pairs; 23 bp (0.0023) fixed-notional non-self-financing accounting: 60M KRW initial NAV, 5M KRW slots, maximum 10 slots.</p>"),
        ("training", "Five-seed training", "<p>Five fixed seeds 0, 1, 2, 3, 4; exactly 200000 timesteps per member. No checkpoint selection, member selection, or synthetic oracle calibration.</p>"),
        ("validation", "Reused-validation controls", "<p>Comparators and controls are reused-validation evidence only. TRAIN_ONLY_SYNTHETIC_WIRING is never market learning or calibration.</p>"),
        ("custody", "Fresh OOS and custody", f"<p class=\"warning\">Fresh OOS: {html.escape(str(result['fresh_oos_state']))}; no fresh OOS read was performed. Sealed custody remains unopened.</p>"),
        ("integrity", "Failures and integrity", f"<p>Revision SHA-256: <code>{revision_sha}</code></p><h3>Failures</h3><ul>{failures}</ul><h3>Source hashes</h3><ul>{hashes}</ul>"),
    )
    tabs = "".join(f'<a href="#{key}">{title}</a>' for key, title, _ in sections)
    body = "".join(f'<section id="{key}"><h2>{title}</h2>{content}</section>' for key, title, content in sections)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Type1 immutable reused-validation report</title><style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem;line-height:1.5}nav{display:flex;gap:.7rem;flex-wrap:wrap}section{border-top:1px solid #cbd5e1;margin-top:1rem}.verdict,.warning{font-weight:bold;padding:.6rem;background:#7f1d1d;color:white}code{overflow-wrap:anywhere}</style></head><body><h1>Type1 immutable reused-validation evidence</h1><nav aria-label=\"Report tabs\">" + tabs + "</nav><main>" + body + "</main></body></html>").encode("utf-8")


def verify_report_catalog(run_dir: str | Path) -> dict[str, Any]:
    root = _root(run_dir)
    events_dir, objects_dir = root / "events", root / "objects"
    try:
        names = list(events_dir.iterdir())
    except OSError as exc:
        raise Type1ReportError("events directory is unreadable") from exc
    event_paths: list[tuple[int, str, Path]] = []
    for path in names:
        match = _EVENT.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file():
            raise Type1ReportError("orphan or malformed event")
        event_paths.append((int(match.group(1)), match.group(2), path))
    event_paths.sort()
    events: list[tuple[dict[str, Any], str]] = []
    revisions: dict[str, tuple[dict[str, Any], str]] = {}
    materialized: dict[str, tuple[dict[str, Any], str]] = {}
    previous: str | None = None
    for position, (ordinal, filename_sha, path) in enumerate(event_paths, 1):
        if ordinal != position:
            raise Type1ReportError("event ordinal gap")
        event, raw = _read_canonical(path, "event")
        digest = _sha(raw)
        if digest != filename_sha or event.get("catalog_ordinal") != ordinal or event.get("previous_event_sha256") != previous:
            raise Type1ReportError("event identity or chain mismatch")
        if position % 2:
            _validate_revision(event)
            if event.get("previous_revision_event_sha256") != (events[-2][1] if len(events) >= 2 else None):
                raise Type1ReportError("revision predecessor mismatch")
            if event["revision_id"] in revisions or event["revision_ordinal"] != (position + 1) // 2:
                raise Type1ReportError("duplicate or noncontiguous revision")
            revisions[event["revision_id"]] = (event, digest)
            if event["source_sha256"] != report_source_sha256(run_dir):
                raise Type1ReportError("revision source hashes differ from fixed evidence paths")
        else:
            if set(event) != {"schema_version", "catalog_ordinal", "previous_event_sha256", "revision_event_sha256", "builder_version", "builder_sha256", "object_id", "html_sha256", "byte_size"}:
                raise Type1ReportError("materialization fields are not exact")
            if event.get("schema_version") != MATERIALIZATION_SCHEMA or event.get("revision_event_sha256") != events[-1][1] or event.get("builder_version") != BUILDER_VERSION or event.get("builder_sha256") != _sha(BUILDER_VERSION.encode()):
                raise Type1ReportError("materialization does not bind preceding revision")
            object_id = event.get("object_id")
            if not isinstance(object_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", object_id) is None or object_id in materialized:
                raise Type1ReportError("materialization object ID is invalid")
            _require_sha(event.get("html_sha256"), "HTML SHA")
            if not isinstance(event.get("byte_size"), int) or event["byte_size"] < 1:
                raise Type1ReportError("materialization byte size is invalid")
            materialized[object_id] = (event, digest)
        events.append((event, digest)); previous = digest
    try:
        object_paths = list(objects_dir.iterdir())
    except OSError as exc:
        raise Type1ReportError("objects directory is unreadable") from exc
    if len(object_paths) != len(materialized):
        raise Type1ReportError("orphan or missing object")
    for path in object_paths:
        match = _OBJECT.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file() or match.group(1) not in materialized:
            raise Type1ReportError("orphan or malformed object")
        event, _ = materialized[match.group(1)]
        try: raw = path.read_bytes()
        except OSError as exc: raise Type1ReportError("object is unreadable") from exc
        if match.group(2) != event["html_sha256"] or _sha(raw) != event["html_sha256"] or len(raw) != event["byte_size"]:
            raise Type1ReportError("object hash mismatch")
    tip_path = root / "committed_report_tip.json"
    if not tip_path.exists():
        return {"state": "DRAFT", "event_count": len(events), "events": events, "root": root}
    if tip_path.is_symlink() or not tip_path.is_file():
        raise Type1ReportError("committed tip is invalid")
    tip, tip_raw = _read_canonical(tip_path, "committed tip")
    if set(tip) != {"schema_version", "identity", "event_count", "final_event_sha256", "latest_revision_event_sha256", "materialization_event_sha256", "object_id", "html_sha256"}:
        raise Type1ReportError("committed tip fields are not exact")
    if tip.get("schema_version") != TIP_SCHEMA or tip.get("identity") != IDENTITY or tip.get("event_count") != len(events) or not events or tip.get("final_event_sha256") != events[-1][1] or len(events) % 2 or tip.get("latest_revision_event_sha256") != events[-2][1] or tip.get("materialization_event_sha256") != events[-1][1]:
        raise Type1ReportError("committed tip does not bind latest materialization")
    event = events[-1][0]
    if tip.get("object_id") != event.get("object_id") or tip.get("html_sha256") != event.get("html_sha256"):
        raise Type1ReportError("committed tip object mismatch")
    return {"state": "COMMITTED", "event_count": len(events), "events": events, "root": root, "tip": tip, "tip_sha256": _sha(tip_raw), "revision": events[-2][0], "materialization": event}


def insert_report_revision(run_dir: str | Path, revision: Mapping[str, Any]) -> dict[str, Any]:
    root = _root(run_dir, create=True)
    snapshot = verify_report_catalog(run_dir)
    if snapshot["state"] == "COMMITTED" or len(snapshot["events"]) % 2:
        raise Type1ReportError("catalog is not open for a revision")
    event = dict(revision)
    expected_ordinal = len(snapshot["events"]) + 1
    expected_previous = snapshot["events"][-1][1] if snapshot["events"] else None
    expected_revision_previous = snapshot["events"][-2][1] if snapshot["events"] else None
    for key, expected in (("catalog_ordinal", expected_ordinal), ("previous_event_sha256", expected_previous), ("previous_revision_event_sha256", expected_revision_previous)):
        if key in event and event[key] != expected:
            raise Type1ReportError(f"{key} does not match catalog predecessor")
        event[key] = expected
    if event.get("revision_ordinal") != (len(snapshot["events"]) // 2) + 1:
        raise Type1ReportError("revision ordinal does not match catalog")
    if any(item[0].get("revision_id") == event.get("revision_id") for item in snapshot["events"][::2]):
        raise Type1ReportError("revision ID already exists")
    _validate_revision(event)
    if event["source_sha256"] != report_source_sha256(run_dir):
        raise Type1ReportError("revision source hashes differ from fixed evidence paths")
    raw = _canonical(event); digest = _sha(raw)
    _write_new(root / "events" / f"{event['catalog_ordinal']:08d}-{digest}.json", raw)
    return {"event_sha256": digest, "catalog_ordinal": event["catalog_ordinal"], "revision_id": event["revision_id"]}


def materialize_report_revision(run_dir: str | Path, revision_event_sha256: str) -> dict[str, Any]:
    _require_sha(revision_event_sha256, "revision event SHA")
    snapshot = verify_report_catalog(run_dir)
    if snapshot["state"] == "COMMITTED" or not snapshot["events"] or len(snapshot["events"]) % 2 == 0 or snapshot["events"][-1][1] != revision_event_sha256:
        raise Type1ReportError("only the latest unmaterialized revision may be materialized")
    root = snapshot["root"]; revision = snapshot["events"][-1][0]
    html_bytes = _render(revision, revision_event_sha256); html_sha = _sha(html_bytes); object_id = revision["revision_id"]
    object_path = root / "objects" / f"{object_id}-{html_sha}.html"
    _write_new(object_path, html_bytes)
    event = {"schema_version": MATERIALIZATION_SCHEMA, "catalog_ordinal": len(snapshot["events"]) + 1, "previous_event_sha256": revision_event_sha256, "revision_event_sha256": revision_event_sha256, "builder_version": BUILDER_VERSION, "builder_sha256": _sha(BUILDER_VERSION.encode()), "object_id": object_id, "html_sha256": html_sha, "byte_size": len(html_bytes)}
    raw = _canonical(event); digest = _sha(raw)
    try:
        _write_new(root / "events" / f"{event['catalog_ordinal']:08d}-{digest}.json", raw)
    except Exception:
        raise Type1ReportError("materialization event failed; orphan object blocks catalog")
    return {"event_sha256": digest, "object_id": object_id, "html_sha256": html_sha, "byte_size": len(html_bytes)}


def commit_report_tip(run_dir: str | Path, materialization_event_sha256: str) -> dict[str, Any]:
    _require_sha(materialization_event_sha256, "materialization event SHA")
    snapshot = verify_report_catalog(run_dir)
    if snapshot["state"] == "COMMITTED" or not snapshot["events"] or len(snapshot["events"]) % 2 or snapshot["events"][-1][1] != materialization_event_sha256:
        raise Type1ReportError("only the latest materialization may be committed")
    root = snapshot["root"]; materialization = snapshot["events"][-1][0]
    tip = {"schema_version": TIP_SCHEMA, "identity": IDENTITY, "event_count": len(snapshot["events"]), "final_event_sha256": materialization_event_sha256, "latest_revision_event_sha256": snapshot["events"][-2][1], "materialization_event_sha256": materialization_event_sha256, "object_id": materialization["object_id"], "html_sha256": materialization["html_sha256"]}
    _write_new(root / "committed_report_tip.json", _canonical(tip))
    return dict(tip)

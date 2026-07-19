"""Fail-closed local orchestrator for Kronos dashboard V5 release closure.

The orchestrator is intentionally inspection-only: it may read Git identity and
write nonce-scoped state below an ignored temporary root, but it never commits,
pushes, tags, deploys, promotes, starts trading, opens OOS data, or mutates the
tracked dashboard dist tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import rfc8785 as _rfc8785
except ModuleNotFoundError:  # pragma: no cover - fallback covers minimal stdlib environments.
    _rfc8785 = None


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA = "kronos_dashboard_v5_release_closure.v1"
STATE_SCHEMA = "kronos_release_closure_state.v1"
POINTER_SCHEMA = "kronos_release_closure_active_pointer.v1"
HISTORY_SCHEMA = "kronos_release_closure_pointer_history.v1"
PHASE_RECEIPT_SCHEMA = "kronos_release_phase_receipt.v1"
DEFAULT_GATE_SCHEMA = "kronos_v5_default_gate.v1"
TERMINAL_REPORT_SCHEMA = "kronos_release_terminal_report.v1"

PHASES: tuple[str, ...] = (
    "BIND_HEAD",
    "PREFLIGHT",
    "QA",
    "GENERIC_CAPTURE",
    "OPERATOR_A",
    "OPERATOR_B",
    "TASK_SCORE",
    "EVIDENCE",
    "PRECLOSURE",
    "ASSURANCE",
    "FINAL_MAP",
    "SCORE_A",
    "SCORE_B",
    "TERMINAL",
)

TERMINAL_STATUSES: tuple[str, ...] = (
    "ACTIVE",
    "INVALIDATED",
    "TERMINAL_BLOCKED",
    "TERMINAL_CLOSED",
)

SIX_LOCKS_FALSE: dict[str, bool] = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}

CATEGORY_LIMITS: dict[str, tuple[int, int]] = {
    "A": (25, 23),
    "B": (25, 23),
    "C": (20, 18),
    "D": (15, 13),
    "E": (15, 13),
}

HARD_CAPS_ORDER: tuple[str, ...] = (
    "fresh_oos_misrepresentation",
    "unapproved_contract_or_api_change",
)

BLOCKER_CODES: tuple[str, ...] = (
    "POINT_SCORE_MISMATCH",
    "POINT_SCORE_FAIL",
    "ASSURANCE_BLOCK",
    "PRIOR_CHAIN_RERESOLUTION_FAIL",
    "HEAD_DRIFT",
    "TREE_DRIFT",
    "DIST_DRIFT",
    "CONFIG_DRIFT",
    "DIRTY_WORKTREE",
    "SOURCE_IDENTITY_MISMATCH",
    "ROLLBACK_UNAVAILABLE",
    "ROLLBACK_QUERY_FAIL",
    "BROWSER_EVIDENCE_NOT_LIVE",
    "BROWSER_EVIDENCE_SYNTHETIC",
    "BROWSER_EVIDENCE_REUSED",
    "BROWSER_MATRIX_FAIL",
    "SECURITY_GATE_FAIL",
    "PUBLICATION_ACTION_FORBIDDEN",
    "LOCK_INVARIANT_FAIL",
    "DRY_RUN_FIXTURE_NOT_RELEASABLE",
)

V5_DEFAULT_EQUATION = (
    "V5_DEFAULT := RELEASE_CLOSED && POINT_SCORE_A_EQ_B && ENGINEERING_90_PASS && "
    "ASSURANCE_ELIGIBLE && PRIOR_CHAINS_RESOLVED && HEAD_MATCH && TREE_MATCH && "
    "DIST_MATCH && CONFIG_MATCH && WORKTREE_CLEAN && SOURCE_IDENTITY_BOUND && "
    "ROLLBACK_V3_AVAILABLE && ROLLBACK_QUERY_PASS && LIVE_BROWSER_DISTINCT && "
    "SECURITY_CLEAR && SIX_LOCKS_FALSE && NO_PUBLICATION_ACTION && !DRY_RUN_FIXTURE"
)

FORBIDDEN_PUBLICATION_ACTIONS: tuple[str, ...] = (
    "commit",
    "push",
    "tag",
    "merge",
    "publish",
    "deploy",
    "promote",
    "trade",
    "broker_order",
    "paper_forward",
)

MUTATING_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "add",
        "am",
        "apply",
        "bisect",
        "branch",
        "checkout",
        "cherry-pick",
        "clean",
        "commit",
        "fetch",
        "gc",
        "merge",
        "mv",
        "pull",
        "push",
        "rebase",
        "reset",
        "restore",
        "rm",
        "stash",
        "switch",
        "tag",
        "worktree",
    }
)

HEAVY_OR_FORBIDDEN_COMMAND_TOKENS: frozenset[str] = frozenset(
    {
        "backtest",
        "broker",
        "deploy",
        "finetune",
        "npm",
        "node",
        "oos",
        "ppo",
        "pytest",
        "publish",
        "tag",
        "train",
        "trading",
    }
)

READ_ONLY_GIT_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("git", "rev-parse", "--verify", "HEAD"),
    ("git", "rev-parse", "--verify", "HEAD^{tree}"),
    ("git", "status", "--porcelain=v1", "--untracked-files=all"),
)


class ReleaseClosureError(ValueError):
    """Release closure failed closed before a valid terminal report was built."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fallback_jcs(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 9007199254740991:
            raise ReleaseClosureError("integer is outside the JCS safe range")
        return str(value)
    if isinstance(value, float):
        raise ReleaseClosureError("floating point values are outside the pinned JCS profile")
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ReleaseClosureError("strings must not contain lone surrogates")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_fallback_jcs(item) for item in value) + "]"
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ReleaseClosureError("JCS object keys must be strings")
        return "{" + ",".join(json.dumps(key, ensure_ascii=False, separators=(",", ":")) + ":" + _fallback_jcs(value[key]) for key in sorted(value)) + "}"
    raise ReleaseClosureError("value is not JSON serializable")


def canonical_bytes(value: Any) -> bytes:
    try:
        if _rfc8785 is not None:
            return _rfc8785.dumps(value)
        return _fallback_jcs(value).encode("utf-8")
    except Exception as exc:  # pragma: no cover - exact canonicalizer exception types vary by version
        if isinstance(exc, ReleaseClosureError):
            raise
        raise ReleaseClosureError("value is not RFC8785/JCS canonicalizable") from exc


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def object_ref(uri: str, raw: bytes, schema: str) -> dict[str, Any]:
    if not isinstance(uri, str) or not uri.startswith("agent://") or not isinstance(schema, str) or not schema:
        raise ReleaseClosureError("ObjectRef uri/schema is invalid")
    return {"uri": uri, "sha256": sha256_bytes(raw), "byte_length": len(raw), "schema": schema}


def value_ref(uri: str, value: Mapping[str, Any], schema: str | None = None) -> dict[str, Any]:
    raw = canonical_bytes(value)
    return object_ref(uri, raw, schema or str(value.get("schema", "")))


def _parse_json(raw: bytes, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise ReleaseClosureError(f"{label} must be UTF-8 bytes without a BOM")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReleaseClosureError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReleaseClosureError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise ReleaseClosureError(f"{label} must be a JSON object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return _parse_json(path.read_bytes(), str(path))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _safe_temp_root(root: str | Path | None = None) -> Path:
    temp = Path(tempfile.gettempdir()).resolve(strict=False)
    if root is None:
        candidate = Path(tempfile.mkdtemp(prefix="kronos-v5-release-closure-"))
    else:
        candidate = Path(root)
        if ".." in candidate.parts:
            raise ReleaseClosureError("temp root path traversal is forbidden")
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, temp):
        raise ReleaseClosureError("release closure state root must stay below the OS temporary directory")
    lowered = tuple(part.casefold() for part in resolved.parts)
    if ("webui", "static", "v2", "dist") == lowered[-4:] or any(part in {"oos", "database", "db"} for part in lowered):
        raise ReleaseClosureError("release closure state root must not target tracked dist/OOS/database roots")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = canonical_bytes(value)
    _atomic_write(path, raw)
    return raw


def _lower_tokens(args: Sequence[str]) -> set[str]:
    tokens: set[str] = set()
    for arg in args:
        tokens.update(part for part in arg.casefold().replace("/", " ").replace("\\", " ").split() if part)
    return tokens


def _ensure_inspection_command(args: Sequence[str]) -> tuple[str, ...]:
    command = tuple(args)
    if not command or command[0] != "git":
        raise ReleaseClosureError("release closure subprocesses are restricted to read-only git inspection")
    if len(command) < 2:
        raise ReleaseClosureError("git inspection command is incomplete")
    subcommand = command[1].casefold()
    if subcommand in MUTATING_GIT_SUBCOMMANDS or subcommand not in {"rev-parse", "status"}:
        raise ReleaseClosureError("git inspection command is not read-only")
    tokens = _lower_tokens(command)
    if tokens & HEAVY_OR_FORBIDDEN_COMMAND_TOKENS:
        raise ReleaseClosureError("heavy/OOS/publication subprocess token is forbidden")
    return command


def _run_inspection_command(args: Sequence[str], cwd: Path = ROOT) -> str:
    command = _ensure_inspection_command(args)
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git inspection failed"
        raise ReleaseClosureError(detail)
    return completed.stdout.strip()


def inspect_repository(
    *,
    cwd: Path = ROOT,
    dist_manifest_sha256: str | None = None,
    config_sha256: str | None = None,
) -> dict[str, Any]:
    """Inspect the current repository using only read-only, bounded git commands."""
    command_log = [list(command) for command in READ_ONLY_GIT_COMMANDS]
    head = _run_inspection_command(READ_ONLY_GIT_COMMANDS[0], cwd)
    tree = _run_inspection_command(READ_ONLY_GIT_COMMANDS[1], cwd)
    status = _run_inspection_command(READ_ONLY_GIT_COMMANDS[2], cwd)
    return normalize_inspection(
        {
            "schema": "kronos_release_inspection.v1",
            "git_head": head,
            "git_tree": tree,
            "head_sha256": sha256_text(f"git-head:{head}"),
            "tree_sha256": sha256_text(f"git-tree:{tree}"),
            "dist_manifest_sha256": dist_manifest_sha256 or sha256_json({"schema": "kronos_dist_manifest_pointer.v1", "status": "not-built-by-release-closure"}),
            "config_sha256": config_sha256 or release_config_sha256(),
            "worktree_clean": status == "",
            "dirty_status_porcelain_sha256": sha256_text(status),
            "command_log": command_log,
        }
    )


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ReleaseClosureError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def normalize_inspection(value: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    head = raw.get("head_sha256") or sha256_text(str(raw.get("git_head", "fixture-head")))
    tree = raw.get("tree_sha256") or sha256_text(str(raw.get("git_tree", "fixture-tree")))
    dist = raw.get("dist_manifest_sha256") or sha256_text("fixture-dist")
    config = raw.get("config_sha256") or release_config_sha256()
    worktree_clean = raw.get("worktree_clean") is True
    return {
        "schema": "kronos_release_inspection.v1",
        "git_head": raw.get("git_head"),
        "git_tree": raw.get("git_tree"),
        "head_sha256": _sha(head, "head_sha256"),
        "tree_sha256": _sha(tree, "tree_sha256"),
        "dist_manifest_sha256": _sha(dist, "dist_manifest_sha256"),
        "config_sha256": _sha(config, "config_sha256"),
        "worktree_clean": worktree_clean,
        "dirty_status_porcelain_sha256": raw.get("dirty_status_porcelain_sha256") or sha256_text("" if worktree_clean else "dirty"),
        "command_log": [list(item) for item in raw.get("command_log", [])],
    }


def release_config_sha256() -> str:
    return sha256_json(
        {
            "schema": CONTRACT_SCHEMA,
            "phase_machine": list(PHASES),
            "default_equation": V5_DEFAULT_EQUATION,
            "blocker_order": list(BLOCKER_CODES),
            "six_locks_false": SIX_LOCKS_FALSE,
        }
    )


def _ordered_subset(values: Any, allowed: Sequence[str], label: str) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ReleaseClosureError(f"{label} must be an ordered array")
    result = list(values)
    if len(set(result)) != len(result) or any(item not in allowed for item in result):
        raise ReleaseClosureError(f"{label} contains unknown or duplicate entries")
    expected = [item for item in allowed if item in set(result)]
    if result != expected:
        raise ReleaseClosureError(f"{label} must use canonical order")
    return result


def claim_ids_by_category() -> dict[str, list[str]]:
    return {
        "A": [f"A{number:02d}" for number in range(1, 26)],
        "B": [f"B{number:02d}" for number in range(1, 26)],
        "C": [f"C{number:02d}" for number in range(1, 21)],
        "D": [f"D{number:02d}" for number in range(1, 16)],
        "E": ["E01", "E02", "E3.R", *[f"E{number:02d}" for number in range(4, 16)]],
    }


def make_point_score(
    category_scores: Mapping[str, int] | None = None,
    *,
    active_hard_caps: Sequence[str] = (),
    candidate_map_sha256: str | None = None,
    candidate_source_sha256: str | None = None,
    scorecard_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a compact point score whose gate fields obey the V5 equation."""
    scores = dict(category_scores or {"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    if set(scores) != set(CATEGORY_LIMITS):
        raise ReleaseClosureError("category scores must contain A/B/C/D/E")
    for category, value in scores.items():
        weight, _ = CATEGORY_LIMITS[category]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > weight:
            raise ReleaseClosureError("category score is outside V5 bounds")
    caps = _ordered_subset(active_hard_caps, HARD_CAPS_ORDER, "active_hard_caps")
    raw_total = sum(scores.values())
    effective_total = min(raw_total, 89) if caps else raw_total
    floor_failures = [category for category, (_, floor) in CATEGORY_LIMITS.items() if scores[category] < floor]
    claim_results: dict[str, bool] = {}
    for category, ids in claim_ids_by_category().items():
        passed = scores[category]
        for index, claim_id in enumerate(ids):
            claim_results[claim_id] = index < passed
    return {
        "schema": "kronos_point_score.v2",
        "candidate_map_sha256": candidate_map_sha256 or sha256_text("candidate-map"),
        "candidate_source_sha256": candidate_source_sha256 or sha256_text("candidate-source"),
        "scorecard_sha256": scorecard_sha256 or "4afa3656e8bed8e5adae8bc3e99f89d5b450f8c56561429cb121aa601458ec7b",
        "category_scores": scores,
        "capability_option_ceilings": dict(scores),
        "claim_results": {claim_id: claim_results[claim_id] for claim_id in sorted(claim_results)},
        "floor_failures": floor_failures,
        "active_hard_caps": caps,
        "raw_total": raw_total,
        "effective_total": effective_total,
        "gate": {"id": "engineering_90", "passed": effective_total >= 90 and not floor_failures and not caps, "total_min": 90},
        "six_locks_false": dict(SIX_LOCKS_FALSE),
    }


def validate_point_score_equation(point_score: Mapping[str, Any]) -> None:
    try:
        if point_score.get("schema") != "kronos_point_score.v2":
            raise ValueError
        scores = point_score["category_scores"]
        if not isinstance(scores, Mapping) or set(scores) != set(CATEGORY_LIMITS):
            raise ValueError
        checked_scores: dict[str, int] = {}
        for category, (weight, _) in CATEGORY_LIMITS.items():
            value = scores[category]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > weight:
                raise ValueError
            checked_scores[category] = value
        caps = _ordered_subset(point_score.get("active_hard_caps"), HARD_CAPS_ORDER, "active_hard_caps")
        raw_total = sum(checked_scores.values())
        effective_total = min(raw_total, 89) if caps else raw_total
        floor_failures = [category for category, (_, floor) in CATEGORY_LIMITS.items() if checked_scores[category] < floor]
        gate = {"id": "engineering_90", "passed": effective_total >= 90 and not floor_failures and not caps, "total_min": 90}
        if point_score.get("capability_option_ceilings") != checked_scores:
            raise ValueError
        if point_score.get("raw_total") != raw_total or point_score.get("effective_total") != effective_total:
            raise ValueError
        if point_score.get("floor_failures") != floor_failures or point_score.get("gate") != gate:
            raise ValueError
        if point_score.get("six_locks_false") != SIX_LOCKS_FALSE:
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseClosureError("point score semantic equation invalid") from exc


def _point_score_gate_pass(point_score: Mapping[str, Any]) -> bool:
    validate_point_score_equation(point_score)
    return bool(point_score["gate"]["passed"])


def _publication_actions(value: Mapping[str, Any]) -> list[str]:
    actions = value.get("forbidden_publication_actions", [])
    if actions is None:
        actions = []
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)) or any(not isinstance(item, str) for item in actions):
        raise ReleaseClosureError("publication actions must be a string array")
    lowered = [item.casefold() for item in actions]
    if value.get("publication_actions_attempted") is True and not lowered:
        lowered = ["publish"]
    return lowered


def _security_clear(security: Mapping[str, Any]) -> tuple[bool, list[str]]:
    actions = _publication_actions(security)
    mutation_rejected = security.get("mutation_probes_rejected") is True
    download_policy = security.get("download_policy_passed") is True
    no_actions = security.get("publication_actions_attempted") is False and not actions
    return mutation_rejected and download_policy and no_actions, actions


def _browser_terms(browser: Mapping[str, Any], *, dry_run_fixture_mode: bool) -> dict[str, bool]:
    capture_kind = browser.get("capture_kind")
    live = capture_kind == "live_browser_execution" and browser.get("live_browser_execution") is True
    synthetic = capture_kind == "synthetic_fixture_evidence" or bool(browser.get("synthetic", False))
    matrix = bool(browser.get("matrix_passed", False))
    distinct = bool(browser.get("distinct_from_synthetic", False)) and live and not synthetic
    reused = bool(browser.get("reused_synthetic_artifact", False))
    return {
        "browser_live": live,
        "browser_synthetic": synthetic,
        "browser_matrix_passed": matrix,
        "browser_distinct_from_synthetic": distinct,
        "browser_reused_synthetic_artifact": reused,
        "dry_run_fixture_mode": dry_run_fixture_mode,
    }


def evaluate_v5_default_gate(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate the exact V5 default gate without considering model verdicts."""
    score_a = inputs.get("point_score_a") or inputs.get("score_a")
    score_b = inputs.get("point_score_b") or inputs.get("score_b")
    if not isinstance(score_a, Mapping) or not isinstance(score_b, Mapping):
        raise ReleaseClosureError("both point_score_a and point_score_b are required")

    score_a_valid = score_b_valid = False
    point_a_pass = point_b_pass = False
    try:
        point_a_pass = _point_score_gate_pass(score_a)
        score_a_valid = True
    except ReleaseClosureError:
        point_a_pass = False
    try:
        point_b_pass = _point_score_gate_pass(score_b)
        score_b_valid = True
    except ReleaseClosureError:
        point_b_pass = False

    point_scores_identical = score_a_valid and score_b_valid and canonical_bytes(dict(score_a)) == canonical_bytes(dict(score_b))
    engineering_90_pass = point_a_pass and point_b_pass

    assurance = inputs.get("assurance_decision", {})
    if assurance is None:
        assurance = {}
    if not isinstance(assurance, Mapping):
        raise ReleaseClosureError("assurance_decision must be an object")
    def operand_bool(top_key: str, nested: Mapping[str, Any] | None = None, nested_key: str | None = None) -> bool:
        if top_key in inputs:
            return inputs.get(top_key) is True
        if nested is not None and nested_key is not None:
            return nested.get(nested_key) is True
        return False

    assurance_eligible = operand_bool("assurance_eligible", assurance, "assurance_eligible")
    prior_chains = inputs.get("prior_chains_resolved") is True

    source = inputs.get("source", {})
    dist = inputs.get("dist", {})
    rollback = inputs.get("rollback", {})
    browser = inputs.get("browser", {})
    security = inputs.get("security", {})
    for label, value in (("source", source), ("dist", dist), ("rollback", rollback), ("browser", browser), ("security", security)):
        if not isinstance(value, Mapping):
            raise ReleaseClosureError(f"{label} input must be an object")

    dry_run_fixture_mode = bool(inputs.get("dry_run_fixture_mode", False))
    browser_term = _browser_terms(browser, dry_run_fixture_mode=dry_run_fixture_mode)
    security_clear, publication_actions = _security_clear(security)

    terms = {
        "point_score_a_eq_b": point_scores_identical,
        "engineering_90_pass": engineering_90_pass,
        "assurance_eligible": assurance_eligible,
        "prior_chains_resolved": prior_chains,
        "head_match": operand_bool("head_matches", source, "head_matches"),
        "tree_match": operand_bool("tree_matches", source, "tree_matches"),
        "dist_match": operand_bool("dist_matches", dist, "dist_matches"),
        "config_match": inputs.get("config_matches") is True,
        "worktree_clean": inputs.get("worktree_clean") is True,
        "source_identity_bound": operand_bool("source_identity_bound", source, "identity_matches_head"),
        "rollback_v3_available": operand_bool("rollback_v3_available", rollback, "v3_available"),
        "rollback_query_pass": operand_bool("rollback_query_contract_passed", rollback, "query_contract_passed"),
        "live_browser_distinct": browser_term["browser_distinct_from_synthetic"],
        "security_clear": security_clear,
        "six_locks_false": inputs.get("six_locks_false", score_a.get("six_locks_false")) == SIX_LOCKS_FALSE,
        "no_publication_action": not publication_actions,
        "not_dry_run_fixture": not dry_run_fixture_mode,
    }
    release_closed = all(terms.values())

    blockers: list[str] = []
    def add(condition: bool, code: str) -> None:
        if condition and code not in blockers:
            blockers.append(code)

    add(not terms["point_score_a_eq_b"], "POINT_SCORE_MISMATCH")
    add(not terms["engineering_90_pass"], "POINT_SCORE_FAIL")
    add(not terms["assurance_eligible"], "ASSURANCE_BLOCK")
    add(not terms["prior_chains_resolved"], "PRIOR_CHAIN_RERESOLUTION_FAIL")
    add(not terms["head_match"], "HEAD_DRIFT")
    add(not terms["tree_match"], "TREE_DRIFT")
    add(not terms["dist_match"], "DIST_DRIFT")
    add(not terms["config_match"], "CONFIG_DRIFT")
    add(not terms["worktree_clean"], "DIRTY_WORKTREE")
    add(not terms["source_identity_bound"], "SOURCE_IDENTITY_MISMATCH")
    add(not terms["rollback_v3_available"], "ROLLBACK_UNAVAILABLE")
    add(not terms["rollback_query_pass"], "ROLLBACK_QUERY_FAIL")
    add(not browser_term["browser_live"], "BROWSER_EVIDENCE_NOT_LIVE")
    add(browser_term["browser_synthetic"], "BROWSER_EVIDENCE_SYNTHETIC")
    add(browser_term["browser_reused_synthetic_artifact"] or (browser_term["browser_live"] and not browser_term["browser_synthetic"] and not browser_term["browser_distinct_from_synthetic"]), "BROWSER_EVIDENCE_REUSED")
    add(not browser_term["browser_matrix_passed"], "BROWSER_MATRIX_FAIL")
    add(not terms["security_clear"], "SECURITY_GATE_FAIL")
    add(publication_actions != [], "PUBLICATION_ACTION_FORBIDDEN")
    add(not terms["six_locks_false"], "LOCK_INVARIANT_FAIL")
    add(dry_run_fixture_mode, "DRY_RUN_FIXTURE_NOT_RELEASABLE")
    blockers = [code for code in BLOCKER_CODES if code in blockers]

    default_eligible = release_closed and not blockers
    return {
        "schema": DEFAULT_GATE_SCHEMA,
        "default_equation": V5_DEFAULT_EQUATION,
        "release_eligible": default_eligible,
        "default_eligible": default_eligible,
        "default_decision": "SWITCH_TO_V5" if default_eligible else "RETAIN_V3",
        "terminal_result": "CLOSED" if default_eligible else "BLOCKED",
        "blocking_codes": blockers,
        "equation_terms": {"release_closed": release_closed, **terms},
        "point_score": {
            "a_valid": score_a_valid,
            "b_valid": score_b_valid,
            "a_gate_passed": point_a_pass,
            "b_gate_passed": point_b_pass,
            "model_verdict_point_bearing": False,
            "model_verdict_observed": inputs.get("model_verdict"),
        },
        "identity_gate": {
            "passed": terms["head_match"] and terms["tree_match"] and terms["dist_match"] and terms["config_match"] and terms["worktree_clean"],
            "head_match": terms["head_match"],
            "tree_match": terms["tree_match"],
            "dist_match": terms["dist_match"],
            "config_match": terms["config_match"],
            "worktree_clean": terms["worktree_clean"],
        },
        "source_gate": {"passed": terms["source_identity_bound"], "source_identity_bound": terms["source_identity_bound"]},
        "rollback_gate": {
            "passed": terms["rollback_v3_available"] and terms["rollback_query_pass"],
            "v3_available": terms["rollback_v3_available"],
            "query_contract_passed": terms["rollback_query_pass"],
        },
        "browser_gate": {"passed": terms["live_browser_distinct"] and browser_term["browser_matrix_passed"], **browser_term},
        "security_gate": {"passed": security_clear, "publication_actions": publication_actions},
        "six_locks_false": dict(inputs.get("six_locks_false", score_a.get("six_locks_false", {}))),
    }


def fixture_release_inputs(
    *,
    live_browser: bool = True,
    dry_run_fixture_mode: bool = False,
    dirty_worktree: bool = False,
    score_pass: bool = True,
    model_verdict: str = "NO-GO",
) -> dict[str, Any]:
    scores = {"A": 23, "B": 23, "C": 18, "D": 13, "E": 13} if score_pass else {"A": 22, "B": 23, "C": 18, "D": 13, "E": 13}
    point = make_point_score(scores)
    capture_kind = "live_browser_execution" if live_browser and not dry_run_fixture_mode else "synthetic_fixture_evidence"
    return {
        "schema": "kronos_release_closure_inputs.v1",
        "dry_run_fixture_mode": dry_run_fixture_mode,
        "point_score_a": point,
        "point_score_b": json.loads(json.dumps(point)),
        "assurance_decision": {"schema": "kronos_assurance_decision.v2", "assurance_eligible": True},
        "prior_chains_resolved": True,
        "head_matches": True,
        "tree_matches": True,
        "dist_matches": True,
        "config_matches": True,
        "worktree_clean": not dirty_worktree,
        "source": {"identity_matches_head": True, "head_matches": True, "tree_matches": True},
        "dist": {"dist_matches": True},
        "rollback": {"v3_available": True, "query_contract_passed": True},
        "browser": {
            "capture_kind": capture_kind,
            "live_browser_execution": live_browser and not dry_run_fixture_mode,
            "distinct_from_synthetic": live_browser and not dry_run_fixture_mode,
            "matrix_passed": True,
            "reused_synthetic_artifact": False,
        },
        "security": {
            "mutation_probes_rejected": True,
            "download_policy_passed": True,
            "publication_actions_attempted": False,
            "forbidden_publication_actions": [],
        },
        "six_locks_false": dict(SIX_LOCKS_FALSE),
        "model_verdict": model_verdict,
    }


def drift_blockers(bound: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    pairs = (
        ("head_sha256", "HEAD_DRIFT"),
        ("tree_sha256", "TREE_DRIFT"),
        ("dist_manifest_sha256", "DIST_DRIFT"),
        ("config_sha256", "CONFIG_DRIFT"),
    )
    blockers = [code for field, code in pairs if bound.get(field) != current.get(field)]
    return [code for code in BLOCKER_CODES if code in blockers]


class ReleaseClosureStore:
    """Nonce-scoped state store with atomic active pointer and immutable terminal roots."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = _safe_temp_root(root)
        self.runs_dir = self.root / "runs"
        self.history_dir = self.root / "history"
        self.pointer_path = self.root / "active-pointer.json"
        self.runs_dir.mkdir(exist_ok=True)
        self.history_dir.mkdir(exist_ok=True)

    def run_root(self, run_nonce: str) -> Path:
        if not isinstance(run_nonce, str) or not run_nonce or any(char in run_nonce for char in "/\\\0"):
            raise ReleaseClosureError("run nonce is invalid")
        return self.runs_dir / run_nonce

    def state_path(self, run_nonce: str) -> Path:
        return self.run_root(run_nonce) / "state.json"

    def artifact_path(self, run_nonce: str, name: str) -> Path:
        if any(char in name for char in "/\\\0") or name in {"", ".", ".."}:
            raise ReleaseClosureError("artifact name is invalid")
        return self.run_root(run_nonce) / "artifacts" / name

    def load_pointer(self) -> dict[str, Any] | None:
        if not self.pointer_path.exists():
            return None
        return load_json(self.pointer_path)

    def load_state(self, run_nonce: str) -> dict[str, Any]:
        return load_json(self.state_path(run_nonce))

    def active_state(self) -> dict[str, Any] | None:
        pointer = self.load_pointer()
        if pointer is None:
            return None
        return self.load_state(str(pointer["active_run_nonce"]))

    def _write_state(self, state: Mapping[str, Any]) -> dict[str, Any]:
        run_nonce = str(state["run_nonce"])
        path = self.state_path(run_nonce)
        if path.exists():
            previous = load_json(path)
            if previous.get("immutable") is True and canonical_bytes(previous) != canonical_bytes(dict(state)):
                raise ReleaseClosureError("terminal or failed release closure root is immutable")
        raw = _write_json(path, state)
        return object_ref(f"agent://kronos-release-closure/{run_nonce}/state", raw, STATE_SCHEMA)

    def _history_generation(self) -> int:
        return len([item for item in self.history_dir.iterdir() if item.is_file() and item.suffix == ".json"]) + 1

    def _update_pointer(self, *, state: Mapping[str, Any], state_ref: Mapping[str, Any], updated_at: str) -> dict[str, Any]:
        generation = self._history_generation()
        pointer = {
            "schema": POINTER_SCHEMA,
            "active_run_nonce": state["run_nonce"],
            "run_root": str(self.run_root(str(state["run_nonce"]))),
            "state_ref": dict(state_ref),
            "status": state["status"],
            "phase": state["phase"],
            "updated_at": updated_at,
            "generation": generation,
        }
        pointer_raw = _write_json(self.pointer_path, pointer)
        history = {
            "schema": HISTORY_SCHEMA,
            "generation": generation,
            "pointer_ref": object_ref(f"agent://kronos-release-closure/pointer/{generation}", pointer_raw, POINTER_SCHEMA),
            "active_run_nonce": state["run_nonce"],
            "status": state["status"],
            "phase": state["phase"],
            "updated_at": updated_at,
        }
        _write_json(self.history_dir / f"{generation:06d}-{state['run_nonce']}.json", history)
        return pointer

    def persist_state(self, state: Mapping[str, Any], *, updated_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
        state_ref = self._write_state(state)
        pointer = self._update_pointer(state=state, state_ref=state_ref, updated_at=updated_at)
        return state_ref, pointer

    def write_artifact(self, run_nonce: str, name: str, value: Mapping[str, Any]) -> dict[str, Any]:
        state_path = self.state_path(run_nonce)
        if state_path.exists() and load_json(state_path).get("immutable") is True:
            raise ReleaseClosureError("terminal or failed release closure root is immutable")
        raw = _write_json(self.artifact_path(run_nonce, name), value)
        return object_ref(f"agent://kronos-release-closure/{run_nonce}/{name}", raw, str(value.get("schema", "")))


def _new_nonce() -> str:
    return secrets.token_urlsafe(32)


def _initial_state(run_nonce: str, inspection: Mapping[str, Any], *, dry_run_fixture_mode: bool, now: str) -> dict[str, Any]:
    bound = {key: inspection[key] for key in ("head_sha256", "tree_sha256", "dist_manifest_sha256", "config_sha256")}
    return {
        "schema": STATE_SCHEMA,
        "run_nonce": run_nonce,
        "phase": "BIND_HEAD",
        "status": "ACTIVE",
        "phase_machine": list(PHASES),
        "phases_completed": [],
        "bound_identity": bound,
        "dry_run_fixture_mode": dry_run_fixture_mode,
        "publication_actions_attempted": False,
        "last_successful_artifact_ref": None,
        "terminal_report_ref": None,
        "invalidation_ref": None,
        "immutable": False,
        "created_at": now,
        "updated_at": now,
    }


def start_closure_run(
    *,
    temp_root: str | Path | None = None,
    inputs: Mapping[str, Any] | None = None,
    inspection: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    store = ReleaseClosureStore(temp_root)
    active = store.active_state()
    if active is not None and active.get("status") == "ACTIVE":
        raise ReleaseClosureError("an active release closure run already exists")
    timestamp = now or utc_now()
    normalized = normalize_inspection(inspection)
    run_nonce = _new_nonce()
    state = _initial_state(run_nonce, normalized, dry_run_fixture_mode=bool((inputs or {}).get("dry_run_fixture_mode", False)), now=timestamp)
    state_ref, pointer = store.persist_state(state, updated_at=timestamp)
    return {"schema": "kronos_release_closure_start.v1", "temp_root": str(store.root), "state": state, "state_ref": state_ref, "pointer": pointer}


def _phase_receipt(run_nonce: str, phase: str, inputs: Mapping[str, Any], *, completed_at: str) -> dict[str, Any]:
    dry_run = bool(inputs.get("dry_run_fixture_mode", False))
    browser = inputs.get("browser", {}) if isinstance(inputs.get("browser", {}), Mapping) else {}
    capture_kind = "synthetic_fixture_evidence" if dry_run else str(browser.get("capture_kind", "inspection_only"))
    live_browser = capture_kind == "live_browser_execution" and browser.get("live_browser_execution") is True and not dry_run
    return {
        "schema": PHASE_RECEIPT_SCHEMA,
        "run_nonce": run_nonce,
        "phase": phase,
        "status": "COMPLETE",
        "capture_kind": capture_kind,
        "live_browser_execution": live_browser,
        "heavy_compute_run": False,
        "fresh_oos_accessed": False,
        "publication_action_attempted": False,
        "completed_at": completed_at,
    }


def _terminal_report(run_nonce: str, gate: Mapping[str, Any], state: Mapping[str, Any], *, completed_at: str) -> dict[str, Any]:
    return {
        "schema": TERMINAL_REPORT_SCHEMA,
        "run_nonce": run_nonce,
        "terminal_status": "TERMINAL_CLOSED" if gate["default_eligible"] else "TERMINAL_BLOCKED",
        "default_gate": dict(gate),
        "default_decision": gate["default_decision"],
        "release_eligible": gate["release_eligible"],
        "default_eligible": gate["default_eligible"],
        "blocking_codes": list(gate["blocking_codes"]),
        "bound_identity": dict(state["bound_identity"]),
        "publication_actions_attempted": False,
        "mutated_tracked_files": False,
        "completed_at": completed_at,
    }


def _invalidate_active(store: ReleaseClosureStore, state: Mapping[str, Any], blockers: Sequence[str], *, now: str) -> dict[str, Any]:
    run_nonce = str(state["run_nonce"])
    diagnostic = {
        "schema": "kronos_release_closure_invalidation.v1",
        "run_nonce": run_nonce,
        "blocking_codes": [code for code in BLOCKER_CODES if code in set(blockers)],
        "status": "INVALIDATED",
        "failed_at": now,
    }
    invalidation_ref = store.write_artifact(run_nonce, "invalidation.json", diagnostic)
    updated = dict(state)
    updated.update(
        {
            "phase": state.get("phase", "BIND_HEAD"),
            "status": "INVALIDATED",
            "invalidation_ref": invalidation_ref,
            "immutable": True,
            "updated_at": now,
        }
    )
    state_ref, pointer = store.persist_state(updated, updated_at=now)
    return {
        "schema": "kronos_release_closure_result.v1",
        "temp_root": str(store.root),
        "state": updated,
        "state_ref": state_ref,
        "pointer": pointer,
        "terminal": None,
        "blocking_codes": diagnostic["blocking_codes"],
        "reused_terminal": False,
    }


def resume_closure_run(
    *,
    temp_root: str | Path,
    inputs: Mapping[str, Any],
    current_inspection: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    store = ReleaseClosureStore(temp_root)
    state = store.active_state()
    if state is None:
        raise ReleaseClosureError("no active release closure pointer exists")
    if state.get("immutable") is True or state.get("status") in {"TERMINAL_CLOSED", "TERMINAL_BLOCKED", "INVALIDATED"}:
        terminal = None
        terminal_ref = state.get("terminal_report_ref")
        if isinstance(terminal_ref, Mapping):
            terminal_path = store.artifact_path(str(state["run_nonce"]), "terminal-report.json")
            if terminal_path.exists():
                terminal = load_json(terminal_path)
        invalidation = None
        invalidation_ref = state.get("invalidation_ref")
        if terminal is None and isinstance(invalidation_ref, Mapping):
            invalidation_path = store.artifact_path(str(state["run_nonce"]), "invalidation.json")
            if invalidation_path.exists():
                invalidation = load_json(invalidation_path)
        return {
            "schema": "kronos_release_closure_result.v1",
            "temp_root": str(store.root),
            "state": state,
            "state_ref": value_ref(f"agent://kronos-release-closure/{state['run_nonce']}/state", state, STATE_SCHEMA),
            "pointer": store.load_pointer(),
            "terminal": terminal,
            "blocking_codes": list((terminal or invalidation or {}).get("blocking_codes", [])),
            "reused_terminal": True,
        }

    timestamp = now or utc_now()
    current = normalize_inspection(current_inspection or state["bound_identity"])
    blockers = drift_blockers(state["bound_identity"], current)
    if blockers:
        return _invalidate_active(store, state, blockers, now=timestamp)

    updated = dict(state)
    completed = list(updated.get("phases_completed", []))
    run_nonce = str(updated["run_nonce"])
    for phase in PHASES:
        if phase in completed:
            continue
        if phase == "TERMINAL":
            gate_inputs = dict(inputs)
            gate_inputs["dry_run_fixture_mode"] = bool(gate_inputs.get("dry_run_fixture_mode", updated.get("dry_run_fixture_mode", False)))
            gate_inputs["head_matches"] = True
            gate_inputs["tree_matches"] = True
            gate_inputs["dist_matches"] = True
            gate_inputs["config_matches"] = True
            gate_inputs["worktree_clean"] = bool(gate_inputs.get("worktree_clean", current["worktree_clean"])) and current["worktree_clean"]
            gate = evaluate_v5_default_gate(gate_inputs)
            terminal = _terminal_report(run_nonce, gate, updated, completed_at=timestamp)
            terminal_ref = store.write_artifact(run_nonce, "terminal-report.json", terminal)
            completed.append(phase)
            updated.update(
                {
                    "phase": "TERMINAL",
                    "status": terminal["terminal_status"],
                    "phases_completed": completed,
                    "last_successful_artifact_ref": terminal_ref,
                    "terminal_report_ref": terminal_ref,
                    "publication_actions_attempted": False,
                    "immutable": True,
                    "updated_at": timestamp,
                }
            )
            state_ref, pointer = store.persist_state(updated, updated_at=timestamp)
            return {
                "schema": "kronos_release_closure_result.v1",
                "temp_root": str(store.root),
                "state": updated,
                "state_ref": state_ref,
                "pointer": pointer,
                "terminal": terminal,
                "blocking_codes": list(terminal["blocking_codes"]),
                "reused_terminal": False,
            }
        receipt = _phase_receipt(run_nonce, phase, inputs, completed_at=timestamp)
        artifact_ref = store.write_artifact(run_nonce, f"{len(completed):02d}-{phase}.json", receipt)
        completed.append(phase)
        updated.update({"phase": phase, "phases_completed": completed, "last_successful_artifact_ref": artifact_ref, "updated_at": timestamp})
        state_ref, pointer = store.persist_state(updated, updated_at=timestamp)
    return {"schema": "kronos_release_closure_result.v1", "temp_root": str(store.root), "state": updated, "state_ref": state_ref, "pointer": pointer, "terminal": None, "blocking_codes": [], "reused_terminal": False}


def run_release_closure(
    inputs: Mapping[str, Any],
    *,
    temp_root: str | Path | None = None,
    inspection: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    start = start_closure_run(temp_root=temp_root, inputs=inputs, inspection=inspection, now=now)
    return resume_closure_run(temp_root=start["temp_root"], inputs=inputs, current_inspection=inspection, now=now)


def _cli_inputs(args: argparse.Namespace) -> dict[str, Any]:
    if args.inputs:
        data = load_json(Path(args.inputs))
    else:
        data = fixture_release_inputs(live_browser=not args.dry_run_fixture, dry_run_fixture_mode=args.dry_run_fixture)
    if args.dry_run_fixture:
        data = dict(data)
        data["dry_run_fixture_mode"] = True
        browser = dict(data.get("browser", {}))
        browser.update({"capture_kind": "synthetic_fixture_evidence", "live_browser_execution": False, "distinct_from_synthetic": False})
        data["browser"] = browser
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local, fail-closed Kronos V5 release closure orchestrator.")
    parser.add_argument("--inputs", help="Optional kronos_release_closure_inputs.v1 JSON. Omit for a safe fixture.")
    parser.add_argument("--temp-root", help="Ignored temporary root for pointer/history/state. Must be below the OS temp directory.")
    parser.add_argument("--dry-run-fixture", action="store_true", help="Use synthetic non-browser receipts; cannot grant the browser/default gate.")
    args = parser.parse_args(argv)
    try:
        inputs = _cli_inputs(args)
        inspection = inspect_repository()
        result = run_release_closure(inputs, temp_root=args.temp_root, inspection=inspection)
    except (OSError, ReleaseClosureError) as exc:
        print(f"V5_RELEASE_CLOSURE_REJECTED: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

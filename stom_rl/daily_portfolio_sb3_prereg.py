"""Synthetic preregistration freeze mechanics for the daily Portfolio SB3 protocol.

This module binds a preregistration draft to the immutable protocol foundation and
local schema/code bytes.  It only validates preregistration mechanics: no PPO
training, SB3 learn call, fresh OOS read, model build, result claim, or broker
operation is performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Final, Mapping, Sequence

import stom_rl.daily_portfolio_sb3_protocol as protocol


PREREG_SCHEMA: Final = "kronos_daily_sb3_prereg.v1"
PREREG_SCHEMA_ID: Final = "https://kronos.local/schemas/kronos_daily_sb3_prereg.v1.schema.json"
PREREG_STATEMENT_SCHEMA: Final = "kronos_daily_sb3_prereg.v1.statement"
RECEIPT_SCHEMA: Final = "kronos_daily_sb3_prereg_test_receipt.v1"
FREEZE_SCHEMA: Final = "kronos_daily_sb3_prereg_freeze.v1"
DRAFT_STATE: Final = "DRAFT"
FROZEN_STATE: Final = "FROZEN"
FROZEN_AT: Final = "2026-07-15T00:00:00Z"
BOUND_AT: Final = "2026-07-15T00:00:00Z"
COMMAND_MANIFEST_PATH: Final = "docs/kronos_dashboard_v5_runner_command_manifest_v1.json"
IDENTITY_STATEMENT_ALGORITHM: Final = "SHA256_RFC8785_PREREG_STATEMENT_V1"
IDENTITY_FREEZE_ALGORITHM: Final = "SHA256_RFC8785_PREREG_FREEZE_V1"
REQUIRED_RECEIPT_COMPONENTS: Final = ("protocol", "runner", "evaluator")
COMPUTE_LOCK_NAMES: Final = (
    "full_ppo_training_allowed",
    "sb3_learn_allowed",
    "fresh_oos_access_allowed",
)
PROMOTION_LOCK_NAMES: Final = (
    "model_build_allowed",
    "promotion_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
)
_RECEIPT_BODY_KEYS: Final = (
    "schema",
    "component",
    "status",
    "session_id",
    "protocol_sha256",
    "scope",
    "command",
    "command_manifest_sha256",
    "approved_command_id",
    "approved_argv",
    "forbidden_argv_tokens",
    "forbidden_token_policy",
    "not_run_synthetic_receipt",
    "synthetic_only",
    "heavy_compute_run",
    "fresh_oos_accessed",
    "full_ppo_status",
    "fresh_oos_status",
)
_RECEIPT_KEYS: Final = frozenset((*_RECEIPT_BODY_KEYS, "receipt_sha256"))
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_UTC_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_REPO_ROOT: Final = Path(__file__).resolve().parents[1]


class DailySb3PreregError(ValueError):
    """Raised when preregistration draft/freeze validation fails closed."""


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785/JCS bytes for preregistration identity material."""

    return protocol.canonical_bytes(value)


def sha256_hex(value: bytes | Any) -> str:
    """Return lower-case SHA-256 over bytes or RFC 8785 canonical JSON."""

    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _repo(repo_root: str | Path | None) -> Path:
    return _REPO_ROOT if repo_root is None else Path(repo_root)


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise DailySb3PreregError(f"{label} is not a canonical lower-case SHA-256 digest")
    return value


def _require_keys(value: Mapping[str, Any], keys: set[str] | frozenset[str], label: str) -> None:
    if set(value) != set(keys):
        raise DailySb3PreregError(f"{label} has an invalid shape")


def _file_ref(repo_root: Path, relative_path: str, role: str) -> dict[str, Any]:
    root = repo_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise DailySb3PreregError(f"{relative_path} escapes the repository root") from exc
    raw = path.read_bytes()
    return {"path": relative_path, "role": role, "sha256": sha256_hex(raw), "byte_length": len(raw)}


def _load_command_manifest(repo_root: Path) -> tuple[Mapping[str, Any], dict[str, Any]]:
    ref = _file_ref(repo_root, COMMAND_MANIFEST_PATH, "runner_command_manifest")
    parsed = json.loads((repo_root / COMMAND_MANIFEST_PATH).read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise DailySb3PreregError("command manifest root is not an object")
    protocol.validate_command_manifest(parsed)
    return parsed, ref


def _require_utc(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise DailySb3PreregError(f"{label} is not a UTC second timestamp")
    return value


def _validate_chronology(statement: Mapping[str, Any], freeze: Mapping[str, Any] | None = None) -> None:
    created_at = _require_utc(statement.get("created_at"), "statement created_at")
    bound_at = _require_utc(statement.get("bound_at"), "statement bound_at")
    protocol_binding = statement.get("protocol_binding")
    if not isinstance(protocol_binding, Mapping):
        raise DailySb3PreregError("protocol binding is missing")
    protocol_created_at = _require_utc(protocol_binding.get("protocol_created_at"), "protocol created_at")
    if created_at > bound_at:
        raise DailySb3PreregError("preregistration created_at must not be after bound_at")
    if protocol_created_at > bound_at:
        raise DailySb3PreregError("protocol binding cannot predate the bound protocol")
    if freeze is not None:
        frozen_at = _require_utc(freeze.get("frozen_at"), "freeze frozen_at")
        if bound_at > frozen_at:
            raise DailySb3PreregError("freeze cannot predate the bound preregistration")


def _session_basis(statement: Mapping[str, Any]) -> dict[str, Any]:
    folds = []
    for fold in statement["calendar"]["folds"]:
        folds.append(
            {
                "fold_id": fold["fold_id"],
                "fit_label_max_session": fold["fit_label_max_session"],
                "train_sessions": fold["train_sessions"],
                "purge_embargo_sessions": fold["purge_embargo_sessions"],
                "validation_sessions": fold["validation_sessions"],
            }
        )
    return {
        "schema": "kronos_daily_sb3_prereg_session_lists.v1",
        "available_sessions": statement["calendar"]["available_sessions"],
        "folds": folds,
    }


def _historical_basis(statement: Mapping[str, Any]) -> dict[str, Any]:
    historical = statement["calendar"]["historical_secondary_only_window"]
    return {
        "schema": "kronos_daily_sb3_prereg_historical_lists.v1",
        "window_id": historical["window_id"],
        "usage": historical["usage"],
        "sessions": historical["sessions"],
        "pre_access_purge_embargo_sessions": historical["pre_access_purge_embargo_sessions"],
        "fresh_oos_access_allowed": historical["fresh_oos_access_allowed"],
        "fresh_oos_consumed": historical["fresh_oos_consumed"],
        "model_go_source": historical["model_go_source"],
    }


def _device_policy(statement: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "kronos_daily_sb3_prereg_device_policy.v1",
        "device_requested": statement["ppo_config"]["device_requested"],
        "runtime_device_used": "NOT_RUN",
        "device_claim_status": "NOT_RUN",
        "cuda_required": False,
        "heavy_compute_allowed": False,
        "sb3_learn_allowed": False,
    }


def _synthetic_session_id(protocol_sha256: str, available_session_list_sha256: str) -> str:
    basis = {
        "schema": "kronos_daily_sb3_prereg_synthetic_session_basis.v1",
        "protocol_sha256": protocol_sha256,
        "available_session_list_sha256": available_session_list_sha256,
    }
    return f"kdp1-prereg-session-{sha256_hex(basis)[:24]}"


def _expected_statement(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = _repo(repo_root)
    built_protocol = protocol.build_protocol()
    protocol.validate_protocol(built_protocol)
    protocol_statement = built_protocol["statement"]
    protocol_identity = built_protocol["identity"]

    schema_refs = [
        _file_ref(root, "docs/schemas/kronos_daily_sb3_protocol.v1.schema.json", "protocol_json_schema"),
        _file_ref(root, "docs/schemas/kronos_daily_sb3_prereg.v1.schema.json", "prereg_json_schema"),
    ]
    code_refs = [
        _file_ref(root, "stom_rl/daily_portfolio_sb3_protocol.py", "protocol_authority_code"),
        _file_ref(root, "stom_rl/daily_portfolio_sb3_prereg.py", "prereg_validator_code"),
    ]
    command_manifest, command_manifest_ref = _load_command_manifest(root)
    session_basis = _session_basis(protocol_statement)
    historical_basis = _historical_basis(protocol_statement)
    device_policy = _device_policy(protocol_statement)
    bound_hashes = {
        "protocol_sha256": protocol_identity["protocol_sha256"],
        "canonical_protocol_json_sha256": sha256_hex(canonical_bytes(built_protocol)),
        "protocol_schema_sha256": schema_refs[0]["sha256"],
        "prereg_schema_sha256": schema_refs[1]["sha256"],
        "protocol_code_sha256": code_refs[0]["sha256"],
        "prereg_code_sha256": code_refs[1]["sha256"],
        "command_manifest_sha256": command_manifest_ref["sha256"],
        "dependency_list_sha256": sha256_hex(protocol_statement["dependencies"]),
        "device_policy_sha256": sha256_hex(device_policy),
        "available_session_list_sha256": sha256_hex(protocol_statement["calendar"]["available_sessions"]),
        "fold_session_lists_sha256": sha256_hex(session_basis),
        "historical_session_list_sha256": sha256_hex(historical_basis),
        "ppo_config_sha256": sha256_hex(protocol_statement["ppo_config"]),
        "matrix_cells_sha256": sha256_hex(built_protocol["matrix"]["cells"]),
        "pass_receipt_commands_sha256": sha256_hex(command_manifest["pass_receipt_commands"]),
    }
    session_id = _synthetic_session_id(protocol_identity["protocol_sha256"], bound_hashes["available_session_list_sha256"])
    compute_locks = {name: False for name in COMPUTE_LOCK_NAMES}
    promotion_locks = {name: False for name in PROMOTION_LOCK_NAMES}

    return {
        "schema": PREREG_STATEMENT_SCHEMA,
        "created_at": "2026-07-14T00:00:00Z",
        "bound_at": BOUND_AT,
        "label": "Kronos daily Portfolio SB3 PPO V5 preregistration mechanics",
        "research_label": "portfolio RL research preregistration",
        "claim_boundary": {
            "result_claim_status": "NOT_RUN",
            "profitability_claim_status": "NOT_RUN",
            "go_claim_status": "NOT_RUN",
            "no_result_profit_or_go_claims": True,
        },
        "protocol_binding": {
            "protocol_schema": protocol.PROTOCOL_SCHEMA,
            "protocol_schema_id": protocol.PROTOCOL_SCHEMA_ID,
            "protocol_version": protocol.PROTOCOL_VERSION,
            "protocol_created_at": protocol_statement["created_at"],
            "protocol_uid": protocol_identity["protocol_uid"],
            "protocol_sha256": protocol_identity["protocol_sha256"],
            "identity_algorithm": protocol.IDENTITY_ALGORITHM,
            "cell_identity_algorithm": protocol.CELL_IDENTITY_ALGORITHM,
        },
        "file_bindings": {"schemas": schema_refs, "code": code_refs},
        "command_manifest_binding": {
            "schema": "kronos_daily_sb3_prereg_command_manifest_binding.v1",
            "path": command_manifest_ref["path"],
            "sha256": command_manifest_ref["sha256"],
            "byte_length": command_manifest_ref["byte_length"],
            "command_id_policy": command_manifest["command_id_policy"],
            "forbidden_token_policy": command_manifest["forbidden_token_policy"],
            "forbidden_argv_tokens": list(command_manifest["forbidden_argv_tokens"]),
            "pass_receipt_commands_sha256": bound_hashes["pass_receipt_commands_sha256"],
            "pass_receipt_commands": list(command_manifest["pass_receipt_commands"]),
        },
        "bound_hashes": bound_hashes,
        "dependency_binding": {
            "dependency_count": len(protocol_statement["dependencies"]),
            "dependency_list_sha256": bound_hashes["dependency_list_sha256"],
            "dependencies": list(protocol_statement["dependencies"]),
        },
        "session_binding": {
            "schema": "kronos_daily_sb3_prereg_session_binding.v1",
            "synthetic_session_id": session_id,
            "available_session_count": protocol_statement["calendar"]["available_session_count"],
            "available_session_list_sha256": bound_hashes["available_session_list_sha256"],
            "fold_session_lists_sha256": bound_hashes["fold_session_lists_sha256"],
            "fold_order": list(protocol_statement["fold_order"]),
        },
        "historical_binding": {
            "schema": "kronos_daily_sb3_prereg_historical_binding.v1",
            "window_id": protocol_statement["calendar"]["historical_secondary_only_window"]["window_id"],
            "status": "NOT_RUN",
            "fresh_oos_access_allowed": False,
            "fresh_oos_consumed": False,
            "historical_session_list_sha256": bound_hashes["historical_session_list_sha256"],
        },
        "matrix_binding": {
            "cell_count": built_protocol["matrix"]["cell_count"],
            "order": built_protocol["matrix"]["order"],
            "first_cell_uid": built_protocol["matrix"]["cells"][0]["cell_uid"],
            "last_cell_uid": built_protocol["matrix"]["cells"][-1]["cell_uid"],
            "matrix_cells_sha256": bound_hashes["matrix_cells_sha256"],
        },
        "ppo_binding": {
            "algorithm": protocol_statement["ppo_config"]["algorithm"],
            "stable_baselines_family": protocol_statement["ppo_config"]["stable_baselines_family"],
            "full_ppo_status": "NOT_RUN",
            "ppo_config_sha256": bound_hashes["ppo_config_sha256"],
        },
        "device_binding": {
            "policy": device_policy,
            "device_policy_sha256": bound_hashes["device_policy_sha256"],
        },
        "no_heavy_compute_state": {
            "schema": "kronos_daily_sb3_prereg_no_heavy_compute_state.v1",
            "approval_state": "APPROVED_NO_HEAVY_COMPUTE_SYNTHETIC_ONLY",
            "compute_mode": protocol.SYNTHETIC_COMPUTE_MODE,
            "no_heavy_compute_marker": protocol.NO_HEAVY_COMPUTE_MARKER,
            "full_ppo_status": "NOT_RUN",
            "fresh_oos_status": "NOT_RUN",
            "compute_locks": compute_locks,
            "promotion_locks": promotion_locks,
        },
        "receipt_gate": {
            "schema": "kronos_daily_sb3_prereg_receipt_gate.v1",
            "required_receipt_components": list(REQUIRED_RECEIPT_COMPONENTS),
            "required_status": "PASS",
            "required_session_id": session_id,
            "required_protocol_sha256": protocol_identity["protocol_sha256"],
            "required_command_manifest_sha256": command_manifest_ref["sha256"],
            "receipt_command_policy": "EXACT_APPROVED_COMMAND_ID_AND_ARGV_ONLY",
            "required_forbidden_token_policy": command_manifest["forbidden_token_policy"],
            "not_run_synthetic_receipt_allowed": True,
            "exact_receipt_order_required": True,
            "heavy_compute_run_allowed": False,
            "fresh_oos_access_allowed": False,
            "missing_receipt_policy": "REJECT",
            "missing_session_policy": "REJECT",
        },
    }


def _identity(statement: Mapping[str, Any], *, frozen_sha256: str | None) -> dict[str, Any]:
    statement_sha256 = sha256_hex(statement)
    return {
        "prereg_uid": f"kdp1-prereg-{statement_sha256[:32]}",
        "statement_sha256": statement_sha256,
        "frozen_sha256": frozen_sha256,
        "identity_algorithm": IDENTITY_FREEZE_ALGORITHM if frozen_sha256 is not None else IDENTITY_STATEMENT_ALGORITHM,
    }


def build_prereg_draft(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Build the deterministic DRAFT preregistration without training or data reads."""

    statement = _expected_statement(repo_root)
    _validate_chronology(statement)
    return {"schema": PREREG_SCHEMA, "state": DRAFT_STATE, "identity": _identity(statement, frozen_sha256=None), "statement": statement}


def _receipt_body(component: str, statement: Mapping[str, Any]) -> dict[str, Any]:
    gate = statement["receipt_gate"]
    command_binding = statement["command_manifest_binding"]
    receipt_commands = {
        command["component"]: command
        for command in command_binding["pass_receipt_commands"]
    }
    approved_command = receipt_commands[component]
    return {
        "schema": RECEIPT_SCHEMA,
        "component": component,
        "status": "PASS",
        "session_id": gate["required_session_id"],
        "protocol_sha256": gate["required_protocol_sha256"],
        "scope": f"{component}_synthetic_mechanics",
        "command": "NOT_RUN_SYNTHETIC_RECEIPT",
        "command_manifest_sha256": gate["required_command_manifest_sha256"],
        "approved_command_id": approved_command["command_id"],
        "approved_argv": list(approved_command["argv"]),
        "forbidden_argv_tokens": list(command_binding["forbidden_argv_tokens"]),
        "forbidden_token_policy": command_binding["forbidden_token_policy"],
        "not_run_synthetic_receipt": True,
        "synthetic_only": True,
        "heavy_compute_run": False,
        "fresh_oos_accessed": False,
        "full_ppo_status": "NOT_RUN",
        "fresh_oos_status": "NOT_RUN",
    }


def _attach_receipt_hash(body: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(body)
    receipt["receipt_sha256"] = sha256_hex({key: receipt[key] for key in _RECEIPT_BODY_KEYS})
    return receipt


def build_synthetic_test_receipts(draft: Mapping[str, Any] | None = None, *, repo_root: str | Path | None = None) -> tuple[dict[str, Any], ...]:
    """Return deterministic PASS receipts for synthetic mechanics tests only."""

    value = build_prereg_draft(repo_root=repo_root) if draft is None else draft
    validate_prereg(value, repo_root=repo_root)
    if value["state"] != DRAFT_STATE:
        raise DailySb3PreregError("synthetic receipts must be built from a DRAFT preregistration")
    return tuple(_attach_receipt_hash(_receipt_body(component, value["statement"])) for component in REQUIRED_RECEIPT_COMPONENTS)


def _validate_receipts(receipts: Sequence[Mapping[str, Any]], statement: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(receipts, (str, bytes)) or not isinstance(receipts, Sequence):
        raise DailySb3PreregError("freeze receipts must be a sequence")
    if len(receipts) != len(REQUIRED_RECEIPT_COMPONENTS):
        raise DailySb3PreregError("freeze requires protocol, runner, and evaluator receipts")

    gate = statement["receipt_gate"]
    command_binding = statement["command_manifest_binding"]
    approved_by_component = {
        command["component"]: command
        for command in command_binding["pass_receipt_commands"]
    }
    if tuple(approved_by_component) != REQUIRED_RECEIPT_COMPONENTS:
        raise DailySb3PreregError("PASS receipt command components drifted")
    normalized: list[dict[str, Any]] = []
    for index, (receipt, expected_component) in enumerate(zip(receipts, REQUIRED_RECEIPT_COMPONENTS, strict=True)):
        if not isinstance(receipt, Mapping):
            raise DailySb3PreregError(f"receipt {index} is not an object")
        _require_keys(receipt, _RECEIPT_KEYS, f"receipt {index}")
        if receipt["schema"] != RECEIPT_SCHEMA:
            raise DailySb3PreregError(f"receipt {index} schema mismatch")
        if receipt["component"] != expected_component:
            raise DailySb3PreregError("receipt order must be protocol/runner/evaluator")
        if receipt["status"] != gate["required_status"]:
            raise DailySb3PreregError(f"{expected_component} receipt did not PASS")
        if receipt["session_id"] != gate["required_session_id"]:
            raise DailySb3PreregError(f"{expected_component} receipt is not bound to the synthetic session")
        if receipt["protocol_sha256"] != gate["required_protocol_sha256"]:
            raise DailySb3PreregError(f"{expected_component} receipt protocol hash drifted")
        if receipt["command_manifest_sha256"] != gate["required_command_manifest_sha256"] or receipt["command_manifest_sha256"] != command_binding["sha256"]:
            raise DailySb3PreregError(f"{expected_component} receipt command manifest hash drifted")
        if not isinstance(receipt["scope"], str) or not receipt["scope"]:
            raise DailySb3PreregError(f"{expected_component} receipt scope is missing")
        approved_command = approved_by_component[expected_component]
        if receipt["approved_command_id"] != approved_command["command_id"] or receipt["approved_argv"] != approved_command["argv"]:
            raise DailySb3PreregError(f"{expected_component} receipt is not bound to the exact approved command id/argv")
        if receipt["forbidden_token_policy"] != gate["required_forbidden_token_policy"] or receipt["forbidden_token_policy"] != command_binding["forbidden_token_policy"]:
            raise DailySb3PreregError(f"{expected_component} receipt forbidden-token policy drifted")
        if receipt["forbidden_argv_tokens"] != command_binding["forbidden_argv_tokens"]:
            raise DailySb3PreregError(f"{expected_component} receipt forbidden-token list drifted")
        if receipt["command"] != "NOT_RUN_SYNTHETIC_RECEIPT" or receipt["not_run_synthetic_receipt"] is not True:
            raise DailySb3PreregError(f"{expected_component} receipt command must be an explicit NOT_RUN_SYNTHETIC_RECEIPT")
        if gate["not_run_synthetic_receipt_allowed"] is not True or approved_command["not_run_synthetic_receipt"] is not True:
            raise DailySb3PreregError(f"{expected_component} NOT_RUN synthetic receipt is not allowed by the closed command manifest")
        if receipt["synthetic_only"] is not True:
            raise DailySb3PreregError(f"{expected_component} receipt is not synthetic-only")
        if receipt["heavy_compute_run"] is not False:
            raise DailySb3PreregError(f"{expected_component} receipt attempted heavy compute")
        if receipt["fresh_oos_accessed"] is not False:
            raise DailySb3PreregError(f"{expected_component} receipt accessed fresh OOS")
        if receipt["full_ppo_status"] != "NOT_RUN" or receipt["fresh_oos_status"] != "NOT_RUN":
            raise DailySb3PreregError(f"{expected_component} receipt reports a forbidden run")
        flattened = " ".join(receipt["approved_argv"]).lower()
        for token in receipt["forbidden_argv_tokens"]:
            if token.lower() in flattened:
                raise DailySb3PreregError(f"{expected_component} receipt approved argv contains forbidden token {token}")
        receipt_hash = _require_sha(receipt["receipt_sha256"], f"{expected_component} receipt_sha256")
        body = {key: receipt[key] for key in _RECEIPT_BODY_KEYS}
        if sha256_hex(body) != receipt_hash:
            raise DailySb3PreregError(f"{expected_component} receipt hash drifted")
        normalized.append(dict(receipt))
    return normalized


def _freeze_metadata(receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": FREEZE_SCHEMA,
        "frozen_at": FROZEN_AT,
        "receipt_components": [receipt["component"] for receipt in receipts],
        "receipt_sha256s": [receipt["receipt_sha256"] for receipt in receipts],
        "receipt_count": len(receipts),
        "immutable": True,
        "no_heavy_compute_confirmed": True,
        "no_fresh_oos_access_confirmed": True,
    }


def _frozen_hash(statement: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]], freeze: Mapping[str, Any]) -> str:
    return sha256_hex({"state": FROZEN_STATE, "statement": statement, "freeze_receipts": list(receipts), "freeze": freeze})


def freeze_prereg(draft: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]], *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Freeze a DRAFT after exact PASS receipts prove synthetic no-OOS mechanics."""

    validate_prereg(draft, repo_root=repo_root)
    if draft["state"] != DRAFT_STATE:
        raise DailySb3PreregError("only a DRAFT preregistration can be frozen")
    normalized_receipts = _validate_receipts(receipts, draft["statement"])
    freeze = _freeze_metadata(normalized_receipts)
    _validate_chronology(draft["statement"], freeze)
    frozen_sha256 = _frozen_hash(draft["statement"], normalized_receipts, freeze)
    frozen = {
        "schema": PREREG_SCHEMA,
        "state": FROZEN_STATE,
        "identity": _identity(draft["statement"], frozen_sha256=frozen_sha256),
        "statement": draft["statement"],
        "freeze_receipts": normalized_receipts,
        "freeze": freeze,
    }
    validate_prereg(frozen, repo_root=repo_root)
    return frozen


def validate_prereg(value: Mapping[str, Any], *, repo_root: str | Path | None = None) -> None:
    """Validate a DRAFT or FROZEN preregistration against current bound authority."""

    if not isinstance(value, Mapping):
        raise DailySb3PreregError("preregistration must be an object")
    if value.get("schema") != PREREG_SCHEMA:
        raise DailySb3PreregError("preregistration schema mismatch")
    state = value.get("state")
    if state not in {DRAFT_STATE, FROZEN_STATE}:
        raise DailySb3PreregError("preregistration state mismatch")
    expected_top = {"schema", "state", "identity", "statement"} if state == DRAFT_STATE else {"schema", "state", "identity", "statement", "freeze_receipts", "freeze"}
    _require_keys(value, expected_top, "preregistration")

    expected_statement = _expected_statement(repo_root)
    if value["statement"] != expected_statement:
        raise DailySb3PreregError("preregistration statement drifted from bound protocol/schema/code state")
    _validate_chronology(expected_statement)

    identity = value["identity"]
    if not isinstance(identity, Mapping):
        raise DailySb3PreregError("preregistration identity must be an object")
    _require_keys(identity, {"prereg_uid", "statement_sha256", "frozen_sha256", "identity_algorithm"}, "preregistration identity")
    expected_statement_identity = _identity(expected_statement, frozen_sha256=None)
    if identity["prereg_uid"] != expected_statement_identity["prereg_uid"] or identity["statement_sha256"] != expected_statement_identity["statement_sha256"]:
        raise DailySb3PreregError("preregistration statement identity drifted")

    if state == DRAFT_STATE:
        if identity != expected_statement_identity:
            raise DailySb3PreregError("draft preregistration identity drifted")
        return

    if identity["identity_algorithm"] != IDENTITY_FREEZE_ALGORITHM:
        raise DailySb3PreregError("frozen preregistration identity algorithm mismatch")
    frozen_sha256 = _require_sha(identity["frozen_sha256"], "frozen_sha256")
    receipts = _validate_receipts(value["freeze_receipts"], expected_statement)
    expected_freeze = _freeze_metadata(receipts)
    _validate_chronology(expected_statement, expected_freeze)
    if value["freeze"] != expected_freeze:
        raise DailySb3PreregError("freeze metadata drifted")
    if _frozen_hash(expected_statement, receipts, expected_freeze) != frozen_sha256:
        raise DailySb3PreregError("frozen preregistration immutable hash drifted")


def _parse_json(path: Path) -> Mapping[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise DailySb3PreregError("JSON root is not an object")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit or validate the Kronos daily SB3 preregistration without training.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit-draft", action="store_true", help="emit the deterministic DRAFT preregistration")
    group.add_argument("--emit-frozen", action="store_true", help="emit the deterministic synthetic FROZEN preregistration")
    group.add_argument("--validate", type=Path, help="validate an existing preregistration JSON file")
    args = parser.parse_args(argv)

    if args.emit_draft:
        payload = build_prereg_draft()
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.emit_frozen:
        draft = build_prereg_draft()
        payload = freeze_prereg(draft, build_synthetic_test_receipts(draft))
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    validate_prereg(_parse_json(args.validate))
    return 0


__all__ = [
    "COMPUTE_LOCK_NAMES",
    "DRAFT_STATE",
    "FROZEN_STATE",
    "PROMOTION_LOCK_NAMES",
    "PREREG_SCHEMA",
    "REQUIRED_RECEIPT_COMPONENTS",
    "DailySb3PreregError",
    "build_prereg_draft",
    "build_synthetic_test_receipts",
    "canonical_bytes",
    "freeze_prereg",
    "sha256_hex",
    "validate_prereg",
]


if __name__ == "__main__":
    raise SystemExit(main())

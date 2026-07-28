#!/usr/bin/env python3
"""Fail-closed verifier for externally captured V5 live-browser matrix receipts.

The verifier reads an already captured receipt plus local evidence files. It never
launches a browser, server, or build; it only validates bytes and normalizes a
small verification result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

import rfc8785

BASE_TABS = ("mission-control", "forecast", "stom", "daily-ohlcv", "daily-rl-guide", "rl", "live-training", "system-health", "artifacts", "history", "settings", "docs")
THEMES = ("light", "dark")
WIDTHS = (375, 768, 1280)
LIFECYCLE = ("ADVANCING", "STALLED", "RESUMED", "RESTARTED_NON_EXACT", "STOPPED", "FAILED", "COMPLETED", "CONFLICT_BLOCKED", "NOT_RUN")
GOVERNANCE = ("D0_BLOCKED", "D1_BLOCKED", "FRESH_OOS_SEALED", "FRESH_OOS_NOT_AVAILABLE", "MISSING_CELL")
ASYNC_SECURITY = ("ISOLATED_TIMEOUT_RETRY", "LATE_LIST_DETAIL_RACE", "ALLOWED_DOWNLOAD", "DENIED_DOWNLOAD")
KEYBOARD_TABS = ("mission-control", "rl", "daily-ohlcv", "live-training")
CATEGORY_COUNTS = {"base": 72, "lifecycle": 18, "governance": 10, "async_security": 8, "keyboard": 4}
FALSE_LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
TIMING_BUDGETS_MS = {"first_critical_cold_ms": 3000, "first_critical_warm_ms": 1500, "full_hydration_cold_ms": 10000, "full_hydration_warm_ms": 6000, "api_cold_ms": 5000, "api_warm_ms": 2000, "isolated_timeout_ms": 20500, "palette_ms": 100, "filter_1000_ms": 150}
PROHIBITED_CLAIMS = ("OOS_CONSUMED", "LIVE_READY", "PROFIT_READY", "GO_READY")
SYNTHETIC_LABELS = ("synthetic_fixture_evidence", "synthetic-browser-v5", "synthetic fixture", "synthetic browser", "placeholder")
REQUIRED_ROUTE_MARKERS = ("kronos-v5-dashboard", "route:/v5")
MIN_REAL_WIDTH = 320
MIN_REAL_HEIGHT = 240

RECEIPT_FIELDS = {"schema", "capture_kind", "live_browser_execution", "nonce", "captured_at", "browser", "browser_sha256", "fixture_ref", "source_ref", "dist_manifest_ref", "fixture_sha256", "source_sha256", "dist_manifest_sha256", "scenario_ids", "scenario_count", "scenarios", "timing_budgets_ms", "security_checks", "false_locks"}
BROWSER_FIELDS = {"name", "version", "user_agent", "executable_sha256"}
OBJECT_REF_REQUIRED = {"relative_path", "sha256", "byte_length", "media_type"}
OBJECT_REF_OPTIONAL = {"schema_id", "captured_at"}
SCENARIO_FIELDS = {"scenario_id", "sequence", "category", "status", "browser_version", "url", "viewport", "route_markers", "dom_ref", "screenshot_ref", "console_errors", "page_errors", "network_errors", "a11y_errors", "overflow", "focus", "keyboard", "chart_table_semantics", "timing", "checks"}
VIEWPORT_FIELDS = {"width", "height", "device_scale_factor", "is_mobile"}
DOM_FIELDS = {"schema", "capture_kind", "live_browser_execution", "scenario_id", "sequence", "url", "root", "route_markers", "landmarks"}
TIMING_FIELDS = {"first_critical_ms", "full_hydration_ms", "api_ms", "isolated_timeout_ms", "palette_ms", "filter_1000_ms"}
CHECK_FIELDS = {"v3_rollback", "denied_download", "retry_visible"}
UTC_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("receipt is outside the RFC8785 profile") from exc


def require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        fail(f"{name} must be a lowercase sha256")
    return value


def require_exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{label} fields are not canonical")
    return value


def require_empty_list(value: Any, label: str) -> None:
    if value != []:
        fail(f"{label} must be empty")


def reject_prohibited_claims(value: Any, label: str) -> None:
    if isinstance(value, str):
        upper = value.upper()
        for claim in PROHIBITED_CLAIMS:
            if claim in upper:
                fail(f"{label} contains prohibited claim {claim}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_prohibited_claims(item, f"{label}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_prohibited_claims(key, f"{label}.{key} key")
            reject_prohibited_claims(item, f"{label}.{key}")


def reject_synthetic_labels(value: Any, label: str) -> None:
    if isinstance(value, str):
        lowered = value.lower()
        for token in SYNTHETIC_LABELS:
            if token in lowered:
                fail(f"{label} contains synthetic or placeholder label {token}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_synthetic_labels(item, f"{label}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_synthetic_labels(key, f"{label}.{key} key")
            reject_synthetic_labels(item, f"{label}.{key}")


def build_matrix() -> tuple[list[str], dict[str, dict[str, Any]]]:
    ids: list[str] = []
    metadata: dict[str, dict[str, Any]] = {}

    def push(scenario_id: str, meta: dict[str, Any]) -> None:
        ids.append(scenario_id)
        metadata[scenario_id] = meta

    for tab in BASE_TABS:
        for theme in THEMES:
            for width in WIDTHS:
                push(f"S-BASE-{tab}-{theme}-{width}", {"category": "base", "tab": tab, "theme": theme, "width": width})
    for state in LIFECYCLE:
        for theme in THEMES:
            push(f"S-LIFE-{state}-{theme}", {"category": "lifecycle", "state": state, "theme": theme})
    for state in GOVERNANCE:
        for theme in THEMES:
            push(f"S-GOV-{state}-{theme}", {"category": "governance", "state": state, "theme": theme})
    for state in ASYNC_SECURITY:
        for theme in THEMES:
            push(f"S-ASYNC-{state}-{theme}", {"category": "async_security", "state": state, "theme": theme})
    for tab in KEYBOARD_TABS:
        push(f"S-KBD-{tab}", {"category": "keyboard", "tab": tab, "width": 375})
    return ids, metadata


def load_canonical_matrix() -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    ids, metadata = build_matrix()
    matrix_path = Path(__file__).resolve().parents[1] / "docs" / "kronos_dashboard_v5_browser_matrix_v1.json"
    raw = json.loads(matrix_path.read_text(encoding="utf-8"))
    if raw.get("schema") != "kronos_dashboard_v5_browser_matrix.v1" or raw.get("scenario_count") != 112:
        fail("canonical browser matrix metadata is invalid")
    if raw.get("base_tabs") != list(BASE_TABS) or raw.get("themes") != list(THEMES) or raw.get("widths") != list(WIDTHS):
        fail("canonical browser matrix dimensions drifted")
    if raw.get("scenarios") != ids or len(set(ids)) != 112:
        fail("canonical browser matrix scenarios drifted")
    return tuple(ids), metadata


SCENARIO_IDS, SCENARIO_METADATA = load_canonical_matrix()


def contained(root: Path, rel: Any) -> Path:
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        fail("ObjectRef relative_path is required")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts) or re.match(r"^[A-Za-z]:", rel):
        fail("ObjectRef must use a safe relative_path")
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"ObjectRef escapes evidence root: {rel}") from exc
    return target


def object_ref(root: Path, raw: Any, media_type: str | None, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not OBJECT_REF_REQUIRED <= set(raw) or set(raw) - OBJECT_REF_REQUIRED - OBJECT_REF_OPTIONAL:
        fail(f"{label} ObjectRef is malformed")
    claimed_media = raw.get("media_type")
    if not isinstance(claimed_media, str) or not claimed_media:
        fail(f"{label} media_type is invalid")
    if media_type is not None and claimed_media != media_type:
        fail(f"{label} media_type must be {media_type}")
    path = contained(root, raw["relative_path"])
    data = path.read_bytes()
    actual = {"relative_path": raw["relative_path"], "sha256": sha256_bytes(data), "byte_length": len(data), "media_type": claimed_media}
    for key, expected in actual.items():
        if raw.get(key) != expected:
            fail(f"{label} ObjectRef {raw.get('relative_path')} has incorrect {key}")
    return actual


def png_info(data: bytes, label: str) -> dict[str, int | bool]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        fail(f"{label} is not PNG")
    pos = 8
    width = height = bit_depth = color_type = 0
    idat: list[bytes] = []
    saw_iend = False
    while pos < len(data):
        if pos + 12 > len(data):
            fail(f"{label} has a truncated PNG chunk")
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        start = pos + 8
        end = start + length
        crc_end = end + 4
        if crc_end > len(data):
            fail(f"{label} has a truncated PNG chunk")
        expected_crc = struct.unpack(">I", data[end:crc_end])[0]
        actual_crc = zlib.crc32(kind + data[start:end]) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            fail(f"{label} has an invalid PNG chunk crc")
        chunk = data[start:end]
        pos = crc_end
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            saw_iend = True
            break
    if not saw_iend or not width or not height or bit_depth != 8 or color_type not in (2, 6) or not idat:
        fail(f"{label} must be an 8-bit RGB/RGBA PNG")
    if width < MIN_REAL_WIDTH or height < MIN_REAL_HEIGHT or (width, height) == (2, 1):
        fail(f"{label} dimensions are a placeholder, not a real browser viewport")
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise ValueError(f"{label} has invalid compressed image data") from exc
    offset = 0
    previous = bytearray(stride)
    distinct: set[bytes] = set()
    for _ in range(height):
        if offset + 1 + stride > len(raw):
            fail(f"{label} has truncated image data")
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            up_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 255
            elif filter_type == 2:
                row[index] = (row[index] + up) & 255
            elif filter_type == 3:
                row[index] = (row[index] + ((left + up) // 2)) & 255
            elif filter_type == 4:
                predictor = left + up - up_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - up_left)
                row[index] = (row[index] + (left if pa <= pb and pa <= pc else up if pb <= pc else up_left)) & 255
            elif filter_type != 0:
                fail(f"{label} has invalid PNG filter")
        for index in range(0, stride, channels):
            distinct.add(bytes(row[index:index + channels]))
            if len(distinct) > 1:
                return {"width": width, "height": height, "non_uniform": True}
        previous = row
    fail(f"{label} is uniform")


def validate_browser(raw: Any) -> dict[str, str]:
    browser = require_exact_fields(raw, BROWSER_FIELDS, "browser")
    for key in ("name", "version", "user_agent"):
        if not isinstance(browser[key], str) or not browser[key].strip():
            fail(f"browser.{key} must be a non-empty string")
    if not any(char.isdigit() for char in browser["version"]):
        fail("browser.version must be a concrete version")
    require_sha(browser["executable_sha256"], "browser.executable_sha256")
    return dict(browser)


def validate_route_markers(value: Any, scenario_id: str, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) < 3 or len(set(value)) != len(value):
        fail(f"{label} route markers are incomplete")
    if any(not isinstance(item, str) or not item for item in value):
        fail(f"{label} route markers are malformed")
    for marker in REQUIRED_ROUTE_MARKERS:
        if marker not in value:
            fail(f"{label} route marker {marker} is missing")
    if not any(scenario_id in item for item in value):
        fail(f"{label} route markers are not scenario-bound")
    return list(value)


def validate_viewport(value: Any, expected_width: int | None, label: str) -> dict[str, Any]:
    viewport = require_exact_fields(value, VIEWPORT_FIELDS, label)
    width = viewport["width"]
    height = viewport["height"]
    scale = viewport["device_scale_factor"]
    if not isinstance(width, int) or not isinstance(height, int) or width < MIN_REAL_WIDTH or height < MIN_REAL_HEIGHT:
        fail(f"{label} dimensions are not real browser dimensions")
    if expected_width is not None and width != expected_width:
        fail(f"{label} width does not match the frozen scenario")
    if not isinstance(scale, int) or scale < 1 or scale > 4 or not isinstance(viewport["is_mobile"], bool):
        fail(f"{label} device metadata is invalid")
    return dict(viewport)


def validate_dom_artifact(raw: Any, scenario_id: str, sequence: int, url: str) -> dict[str, Any]:
    reject_prohibited_claims(raw, f"{scenario_id}: DOM artifact")
    reject_synthetic_labels(raw, f"{scenario_id}: DOM artifact")
    dom = require_exact_fields(raw, DOM_FIELDS, f"{scenario_id}: DOM artifact")
    if dom["schema"] != "kronos_v5_browser_dom.v1" or dom["capture_kind"] != "live_browser_execution" or dom["live_browser_execution"] is not True:
        fail(f"{scenario_id}: DOM artifact identity is invalid")
    if dom["scenario_id"] != scenario_id or dom["sequence"] != sequence or dom["url"] != url:
        fail(f"{scenario_id}: DOM artifact binding is invalid")
    if not isinstance(dom["root"], str) or not dom["root"]:
        fail(f"{scenario_id}: DOM root marker is missing")
    if not isinstance(dom["landmarks"], list) or not dom["landmarks"] or any(not isinstance(item, str) or not item for item in dom["landmarks"]):
        fail(f"{scenario_id}: DOM landmarks are invalid")
    validate_route_markers(dom["route_markers"], scenario_id, f"{scenario_id}: DOM")
    return dict(dom)


def validate_timing(value: Any, scenario_id: str) -> dict[str, int]:
    timing = require_exact_fields(value, TIMING_FIELDS, f"{scenario_id}: timing")
    for key, item in timing.items():
        if not isinstance(item, int) or item < 0:
            fail(f"{scenario_id}: {key} must be a non-negative integer")
    limits = {
        "first_critical_ms": TIMING_BUDGETS_MS["first_critical_cold_ms"],
        "full_hydration_ms": TIMING_BUDGETS_MS["full_hydration_cold_ms"],
        "api_ms": TIMING_BUDGETS_MS["api_cold_ms"],
        "isolated_timeout_ms": TIMING_BUDGETS_MS["isolated_timeout_ms"],
        "palette_ms": TIMING_BUDGETS_MS["palette_ms"],
        "filter_1000_ms": TIMING_BUDGETS_MS["filter_1000_ms"],
    }
    over = [key for key, limit in limits.items() if timing[key] > limit]
    if over:
        fail(f"{scenario_id}: timing budget exceeded for {', '.join(over)}")
    return dict(timing)


def validate_checks(value: Any, scenario_id: str) -> dict[str, bool]:
    checks = require_exact_fields(value, CHECK_FIELDS, f"{scenario_id}: checks")
    if any(not isinstance(item, bool) for item in checks.values()):
        fail(f"{scenario_id}: checks must be booleans")
    if "RESTARTED_NON_EXACT" in scenario_id and checks["v3_rollback"] is not True:
        fail(f"{scenario_id}: V3 rollback proof is missing")
    if "DENIED_DOWNLOAD" in scenario_id and checks["denied_download"] is not True:
        fail(f"{scenario_id}: denied download proof is missing")
    if "ISOLATED_TIMEOUT_RETRY" in scenario_id and checks["retry_visible"] is not True:
        fail(f"{scenario_id}: retry proof is missing")
    return dict(checks)


def validate_security_checks(value: Any) -> dict[str, bool]:
    checks = require_exact_fields(value, CHECK_FIELDS, "security_checks")
    if checks != {"v3_rollback": True, "denied_download": True, "retry_visible": True}:
        fail("receipt must include V3 rollback, denied download, and retry proofs")
    return dict(checks)


def validate_scenario(root: Path, row: Any, expected_id: str, sequence: int, browser: dict[str, str], seen_refs: set[str]) -> dict[str, Any]:
    scenario = require_exact_fields(row, SCENARIO_FIELDS, f"{expected_id}: scenario")
    meta = SCENARIO_METADATA[expected_id]
    if scenario["scenario_id"] != expected_id or scenario["sequence"] != sequence or scenario["category"] != meta["category"] or scenario["status"] != "passed":
        fail(f"{expected_id}: scenario identity is invalid")
    if scenario["browser_version"] != browser["version"]:
        fail(f"{expected_id}: browser version is not bound to the receipt browser")
    url = scenario["url"]
    if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")) or expected_id not in url:
        fail(f"{expected_id}: URL is not a scenario-bound browser URL")
    route_markers = validate_route_markers(scenario["route_markers"], expected_id, expected_id)
    expected_width = meta.get("width") if isinstance(meta.get("width"), int) else None
    viewport = validate_viewport(scenario["viewport"], expected_width, f"{expected_id}: viewport")

    screenshot_ref = object_ref(root, scenario["screenshot_ref"], "image/png", f"{expected_id}: screenshot")
    for value in (screenshot_ref["relative_path"], screenshot_ref["sha256"]):
        if value in seen_refs:
            fail(f"{expected_id}: duplicate screenshot evidence")
        seen_refs.add(value)
    png = png_info(contained(root, screenshot_ref["relative_path"]).read_bytes(), f"{expected_id}: screenshot")
    if png["width"] != viewport["width"] or png["height"] != viewport["height"]:
        fail(f"{expected_id}: screenshot dimensions do not match viewport")

    dom_ref = object_ref(root, scenario["dom_ref"], "application/json", f"{expected_id}: DOM")
    for value in (dom_ref["relative_path"], dom_ref["sha256"]):
        if value in seen_refs:
            fail(f"{expected_id}: duplicate DOM evidence")
        seen_refs.add(value)
    try:
        dom_json = json.loads(contained(root, dom_ref["relative_path"]).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{expected_id}: DOM artifact is not valid JSON") from exc
    dom = validate_dom_artifact(dom_json, expected_id, sequence, url)
    if dom["route_markers"] != route_markers:
        fail(f"{expected_id}: route markers are not consistently captured")

    for key in ("console_errors", "page_errors", "network_errors", "a11y_errors"):
        require_empty_list(scenario[key], f"{expected_id}: {key}")
    if scenario["overflow"] is not False or scenario["focus"] != "passed" or scenario["keyboard"] != "passed" or scenario["chart_table_semantics"] != "passed":
        fail(f"{expected_id}: semantic browser checks failed")

    return {
        "scenario_id": expected_id,
        "sequence": sequence,
        "category": meta["category"],
        "status": "passed",
        "viewport": viewport,
        "screenshot": {"width": png["width"], "height": png["height"], "non_uniform": True},
        "screenshot_ref": screenshot_ref,
        "dom_ref": dom_ref,
        "timing": validate_timing(scenario["timing"], expected_id),
        "checks": validate_checks(scenario["checks"], expected_id),
    }


def produce(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    root = root.resolve()
    reject_prohibited_claims(raw, "receipt")
    reject_synthetic_labels(raw, "receipt")
    receipt = require_exact_fields(raw, RECEIPT_FIELDS, "receipt")
    if receipt["schema"] != "kronos_v5_browser_receipt.v1" or receipt["capture_kind"] != "live_browser_execution" or receipt["live_browser_execution"] is not True:
        fail("receipt must be explicit live_browser_execution evidence")
    if not isinstance(receipt["captured_at"], str) or not UTC_SECOND.fullmatch(receipt["captured_at"]):
        fail("captured_at must be an RFC3339 UTC second")
    nonce = require_sha(receipt["nonce"], "nonce")
    browser = validate_browser(receipt["browser"])
    browser_sha256 = require_sha(receipt["browser_sha256"], "browser_sha256")
    if browser_sha256 != browser["executable_sha256"]:
        fail("browser_sha256 must match browser.executable_sha256")

    fixture_ref = object_ref(root, receipt["fixture_ref"], "application/json", "fixture_ref")
    source_ref = object_ref(root, receipt["source_ref"], None, "source_ref")
    dist_manifest_ref = object_ref(root, receipt["dist_manifest_ref"], "application/json", "dist_manifest_ref")
    if receipt["fixture_sha256"] != fixture_ref["sha256"] or receipt["source_sha256"] != source_ref["sha256"] or receipt["dist_manifest_sha256"] != dist_manifest_ref["sha256"]:
        fail("source, dist, and fixture hashes must match their object refs")
    if receipt["timing_budgets_ms"] != TIMING_BUDGETS_MS:
        fail("timing budget contract drifted")
    if receipt["false_locks"] != FALSE_LOCKS:
        fail("six false locks must all be false")
    security_checks = validate_security_checks(receipt["security_checks"])

    if receipt["scenario_count"] != len(SCENARIO_IDS) or receipt["scenario_ids"] != list(SCENARIO_IDS):
        fail("scenario matrix must be the ordered frozen 112 S-* IDs")
    scenarios_raw = receipt["scenarios"]
    if not isinstance(scenarios_raw, list) or len(scenarios_raw) != len(SCENARIO_IDS):
        fail("receipt scenarios are incomplete")
    seen_refs: set[str] = set()
    scenarios = [validate_scenario(root, row, expected_id, index + 1, browser, seen_refs) for index, (row, expected_id) in enumerate(zip(scenarios_raw, SCENARIO_IDS, strict=True))]
    counts = {key: sum(1 for item in scenarios if item["category"] == key) for key in CATEGORY_COUNTS}
    if counts != CATEGORY_COUNTS:
        fail("scenario category counts are not the frozen 72/18/10/8/4 matrix")

    result = {
        "schema": "kronos_v5_browser_matrix_verification.v1",
        "capture_kind": "live_browser_execution",
        "live_browser_execution": True,
        "nonce": nonce,
        "captured_at": receipt["captured_at"],
        "browser": browser,
        "browser_sha256": browser_sha256,
        "fixture_sha256": fixture_ref["sha256"],
        "source_sha256": source_ref["sha256"],
        "dist_manifest_sha256": dist_manifest_ref["sha256"],
        "scenario_ids": list(SCENARIO_IDS),
        "scenario_count": len(SCENARIO_IDS),
        "category_counts": counts,
        "timing_budgets_ms": TIMING_BUDGETS_MS,
        "security_checks": security_checks,
        "status": "passed",
        "false_locks": FALSE_LOCKS,
        "receipt_sha256": sha256_bytes(canonical(receipt)),
    }
    result["verification_sha256"] = sha256_bytes(canonical(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an externally captured V5 live-browser matrix receipt without launching a browser.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = produce(json.loads(Path(args.input).read_text(encoding="utf-8")), Path(args.evidence_root))
        Path(args.out).write_bytes(canonical(result) + b"\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"browser receipt failed closed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

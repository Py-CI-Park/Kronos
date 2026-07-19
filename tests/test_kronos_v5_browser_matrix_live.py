from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_dashboard_v5_browser_matrix.py"
SCHEMA = ROOT / "docs" / "schemas" / "kronos_v5_browser_receipt.v1.schema.json"
FIXTURE = ROOT / "tests" / "data" / "kronos_v5_browser_receipt_fixture.json"
MATRIX = ROOT / "docs" / "kronos_dashboard_v5_browser_matrix_v1.json"


def _module():
    spec = importlib.util.spec_from_file_location("verify_dashboard_v5_browser_matrix", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = _module()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json(root: Path, rel: str, value: dict) -> dict[str, object]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _json_bytes(value)
    path.write_bytes(data)
    return {"relative_path": rel, "sha256": _sha(data), "byte_length": len(data), "media_type": "application/json"}


def _ref(root: Path, rel: str, media_type: str) -> dict[str, object]:
    data = (root / rel).read_bytes()
    return {"relative_path": rel, "sha256": _sha(data), "byte_length": len(data), "media_type": media_type}


def _png(width: int, height: int, seed: int, *, uniform: bool = False) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    left = seed % 256
    right = left if uniform else (seed + 37) % 256
    raw = bytearray()
    for _ in range(height):
        raw.append(0)
        for x in range(width):
            value = left if x < max(1, width // 2) else right
            raw.extend([value, (value + 17) % 256, (value + 31) % 256])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def _metadata(scenario_id: str) -> tuple[str, int | None]:
    if scenario_id.startswith("S-BASE-"):
        return "base", int(scenario_id.rsplit("-", 1)[1])
    if scenario_id.startswith("S-LIFE-"):
        return "lifecycle", None
    if scenario_id.startswith("S-GOV-"):
        return "governance", None
    if scenario_id.startswith("S-ASYNC-"):
        return "async_security", None
    if scenario_id.startswith("S-KBD-"):
        return "keyboard", 375
    raise AssertionError(scenario_id)


def _materialize_receipt(tmp_path: Path) -> tuple[dict, Path]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    root = tmp_path / "evidence"
    root.mkdir(parents=True)
    fixture_ref = _write_json(root, "fixture/fixture.json", fixture["artifact_payloads"]["fixture"])
    source_ref = _write_json(root, "manifests/source.json", fixture["artifact_payloads"]["source"])
    dist_ref = _write_json(root, "manifests/dist.json", fixture["artifact_payloads"]["dist_manifest"])

    scenarios = []
    for sequence, scenario_id in enumerate(fixture["scenario_ids"], start=1):
        category, frozen_width = _metadata(scenario_id)
        width = frozen_width if frozen_width is not None else 1280
        height = fixture["viewport_heights"][str(width)]
        screenshot_rel = f"screens/{sequence:03d}.png"
        dom_rel = f"dom/{sequence:03d}.json"
        (root / screenshot_rel).parent.mkdir(parents=True, exist_ok=True)
        (root / screenshot_rel).write_bytes(_png(width, height, sequence))
        url = f"http://127.0.0.1:4173/v5?scenario_id={quote(scenario_id, safe='')}"
        route_markers = ["kronos-v5-dashboard", "route:/v5", f"scenario:{scenario_id}"]
        dom_ref = _write_json(root, dom_rel, {"schema": "kronos_v5_browser_dom.v1", "capture_kind": "live_browser_execution", "live_browser_execution": True, "scenario_id": scenario_id, "sequence": sequence, "url": url, "root": "#app", "route_markers": route_markers, "landmarks": ["navigation", "main"]})
        scenarios.append({
            "scenario_id": scenario_id,
            "sequence": sequence,
            "category": category,
            "status": "passed",
            "browser_version": fixture["browser"]["version"],
            "url": url,
            "viewport": {"width": width, "height": height, "device_scale_factor": 1, "is_mobile": width == 375},
            "route_markers": route_markers,
            "dom_ref": dom_ref,
            "screenshot_ref": _ref(root, screenshot_rel, "image/png"),
            "console_errors": [],
            "page_errors": [],
            "network_errors": [],
            "a11y_errors": [],
            "overflow": False,
            "focus": "passed",
            "keyboard": "passed",
            "chart_table_semantics": "passed",
            "timing": dict(fixture["row_timing_ms"]),
            "checks": {"v3_rollback": "RESTARTED_NON_EXACT" in scenario_id, "denied_download": "DENIED_DOWNLOAD" in scenario_id, "retry_visible": "ISOLATED_TIMEOUT_RETRY" in scenario_id},
        })
    receipt = {
        "schema": fixture["receipt_schema"],
        "capture_kind": fixture["capture_kind"],
        "live_browser_execution": fixture["live_browser_execution"],
        "nonce": fixture["nonce"],
        "captured_at": fixture["captured_at"],
        "browser": dict(fixture["browser"]),
        "browser_sha256": fixture["browser"]["executable_sha256"],
        "fixture_ref": fixture_ref,
        "source_ref": source_ref,
        "dist_manifest_ref": dist_ref,
        "fixture_sha256": fixture_ref["sha256"],
        "source_sha256": source_ref["sha256"],
        "dist_manifest_sha256": dist_ref["sha256"],
        "scenario_ids": fixture["scenario_ids"],
        "scenario_count": matrix["scenario_count"],
        "scenarios": scenarios,
        "timing_budgets_ms": dict(fixture["timing_budgets_ms"]),
        "security_checks": dict(fixture["security_checks"]),
        "false_locks": dict(fixture["false_locks"]),
    }
    return receipt, root


def _rebind_first_screenshot(receipt: dict, root: Path, image: bytes, width: int, height: int) -> None:
    rel = receipt["scenarios"][0]["screenshot_ref"]["relative_path"]
    (root / rel).write_bytes(image)
    receipt["scenarios"][0]["screenshot_ref"] = _ref(root, rel, "image/png")
    receipt["scenarios"][0]["viewport"]["width"] = width
    receipt["scenarios"][0]["viewport"]["height"] = height


def _update_dom(receipt: dict, root: Path, index: int, mutator) -> None:
    rel = receipt["scenarios"][index]["dom_ref"]["relative_path"]
    dom = json.loads((root / rel).read_text(encoding="utf-8"))
    mutator(dom)
    receipt["scenarios"][index]["dom_ref"] = _write_json(root, rel, dom)


def test_fixture_freezes_live_contract_and_112_matrix_categories() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert fixture["capture_kind"] == "live_browser_execution"
    assert fixture["live_browser_execution"] is True
    assert fixture["receipt_schema"] == "kronos_v5_browser_receipt.v1"
    assert fixture["matrix"] == {
        "scenario_source": "docs/kronos_dashboard_v5_browser_matrix_v1.json",
        "base": {"count": 72, "category": "base"},
        "lifecycle": {"count": 18, "category": "lifecycle"},
        "governance": {"count": 10, "category": "governance"},
        "async_security": {"count": 8, "category": "async_security"},
        "keyboard": {"count": 4, "category": "keyboard"},
        "count": 112,
    }
    assert matrix["scenario_count"] == 112
    assert len(matrix["scenarios"]) == len(set(matrix["scenarios"])) == 112
    assert fixture["scenario_ids"] == matrix["scenarios"]
    assert sum(section["count"] for key, section in fixture["matrix"].items() if key not in {"scenario_source", "count"}) == 112
    assert all(value is False for value in fixture["false_locks"].values())


def test_live_receipt_schema_and_verifier_accept_real_size_artifacts(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    receipt, root = _materialize_receipt(tmp_path)
    jsonschema.Draft202012Validator(schema).validate(receipt)

    result = verifier.produce(receipt, root)
    assert result["schema"] == "kronos_v5_browser_matrix_verification.v1"
    assert result["capture_kind"] == "live_browser_execution"
    assert result["live_browser_execution"] is True
    assert result["scenario_count"] == 112
    assert result["category_counts"] == {"base": 72, "lifecycle": 18, "governance": 10, "async_security": 8, "keyboard": 4}
    assert result["security_checks"] == {"v3_rollback": True, "denied_download": True, "retry_visible": True}
    assert result["fixture_sha256"] == receipt["fixture_sha256"]
    assert result["source_sha256"] == receipt["source_sha256"]
    assert result["dist_manifest_sha256"] == receipt["dist_manifest_sha256"]
    assert all(value is False for value in result["false_locks"].values())


@pytest.mark.parametrize("mutator", [
    lambda receipt, root: receipt.__setitem__("capture_kind", "synthetic_fixture_evidence"),
    lambda receipt, root: receipt.__setitem__("live_browser_execution", False),
    lambda receipt, root: receipt["scenarios"].pop(),
    lambda receipt, root: receipt["scenarios"][1].__setitem__("scenario_id", receipt["scenarios"][0]["scenario_id"]),
    lambda receipt, root: receipt["scenarios"][0].__setitem__("category", "lifecycle"),
    lambda receipt, root: receipt["browser"].__setitem__("version", "synthetic-browser-v5"),
    lambda receipt, root: _rebind_first_screenshot(receipt, root, _png(2, 1, 1), 2, 1),
    lambda receipt, root: _rebind_first_screenshot(receipt, root, _png(receipt["scenarios"][0]["viewport"]["width"], receipt["scenarios"][0]["viewport"]["height"], 1, uniform=True), receipt["scenarios"][0]["viewport"]["width"], receipt["scenarios"][0]["viewport"]["height"]),
    lambda receipt, root: receipt["scenarios"][1].__setitem__("screenshot_ref", copy.deepcopy(receipt["scenarios"][0]["screenshot_ref"])),
])
def test_live_verifier_rejects_synthetic_placeholders_duplicates_missing_and_mislabeled(tmp_path: Path, mutator) -> None:
    receipt, root = _materialize_receipt(tmp_path)
    mutator(receipt, root)
    with pytest.raises(ValueError):
        verifier.produce(receipt, root)


@pytest.mark.parametrize(("field", "value"), [
    ("console_errors", ["console error"]),
    ("page_errors", ["page error"]),
    ("network_errors", ["network error"]),
    ("a11y_errors", ["a11y error"]),
])
def test_live_verifier_rejects_any_browser_or_a11y_error(tmp_path: Path, field: str, value: list[str]) -> None:
    receipt, root = _materialize_receipt(tmp_path)
    receipt["scenarios"][0][field] = value
    with pytest.raises(ValueError):
        verifier.produce(receipt, root)


@pytest.mark.parametrize("mutator", [
    lambda receipt, root: receipt.__setitem__("source_sha256", "0" * 64),
    lambda receipt, root: receipt["timing_budgets_ms"].__setitem__("palette_ms", 101),
    lambda receipt, root: receipt["security_checks"].__setitem__("denied_download", False),
    lambda receipt, root: receipt["scenarios"][0]["timing"].__setitem__("palette_ms", 101),
    lambda receipt, root: _update_dom(receipt, root, 0, lambda dom: dom["route_markers"].remove("route:/v5")),
])
def test_live_verifier_rejects_hash_route_marker_timing_and_summary_tampers(tmp_path: Path, mutator) -> None:
    receipt, root = _materialize_receipt(tmp_path)
    mutator(receipt, root)
    with pytest.raises(ValueError):
        verifier.produce(receipt, root)


@pytest.mark.parametrize(("needle", "check"), [
    ("RESTARTED_NON_EXACT", "v3_rollback"),
    ("DENIED_DOWNLOAD", "denied_download"),
    ("ISOLATED_TIMEOUT_RETRY", "retry_visible"),
])
def test_live_verifier_rejects_missing_required_scenario_proofs(tmp_path: Path, needle: str, check: str) -> None:
    receipt, root = _materialize_receipt(tmp_path)
    index = next(i for i, row in enumerate(receipt["scenarios"]) if needle in row["scenario_id"])
    receipt["scenarios"][index]["checks"][check] = False
    with pytest.raises(ValueError):
        verifier.produce(receipt, root)

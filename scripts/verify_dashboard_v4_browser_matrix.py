"""Verify a GJC Chromium/Puppeteer browser-automation transcript for the G008
all-tab visual/accessibility/performance polish matrix.

Read-only, stdlib-only, no network and no browser dependency. Consumes a JSON
transcript (produced elsewhere by a real browser run) describing one scenario
per (tab, theme, width) tuple and independently re-verifies every claim the
transcript makes:

  * Exactly the 12 canonical App tab ids x 2 themes (light/dark) x 3 widths
    (375/768/1280) == 72 scenarios, each appearing exactly once, all "passed".
  * Every declared PNG artifact is decoded from scratch (PNG chunk framing +
    zlib inflate + per-scanline defilter, stdlib `zlib`/`struct`/`hashlib`
    only) and its SHA-256, byte size, pixel dimensions, and non-uniform
    (non-blank/non-placeholder) marker are independently recomputed and
    compared against the transcript's claims.
  * API requests recorded for the scenario are GET-only.
  * console/page/request failures are empty and layout overflow is zero.
  * WCAG A/AA violation counts are zero.
  * keyboard/focus/chart-semantic checks are "passed".
  * first-card/full-hydration/API/palette timings are present as finite,
    non-negative numbers (the performance cross-link G008PerformanceBudget
    consumes separately; this script only proves the fields exist and are
    sane numbers, it does not import or depend on that module's schema).

Fails closed: any duplicate tuple, missing tuple, unknown tab/theme/width,
non-GET request, non-empty failure list, nonzero overflow/a11y violation,
non-"passed" keyboard/focus/chart check, missing/non-finite timing, or a bad
artifact (missing file, hash mismatch, size mismatch, too-small/placeholder,
blank/uniform pixels, dimension mismatch, or a path that escapes the
artifacts root) causes verification to fail.

Writes a deterministic JSON report to --out and exits 0 iff every check
passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CANONICAL_TABS: Tuple[str, ...] = (
    "mission-control",
    "live-training",
    "forecast",
    "stom",
    "daily-ohlcv",
    "daily-rl-guide",
    "rl",
    "artifacts",
    "history",
    "system-health",
    "settings",
    "docs",
)
THEMES: Tuple[str, ...] = ("light", "dark")
WIDTHS: Tuple[int, ...] = (375, 768, 1280)
EXPECTED_SCENARIO_COUNT = len(CANONICAL_TABS) * len(THEMES) * len(WIDTHS)

REQUIRED_TIMING_KEYS: Tuple[str, ...] = ("first_card", "full_hydration", "api", "palette")

MIN_ARTIFACT_BYTES = 1024
MIN_ARTIFACT_HEIGHT = 50

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_CHANNELS_BY_COLOR_TYPE: Dict[int, int] = {0: 1, 2: 3, 4: 2, 6: 4}


class VerifyError(ValueError):
    """Raised for a single, reportable verification failure."""


# --------------------------------------------------------------------------
# PNG decode (stdlib only): chunk framing -> zlib inflate -> defilter.
# --------------------------------------------------------------------------


def _read_png_chunks(data: bytes) -> List[Tuple[str, bytes]]:
    if data[:8] != _PNG_SIGNATURE:
        raise VerifyError("not a PNG file (bad signature)")
    pos = 8
    n = len(data)
    chunks: List[Tuple[str, bytes]] = []
    while pos < n:
        if pos + 8 > n:
            raise VerifyError("truncated PNG chunk header")
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8].decode("ascii", "replace")
        pos += 8
        if pos + length + 4 > n:
            raise VerifyError("truncated PNG chunk data")
        cdata = data[pos : pos + length]
        pos += length + 4  # skip payload + CRC
        chunks.append((ctype, cdata))
        if ctype == "IEND":
            break
    return chunks


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter_line(ftype: int, line: bytearray, prev: bytearray, bpp: int) -> None:
    n = len(line)
    if ftype == 0:
        return
    if ftype == 1:  # Sub
        for i in range(n):
            a = line[i - bpp] if i >= bpp else 0
            line[i] = (line[i] + a) & 0xFF
    elif ftype == 2:  # Up
        for i in range(n):
            line[i] = (line[i] + prev[i]) & 0xFF
    elif ftype == 3:  # Average
        for i in range(n):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            line[i] = (line[i] + ((a + b) // 2)) & 0xFF
    elif ftype == 4:  # Paeth
        for i in range(n):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
    else:
        raise VerifyError(f"unsupported PNG scanline filter type {ftype}")


def decode_png(data: bytes) -> Tuple[int, int, int, bytes]:
    """Return (width, height, channels, raw_pixel_bytes) for a stdlib-decodable PNG."""
    chunks = _read_png_chunks(data)
    ihdr: Optional[bytes] = None
    idat = bytearray()
    for ctype, cdata in chunks:
        if ctype == "IHDR":
            ihdr = cdata
        elif ctype == "IDAT":
            idat.extend(cdata)
    if ihdr is None or len(ihdr) < 13:
        raise VerifyError("PNG missing IHDR chunk")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", ihdr[:13]
    )
    if width <= 0 or height <= 0:
        raise VerifyError("PNG has non-positive dimensions")
    if compression != 0 or filter_method != 0:
        raise VerifyError("unsupported PNG compression/filter method")
    if interlace != 0:
        raise VerifyError("interlaced PNG not supported")
    if bit_depth != 8:
        raise VerifyError(f"unsupported PNG bit depth {bit_depth}")
    if color_type not in _PNG_CHANNELS_BY_COLOR_TYPE:
        raise VerifyError(f"unsupported PNG color type {color_type}")
    if not idat:
        raise VerifyError("PNG has no IDAT data")
    channels = _PNG_CHANNELS_BY_COLOR_TYPE[color_type]
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise VerifyError(f"PNG IDAT inflate failed: {exc}") from exc
    stride = width * channels
    expected_len = (stride + 1) * height
    if len(raw) != expected_len:
        raise VerifyError("PNG raw scanline data length mismatch")
    prev = bytearray(stride)
    out = bytearray()
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        _unfilter_line(ftype, line, prev, channels)
        out.extend(line)
        prev = line
    return width, height, channels, bytes(out)


def pixels_are_non_uniform(pixel_bytes: bytes, channels: int) -> bool:
    if len(pixel_bytes) < channels:
        return False
    first = pixel_bytes[:channels]
    for i in range(0, len(pixel_bytes) - channels + 1, channels):
        if pixel_bytes[i : i + channels] != first:
            return True
    return False


# --------------------------------------------------------------------------
# Path safety
# --------------------------------------------------------------------------


def safe_resolve_artifact_path(artifacts_root: Path, rel_path: Any) -> Path:
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise VerifyError("artifact.path is missing or blank")
    if rel_path.startswith(("/", "\\")):
        raise VerifyError(f"artifact.path is absolute: {rel_path!r}")
    if len(rel_path) >= 2 and rel_path[1] == ":":
        raise VerifyError(f"artifact.path has a drive prefix: {rel_path!r}")
    root_resolved = artifacts_root.resolve()
    candidate = (artifacts_root / rel_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise VerifyError(f"artifact.path escapes artifacts root: {rel_path!r}") from exc
    return candidate


# --------------------------------------------------------------------------
# Scenario validation
# --------------------------------------------------------------------------


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and value not in (
        float("inf"),
        float("-inf"),
    )


def _check_list_empty(scenario: Dict[str, Any], key: str, errors: List[str]) -> None:
    value = scenario.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return
    if value:
        errors.append(f"{key} must be empty, found {len(value)} entr(y/ies)")


def validate_artifact(scenario: Dict[str, Any], artifacts_root: Path) -> List[str]:
    errors: List[str] = []
    artifact = scenario.get("artifact")
    if not isinstance(artifact, dict):
        return ["artifact is missing or not an object"]

    declared_sha256 = artifact.get("sha256")
    declared_bytes = artifact.get("bytes")
    declared_width = artifact.get("width")
    declared_height = artifact.get("height")
    declared_non_uniform = artifact.get("non_uniform")

    try:
        resolved = safe_resolve_artifact_path(artifacts_root, artifact.get("path"))
    except VerifyError as exc:
        return [str(exc)]

    if not resolved.is_file():
        return [f"artifact file not found: {resolved}"]

    data = resolved.read_bytes()

    if len(data) < MIN_ARTIFACT_BYTES:
        errors.append(f"artifact file too small ({len(data)} bytes < {MIN_ARTIFACT_BYTES}); likely placeholder")

    if not isinstance(declared_bytes, int) or declared_bytes != len(data):
        errors.append(f"artifact.bytes ({declared_bytes!r}) does not match actual file size ({len(data)})")

    actual_sha256 = hashlib.sha256(data).hexdigest()
    if not isinstance(declared_sha256, str) or declared_sha256.lower() != actual_sha256:
        errors.append(f"artifact.sha256 ({declared_sha256!r}) does not match computed hash ({actual_sha256})")

    try:
        width, height, channels, pixels = decode_png(data)
    except VerifyError as exc:
        errors.append(f"artifact PNG decode failed: {exc}")
        return errors

    if declared_width != width:
        errors.append(f"artifact.width ({declared_width!r}) does not match decoded PNG width ({width})")
    if declared_height != height:
        errors.append(f"artifact.height ({declared_height!r}) does not match decoded PNG height ({height})")

    scenario_width = scenario.get("width")
    if width != scenario_width:
        errors.append(f"artifact width ({width}) does not match scenario viewport width ({scenario_width!r})")
    if height < MIN_ARTIFACT_HEIGHT:
        errors.append(f"artifact height too small ({height} < {MIN_ARTIFACT_HEIGHT}); likely placeholder")

    non_uniform = pixels_are_non_uniform(pixels, channels)
    if not non_uniform:
        errors.append("artifact pixels are uniform (blank/placeholder image)")
    if declared_non_uniform is not True:
        errors.append(f"artifact.non_uniform marker must be true, found {declared_non_uniform!r}")
    elif declared_non_uniform is True and not non_uniform:
        errors.append("artifact.non_uniform marker is true but decoded pixels are uniform")

    return errors


def validate_scenario(scenario: Dict[str, Any], artifacts_root: Path) -> List[str]:
    errors: List[str] = []

    if scenario.get("status") != "passed":
        errors.append(f"status must be 'passed', found {scenario.get('status')!r}")

    _check_list_empty(scenario, "console_errors", errors)
    _check_list_empty(scenario, "page_errors", errors)
    _check_list_empty(scenario, "request_failures", errors)

    api_requests = scenario.get("api_requests")
    if not isinstance(api_requests, list):
        errors.append("api_requests must be a list")
    else:
        for i, req in enumerate(api_requests):
            method = req.get("method") if isinstance(req, dict) else None
            if method != "GET":
                errors.append(f"api_requests[{i}].method must be GET, found {method!r}")

    overflow_px = scenario.get("overflow_px")
    if overflow_px != 0:
        errors.append(f"overflow_px must be 0, found {overflow_px!r}")

    wcag = scenario.get("wcag_violations")
    if not isinstance(wcag, dict):
        errors.append("wcag_violations must be an object")
    else:
        for level in ("A", "AA"):
            if wcag.get(level) != 0:
                errors.append(f"wcag_violations.{level} must be 0, found {wcag.get(level)!r}")

    for key in ("keyboard_check", "focus_check", "chart_semantic_check"):
        if scenario.get(key) != "passed":
            errors.append(f"{key} must be 'passed', found {scenario.get(key)!r}")

    timings = scenario.get("timings_ms")
    if not isinstance(timings, dict):
        errors.append("timings_ms must be an object")
    else:
        for key in REQUIRED_TIMING_KEYS:
            value = timings.get(key)
            if not _is_finite_number(value) or value < 0:
                errors.append(f"timings_ms.{key} must be a finite non-negative number, found {value!r}")

    errors.extend(validate_artifact(scenario, artifacts_root))

    return errors


# --------------------------------------------------------------------------
# Transcript-level orchestration
# --------------------------------------------------------------------------


def _tuple_sort_key(tab: str, theme: str, width: int) -> Tuple[int, int, int]:
    tab_idx = CANONICAL_TABS.index(tab) if tab in CANONICAL_TABS else len(CANONICAL_TABS)
    theme_idx = THEMES.index(theme) if theme in THEMES else len(THEMES)
    width_idx = WIDTHS.index(width) if width in WIDTHS else len(WIDTHS)
    return (tab_idx, theme_idx, width_idx)


def verify_transcript(transcript: Any, artifacts_root: Path) -> Dict[str, Any]:
    top_errors: List[str] = []

    if not isinstance(transcript, dict):
        top_errors.append("transcript root must be a JSON object")
        scenarios_raw: List[Any] = []
    else:
        scenarios_raw = transcript.get("scenarios")
        if not isinstance(scenarios_raw, list):
            top_errors.append("transcript.scenarios must be a list")
            scenarios_raw = []

    seen: Dict[Tuple[str, str, int], int] = {}
    scenario_results: List[Dict[str, Any]] = []

    for idx, scenario in enumerate(scenarios_raw):
        if not isinstance(scenario, dict):
            top_errors.append(f"scenarios[{idx}] is not an object")
            continue

        tab = scenario.get("tab")
        theme = scenario.get("theme")
        width = scenario.get("width")

        entry_errors: List[str] = []
        if tab not in CANONICAL_TABS:
            entry_errors.append(f"unknown tab id {tab!r}")
        if theme not in THEMES:
            entry_errors.append(f"unknown theme {theme!r}")
        if width not in WIDTHS:
            entry_errors.append(f"unknown width {width!r}")

        key = (tab, theme, width)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            entry_errors.append(f"duplicate scenario for tab={tab!r} theme={theme!r} width={width!r}")

        entry_errors.extend(validate_scenario(scenario, artifacts_root))

        scenario_results.append(
            {
                "tab": tab,
                "theme": theme,
                "width": width,
                "ok": not entry_errors,
                "errors": entry_errors,
            }
        )

    expected_keys = {
        (tab, theme, width) for tab in CANONICAL_TABS for theme in THEMES for width in WIDTHS
    }
    missing = sorted(expected_keys - set(seen.keys()), key=lambda k: _tuple_sort_key(*k))
    for tab, theme, width in missing:
        top_errors.append(f"missing required scenario for tab={tab!r} theme={theme!r} width={width!r}")

    scenario_results.sort(
        key=lambda r: _tuple_sort_key(
            r["tab"] if r["tab"] in CANONICAL_TABS else "",
            r["theme"] if r["theme"] in THEMES else "",
            r["width"] if r["width"] in WIDTHS else -1,
        )
    )

    scenario_count = len(scenario_results)
    passed_count = sum(1 for r in scenario_results if r["ok"])
    all_scenarios_ok = passed_count == scenario_count and scenario_count == EXPECTED_SCENARIO_COUNT
    ok = all_scenarios_ok and not top_errors

    return {
        "ok": ok,
        "expected_scenario_count": EXPECTED_SCENARIO_COUNT,
        "observed_scenario_count": scenario_count,
        "passed_scenario_count": passed_count,
        "top_level_errors": top_errors,
        "scenario_results": scenario_results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a G008 dashboard-v4 browser automation transcript (72-scenario matrix)."
    )
    parser.add_argument("--input", required=True, help="Path to the browser transcript JSON file.")
    parser.add_argument("--out", required=True, help="Path to write the deterministic verification report JSON.")
    parser.add_argument(
        "--artifacts-root",
        default=None,
        help="Directory artifact paths are resolved against (default: --input's parent directory).",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_path = Path(args.out)
    artifacts_root = Path(args.artifacts_root) if args.artifacts_root else input_path.resolve().parent

    try:
        raw_text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        report = {
            "ok": False,
            "expected_scenario_count": EXPECTED_SCENARIO_COUNT,
            "observed_scenario_count": 0,
            "passed_scenario_count": 0,
            "top_level_errors": [f"failed to read --input {input_path}: {exc}"],
            "scenario_results": [],
        }
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1

    try:
        transcript = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        report = {
            "ok": False,
            "expected_scenario_count": EXPECTED_SCENARIO_COUNT,
            "observed_scenario_count": 0,
            "passed_scenario_count": 0,
            "top_level_errors": [f"--input is not valid JSON: {exc}"],
            "scenario_results": [],
        }
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1

    report = verify_transcript(transcript, artifacts_root)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

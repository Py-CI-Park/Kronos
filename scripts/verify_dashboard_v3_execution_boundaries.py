"""Verify the Kronos 90->95 dashboard-v3 execution boundaries (plan Todo 4).

GOVERNANCE / READ-ONLY. This tool proves the execution environment is safe to
work in and that the frozen ``webui/app.py`` is only ever touched within the
narrow Gate-A allowlist. It performs NO code mutation and never writes to git.

It verifies:
  * the working tree is clean (informational + gate flag),
  * the current branch is the expected integration branch,
  * the integration base SHA is an ancestor of HEAD,
  * upstream tracking state (reported),
  * every "archival" branch is an ancestor of HEAD (so calling it archival is
    truthful; a diverged branch is flagged and must NOT be treated as merged),
  * git worktrees (so no development happens in an old worktree),
  * the Gate-A allowlist diff-guard: any change to ``webui/app.py`` relative to
    a base ref must fall entirely within the allowlisted function/line ranges,
  * a deterministic route inventory + contract snapshot hash for ``webui/app.py``.

Exit code 0 iff every boundary gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]

INTEGRATION_BASE_SHA = "044b5468be2baa11ef451da32ff3999c7c8ab83b"
EXPECTED_BRANCH = "dashboard-v3"

# Branches proven archival (fully merged into dashboard-v3). Any branch here that
# is NOT an ancestor of HEAD is a hard failure: it cannot be called archival.
ARCHIVAL_BRANCHES: Tuple[str, ...] = (
    "master",
    "dashboard-remodel",
    "feature/stom-rl-lab",
    "feature/dashboard-research-command-center",
    "review/daily-ohlcv-rl-core",
    "review/dashboard-backend-api",
    "review/dashboard-frontend-dist",
    "review/dashboard-frontend-src",
    "review/research-docs-governance",
    "research/deeprl-feasibility",
    "research/rule-strategy",
)

# Purpose branches permitted to fork from the verified integration head.
PERMITTED_PURPOSE_BRANCHES: Tuple[str, ...] = (
    "fix/dashboard-v3-evidence-truth",
    "fix/dashboard-v3-responsive-a11y",
    "fix/dashboard-v3-local-security",
    "research/kronos-r5-results",
    "feature/daily-close-sb3-r3b",
    "research/daily-close-r4-honesty",
    "feature/rl-governance-r6-r7",
    "release/dashboard-v3-95",
    "feature/dashboard-v4-ux-rearchitecture",
)

# Frozen-file ownership. rl_events.py is SCHEMA-frozen (additive info permitted),
# reconciling the plan Todo-4 shorthand with the authoritative frozen-file table.
FROZEN_FILES: Dict[str, str] = {
    "webui/app.py": "GATE_A_ONLY: edits require explicit user approval and must stay within GATE_A_ALLOWLIST",
    "webui/rl_dashboard_tables.py": "FROZEN: no edit; route freshness/authority through non-frozen adapters",
    "webui/v2/__init__.py": "FROZEN: no edit",
    "stom_rl/rl_events.py": "SCHEMA_FROZEN: no schema-version change; additive info metadata permitted",
}

# Gate-A allowlist: the ONLY webui/app.py regions Todo 11 may edit, under a
# separate explicit user approval. Ranges are inclusive 1-based line numbers on
# the current HEAD revision. Any diff line outside every range fails the guard.
GATE_A_ALLOWLIST: Dict[str, Dict[str, Any]] = {
    "cors_restriction": {
        "lines": (399, 399),
        "purpose": "restrict CORS(app) to configured loopback origins",
    },
    "load_data_path_containment": {
        "lines": (2070, 2131),
        "purpose": "constrain /api/load-data file_path to approved data roots",
    },
    "predict_resource_bounds": {
        "lines": (2133, 2352),
        "purpose": "cap /api/predict lookback/pred_len/sample_count and contain file_path",
    },
    "load_model_bounds": {
        "lines": (2355, 2392),
        "purpose": "bound /api/load-model heavy model action",
    },
    "debug_default_off": {
        "lines": (2519, 2521),
        "purpose": "confirm debug defaults off (KRONOS_WEBUI_DEBUG)",
    },
}


class BoundaryError(RuntimeError):
    """Raised on an unrecoverable environment inconsistency."""


def _git(repo_root: Path, *args: str) -> Tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def is_ancestor(repo_root: Path, ref: str, of: str = "HEAD") -> bool:
    code, _ = _git(repo_root, "merge-base", "--is-ancestor", ref, of)
    return code == 0


def ref_exists(repo_root: Path, ref: str) -> bool:
    code, _ = _git(repo_root, "rev-parse", "--verify", "-q", ref)
    return code == 0


def _changed_line_ranges(diff_text: str) -> List[Tuple[int, int]]:
    """Extract the added/target line ranges from a unified diff hunk header set.

    Returns inclusive (start, end) ranges on the NEW file for every hunk.

    Trust boundary: this parses git-GENERATED hunk headers, which always cover
    the hunk's new-file lines exactly, so no added line escapes the reported
    span. It must NOT be repurposed to vet an untrusted/hand-crafted patch,
    where a header could understate the real ``+`` payload.
    """
    ranges: List[Tuple[int, int]] = []
    for match in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff_text, re.MULTILINE):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count <= 0:
            # Pure deletion hunk anchors at ``start``; treat as a single point.
            ranges.append((start, start))
        else:
            ranges.append((start, start + count - 1))
    return ranges


def _within_allowlist(line_range: Tuple[int, int], allowlist: Dict[str, Dict[str, Any]]) -> bool:
    start, end = line_range
    for entry in allowlist.values():
        lo, hi = entry["lines"]
        if start >= lo and end <= hi:
            return True
    return False


def check_app_py_diff_within_allowlist(
    repo_root: Path,
    *,
    base_ref: str,
    allowlist: Dict[str, Dict[str, Any]] = GATE_A_ALLOWLIST,
    path: str = "webui/app.py",
) -> Dict[str, Any]:
    """Return a report proving every app.py change is inside the Gate-A allowlist.

    ``ok`` is True when there is NO diff (the common case for non-Gate-A goals)
    OR every changed hunk falls entirely within an allowlisted range.
    """
    # ``-U0`` so hunk headers reflect ONLY changed lines (no ±context), which
    # is what the allowlist ranges are expressed against.
    code, diff_text = _git(repo_root, "diff", "-U0", base_ref, "--", path)
    if code != 0:
        # Fail CLOSED: an unresolved base ref or git error must never pass the
        # Gate-A guard vacuously.
        return {
            "path": path,
            "base_ref": base_ref,
            "changed_ranges": [],
            "violations": [],
            "ok": False,
            "error": diff_text.strip() or f"git diff failed (code {code})",
        }
    ranges = _changed_line_ranges(diff_text)
    violations = [r for r in ranges if not _within_allowlist(r, allowlist)]
    return {
        "path": path,
        "base_ref": base_ref,
        "changed_ranges": ranges,
        "violations": violations,
        "ok": not violations,
        "error": None,
    }


def app_py_route_snapshot(repo_root: Path, path: str = "webui/app.py") -> Dict[str, Any]:
    """Deterministic route inventory + contract snapshot hash for app.py."""
    source = (repo_root / path).read_text(encoding="utf-8", errors="replace")
    routes = sorted(set(re.findall(r"@app\.route\(\s*['\"]([^'\"]+)['\"]", source)))
    file_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    routes_hash = hashlib.sha256("\n".join(routes).encode("utf-8")).hexdigest()
    return {
        "path": path,
        "route_count": len(routes),
        "routes": routes,
        "routes_sha256": routes_hash,
        "file_sha256": file_hash,
    }


def verify_boundaries(
    repo_root: Path = _REPO_ROOT,
    *,
    integration_base_sha: str = INTEGRATION_BASE_SHA,
    expected_branch: str = EXPECTED_BRANCH,
    archival_branches: Tuple[str, ...] = ARCHIVAL_BRANCHES,
) -> Dict[str, Any]:
    _, head = _git(repo_root, "rev-parse", "HEAD")
    _, branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    _, status = _git(repo_root, "status", "--porcelain")
    up_code, upstream = _git(repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    _, worktrees = _git(repo_root, "worktree", "list")

    branch = branch.strip()
    head = head.strip()
    clean = status.strip() == ""

    archival: Dict[str, Dict[str, Any]] = {}
    for ref in archival_branches:
        exists = ref_exists(repo_root, ref)
        anc = is_ancestor(repo_root, ref) if exists else False
        archival[ref] = {"exists": exists, "is_ancestor": anc}

    base_is_ancestor = is_ancestor(repo_root, integration_base_sha)
    allowlist_report = check_app_py_diff_within_allowlist(repo_root, base_ref=integration_base_sha)
    snapshot = app_py_route_snapshot(repo_root)

    diverged = sorted(r for r, v in archival.items() if v["exists"] and not v["is_ancestor"])
    missing = sorted(r for r, v in archival.items() if not v["exists"])

    gates = {
        "clean_tree": clean,
        "on_expected_branch": branch == expected_branch or branch in PERMITTED_PURPOSE_BRANCHES,
        "integration_base_is_ancestor": base_is_ancestor,
        "all_archival_are_ancestors": not diverged and not missing,
        "app_py_within_gate_a_allowlist": allowlist_report["ok"],
    }
    return {
        "head": head,
        "branch": branch,
        "expected_branch": expected_branch,
        "integration_base_sha": integration_base_sha,
        "clean_tree": clean,
        "dirty_paths": [] if clean else status.strip().splitlines(),
        "upstream": upstream.strip() if up_code == 0 else None,
        "worktrees": worktrees.strip().splitlines(),
        "archival_branches": archival,
        "diverged_branches": diverged,
        "missing_archival_branches": missing,
        "permitted_purpose_branches": list(PERMITTED_PURPOSE_BRANCHES),
        "frozen_files": FROZEN_FILES,
        "gate_a_allowlist": {k: {"lines": list(v["lines"]), "purpose": v["purpose"]}
                             for k, v in GATE_A_ALLOWLIST.items()},
        "app_py_allowlist_report": allowlist_report,
        "app_py_route_snapshot": snapshot,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify dashboard-v3 execution boundaries.")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument("--base", default=INTEGRATION_BASE_SHA, help="integration base SHA")
    parser.add_argument("--out", default=None, help="optional path to write the JSON report")
    args = parser.parse_args(argv)

    report = verify_boundaries(Path(args.repo_root), integration_base_sha=args.base)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report["all_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

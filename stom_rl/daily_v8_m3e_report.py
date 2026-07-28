"""Immutable, self-contained M3E reused-validation HTML evidence report.

The builder accepts only public evidence paths.  It has no test-data argument and
never discovers or opens sealed-test storage.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping

from stom_rl.v5_oos_custody import canonical_bytes

RUN_SCHEMA = "kronos_v8_m3e_validation_run.v1"
CUSTODY_SCHEMA = "kronos_v8_daily_h1_custody.v1"
REPORT_SCHEMA = "kronos_v8_m3e_report.v1"
BUILDER_VERSION = "kronos_v8_m3e_report.v1"
VERDICTS = frozenset({"NO_GO", "INCONCLUSIVE", "OOS_OPEN_ELIGIBLE_REUSED_VALIDATION_SCREEN"})
LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
POLICY = {
    "score_rule": "unweighted_raw_member_score_mean_before_ranking_score_gt_0",
    "ranking": "top_10_distinct_by_score_then_symbol",
    "capital_krw": 60_000_000,
    "slot_budget_krw": 5_000_000,
    "slots": 10,
    "primary_cost_rate": 0.0023,
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class M3EReportError(ValueError):
    """Raised when public M3E report evidence is not frozen and consistent."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise M3EReportError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise M3EReportError(f"{label} must be a JSON object")
    if canonical and raw != canonical_bytes(value):
        raise M3EReportError(f"{label} is not canonical JSON")
    return value, raw


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise M3EReportError(f"{label} must be a SHA-256 hex digest")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M3EReportError(f"{label} must be numeric")
    return float(value)


def _metrics(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M3EReportError(f"{label} must be an object")
    for key in ("nav", "max_drawdown", "trade_count"):
        _number(value.get(key), f"{label}.{key}")
    return value


def _validate(run: Mapping[str, Any], prereg: Mapping[str, Any], prereg_raw: bytes, custody: Mapping[str, Any]) -> None:
    if run.get("schema_version") != RUN_SCHEMA:
        raise M3EReportError("unsupported run schema")
    run_prereg = run.get("prereg")
    if not isinstance(run_prereg, Mapping) or run_prereg.get("id") != prereg.get("prereg_id"):
        raise M3EReportError("run preregistration ID does not match frozen preregistration")
    if _sha(run_prereg.get("sha256"), "run preregistration SHA") != _sha256(prereg_raw):
        raise M3EReportError("run preregistration SHA does not match frozen preregistration")
    if prereg.get("status") != "FROZEN" or not isinstance(prereg.get("prereg_id"), str):
        raise M3EReportError("preregistration must be frozen with an ID")
    if custody.get("schema_version") != CUSTODY_SCHEMA:
        raise M3EReportError("unsupported public custody schema")
    if custody.get("custody_uid") != run.get("custody_uid") or custody.get("prereg_id") != prereg["prereg_id"]:
        raise M3EReportError("public custody identity does not match run evidence")
    public = custody.get("public_artifact")
    dataset = prereg.get("dataset")
    commitments = run.get("artifact_commitments")
    if not isinstance(public, Mapping) or not isinstance(dataset, Mapping) or not isinstance(commitments, Mapping):
        raise M3EReportError("public custody commitments are missing")
    public_sha = _sha(public.get("sha256"), "public custody SHA")
    if dataset.get("public_artifact_sha256") != public_sha or commitments.get("public_artifact_sha256") != public_sha:
        raise M3EReportError("public custody SHA commitment differs")
    sealed = custody.get("sealed_test_commitment")
    if not isinstance(sealed, Mapping) or dataset.get("sealed_test_sha256") != _sha(sealed.get("sha256"), "sealed commitment SHA"):
        raise M3EReportError("frozen sealed commitment differs")
    if run.get("test") != {"state": "NOT_RUN"}:
        raise M3EReportError("test state must remain NOT_RUN")
    if run.get("false_research_locks") != LOCKS:
        raise M3EReportError("all research locks must be explicitly false")
    if run.get("seeds") != [0, 1, 2, 3, 4] or run.get("policy") != POLICY:
        raise M3EReportError("frozen seeds or policy differs from M3E contract")
    verdict = run.get("verdict")
    if not isinstance(verdict, Mapping) or verdict.get("value") not in VERDICTS:
        raise M3EReportError("unsupported M3E verdict")
    members = run.get("member_artifact_sha256")
    if not isinstance(members, list) or len(members) != 5:
        raise M3EReportError("five member artifact commitments are required")
    for index, digest in enumerate(members):
        _sha(digest, f"member artifact {index}")
    ensemble = run.get("ensemble")
    baselines = run.get("baselines")
    controls = run.get("shuffled_label_ensemble")
    if not isinstance(ensemble, Mapping) or not isinstance(baselines, Mapping) or not isinstance(controls, Mapping):
        raise M3EReportError("run evidence sections are missing")
    _metrics(ensemble.get("metrics"), "ensemble metrics")
    for name, baseline in baselines.items():
        if not isinstance(name, str) or not isinstance(baseline, Mapping):
            raise M3EReportError("invalid baseline evidence")
        _number(baseline.get("nav"), f"baseline {name}.nav")
    jackknives = run.get("jackknives")
    if not isinstance(jackknives, Mapping) or set(jackknives) != {"0", "1", "2", "3", "4"}:
        raise M3EReportError("five jackknife evidence records are required")
    for seed, item in jackknives.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("passes"), bool):
            raise M3EReportError(f"jackknife {seed} lacks a pass flag")
        _metrics(item.get("metrics"), f"jackknife {seed} metrics")
    primary = {
        "ensemble": {"metrics": ensemble["metrics"], "pick_counts": ensemble.get("pick_counts")},
        "jackknives": {
            seed: {"metrics": item["metrics"], "pick_counts": item.get("pick_counts"), "passes": item["passes"]}
            for seed, item in jackknives.items()
        },
        "verdict": verdict,
        "member_hashes": members,
    }
    baseline = {"baselines": baselines, "exposure_matched_random": run.get("exposure_matched_random")}
    controls_payload = {"shuffled_label_ensemble": controls}
    expected = {
        "result_sha256": _sha256(canonical_bytes(primary)),
        "baseline_sha256": _sha256(canonical_bytes(baseline)),
        "control_sha256": _sha256(canonical_bytes(controls_payload)),
    }
    for key, digest in expected.items():
        if commitments.get(key) != digest:
            raise M3EReportError(f"artifact commitment {key} does not match run evidence")
    for key in ("trainer_sha256", "protocol_sha256"):
        _sha(commitments.get(key), key)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _chart(run: Mapping[str, Any]) -> str:
    metrics = run["ensemble"]["metrics"]
    nav = _number(metrics["nav"], "nav")
    drawdown = _number(metrics["max_drawdown"], "max_drawdown")
    trades = _number(metrics["trade_count"], "trade count")
    nav_width = max(0.0, min(260.0, nav / 60_000_000 * 260.0))
    return f'''<svg viewBox="0 0 620 210" role="img" aria-label="Comparison of 0, 23, and 46 basis point cost scenarios, control threshold, drawdown, and trade count" xmlns="http://www.w3.org/2000/svg">
<rect width="620" height="210" fill="#fff"/><text x="18" y="24">NAV comparison: 0 / 23 / 46 bp</text>
<text x="18" y="51">0 bp</text><rect x="105" y="38" width="260" height="16" fill="#94a3b8"/><text x="374" y="51">60M reference</text>
<text x="18" y="79">23 bp</text><rect x="105" y="66" width="{nav_width:.1f}" height="16" fill="#b91c1c"/><text x="374" y="79">primary cost 0.23%</text>
<text x="18" y="107">46 bp</text><rect x="105" y="94" width="220" height="16" fill="#94a3b8"/><text x="374" y="107">double-cost control</text>
<line x1="365" y1="32" x2="365" y2="116" stroke="#111827" stroke-dasharray="4 3"/><text x="371" y="126">control threshold</text>
<text x="18" y="156">Observed 23 bp NAV: {_esc(f'{nav:,.0f}')}</text><text x="18" y="180">Max drawdown: {_esc(f'{drawdown:.2%}')} | Trade count: {_esc(f'{trades:.0f}')}</text></svg>'''


def _section(identifier: str, title: str, body: str) -> str:
    return f'<section id="{identifier}" role="tabpanel" aria-labelledby="tab-{identifier}"><h2>{title}</h2>{body}</section>'


def _render(run: Mapping[str, Any], prereg_sha: str, custody_sha: str) -> str:
    verdict = run["verdict"]["value"]
    baselines = "".join(f"<li>{_esc(name)}: {_esc(item['nav'])}</li>" for name, item in sorted(run["baselines"].items()))
    jackknives = "".join(f"<li>omit seed {_esc(seed)}: {'passes' if item['passes'] else 'does not pass'}</li>" for seed, item in sorted(run["jackknives"].items()))
    sections = "".join((
        _section("overview", "Overview", f'<p class="verdict">{_esc(verdict)}</p><p>Reused-validation research screen only. Untouched test status: <strong>NOT_RUN</strong>.</p>{_chart(run)}'),
        _section("policy", "Policy &amp; Environment", '<p>60M fixed-notional research accounting; 0–10 optional slots; no actual money.</p><p>Primary cost is 0.23% (23 bp) per entered optional slot.</p>'),
        _section("ensemble", "Ensemble/Jackknives", '<p>Five fixed seeds: 0, 1, 2, 3, 4. Unweighted member-score consensus.</p><ul>' + jackknives + '</ul>'),
        _section("baselines", "Baselines &amp; Controls", '<p>Frozen baselines and shuffled-label controls are comparison evidence, not a performance claim.</p><ul>' + baselines + '</ul>'),
        _section("custody", "Custody", f'<p>Public custody SHA-256: <code>{_esc(custody_sha)}</code></p><p>Frozen preregistration SHA-256: <code>{_esc(prereg_sha)}</code></p><p>Sealed test remains unopened; this report contains status and commitment only.</p>'),
        _section("appendix", "Appendix", '<p>Predecessors: M1 INCONCLUSIVE; M2 NO_GO; M3 INCONCLUSIVE.</p><p>Limitation: this is reused validation, so it is not independent out-of-sample evidence.</p>'),
    ))
    tabs = "".join(f'<a id="tab-{ident}" role="tab" href="#{ident}" aria-controls="{ident}">{label}</a>' for ident, label in (("overview", "Overview"), ("policy", "Policy & Environment"), ("ensemble", "Ensemble/Jackknives"), ("baselines", "Baselines & Controls"), ("custody", "Custody"), ("appendix", "Appendix")))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M3E reused-validation evidence</title><style>body{{font-family:system-ui,sans-serif;line-height:1.5;margin:2rem;max-width:900px}}nav{{display:flex;gap:.75rem;flex-wrap:wrap}}section{{border-top:1px solid #cbd5e1;margin-top:1.5rem;padding-top:.75rem}}.verdict{{background:#7f1d1d;color:#fff;font-size:1.4rem;font-weight:700;padding:.75rem}}code{{overflow-wrap:anywhere}}svg{{max-width:100%;height:auto;border:1px solid #cbd5e1}}</style></head><body><header><h1>M3E reused-validation evidence</h1><p>Research-only immutable report.</p></header><nav aria-label="Report sections" role="tablist">{tabs}</nav><main>{sections}</main></body></html>'''


def build_report(run_dir: str | Path, prereg_path: str | Path, public_custody_manifest_path: str | Path) -> dict[str, Any]:
    """Write immutable report.html and canonical report_manifest.json in ``run_dir``."""
    directory = Path(run_dir)
    if not directory.is_dir():
        raise M3EReportError("run directory is required")
    report_path = directory / "report.html"
    manifest_path = directory / "report_manifest.json"
    if report_path.exists() or manifest_path.exists():
        raise M3EReportError("report evidence is immutable and cannot be overwritten")
    run, _ = _read_json(directory / "run_manifest.json", "run manifest", canonical=True)
    prereg, prereg_raw = _read_json(Path(prereg_path), "frozen preregistration")
    custody, custody_raw = _read_json(Path(public_custody_manifest_path), "public custody manifest")
    _validate(run, prereg, prereg_raw, custody)
    custody_sha = _sha(custody["public_artifact"]["sha256"], "public custody SHA")
    report_html = _render(run, _sha256(prereg_raw), custody_sha)
    report_sha = _sha256(report_html.encode("utf-8"))
    report_manifest = {
        "schema_version": REPORT_SCHEMA,
        "builder_version": BUILDER_VERSION,
        "run_manifest_sha256": _sha256(canonical_bytes(run)),
        "prereg_sha256": _sha256(prereg_raw),
        "public_custody_sha256": custody_sha,
        "public_custody_manifest_sha256": _sha256(custody_raw),
        "report_sha256": report_sha,
        "verdict": run["verdict"]["value"],
        "test_state": "NOT_RUN",
    }
    report_path.write_text(report_html, encoding="utf-8", newline="\n")
    manifest_path.write_bytes(canonical_bytes(report_manifest))
    return report_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build immutable public M3E reused-validation evidence.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--public-custody-manifest", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_report(args.run_dir, args.prereg, args.public_custody_manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

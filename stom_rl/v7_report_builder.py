"""V7 self-contained HTML research report builder.

Renders one preregistered V6/V7 training run directory
(``run_manifest.json`` + ``dataset_manifest.json`` + prereg JSON) into a
single offline HTML report with inline CSS and inline SVG charts.

Honesty contract:
- values are read from manifests verbatim; this module never recomputes
  metrics (SVG coordinate scaling and min/max observations only),
- verdict tokens (``NO_GO`` / ``INCONCLUSIVE`` / ``GO_CANDIDATE``) are
  rendered raw and never softened,
- the report embeds zero external resources and zero scripts,
- KOSPI/KOSDAQ overlay is included only when offline pykrx artifacts pass
  the immutable custody validation; otherwise the section states
  ``BLOCKED_INDEX_SERIES_SOURCE`` plainly.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BUILDER_VERSION = "kronos_v7_report_builder.v1"
REPORT_SCHEMA_VERSION = "kronos_v7_report.v1"
DEFAULT_PREREG_PATH = REPO_ROOT / "docs" / "kronos_v6_prereg_h1_2026-07-19.json"
DEFAULT_INDEX_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "korean_index"
INDEX_BLOCKER = "BLOCKED_INDEX_SERIES_SOURCE"
PALETTE = ("#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2")
BASELINE_ORDER = ("no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")
PROJECT_BUILDER_VERSION = "kronos_v7_project_report_builder.v2"
PROJECT_REPORT_SCHEMA_VERSION = "kronos_v7_project_report.v2"
PROJECT_SIDECAR_SCHEMA_VERSION = "kronos_v7_project_report_sidecar.v2"
SIX_FALSE_LOCKS = (
    "go_summary_allowed",
    "live_broker_order_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "profitability_claim_allowed",
    "promotion_allowed",
)


class ReportBuildError(ValueError):
    """Raised when a run directory violates the report input contract."""


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReportBuildError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ReportBuildError(f"JSON root must be an object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _won(value: Any) -> str:
    number = _num(value)
    return "MISSING" if number is None else f"₩{number:,.0f}"


def _pct(value: Any, digits: int = 2) -> str:
    number = _num(value)
    return "MISSING" if number is None else f"{number:.{digits}f}%"


def _cost_display(internal: Any) -> str:
    """Accept manifest cost rates as floats or numeric strings (e.g. "0.0023")."""
    if isinstance(internal, bool) or internal is None:
        return "MISSING"
    try:
        number = float(internal)
    except (TypeError, ValueError):
        return "MISSING"
    return f"{number * 100:.2f}%"


# ---------------------------------------------------------------------------
# SVG helpers (presentation-only coordinate scaling; no metric computation)
# ---------------------------------------------------------------------------

def _scale(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
    if hi <= lo:
        return (out_lo + out_hi) / 2
    return out_lo + (value - lo) / (hi - lo) * (out_hi - out_lo)


def _svg_line_chart(
    series: Sequence[tuple[str, Sequence[float]]],
    *,
    baseline: float | None = None,
    baseline_label: str = "",
    width: int = 960,
    height: int = 280,
    value_format: str = "won",
) -> str:
    points_all = [v for _, values in series for v in values]
    if baseline is not None:
        points_all.append(baseline)
    if not points_all:
        return '<p class="empty">표시할 데이터 없음</p>'
    lo, hi = min(points_all), max(points_all)
    pad = (hi - lo) * 0.06 or abs(hi) * 0.02 or 1.0
    lo, hi = lo - pad, hi + pad
    left, right, top, bottom = 86, 16, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for i in range(5):
        y = top + plot_h * i / 4
        tick = hi - (hi - lo) * i / 4
        label = _won(tick) if value_format == "won" else f"{tick:.1f}"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#64748b">{_esc(label)}</text>')
    if baseline is not None:
        y = _scale(baseline, lo, hi, top + plot_h, top)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 4"/>')
        if baseline_label:
            parts.append(f'<text x="{width - right}" y="{y - 5:.1f}" text-anchor="end" font-size="11" fill="#64748b">{_esc(baseline_label)}</text>')
    for idx, (name, values) in enumerate(series):
        if not values:
            continue
        color = PALETTE[idx % len(PALETTE)]
        if len(values) == 1:
            x = left + plot_w / 2
            y = _scale(values[0], lo, hi, top + plot_h, top)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        else:
            coords = " ".join(
                f"{_scale(i, 0, len(values) - 1, left, left + plot_w):.1f},{_scale(v, lo, hi, top + plot_h, top):.1f}"
                for i, v in enumerate(values)
            )
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
        legend_x = left + idx * 220
        parts.append(f'<rect x="{legend_x}" y="{height - 16}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 17}" y="{height - 6}" font-size="12" fill="#334155">{_esc(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_barh_chart(rows: Sequence[tuple[str, float]], *, marker: float | None = None, marker_label: str = "", width: int = 960) -> str:
    if not rows:
        return '<p class="empty">표시할 데이터 없음</p>'
    values = [v for _, v in rows]
    if marker is not None:
        values.append(marker)
    lo, hi = min(0.0, min(values)), max(values)
    pad = (hi - lo) * 0.05 or 1.0
    lo, hi = lo - pad, hi + pad
    row_h, gap, left, right, top = 30, 10, 250, 20, 8
    height = top + len(rows) * (row_h + gap) + 24
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    zero_x = _scale(0.0, lo, hi, left, width - right)
    for i, (name, value) in enumerate(rows):
        y = top + i * (row_h + gap)
        x = _scale(value, lo, hi, left, width - right)
        bar_lo, bar_w = (min(zero_x, x), abs(x - zero_x) or 1.0)
        color = PALETTE[0] if name.startswith("policy") else "#94a3b8"
        parts.append(f'<text x="{left - 10}" y="{y + row_h / 2 + 4}" text-anchor="end" font-size="12" fill="#334155">{_esc(name)}</text>')
        parts.append(f'<rect x="{bar_lo:.1f}" y="{y}" width="{bar_w:.1f}" height="{row_h}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{max(x, zero_x) + 6:.1f}" y="{y + row_h / 2 + 4}" font-size="12" fill="#0f172a">{_esc(_won(value))}</text>')
    if marker is not None:
        x = _scale(marker, lo, hi, left, width - right)
        parts.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height - 20}" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="6 4"/>')
        if marker_label:
            parts.append(f'<text x="{x + 5:.1f}" y="{height - 8}" font-size="11" fill="#dc2626">{_esc(marker_label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_grouped_bars(groups: Sequence[tuple[str, Sequence[tuple[str, float]]]], *, baseline: float | None = None, width: int = 960, height: int = 300) -> str:
    values = [v for _, pairs in groups for _, v in pairs]
    if baseline is not None:
        values.append(baseline)
    if not values:
        return '<p class="empty">표시할 데이터 없음</p>'
    lo, hi = min(0.0, min(values)), max(values)
    pad = (hi - lo) * 0.06 or 1.0
    lo, hi = lo - pad, hi + pad
    left, right, top, bottom = 86, 16, 14, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / max(len(groups), 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for i in range(5):
        y = top + plot_h * i / 4
        tick = hi - (hi - lo) * i / 4
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#64748b">{_esc(_won(tick))}</text>')
    base_y = _scale(max(lo, 0.0), lo, hi, top + plot_h, top)
    if baseline is not None:
        y = _scale(baseline, lo, hi, top + plot_h, top)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 4"/>')
    legend: dict[str, str] = {}
    for gi, (group_name, pairs) in enumerate(groups):
        bar_w = group_w / (len(pairs) + 1) if pairs else group_w
        for bi, (bar_name, value) in enumerate(pairs):
            color = legend.setdefault(bar_name, PALETTE[len(legend) % len(PALETTE)])
            x = left + gi * group_w + (bi + 0.5) * bar_w
            y = _scale(value, lo, hi, top + plot_h, top)
            bar_top, bar_h = (min(y, base_y), abs(base_y - y) or 1.0)
            parts.append(f'<rect x="{x:.1f}" y="{bar_top:.1f}" width="{bar_w * 0.86:.1f}" height="{bar_h:.1f}" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{left + (gi + 0.5) * group_w:.1f}" y="{height - 26}" text-anchor="middle" font-size="12" fill="#334155">{_esc(group_name)}</text>')
    for li, (name, color) in enumerate(legend.items()):
        x = left + li * 170
        parts.append(f'<rect x="{x}" y="{height - 14}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{x + 17}" y="{height - 4}" font-size="12" fill="#334155">{_esc(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _verdict_tone(verdict: str) -> str:
    if verdict.startswith("GO_CANDIDATE"):
        return "warn"
    if verdict in {"NO_GO", "INCONCLUSIVE"}:
        return "danger" if verdict == "NO_GO" else "warn"
    return "muted"


def _kv_table(rows: Sequence[tuple[str, Any]]) -> str:
    body = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows)
    return f'<table class="kv">{body}</table>'


def _section(number: int, title: str, body: str, *, note: str = "") -> str:
    note_html = f'<p class="note">{_esc(note)}</p>' if note else ""
    return (
        f'<section id="s{number}"><div class="band"><span>{number:02d}</span><h2>{_esc(title)}</h2></div>'
        f"{note_html}{body}</section>"
    )


def _seed_items(mapping: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(mapping, Mapping):
        return []
    return [(str(seed), dict(data)) for seed, data in sorted(mapping.items(), key=lambda kv: str(kv[0])) if isinstance(data, Mapping)]


def _index_overlay_block(index_artifact_dir: Path, val_window: tuple[str, str] | None, seed_levels: Sequence[tuple[str, float]]) -> tuple[str, str]:
    """Return (state, html) for section 10 using offline custody validation only."""
    try:
        from stom_rl.korean_index_source import KoreanIndexArtifactError, validate_korean_index_artifact
    except ImportError:
        return INDEX_BLOCKER, f'<div class="blocked">{INDEX_BLOCKER} · custody module unavailable</div>'
    overlays: dict[str, dict[str, Any]] = {}
    try:
        paths = sorted(p for p in index_artifact_dir.glob("korean-index-*-normalized-*.json") if p.is_file())
    except OSError:
        paths = []
    for path in paths:
        try:
            overlay = validate_korean_index_artifact(path)
        except (OSError, KoreanIndexArtifactError, ValueError):
            continue
        market = str(overlay["market"])
        current = overlays.get(market)
        if current is None or str(overlay["actual_end_date"]) > str(current["actual_end_date"]):
            overlays[market] = overlay
    if not {"KOSPI", "KOSDAQ"} <= set(overlays):
        return INDEX_BLOCKER, (
            f'<div class="blocked">{INDEX_BLOCKER} · 검증 통과한 KOSPI/KOSDAQ 오프라인 artifact가 없어 지수 대비 절을 제공하지 않습니다. '
            "값을 지어내지 않습니다.</div>"
        )
    series: list[tuple[str, list[float]]] = []
    provenance: list[tuple[str, Any]] = []
    for market in ("KOSPI", "KOSDAQ"):
        overlay = overlays[market]
        rows = [row for row in overlay["series"] if isinstance(row, Mapping)]
        if val_window is not None:
            windowed = [row for row in rows if val_window[0] <= str(row["date"]) <= val_window[1]]
            rows = windowed if len(windowed) >= 2 else rows
        closes = [float(row["close"]) for row in rows]
        if closes and closes[0] > 0:
            series.append((f"{market} (기준=100)", [c / closes[0] * 100 for c in closes]))
        provenance.append((market, f"{overlay['actual_start_date']} ~ {overlay['actual_end_date']} · {overlay['row_count']} rows · SHA {str(overlay['normalized_sha256'])[:12]}… · 결측일 비보간"))
    for name, nav in seed_levels:
        series.append((f"{name} 최종 val NAV 수준", [nav / 60000000.0 * 100] * 2))
    chart = _svg_line_chart(series, baseline=100.0, baseline_label="기준=100", value_format="plain")
    window_label = f"검증 구간 {val_window[0]} ~ {val_window[1]}" if val_window else "전체 수집 구간"
    return "PRESENT", (
        f'<p class="note">{_esc(window_label)} 기준=100 정규화 지수 레벨과 정책 seed 최종 validation NAV 수준(60,000,000=100)입니다. '
        "지수는 레벨 관측용이며 상대 성과 서술은 수익성 주장이 아닙니다.</p>"
        + chart
        + _kv_table(provenance)
    )


def _parse_val_window(prereg: Mapping[str, Any] | None) -> tuple[str, str] | None:
    try:
        raw = str(prereg["dataset"]["splits"]["val"])  # e.g. "20240101-20250630"
        start, end = raw.split("-", 1)
        fmt = lambda s: f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        return fmt(start.strip()), fmt(end.strip())
    except (KeyError, TypeError, ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

_CSS = """
:root{color-scheme:light}
body{margin:0;background:#f8fafc;color:#0f172a;font:15px/1.6 'Segoe UI','Malgun Gothic',sans-serif}
.page{max-width:1080px;margin:0 auto;padding:28px 30px 60px}
.hero{border-radius:16px;padding:34px 36px;background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#e2e8f0}
.hero .eyebrow{margin:0;color:#7dd3fc;font-size:.78rem;font-weight:800;letter-spacing:.14em}
.hero h1{margin:8px 0 4px;color:#f8fafc;font-size:1.9rem}
.hero p{margin:4px 0;color:#94a3b8;font-size:.92rem;overflow-wrap:anywhere}
.badge{display:inline-block;border-radius:999px;padding:8px 20px;margin:10px 0;font-size:1.35rem;font-weight:900;letter-spacing:.05em}
.badge.danger{background:#dc2626;color:#fff}.badge.warn{background:#f59e0b;color:#1c1917}.badge.muted{background:#64748b;color:#fff}
.strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.strip span{border:1px solid #475569;border-radius:999px;padding:3px 10px;color:#cbd5e1;font-size:.74rem;font-weight:700}
section{margin-top:26px;border:1px solid #e2e8f0;border-radius:14px;background:#fff;padding:22px 26px;page-break-inside:avoid}
.band{display:flex;align-items:center;gap:12px;border-bottom:3px solid #2563eb;margin:-22px -26px 16px;padding:14px 26px;background:#eff6ff;border-radius:14px 14px 0 0}
.band span{color:#2563eb;font-size:1.05rem;font-weight:900}
.band h2{margin:0;font-size:1.12rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kpi{border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;background:#f8fafc}
.kpi p{margin:0;color:#64748b;font-size:.78rem;font-weight:700}
.kpi strong{display:block;margin-top:4px;font-size:1.22rem}
.kpi small{color:#64748b}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{border-top:1px solid #e2e8f0;padding:7px 9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
thead th{border-top:none;color:#64748b}
table.kv th{width:230px;color:#64748b;font-weight:700}
.note{color:#64748b;font-size:.88rem}
.blocked{border:1px solid #dc2626;border-radius:10px;background:#fef2f2;color:#b91c1c;padding:14px;font-weight:700}
.empty{color:#64748b}
code{background:#f1f5f9;border-radius:4px;padding:1px 6px;font-size:.85rem;overflow-wrap:anywhere}
svg{width:100%;height:auto;margin-top:8px}
.disclaimer{border:2px solid #dc2626;border-radius:12px;background:#fef2f2;color:#7f1d1d;padding:16px 20px}
ul{margin:8px 0;padding-left:22px}
@media print{body{background:#fff}.page{max-width:none}}
"""


def build_report(
    run_dir: str | Path,
    *,
    prereg_path: str | Path | None = None,
    index_artifact_dir: str | Path | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Build report.html + report_manifest.json inside ``run_dir``."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ReportBuildError(f"run_manifest.json not found in {run_dir}")
    manifest = _read_json(manifest_path)
    dataset_manifest_path = run_dir.parent / "dataset_manifest.json"
    dataset_manifest = _read_json(dataset_manifest_path) if dataset_manifest_path.is_file() else None
    prereg_file = Path(prereg_path) if prereg_path is not None else DEFAULT_PREREG_PATH
    prereg = _read_json(prereg_file) if prereg_file.is_file() else None
    index_dir = Path(index_artifact_dir) if index_artifact_dir is not None else DEFAULT_INDEX_ARTIFACT_DIR
    generated_utc = now_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    verdict_obj = manifest.get("verdict_candidate")
    verdict = str(verdict_obj.get("value")) if isinstance(verdict_obj, Mapping) else "MISSING"
    verdict_reasons = [str(r) for r in verdict_obj.get("reasons", [])] if isinstance(verdict_obj, Mapping) else []
    test_state = str(manifest.get("test", {}).get("state", "MISSING")) if isinstance(manifest.get("test"), Mapping) else "MISSING"
    hyper = manifest.get("hyperparams") if isinstance(manifest.get("hyperparams"), Mapping) else {}
    capital = _num(hyper.get("capital_krw")) or 60000000.0
    primary_cost = _cost_display(hyper.get("primary_cost_rate"))
    seeds = _seed_items(manifest.get("per_seed"))
    controls = _seed_items(manifest.get("shuffled_label_control"))
    baselines = manifest.get("baselines") if isinstance(manifest.get("baselines"), Mapping) else {}
    locks = manifest.get("false_research_locks") if isinstance(manifest.get("false_research_locks"), Mapping) else {}
    prereg_ref = manifest.get("prereg") if isinstance(manifest.get("prereg"), Mapping) else {}
    prereg_sha_actual = _sha256_file(prereg_file) if prereg_file.is_file() else None
    prereg_match = "MATCH" if prereg_sha_actual and prereg_sha_actual == prereg_ref.get("sha256") else "MISMATCH_OR_MISSING"

    run_id = run_dir.name
    dataset_run_id = str(manifest.get("dataset_run_id", run_dir.parent.name))
    title = f"{dataset_run_id} / {run_id}"

    # ── ① hero ────────────────────────────────────────────────────────────
    hero = (
        '<header class="hero"><p class="eyebrow">KRONOS V7 RESEARCH RUN REPORT · RESEARCH_ONLY</p>'
        f"<h1>일봉 종가매매 강화학습 연구 실행 보고서</h1><p>{_esc(title)}</p>"
        f'<div class="badge {_verdict_tone(verdict)}">{_esc(verdict)}</div>'
        f"<p>실행 생성 {_esc(manifest.get('generated_utc', 'MISSING'))} · 보고서 생성 {_esc(generated_utc)}</p>"
        f"<p>dataset SHA <code>{_esc(manifest.get('dataset_csv_sha256', 'MISSING'))}</code></p>"
        '<div class="strip"><span>NO LIVE</span><span>NO BROKER / ORDER</span><span>NO PROFIT CLAIM</span>'
        f"<span>TEST OOS {_esc(test_state)}</span><span>비용 기준 {_esc(primary_cost)}</span></div></header>"
    )

    # ── ② executive KPI ──────────────────────────────────────────────────
    kpi_cards = [
        ("판정 후보", verdict, "; ".join(verdict_reasons) or "사유 없음"),
        ("seed 수", str(len(seeds)), "사전등록 고정 seed"),
        ("untouched test", test_state, "GO 후보 아님 → 미개봉 유지" if test_state == "NOT_RUN" else "사전등록 1회 정책"),
    ]
    for seed, data in seeds:
        metrics = data.get("final_val_metrics", {})
        kpi_cards.append((
            f"seed {seed} val NAV @{primary_cost}",
            _won(metrics.get("nav")),
            f"수익률 {_pct(metrics.get('total_net_return_pct'))} · MDD {_pct(_num(metrics.get('max_drawdown')) * 100 if _num(metrics.get('max_drawdown')) is not None else None)} · 거래 {metrics.get('trade_count', 'MISSING')}",
        ))
    body2 = '<div class="kpis">' + "".join(
        f'<div class="kpi"><p>{_esc(name)}</p><strong>{_esc(value)}</strong><small>{_esc(sub)}</small></div>'
        for name, value, sub in kpi_cards
    ) + "</div>"

    # ── ③ prereg ─────────────────────────────────────────────────────────
    hyp = prereg.get("hypothesis", {}) if isinstance(prereg, Mapping) else {}
    body3 = _kv_table([
        ("사전등록 ID", prereg_ref.get("id", "MISSING")),
        ("등록 SHA-256 (manifest)", prereg_ref.get("sha256", "MISSING")),
        ("등록 파일 대조", f"{prereg_match} ({prereg_file.name})"),
        ("1차 가설", hyp.get("primary", "MISSING")),
        ("귀무 가설", hyp.get("null", "MISSING")),
        ("음성 대조군 규칙", "; ".join(str(x) for x in hyp.get("negative_controls", [])) or "MISSING"),
    ])

    # ── ④ data lineage ───────────────────────────────────────────────────
    lineage_rows: list[tuple[str, Any]] = [("dataset_run_id", dataset_run_id), ("dataset CSV SHA-256", manifest.get("dataset_csv_sha256", "MISSING"))]
    if dataset_manifest:
        splits = dataset_manifest.get("split_row_counts", {})
        lineage_rows += [
            ("dataset 계약", dataset_manifest.get("schema_version", "MISSING")),
            ("universe 크기", dataset_manifest.get("universe", {}).get("size", "MISSING") if isinstance(dataset_manifest.get("universe"), Mapping) else "MISSING"),
            ("split 행수", ", ".join(f"{k}={v:,}" for k, v in splits.items()) if isinstance(splits, Mapping) else "MISSING"),
            ("dataset 생성", dataset_manifest.get("generated_utc", "MISSING")),
        ]
    missing = manifest.get("missing_h1_label_excluded")
    if isinstance(missing, Mapping):
        lineage_rows.append(("H1 라벨 결측 제외", ", ".join(f"{k}={v:,}" for k, v in sorted(missing.items()))))
    body4 = _kv_table(lineage_rows) + (
        '<p class="note">일봉 DB 가격 기준은 UNKNOWN_CONFIRMED로 feature 입력 전용이며 수익률 증거로 쓰지 않습니다. '
        "라벨·체결 권위는 5분봉 exact 15:20 proxy 단일이고 결측 봉은 결측으로 남습니다(보간·대체 없음).</p>"
    )

    # ── ⑤ accounting ─────────────────────────────────────────────────────
    body5 = _kv_table([
        ("총 자본", _won(hyper.get("capital_krw"))),
        ("슬롯", f"{hyper.get('slots', 'MISSING')}개 × {_won(hyper.get('slot_budget_krw'))} (매수비용 포함)"),
        ("최대 투입", _won(hyper.get("max_invested_krw"))),
        ("예비", _won(capital - (_num(hyper.get("max_invested_krw")) or 0.0))),
        ("비용 시나리오", f"0.00% / {primary_cost}(1차) / 0.46%(스트레스)"),
        ("NAV 산식(원문)", hyper.get("nav_formula", "MISSING")),
    ])

    # ── ⑥ algorithm ──────────────────────────────────────────────────────
    algo_rows = [(k, v) for k, v in sorted(hyper.items()) if k != "nav_formula"]
    bucket = manifest.get("bucket_boundaries")
    if isinstance(bucket, Mapping):
        algo_rows += [(f"bucket · {k}", ", ".join(f"{_num(x):.5f}" for x in v if _num(x) is not None)) for k, v in sorted(bucket.items())]
    body6 = _kv_table(algo_rows)

    # ── ⑦ learning curves ────────────────────────────────────────────────
    curve_series = [(f"seed {seed}", [float(v) for v in data.get("val_nav_curve", []) if _num(v) is not None]) for seed, data in seeds]
    body7 = _svg_line_chart(curve_series, baseline=capital, baseline_label=_won(capital)) + (
        f'<p class="note">episode별 validation NAV @{_esc(primary_cost)} (manifest val_nav_curve 원문). 점선은 원금입니다.</p>'
    )

    # ── ⑧ cost sensitivity ───────────────────────────────────────────────
    groups = []
    for seed, data in seeds:
        navs = data.get("final_val_metrics", {}).get("cost_scenario_navs", {})
        if isinstance(navs, Mapping):
            groups.append((f"seed {seed}", [(_cost_display(k), float(v)) for k, v in sorted(navs.items()) if _num(v) is not None]))
    body8 = _svg_grouped_bars(groups, baseline=capital) + '<p class="note">최종 validation NAV의 비용 3중 시나리오입니다. 0.00%는 대조 표시 전용이며 판정에 쓰지 않습니다.</p>'

    # ── ⑨ baselines & controls ───────────────────────────────────────────
    bars: list[tuple[str, float]] = []
    for seed, data in seeds:
        nav = _num(data.get("final_val_metrics", {}).get("nav"))
        if nav is not None:
            bars.append((f"policy seed {seed}", nav))
    for name in BASELINE_ORDER:
        nav = _num(baselines.get(name, {}).get("nav")) if isinstance(baselines.get(name), Mapping) else None
        if nav is not None:
            bars.append((name, nav))
    for seed, data in controls:
        nav = _num(data.get("final_val_metrics", {}).get("nav"))
        if nav is not None:
            bars.append((f"shuffled control seed {seed}", nav))
    control_rows = "".join(
        f"<tr><td>shuffled seed {_esc(seed)}</td><td>{_esc(_won(data.get('final_val_metrics', {}).get('nav')))}</td>"
        f"<td>{_esc(data.get('final_val_metrics', {}).get('trade_count', 'MISSING'))}</td>"
        f"<td><code>{_esc(str(data.get('shuffled_train_labels_sha256', 'MISSING'))[:12])}…</code></td></tr>"
        for seed, data in controls
    )
    body9 = _svg_barh_chart(bars, marker=capital, marker_label=_won(capital)) + (
        '<table><thead><tr><th>대조군</th><th>val NAV</th><th>거래수</th><th>셔플 라벨 SHA</th></tr></thead>'
        f"<tbody>{control_rows or '<tr><td colspan=4>대조군 기록 없음</td></tr>'}</tbody></table>"
        '<p class="note">대조군 절은 생략할 수 없습니다. 셔플 라벨 대조군이 no-trade를 넘으면 사전등록 규칙상 NO_GO입니다.</p>'
    )

    # ── ⑩ index overlay ──────────────────────────────────────────────────
    seed_levels = [(f"seed {seed}", _num(data.get("final_val_metrics", {}).get("nav")) or capital) for seed, data in seeds]
    index_state, body10 = _index_overlay_block(index_dir, _parse_val_window(prereg), seed_levels)

    # ── ⑪ observations (manifest facts only) ─────────────────────────────
    navs = [nav for _, nav in seed_levels]
    obs_rows: list[tuple[str, Any]] = []
    if navs:
        obs_rows += [
            ("seed 최종 val NAV 범위", f"{_won(min(navs))} ~ {_won(max(navs))} (관측 분산)"),
            ("원금(60M) 초과 seed", f"{sum(1 for n in navs if n > capital)} / {len(navs)}"),
        ]
    obs_rows += [("판정 사유(원문)", "; ".join(verdict_reasons) or "MISSING")]
    for seed, data in seeds:
        metrics = data.get("final_val_metrics", {})
        obs_rows.append((f"seed {seed} 거래/회전", f"trade {metrics.get('trade_count', 'MISSING')} · turnover days {metrics.get('turnover_days', 'MISSING')} · 최대 동시 {metrics.get('max_positions_per_session', 'MISSING')}슬롯"))
    body11 = _kv_table(obs_rows) + '<p class="note">이 절은 manifest 값의 관측 요약이며 원인 해석·개선안은 별도 사전등록 실험으로만 검증합니다.</p>'

    # ── ⑫ verdict ────────────────────────────────────────────────────────
    body12 = _kv_table([
        ("판정 후보(원문)", verdict),
        ("사유", "; ".join(verdict_reasons) or "MISSING"),
        ("untouched test", f"{test_state} · GO 후보 조건 충족 시에만 1회 개봉"),
        ("사후 재조정", "금지 · 변경은 새 사전등록 버전으로만"),
    ])

    # ── ⑬ limitations ────────────────────────────────────────────────────
    lock_list = "".join(f"<li><code>{_esc(k)}</code> = {_esc(v)}</li>" for k, v in sorted(locks.items()))
    body13 = (
        "<ul>"
        "<li>15:20 봉 종가 proxy 체결 가정이며 공식 종가·호가 체결 검증이 아닙니다.</li>"
        "<li>일봉 DB 가격 기준 UNKNOWN_CONFIRMED — feature 전용.</li>"
        "<li>H1 라벨 결측 행은 제외로 처리(위 ④), 보간 없음.</li>"
        f"<li>지수 대비 절 상태: <code>{_esc(index_state)}</code></li>"
        "</ul>"
        f"<p>여섯 안전 잠금(모두 false 유지):</p><ul>{lock_list or '<li>MISSING</li>'}</ul>"
    )

    # ── ⑭ reproduction ───────────────────────────────────────────────────
    body14 = _kv_table([
        ("학습 재현", f"py -3.11 -m stom_rl.daily_v6_train --dataset-run-id {dataset_run_id}"),
        ("보고서 재생성", f"py -3.11 -m stom_rl.v7_report_builder {run_dir.as_posix()}"),
        ("사전등록 파일", prereg_file.as_posix()),
    ])

    # ── ⑮ hash appendix ──────────────────────────────────────────────────
    hash_rows: list[tuple[str, Any]] = [
        ("run_manifest.json SHA-256", _sha256_file(manifest_path)),
        ("dataset CSV SHA-256", manifest.get("dataset_csv_sha256", "MISSING")),
        ("prereg SHA-256 (manifest)", prereg_ref.get("sha256", "MISSING")),
        ("prereg SHA-256 (파일 실측)", prereg_sha_actual or "MISSING"),
    ]
    if dataset_manifest_path.is_file():
        hash_rows.append(("dataset_manifest.json SHA-256", _sha256_file(dataset_manifest_path)))
    body15 = _kv_table(hash_rows)

    # ── ⑯ disclaimer ─────────────────────────────────────────────────────
    body16 = (
        '<div class="disclaimer"><strong>연구 전용 보고서.</strong> 본 문서는 로컬 백테스트 연구 증거이며 '
        "실거래·브로커 연동·수익성·모델 승격·paper-forward 준비 상태를 주장하지 않습니다. "
        "판정 토큰은 사전등록 규칙의 원문이며 어떤 시각화도 판정을 대체하지 않습니다.</div>"
    )

    sections = [
        _section(2, "경영 요약", body2),
        _section(3, "연구 질문과 사전등록", body3),
        _section(4, "데이터 계보", body4),
        _section(5, "환경·회계", body5),
        _section(6, "알고리즘·하이퍼파라미터", body6),
        _section(7, "학습 곡선", body7),
        _section(8, "비용 민감도", body8),
        _section(9, "기준선·음성 대조군", body9),
        _section(10, "KOSPI/KOSDAQ 대비", body10),
        _section(11, "관측 요약(구조 해석 입력)", body11),
        _section(12, "판정과 근거", body12),
        _section(13, "한계·안전 잠금", body13),
        _section(14, "재현 명령", body14),
        _section(15, "artifact 해시 부록", body15),
        _section(16, "면책", body16),
    ]
    toc = "<nav><ol>" + "".join(f'<li><a href="#s{i}">{_esc(t)}</a></li>' for i, t in enumerate((
        "경영 요약", "연구 질문과 사전등록", "데이터 계보", "환경·회계", "알고리즘·하이퍼파라미터",
        "학습 곡선", "비용 민감도", "기준선·음성 대조군", "KOSPI/KOSDAQ 대비", "관측 요약",
        "판정과 근거", "한계·안전 잠금", "재현 명령", "artifact 해시 부록", "면책"), start=2)) + "</ol></nav>"

    html_text = (
        "<!DOCTYPE html>"
        f'<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)} · Kronos 연구 보고서</title><style>{_CSS}</style></head>"
        f'<body><div class="page">{hero}<section id="s1"><div class="band"><span>목차</span><h2>보고서 구성</h2></div>{toc}</section>'
        + "".join(sections)
        + "</div></body></html>"
    )

    report_path = run_dir / "report.html"
    report_path.write_text(html_text, encoding="utf-8")
    report_sha = _sha256_file(report_path)
    report_manifest = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "generated_utc": generated_utc,
        "run_id": run_id,
        "dataset_run_id": dataset_run_id,
        "verdict": verdict,
        "test_state": test_state,
        "index_overlay_state": index_state,
        "prereg_match": prereg_match,
        "report_sha256": report_sha,
        "source_sha256": {
            "run_manifest": _sha256_file(manifest_path),
            "dataset_manifest": _sha256_file(dataset_manifest_path) if dataset_manifest_path.is_file() else None,
            "prereg": prereg_sha_actual,
        },
        "false_research_locks": dict(locks),
    }
    (run_dir / "report_manifest.json").write_text(
        json.dumps(report_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report_manifest


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportBuildError(f"project sidecar {field} must be a non-empty string")
    return value


def _six_false_locks(value: Any, run_dir: Path) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != set(SIX_FALSE_LOCKS) or any(value[name] is not False for name in SIX_FALSE_LOCKS):
        raise ReportBuildError(f"run {run_dir} must record exactly the six false research locks")
    return {name: False for name in SIX_FALSE_LOCKS}


def _project_prereg(cycle: Mapping[str, Any], sidecar_dir: Path, cycle_id: str) -> tuple[Path, str]:
    prereg = cycle.get("prereg")
    if isinstance(prereg, Mapping):
        path_value, expected_sha = prereg.get("path"), prereg.get("sha256")
    else:
        path_value, expected_sha = cycle.get("prereg_path"), cycle.get("prereg_sha256")
    prereg_path = (sidecar_dir / _required_text(path_value, f"cycles[{cycle_id}].prereg.path")).resolve()
    expected_sha = _required_text(expected_sha, f"cycles[{cycle_id}].prereg.sha256")
    if len(expected_sha) != 64 or any(char not in "0123456789abcdef" for char in expected_sha.lower()):
        raise ReportBuildError(f"project sidecar cycles[{cycle_id}] prereg SHA-256 is invalid")
    if not prereg_path.is_file():
        raise ReportBuildError(f"project sidecar preregistration not found: {prereg_path}")
    if _sha256_file(prereg_path) != expected_sha:
        raise ReportBuildError(f"project sidecar preregistration SHA-256 mismatch: {prereg_path}")
    return prereg_path, expected_sha


def _comparison_key(manifest: Mapping[str, Any]) -> tuple[Any, ...]:
    hyper = manifest.get("hyperparams")
    hyper = hyper if isinstance(hyper, Mapping) else {}
    return (manifest.get("schema_version"), manifest.get("dataset_run_id"), hyper.get("capital_krw"),
            hyper.get("slots"), hyper.get("primary_cost_rate"))


_PROJECT_CSS = """
:root{color-scheme:light}body{margin:0;background:#f8fafc;color:#0f172a;font:16px/1.55 system-ui,sans-serif}
.page{max-width:1100px;margin:auto;padding:28px}.hero,.panel{background:#fff;border:1px solid #cbd5e1;border-radius:16px;padding:26px;box-shadow:0 14px 35px rgba(15,23,42,.07)}
.hero{background:linear-gradient(135deg,#0f172a 0%,#172554 55%,#164e63 100%);color:#e2e8f0}.hero h1{margin:8px 0;font-size:clamp(1.8rem,4vw,2.6rem)}.meta{color:#64748b}.hero .meta{color:#bae6fd}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}.kpi{border:1px solid #dbeafe;border-radius:12px;padding:14px;background:linear-gradient(145deg,#eff6ff,#f8fafc)}.kpi strong{display:block;font-size:1.5rem;color:#1e3a8a}.kpi small{color:#64748b}.status{display:inline-block;border-radius:999px;padding:4px 10px;font-size:.76rem;font-weight:900;white-space:nowrap}.status.danger{background:#dc2626;color:#fff}.status.warn{background:#f59e0b;color:#1c1917}.status.muted{background:#64748b;color:#fff}.cycle-index{display:grid;width:30px;height:30px;place-items:center;border-radius:50%;background:#dbeafe;color:#1d4ed8;font-weight:900}
.tabs input{position:absolute;opacity:0}.tabs label{display:inline-block;margin:16px 6px 0 0;padding:9px 14px;border:1px solid #94a3b8;border-radius:8px 8px 0 0;font-weight:700;cursor:pointer}.tabs input:focus-visible+label{outline:3px solid #f59e0b;outline-offset:2px}
.panels{margin-top:16px}.panel{display:none}.tabs #tab-summary:checked~.panels #panel-summary,.tabs #tab-cycles:checked~.panels #panel-cycles,.tabs #tab-comparison:checked~.panels #panel-comparison,.tabs #tab-traceability:checked~.panels #panel-traceability,.tabs #tab-integrity:checked~.panels #panel-integrity{display:block}
.tabs #tab-summary:checked~label[for=tab-summary],.tabs #tab-cycles:checked~label[for=tab-cycles],.tabs #tab-comparison:checked~label[for=tab-comparison],.tabs #tab-traceability:checked~label[for=tab-traceability],.tabs #tab-integrity:checked~label[for=tab-integrity]{background:#2563eb;color:#fff}
table{width:100%;border-collapse:collapse}th,td{border-top:1px solid #cbd5e1;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}thead th{border-top:0;color:#475569;font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}tbody tr:hover{background:#f8fafc}code{overflow-wrap:anywhere}.panel{overflow-x:auto}.danger{color:#b91c1c;font-weight:800}.verdict{font-weight:900}.notice{border-left:4px solid #dc2626;padding:10px;background:#fef2f2}@media(max-width:600px){.page{padding:12px}.hero,.panel{padding:16px}.tabs label{margin-top:8px;padding:8px 10px}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}@media print{.panel{display:block!important;box-shadow:none}.tabs label{display:none}}
"""


def build_project_report(sidecar_path: str | Path, output_dir: str | Path, *, now_utc: str | None = None) -> dict[str, Any]:
    """Build a deterministic V2 project report from an authoritative project sidecar."""
    sidecar_file = Path(sidecar_path).resolve()
    sidecar = _read_json(sidecar_file)
    if sidecar.get("schema_version") != PROJECT_SIDECAR_SCHEMA_VERSION:
        raise ReportBuildError(f"project sidecar schema_version must be {PROJECT_SIDECAR_SCHEMA_VERSION}")
    project_id = _required_text(sidecar.get("project_id"), "project_id")
    title = _required_text(sidecar.get("title"), "title")
    cycles = sidecar.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        raise ReportBuildError("project sidecar cycles must be a non-empty ordered list")

    sidecar_dir = sidecar_file.parent
    records: list[dict[str, Any]] = []
    seen_cycle_ids: set[str] = set()
    seen_orders: set[int] = set()
    for cycle in cycles:
        if not isinstance(cycle, Mapping):
            raise ReportBuildError("project sidecar cycle must be an object")
        cycle_id = _required_text(cycle.get("cycle_id"), "cycles[].cycle_id")
        title_value = _required_text(cycle.get("title"), f"cycles[{cycle_id}].title")
        hypothesis_delta = _required_text(cycle.get("hypothesis_delta"), f"cycles[{cycle_id}].hypothesis_delta")
        order = cycle.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ReportBuildError(f"project sidecar cycles[{cycle_id}].order must be a positive integer")
        if cycle_id in seen_cycle_ids or order in seen_orders:
            raise ReportBuildError("project sidecar cycle_id and order values must be unique")
        seen_cycle_ids.add(cycle_id)
        seen_orders.add(order)
        prereg_path, prereg_sha = _project_prereg(cycle, sidecar_dir, cycle_id)
        run_refs = cycle.get("run_dirs")
        if not isinstance(run_refs, list) or not run_refs or any(not isinstance(item, str) or not item for item in run_refs):
            raise ReportBuildError(f"project sidecar cycles[{cycle_id}].run_dirs must be a non-empty list of paths")
        runs: list[dict[str, Any]] = []
        for run_ref in run_refs:
            run_dir = (sidecar_dir / run_ref).resolve()
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.is_file():
                raise ReportBuildError(f"run_manifest.json not found in {run_dir}")
            manifest = _read_json(manifest_path)
            locks = _six_false_locks(manifest.get("false_research_locks"), run_dir)
            prereg_ref = manifest.get("prereg")
            if not isinstance(prereg_ref, Mapping) or prereg_ref.get("sha256") != prereg_sha:
                raise ReportBuildError(f"run {run_dir} preregistration SHA-256 does not match cycle {cycle_id}")
            verdict_obj = manifest.get("verdict_candidate")
            verdict = str(verdict_obj.get("value")) if isinstance(verdict_obj, Mapping) else "MISSING"
            test = manifest.get("test")
            test_state = str(test.get("state", "MISSING")) if isinstance(test, Mapping) else "MISSING"
            metrics = []
            for seed, seed_data in _seed_items(manifest.get("per_seed")):
                final = seed_data.get("final_val_metrics")
                metrics.append({"seed": seed, "val_nav": final.get("nav", "MISSING") if isinstance(final, Mapping) else "MISSING"})
            dataset_manifest = run_dir.parent / "dataset_manifest.json"
            runs.append({
                "run_ref": run_ref,
                "run_manifest_path": manifest_path,
                "dataset_manifest_path": dataset_manifest if dataset_manifest.is_file() else None,
                "dataset_run_id": str(manifest.get("dataset_run_id", run_dir.parent.name)),
                "train_run_id": run_dir.name,
                "verdict": verdict,
                "test_state": test_state,
                "metrics": metrics,
                "locks": locks,
                "comparison_key": _comparison_key(manifest),
            })
        records.append({"cycle_id": cycle_id, "order": order, "title": title_value, "hypothesis_delta": hypothesis_delta,
                        "prereg_path": prereg_path, "prereg_sha256": prereg_sha, "runs": runs})
    if [record["order"] for record in records] != sorted(record["order"] for record in records):
        raise ReportBuildError("project sidecar cycles must be ordered by ascending order")

    generated_utc = now_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    flat_runs = [run for record in records for run in record["runs"]]
    reference = flat_runs[0]
    cycle_rows = "".join(
        f"<tr><td><span class=cycle-index>{record['order']}</span></td><td><strong>{_esc(record['cycle_id'])}</strong></td><td>{_esc(record['title'])}</td><td>{_esc(record['hypothesis_delta'])}</td><td>{len(record['runs'])}</td></tr>"
        for record in records
    )
    def render_metrics(run: Mapping[str, Any]) -> str:
        return ", ".join(f"seed {metric['seed']}: {_won(metric['val_nav'])}" for metric in run["metrics"]) or "MISSING"
    run_rows = "".join(
        f"<tr><td><strong>{_esc(record['cycle_id'])}</strong></td><td><code>{_esc(run['dataset_run_id'])}<br>{_esc(run['train_run_id'])}</code></td><td><span class='status {_verdict_tone(run['verdict'])}'>{_esc(run['verdict'])}</span></td><td><span class='status muted'>{_esc(run['test_state'])}</span></td><td>{_esc(render_metrics(run))}</td></tr>"
        for record in records for run in record["runs"]
    )
    comparison_rows = "".join(
        f"<tr><td><code>{_esc(run['run_ref'])}</code></td><td>{'COMPATIBLE' if run['comparison_key'] == reference['comparison_key'] else '<span class=danger>INCOMPATIBLE</span>'}</td><td>{_esc('same comparison contract as ' + reference['run_ref'] if run['comparison_key'] == reference['comparison_key'] else 'dataset/schema/capital/slots/cost contract differs; no cross-run metric comparison')}</td></tr>"
        for run in flat_runs
    )
    trace_rows = "".join(
        f"<tr><td>{_esc(record['cycle_id'])}</td><td><code>{_esc(record['prereg_path'])}</code></td><td><code>{record['prereg_sha256']}</code></td></tr>"
        for record in records
    )
    source_rows = [("project sidecar", sidecar_file, _sha256_file(sidecar_file))]
    source_rows += [(f"{record['cycle_id']} preregistration", record["prereg_path"], record["prereg_sha256"]) for record in records]
    for run in flat_runs:
        source_rows.append((f"{run['run_ref']} run_manifest", run["run_manifest_path"], _sha256_file(run["run_manifest_path"])))
        if run["dataset_manifest_path"] is not None:
            source_rows.append((f"{run['run_ref']} dataset_manifest", run["dataset_manifest_path"], _sha256_file(run["dataset_manifest_path"])))
    source_html = "".join(f"<tr><td>{_esc(label)}</td><td><code>{_esc(path)}</code></td><td><code>{sha}</code></td></tr>" for label, path, sha in source_rows)
    lock_html = "".join(f"<tr><td><code>{_esc(run['run_ref'])}</code></td><td>{_esc(', '.join(f'{name}=False' for name in SIX_FALSE_LOCKS))}</td></tr>" for run in flat_runs)
    html_text = (
        "<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(title)} · Kronos project report</title><style>{_PROJECT_CSS}</style></head><body><main class=page>"
        f"<header class=hero><p>KRONOS PROJECT REPORT V2 · RESEARCH_ONLY</p><h1>{_esc(title)}</h1><p class=meta>{_esc(project_id)} · generated {generated_utc}</p><p>NO LIVE · NO BROKER / ORDER · NO PROFIT CLAIM · OOS remains closed unless each source manifest states otherwise.</p></header>"
        '<div class=tabs><input type=radio name=tabs id=tab-summary checked><label for=tab-summary>Summary</label><input type=radio name=tabs id=tab-cycles><label for=tab-cycles>Cycles</label><input type=radio name=tabs id=tab-comparison><label for=tab-comparison>Comparison</label><input type=radio name=tabs id=tab-traceability><label for=tab-traceability>Traceability</label><input type=radio name=tabs id=tab-integrity><label for=tab-integrity>Integrity</label><div class=panels>'
        f'<section class=panel id=panel-summary><h2>Summary</h2><p>{len(records)} ordered cycles · {len(flat_runs)} source runs. Verdict and OOS state are copied verbatim from source manifests.</p><div class=kpis><div class=kpi><strong>{len(records)}</strong><small>ordered cycles</small></div><div class=kpi><strong>{len(flat_runs)}</strong><small>source runs</small></div><div class=kpi><strong>{sum(1 for run in flat_runs if run["verdict"] == "NO_GO")}</strong><small>NO_GO cycles</small></div><div class=kpi><strong>{sum(1 for run in flat_runs if run["test_state"] == "NOT_RUN")}</strong><small>untouched OOS closed</small></div></div><table><thead><tr><th>Cycle</th><th>Run</th><th>Verdict</th><th>OOS state</th><th>Validation NAV</th></tr></thead><tbody>{run_rows}</tbody></table></section>'
        f'<section class=panel id=panel-cycles><h2>Cycles</h2><table><thead><tr><th>Order</th><th>Cycle ID</th><th>Title</th><th>Hypothesis delta</th><th>Runs</th></tr></thead><tbody>{cycle_rows}</tbody></table></section>'
        f'<section class=panel id=panel-comparison><h2>Comparison</h2><p class=notice>Only COMPATIBLE runs may be compared. INCOMPATIBLE runs are displayed but not scored or ranked.</p><table><thead><tr><th>Run</th><th>State</th><th>Reason</th></tr></thead><tbody>{comparison_rows}</tbody></table></section>'
        f'<section class=panel id=panel-traceability><h2>Traceability</h2><table><thead><tr><th>Cycle</th><th>Authoritative preregistration source</th><th>SHA-256</th></tr></thead><tbody>{trace_rows}</tbody></table></section>'
        f'<section class=panel id=panel-integrity><h2>Integrity</h2><p>Exact six-false-lock state is required for every source run.</p><table><thead><tr><th>Run</th><th>Locks</th></tr></thead><tbody>{lock_html}</tbody></table><h3>All source hashes</h3><table><thead><tr><th>Source</th><th>Path</th><th>SHA-256</th></tr></thead><tbody>{source_html}</tbody></table></section>'
        "</div></div></main></body></html>"
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "project_report.html"
    report_path.write_text(html_text, encoding="utf-8")
    report_sha = _sha256_file(report_path)
    report_manifest = {
        "schema_version": PROJECT_REPORT_SCHEMA_VERSION,
        "builder_version": PROJECT_BUILDER_VERSION,
        "generated_utc": generated_utc,
        "project_id": project_id,
        "title": title,
        "report_sha256": report_sha,
        "source_sha256": [{"label": label, "path": str(path), "sha256": sha} for label, path, sha in source_rows],
        "cycle_count": len(records),
        "run_count": len(flat_runs),
        "verdicts": sorted({str(run["verdict"]) for run in flat_runs}),
        "test_states": sorted({str(run["test_state"]) for run in flat_runs}),
        "cycles": [
            {
                "cycle_id": record["cycle_id"],
                "order": record["order"],
                "title": record["title"],
                "hypothesis_delta": record["hypothesis_delta"],
                "prereg_sha256": record["prereg_sha256"],
                "runs": [
                    {
                        "run_ref": run["run_ref"],
                        "dataset_run_id": run["dataset_run_id"],
                        "train_run_id": run["train_run_id"],
                        "verdict": run["verdict"],
                        "test_state": run["test_state"],
                        "comparison_state": "COMPARABLE" if run["comparison_key"] == reference["comparison_key"] else "INCOMPARABLE",
                    }
                    for run in record["runs"]
                ],
            }
            for record in records
        ],
        "false_research_locks": {name: False for name in SIX_FALSE_LOCKS},
    }
    (output_path / "project_report_manifest.json").write_text(json.dumps(report_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build self-contained HTML research reports for run directories.")
    parser.add_argument("run_dirs", nargs="*", help="run directories containing run_manifest.json")
    parser.add_argument("--project-sidecar", default=None, help="project report V2 sidecar JSON path")
    parser.add_argument("--project-output-dir", default=None, help="project report V2 output directory")
    parser.add_argument("--prereg", default=None, help="preregistration JSON path (default: H1 prereg)")
    parser.add_argument("--index-artifact-dir", default=None, help="offline index artifact directory")
    args = parser.parse_args(argv)
    if args.project_sidecar:
        if args.run_dirs or not args.project_output_dir:
            parser.error("--project-sidecar requires --project-output-dir and no run directories")
        summary = build_project_report(args.project_sidecar, args.project_output_dir)
        print(json.dumps({k: summary[k] for k in ("project_id", "report_sha256")}, ensure_ascii=False))
        return 0
    if not args.run_dirs:
        parser.error("at least one run directory is required unless --project-sidecar is provided")
    for run_dir in args.run_dirs:
        summary = build_report(run_dir, prereg_path=args.prereg, index_artifact_dir=args.index_artifact_dir)
        print(json.dumps({k: summary[k] for k in ("run_id", "verdict", "index_overlay_state", "report_sha256")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

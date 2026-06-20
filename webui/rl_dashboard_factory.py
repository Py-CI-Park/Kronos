"""Read-only STOM model-factory dashboard helpers.

Honesty guardrails: this module is a read-only evidence viewer for the model
factory registry and probability-lane artifacts. It never writes registry
rows, never places orders, and makes no profit or live-readiness claim.
Net pct figures in lane artifacts are stated at the 23bp round-trip cost
assumption. Rule baselines (e.g. ``ts_imb``) are RULE baselines, not RL.
"""

from __future__ import annotations

import json
import sqlite3
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

WEBUI_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WEBUI_ROOT.parent
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - mirrors webui/app.py
    sys.path.append(str(REPO_ROOT))

FACTORY_REGISTRY_PATH = Path('webui') / 'rl_runs' / 'factory_registry.sqlite'
PROBABILITY_LANE_ROOT = Path('webui') / 'rl_runs' / 'probability_lane'
SIZING_LAB_ROOT = Path('webui') / 'rl_runs' / 'sizing_lab'
FORWARD_LEDGER_ROOT = Path('webui') / 'rl_runs' / 'forward_ledger'
RISK_POLICY_ROOT = Path('webui') / 'rl_runs' / 'risk_policy_lab'
FRESH_VALIDATION_ROOT = Path('webui') / 'rl_runs' / 'fresh_policy_validation'

GUARDRAIL = (
    "Read-only research evidence viewer — no profit claim, no live-readiness "
    "claim. Net pct values are stated at the 23bp round-trip cost assumption; "
    "rule baselines are RULE baselines, not RL."
)

_RUN_NAME_RE = re.compile(r'^[A-Za-z0-9_\-]+$')
_VALID_DECISIONS = ('TAKE', 'SKIP')
_MAX_LEDGER_LIMIT = 5000
_DEFAULT_LEDGER_LIMIT = 500


def _resolve_path(override: Optional[Path | str], default: Path) -> Path:
    """Resolve an optional override (tests) or anchor the default at REPO_ROOT."""
    path = Path(override) if override is not None else Path(default)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _safe_run_dir(run_name: str, root: Path) -> Path:
    """Return ``root/run_name`` after rejecting traversal-capable names."""
    if not isinstance(run_name, str) or not _RUN_NAME_RE.match(run_name):
        raise ValueError(f"invalid run name: {run_name!r}")
    resolved_root = Path(root).resolve()
    candidate = (resolved_root / run_name).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        raise ValueError(f"run name escapes lane root: {run_name!r}") from None
    if candidate == resolved_root:
        raise ValueError(f"invalid run name: {run_name!r}")
    return candidate


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected JSON payload shape in {path.name}")
    return payload


def _mean(values: List[Any]) -> Optional[float]:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 6)
_READ_ONLY_DASHBOARD_NOTE = (
    "Dashboard consumption is read-only: no training, no orders, no registry writes "
    "from webui. Research tracking only — no profit claim."
)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _readonly_registry_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fill_mode_from_run(run_name: str, payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if isinstance(payload, dict):
        fill_mode = payload.get('fill_mode') or payload.get('fill_assumption')
        if fill_mode:
            return str(fill_mode)
    if '_realized_full_' in run_name or run_name.endswith('_realized_full'):
        return 'realized_full'
    if '_slgap_full_' in run_name or run_name.endswith('_slgap_full'):
        return 'slgap_full'
    return None


def _nested_number(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if isinstance(cur, (int, float)) and not isinstance(cur, bool):
        return float(cur)
    return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _status_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        status = str(row.get('outcome_status') or 'unknown')
        counts[status] = counts.get(status, 0) + 1
    return counts




def load_factory_queue(registry_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Read-only snapshot of the factory experiment queue registry."""
    path = _resolve_path(registry_path, FACTORY_REGISTRY_PATH)
    if not path.is_file():
        return {
            'available': False,
            'reason': 'registry_not_found',
            'registry_path': str(path),
            'guardrail': GUARDRAIL,
        }

    try:
        with _readonly_registry_connection(path) as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'runs'"
            ).fetchone()
            if table is None:
                return {
                    'available': False,
                    'reason': 'registry_table_not_found',
                    'registry_path': str(path),
                    'guardrail': GUARDRAIL,
                    'read_only_dashboard_note': _READ_ONLY_DASHBOARD_NOTE,
                }
            rows = conn.execute("SELECT status, COUNT(*) AS n FROM runs GROUP BY status").fetchall()
            latest_rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_utc DESC, rowid DESC LIMIT 20"
            ).fetchall()
    except sqlite3.Error as exc:
        return {
            'available': False,
            'reason': 'registry_read_error',
            'registry_path': str(path),
            'error': str(exc),
            'guardrail': GUARDRAIL,
            'read_only_dashboard_note': _READ_ONLY_DASHBOARD_NOTE,
        }

    counts = {status: 0 for status in ("queued", "running", "done", "failed")}
    for row in rows:
        counts[row["status"]] = int(row["n"])
    return {
        'available': True,
        'guardrail': GUARDRAIL,
        'registry_path': str(path),
        'counts_by_status': counts,
        'latest_runs': [_row_to_dict(row) for row in latest_rows],
        'read_only_dashboard_note': _READ_ONLY_DASHBOARD_NOTE,
    }


def load_lane_calibration(run_name: str, *, root: Optional[Path | str] = None) -> Dict[str, Any]:
    """Read ``calibration.json`` for a probability-lane run."""
    run_dir = _safe_run_dir(run_name, _resolve_path(root, PROBABILITY_LANE_ROOT))
    path = run_dir / 'calibration.json'
    if not path.is_file():
        return {
            'available': False,
            'reason': 'calibration_not_found',
            'run': run_name,
            'guardrail': GUARDRAIL,
        }
    payload = _read_json(path)
    return {'available': True, 'run': run_name, 'guardrail': GUARDRAIL, **payload}


def load_lane_edge_ledger(
    run_name: str,
    *,
    root: Optional[Path | str] = None,
    limit: int = _DEFAULT_LEDGER_LIMIT,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    """Read ``edge_ledger.json`` with a server-computed summary.

    The summary is computed over the full ledger so the UI never invents
    trading interpretations; ``rows`` is the (optionally decision-filtered)
    list truncated to ``limit``.
    """
    run_dir = _safe_run_dir(run_name, _resolve_path(root, PROBABILITY_LANE_ROOT))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_LEDGER_LIMIT
    limit = max(0, min(limit, _MAX_LEDGER_LIMIT))

    if decision is not None:
        decision = str(decision).upper()
        if decision not in _VALID_DECISIONS:
            raise ValueError(f"invalid decision filter: {decision!r} (use TAKE or SKIP)")

    path = run_dir / 'edge_ledger.json'
    if not path.is_file():
        return {
            'available': False,
            'reason': 'edge_ledger_not_found',
            'run': run_name,
            'guardrail': GUARDRAIL,
        }
    payload = _read_json(path)
    all_rows = [row for row in payload.get('rows') or [] if isinstance(row, dict)]
    take_rows = [row for row in all_rows if row.get('decision') == 'TAKE']
    skip_rows = [row for row in all_rows if row.get('decision') == 'SKIP']

    summary = {
        'total_rows': len(all_rows),
        'take_count': len(take_rows),
        'skip_count': len(skip_rows),
        'take_mean_net_pct': _mean([row.get('net_pct_23bp') for row in take_rows]),
        'skip_mean_net_pct': _mean([row.get('net_pct_23bp') for row in skip_rows]),
        'mean_edge_pct': _mean([row.get('edge_pct') for row in all_rows]),
        'breakeven_note': payload.get('breakeven_note'),
        'cost_note': 'net pct values are at 23bp round-trip cost',
    }

    filtered = [row for row in all_rows if row.get('decision') == decision] if decision else all_rows
    return {
        'available': True,
        'run': run_name,
        'guardrail': GUARDRAIL,
        'summary': summary,
        'decision_filter': decision,
        'returned_rows': min(limit, len(filtered)),
        'rows': filtered[:limit],
    }


def list_lane_runs(root: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """List probability-lane run directories, newest summary mtime first."""
    base = _resolve_path(root, PROBABILITY_LANE_ROOT)
    if not base.is_dir():
        return []
    entries: List[tuple[float, Dict[str, Any]]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        summary_path = child / 'probability_lane_summary.json'
        if not summary_path.is_file():
            continue
        try:
            payload = json.loads(summary_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        calibration = payload.get('calibration')
        if not isinstance(calibration, dict):
            calibration = {}
        aggregate = payload.get('aggregate')
        if not isinstance(aggregate, dict):
            aggregate = {}
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        entries.append(
            (
                mtime,
                {
                    'run': child.name,
                    'verdict': payload.get('verdict'),
                    'mode': payload.get('mode'),
                    'strategy_label': payload.get('strategy_label'),
                    'fill_mode': payload.get('fill_mode'),
                    'cost_bps': payload.get('cost_bps'),
                    'seed': payload.get('seed'),
                    'split_seed': (payload.get('split') or {}).get('split_seed') if isinstance(payload.get('split'), dict) else None,
                    'split_hash': (payload.get('split') or {}).get('split_hash') if isinstance(payload.get('split'), dict) else None,
                    'parent_run': payload.get('parent_run'),
                    'prereg_doc': payload.get('prereg_doc'),
                    'oos_take_count': payload.get('oos_take_count', aggregate.get('oos_take_count')),
                    'oos_take_mean_net_pct': aggregate.get('oos_take_mean_net_pct'),
                    'oos_take_total_net_pct': aggregate.get('oos_take_total_net_pct'),
                    'take_all_mean_net_pct': aggregate.get('take_all_mean_net_pct'),
                    'ts_imb_mean_net_pct': aggregate.get('ts_imb_mean_net_pct'),
                    'ts_imb_count': aggregate.get('ts_imb_count'),
                    'ts_imb_total_net_pct': (
                        float(aggregate.get('ts_imb_mean_net_pct')) * float(aggregate.get('ts_imb_count'))
                        if isinstance(aggregate.get('ts_imb_mean_net_pct'), (int, float)) and isinstance(aggregate.get('ts_imb_count'), (int, float))
                        else None
                    ),
                    'skipped_count': aggregate.get('skipped_count'),
                    'skipped_mean_net_pct': aggregate.get('skipped_mean_net_pct'),
                    'mean_trade_delta_pct': (
                        float(aggregate.get('oos_take_mean_net_pct')) - float(aggregate.get('ts_imb_mean_net_pct'))
                        if isinstance(aggregate.get('oos_take_mean_net_pct'), (int, float)) and isinstance(aggregate.get('ts_imb_mean_net_pct'), (int, float))
                        else None
                    ),
                    'total_pp_delta': (
                        float(aggregate.get('oos_take_total_net_pct')) - float(aggregate.get('ts_imb_mean_net_pct')) * float(aggregate.get('ts_imb_count'))
                        if isinstance(aggregate.get('oos_take_total_net_pct'), (int, float))
                        and isinstance(aggregate.get('ts_imb_mean_net_pct'), (int, float))
                        and isinstance(aggregate.get('ts_imb_count'), (int, float))
                        else None
                    ),
                    'brier': payload.get('brier', aggregate.get('brier', calibration.get('brier'))),
                    'brier_constant': aggregate.get('brier_constant', calibration.get('brier_constant')),
                    'consistent_folds': (payload.get('gates') or {}).get('consistent_folds') if isinstance(payload.get('gates'), dict) else None,
                    'ablations_better_than_full': (payload.get('gates') or {}).get('ablations_better_than_full') if isinstance(payload.get('gates'), dict) else None,
                    'blocking_reasons': (payload.get('gates') or {}).get('blocking_reasons') if isinstance(payload.get('gates'), dict) else [],
                    'control_brier': (payload.get('shuffled_label_control') or {}).get('brier') if isinstance(payload.get('shuffled_label_control'), dict) else None,
                    'control_oos_take_mean_net_pct': (payload.get('shuffled_label_control') or {}).get('oos_take_mean_net_pct') if isinstance(payload.get('shuffled_label_control'), dict) else None,
                    'guardrail': payload.get('guardrail', GUARDRAIL),
                },
            )
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries]


def list_sizing_runs(root: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """List stacked sizing/risk lab summaries, newest first."""
    base = _resolve_path(root, SIZING_LAB_ROOT)
    if not base.is_dir():
        return []
    entries: List[tuple[float, Dict[str, Any]]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        summary_path = child / 'sizing_summary.json'
        if not summary_path.is_file():
            continue
        try:
            payload = _read_json(summary_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if payload.get('artifact_type') != 'stacked_sizing_risk_lab':
            continue
        comparison = payload.get('comparison') if isinstance(payload.get('comparison'), dict) else {}
        strategy = payload.get('strategy') if isinstance(payload.get('strategy'), dict) else {}
        baseline = payload.get('baseline') if isinstance(payload.get('baseline'), dict) else {}
        p5 = payload.get('p5_prerequisite') if isinstance(payload.get('p5_prerequisite'), dict) else {}
        basis_key = str(comparison.get('basis_fraction', 0.5))
        strategy_basis = (strategy.get('fixed_fraction') or {}).get(basis_key, {}) if isinstance(strategy.get('fixed_fraction'), dict) else {}
        baseline_basis = (baseline.get('fixed_fraction') or {}).get(basis_key, {}) if isinstance(baseline.get('fixed_fraction'), dict) else {}
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        p5_met = bool(p5.get('account_level_risk_adjusted_improvement'))
        entries.append(
            (
                mtime,
                {
                    'run': child.name,
                    'artifact_type': payload.get('artifact_type'),
                    'input_kind': payload.get('input_kind'),
                    'fill_mode': _fill_mode_from_run(child.name, payload),
                    'strategy_label': payload.get('strategy_label'),
                    'baseline_label': payload.get('baseline_label'),
                    'guardrail': payload.get('guardrail', GUARDRAIL),
                    'cost_note': payload.get('cost_note'),
                    'edge_ledger_path': payload.get('edge_ledger_path'),
                    'strategy_trade_count': strategy.get('n_trades'),
                    'baseline_trade_count': baseline.get('n_trades'),
                    'strategy_session_count': strategy.get('n_sessions'),
                    'baseline_session_count': baseline.get('n_sessions'),
                    'basis_fraction': comparison.get('basis_fraction'),
                    'strategy_total_pct': comparison.get('strategy_total_pct'),
                    'baseline_total_pct': comparison.get('baseline_total_pct'),
                    'total_pct_delta': comparison.get('total_pct_delta'),
                    'strategy_max_drawdown_pct': comparison.get('strategy_max_drawdown_pct'),
                    'baseline_max_drawdown_pct': comparison.get('baseline_max_drawdown_pct'),
                    'max_drawdown_delta': comparison.get('max_drawdown_delta'),
                    'strategy_risk_adjusted_mean_over_std': comparison.get('strategy_risk_adjusted_mean_over_std'),
                    'baseline_risk_adjusted_mean_over_std': comparison.get('baseline_risk_adjusted_mean_over_std'),
                    'risk_adjusted_improvement': comparison.get('risk_adjusted_improvement'),
                    'drawdown_improvement': comparison.get('drawdown_improvement'),
                    'strategy_mean_trade_pct': strategy_basis.get('mean_trade_pct'),
                    'baseline_mean_trade_pct': baseline_basis.get('mean_trade_pct'),
                    'mean_trade_delta_pct': (
                        float(strategy_basis.get('mean_trade_pct')) - float(baseline_basis.get('mean_trade_pct'))
                        if isinstance(strategy_basis.get('mean_trade_pct'), (int, float)) and isinstance(baseline_basis.get('mean_trade_pct'), (int, float))
                        else None
                    ),
                    'strategy_capacity_skipped': _nested_number(strategy, 'capacity_cap', 'trades_skipped_capacity'),
                    'baseline_capacity_skipped': _nested_number(baseline, 'capacity_cap', 'trades_skipped_capacity'),
                    'strategy_daily_halt_5_total_pct': _nested_number(strategy, 'daily_halt', '5.0', 'total_pct'),
                    'baseline_daily_halt_5_total_pct': _nested_number(baseline, 'daily_halt', '5.0', 'total_pct'),
                    'strategy_daily_halt_5_sessions': _nested_number(strategy, 'daily_halt', '5.0', 'sessions_halted'),
                    'baseline_daily_halt_5_sessions': _nested_number(baseline, 'daily_halt', '5.0', 'sessions_halted'),
                    'strategy_worst_session_net_pct': _nested_number(strategy, 'worst_session', 'net_pct'),
                    'baseline_worst_session_net_pct': _nested_number(baseline, 'worst_session', 'net_pct'),
                    'p5_prerequisite_met': p5_met,
                    'p5_status': 'P5_PREREQUISITE_MET' if p5_met else 'P5_BLOCKED_BY_P2',
                    'p5_note': p5.get('note'),
                },
            )
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries]


def list_risk_policy_runs(root: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """List deterministic risk-policy lab summaries, newest first."""
    base = _resolve_path(root, RISK_POLICY_ROOT)
    if not base.is_dir():
        return []
    entries: List[tuple[float, Dict[str, Any]]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        summary_path = child / 'summary.json'
        if not summary_path.is_file():
            continue
        try:
            payload = _read_json(summary_path)
            mtime = summary_path.stat().st_mtime
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if payload.get('artifact_type') != 'risk_policy_lab':
            continue
        best = payload.get('best') if isinstance(payload.get('best'), dict) else {}
        policy = best.get('policy') if isinstance(best.get('policy'), dict) else {}
        comparison = best.get('comparison') if isinstance(best.get('comparison'), dict) else {}
        baseline = payload.get('baseline') if isinstance(payload.get('baseline'), dict) else {}
        gate = payload.get('gate') if isinstance(payload.get('gate'), dict) else {}
        entries.append(
            (
                mtime,
                {
                    'run': child.name,
                    'run_id': payload.get('run_id', child.name),
                    'artifact_type': payload.get('artifact_type'),
                    'fill_mode': _fill_mode_from_run(child.name, payload),
                    'input_kind': payload.get('input_kind'),
                    'strategy_label': payload.get('strategy_label'),
                    'baseline_label': payload.get('baseline_label'),
                    'guardrail': payload.get('guardrail', GUARDRAIL),
                    'cost_bps': payload.get('cost_bps'),
                    'basis_fraction': payload.get('basis_fraction'),
                    'selection_bias_note': payload.get('selection_bias_note'),
                    'edge_ledger_path': payload.get('edge_ledger_path'),
                    'baseline_total_pct': baseline.get('total_pct'),
                    'baseline_max_drawdown_pct': baseline.get('max_drawdown_pct'),
                    'baseline_risk_adjusted_mean_over_std': baseline.get('risk_adjusted_mean_over_std'),
                    'baseline_trade_count': baseline.get('n_trades'),
                    'baseline_session_count': baseline.get('n_sessions'),
                    'best_policy_id': policy.get('policy_id'),
                    'best_policy_description': policy.get('description'),
                    'candidate_total_pct': policy.get('total_pct'),
                    'candidate_max_drawdown_pct': policy.get('max_drawdown_pct'),
                    'candidate_risk_adjusted_mean_over_std': policy.get('risk_adjusted_mean_over_std'),
                    'candidate_trade_count': policy.get('n_trades'),
                    'candidate_session_count': policy.get('n_sessions'),
                    'source_take_count': policy.get('source_take_count'),
                    'selected_before_halt': policy.get('selected_before_halt'),
                    'trades_skipped_filter': policy.get('trades_skipped_filter'),
                    'trades_skipped_halt': policy.get('trades_skipped_halt'),
                    'sessions_halted': policy.get('sessions_halted'),
                    'mean_size_before_halt': policy.get('mean_size_before_halt'),
                    'total_pct_delta': comparison.get('total_pct_delta'),
                    'max_drawdown_delta': comparison.get('max_drawdown_delta'),
                    'risk_adjusted_delta': comparison.get('risk_adjusted_delta'),
                    'risk_adjusted_improvement': comparison.get('risk_adjusted_improvement'),
                    'drawdown_improvement': comparison.get('drawdown_improvement'),
                    'total_noninferior': comparison.get('total_noninferior'),
                    'candidate_p2_pass': comparison.get('p2_candidate_pass'),
                    'verdict': gate.get('verdict'),
                    'implementation_unlocked': gate.get('implementation_unlocked'),
                    'unlock_note': gate.get('unlock_note'),
                },
            )
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries]


def list_fresh_validation_runs(root: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """List frozen-policy fresh-validation summaries, newest first."""
    base = _resolve_path(root, FRESH_VALIDATION_ROOT)
    if not base.is_dir():
        return []
    entries: List[tuple[float, Dict[str, Any]]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        summary_path = child / 'summary.json'
        if not summary_path.is_file():
            continue
        try:
            payload = _read_json(summary_path)
            mtime = summary_path.stat().st_mtime
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if payload.get('artifact_type') != 'frozen_policy_fresh_validation':
            continue
        policy = payload.get('policy') if isinstance(payload.get('policy'), dict) else {}
        baseline = payload.get('baseline') if isinstance(payload.get('baseline'), dict) else {}
        comparison = payload.get('comparison') if isinstance(payload.get('comparison'), dict) else {}
        gate = payload.get('gate') if isinstance(payload.get('gate'), dict) else {}
        entries.append(
            (
                mtime,
                {
                    'run': child.name,
                    'run_id': payload.get('run_id', child.name),
                    'artifact_type': payload.get('artifact_type'),
                    'schema_version': payload.get('schema_version'),
                    'fill_mode': _fill_mode_from_run(child.name, payload),
                    'validation_scope': payload.get('validation_scope'),
                    'is_fresh_validation': payload.get('is_fresh_validation'),
                    'source_path': payload.get('source_path'),
                    'strategy_label': payload.get('strategy_label'),
                    'baseline_label': payload.get('baseline_label'),
                    'guardrail': payload.get('guardrail', GUARDRAIL),
                    'cost_bps': payload.get('cost_bps'),
                    'selection_bias_guardrail': payload.get('selection_bias_guardrail'),
                    'policy_id': policy.get('policy_id'),
                    'policy_total_pct': policy.get('total_pct'),
                    'policy_max_drawdown_pct': policy.get('max_drawdown_pct'),
                    'policy_risk_adjusted_mean_over_std': policy.get('risk_adjusted_mean_over_std'),
                    'policy_trade_count': policy.get('n_trades'),
                    'policy_session_count': policy.get('n_sessions'),
                    'selected_before_halt': policy.get('selected_before_halt'),
                    'sessions_halted': policy.get('sessions_halted'),
                    'baseline_total_pct': baseline.get('total_pct'),
                    'baseline_max_drawdown_pct': baseline.get('max_drawdown_pct'),
                    'baseline_risk_adjusted_mean_over_std': baseline.get('risk_adjusted_mean_over_std'),
                    'baseline_trade_count': baseline.get('n_trades'),
                    'baseline_session_count': baseline.get('n_sessions'),
                    'total_pct_delta': comparison.get('total_pct_delta'),
                    'max_drawdown_delta': comparison.get('max_drawdown_delta'),
                    'risk_adjusted_delta': comparison.get('risk_adjusted_delta'),
                    'risk_adjusted_improvement': comparison.get('risk_adjusted_improvement'),
                    'drawdown_improvement': comparison.get('drawdown_improvement'),
                    'total_noninferior': comparison.get('total_noninferior'),
                    'enough_trades': comparison.get('enough_trades'),
                    'fresh_gate_pass': comparison.get('fresh_gate_pass'),
                    'verdict': gate.get('verdict'),
                    'fresh_validation_pass': gate.get('fresh_validation_pass'),
                    'implementation_unlocked': gate.get('implementation_unlocked'),
                    'unlock_note': gate.get('unlock_note'),
                    'min_trades': gate.get('min_trades'),
                    'min_total_delta_pct': gate.get('min_total_delta_pct'),
                },
            )
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries]


def load_model_build_readiness(
    *,
    risk_root: Optional[Path | str] = None,
    sizing_root: Optional[Path | str] = None,
    forward_root: Optional[Path | str] = None,
    fresh_root: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Summarize whether the project may proceed from evidence to RL implementation."""
    required_fill_modes = ('realized_full', 'slgap_full')
    risk_runs = list_risk_policy_runs(risk_root)
    sizing_runs = list_sizing_runs(sizing_root)
    forward_runs = list_forward_ledger_runs(forward_root)
    fresh_runs = list_fresh_validation_runs(fresh_root)

    risk_by_fill: Dict[str, Dict[str, Any]] = {}
    for run in risk_runs:
        fill_mode = str(run.get('fill_mode') or '')
        if fill_mode in required_fill_modes and fill_mode not in risk_by_fill:
            risk_by_fill[fill_mode] = run

    fresh_by_fill: Dict[str, Dict[str, Any]] = {}
    for run in fresh_runs:
        if not bool(run.get('is_fresh_validation')):
            continue
        fill_mode = str(run.get('fill_mode') or '')
        if fill_mode in required_fill_modes and fill_mode not in fresh_by_fill:
            fresh_by_fill[fill_mode] = run

    missing_risk_modes = [mode for mode in required_fill_modes if mode not in risk_by_fill]
    candidate_pass_modes = [
        mode
        for mode in required_fill_modes
        if bool((risk_by_fill.get(mode) or {}).get('candidate_p2_pass'))
    ]
    candidate_all_modes = not missing_risk_modes and len(candidate_pass_modes) == len(required_fill_modes)

    missing_fresh_modes = [mode for mode in required_fill_modes if mode not in fresh_by_fill]
    fresh_pass_modes = [
        mode
        for mode in required_fill_modes
        if bool((fresh_by_fill.get(mode) or {}).get('fresh_validation_pass'))
    ]
    fresh_all_modes = not missing_fresh_modes and len(fresh_pass_modes) == len(required_fill_modes)
    implementation_unlocked = bool(candidate_all_modes and fresh_all_modes)

    original_p2_any_pass = any(bool(run.get('p5_prerequisite_met')) for run in sizing_runs)
    original_p2_status = 'PASS' if original_p2_any_pass else ('FAIL' if sizing_runs else 'MISSING')
    p1_status = 'PASS' if not missing_risk_modes else ('PARTIAL' if risk_runs else 'MISSING')
    risk_policy_status = (
        'CANDIDATE_PASS'
        if candidate_all_modes
        else ('PARTIAL_CANDIDATE' if candidate_pass_modes else ('NO_GO' if risk_runs else 'MISSING'))
    )
    fresh_validation_status = (
        'FRESH_VALIDATION_PASS'
        if fresh_all_modes
        else ('PARTIAL_FRESH_VALIDATION' if fresh_pass_modes else ('FRESH_VALIDATION_REQUIRED' if candidate_all_modes else 'WAITING_FOR_CANDIDATE'))
    )
    p3_status = 'PASS' if forward_runs else 'MISSING'
    p4_status = 'PASS'

    if implementation_unlocked:
        restricted_rl_status = 'READY_FOR_RESTRICTED_RL_IMPLEMENTATION'
        status = 'MODEL_BUILD_READY_FOR_RESTRICTED_RL'
    elif candidate_all_modes:
        restricted_rl_status = 'LOCKED_FRESH_OOS_FORWARD_REQUIRED'
        status = 'MODEL_BUILD_CANDIDATE_NEEDS_FRESH_VALIDATION'
    else:
        restricted_rl_status = 'LOCKED_BY_P2'
        status = 'MODEL_BUILD_BLOCKED'

    selected_policy_ids = sorted(
        {
            str(run.get('best_policy_id'))
            for run in risk_by_fill.values()
            if run.get('best_policy_id')
        }
    )

    steps = [
        {
            'id': 'P1',
            'label': 'Full fill-mode evidence',
            'status': p1_status,
            'evidence': f"risk-policy summaries by fill mode: {', '.join(sorted(risk_by_fill)) or 'none'}",
        },
        {
            'id': 'P2-original',
            'label': 'Original fixed-sizing account-risk gate',
            'status': original_p2_status,
            'evidence': 'sizing_lab p5_prerequisite_met remains false' if original_p2_status == 'FAIL' else 'sizing_lab evidence',
        },
        {
            'id': 'P2-risk-policy',
            'label': 'Deterministic risk-policy candidate gate',
            'status': risk_policy_status,
            'evidence': f"candidate pass modes: {', '.join(candidate_pass_modes) or 'none'}; selected policies: {', '.join(selected_policy_ids) or 'none'}",
        },
        {
            'id': 'P2-fresh-validation',
            'label': 'Frozen policy fresh OOS/forward validation',
            'status': fresh_validation_status,
            'evidence': f"fresh pass modes: {', '.join(fresh_pass_modes) or 'none'}; missing modes: {', '.join(missing_fresh_modes) or 'none'}",
        },
        {
            'id': 'P3',
            'label': 'Forward/paper read-only ledger',
            'status': p3_status,
            'evidence': f"{len(forward_runs)} forward ledger run(s) found",
        },
        {
            'id': 'P4',
            'label': 'Dashboard evidence surface',
            'status': p4_status,
            'evidence': 'read-only dashboard aggregates model-build readiness; no training/orders from webui',
        },
        {
            'id': 'RL-implementation',
            'label': 'Restricted RL sizing/exit implementation',
            'status': restricted_rl_status,
            'evidence': (
                'fresh validation passed for both required fill modes; implementation may be considered under research guardrails'
                if implementation_unlocked
                else 'implementation_unlocked is false until frozen fresh_oos/fresh_forward validation passes both fill modes'
            ),
        },
    ]

    return {
        'available': True,
        'artifact_type': 'model_build_readiness',
        'strategy_label': 'model-build readiness audit - NOT an RL model',
        'baseline_label': 'ts_imb RULE baseline',
        'guardrail': GUARDRAIL,
        'cost_bps': 23.0,
        'status': status,
        'required_fill_modes': list(required_fill_modes),
        'p1_status': p1_status,
        'original_p2_status': original_p2_status,
        'risk_policy_status': risk_policy_status,
        'fresh_validation_status': fresh_validation_status,
        'p3_status': p3_status,
        'p4_status': p4_status,
        'restricted_rl_status': restricted_rl_status,
        'implementation_unlocked': implementation_unlocked,
        'selected_policy_ids': selected_policy_ids,
        'selection_bias_note': (
            'Risk-policy choice was made after reviewing full OOS artifacts; treat it as hypothesis generation, '
            'not a deployable RL/profit proof.'
        ),
        'unlock_requirements': [
            'Preregister the selected risk policy before any new validation run.',
            'Run frozen fresh_oos or fresh_forward validation not used to choose the policy.',
            'Require both realized_full and slgap_full fresh-validation passes.',
            'Keep 23bp cost, same-fill ts_imb RULE baseline, drawdown, and risk-adjusted gates visible.',
            'Only then consider a restricted RL sizing/exit controller; never add broker/live-order behavior to the dashboard.',
        ],
        'readiness_steps': steps,
        'risk_policy_runs': [risk_by_fill[mode] for mode in required_fill_modes if mode in risk_by_fill],
        'fresh_validation_runs': [fresh_by_fill[mode] for mode in required_fill_modes if mode in fresh_by_fill],
        'original_sizing_runs': sizing_runs[:4],
        'forward_ledger_runs': forward_runs[:4],
    }


def list_forward_ledger_runs(root: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """List forward/paper ledger summaries, newest first."""
    base = _resolve_path(root, FORWARD_LEDGER_ROOT)
    if not base.is_dir():
        return []
    entries: List[tuple[float, Dict[str, Any]]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        summary_path = child / 'ledger.summary.json'
        if not summary_path.is_file():
            continue
        try:
            payload = _read_json(summary_path)
            mtime = summary_path.stat().st_mtime
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        status_counts = payload.get('status_counts') if isinstance(payload.get('status_counts'), dict) else {}
        entries.append(
            (
                mtime,
                {
                    'run': child.name,
                    'run_id': payload.get('run_id', child.name),
                    'model_version': payload.get('model_version'),
                    'fill_assumption': payload.get('fill_assumption'),
                    'cost_bps': payload.get('cost_bps'),
                    'schema_version': payload.get('schema_version'),
                    'total_count': payload.get('total_count'),
                    'pending_count': status_counts.get('pending', 0),
                    'resolved_count': status_counts.get('resolved', 0),
                    'status_counts': status_counts,
                    'duplicate_policy': payload.get('duplicate_policy'),
                    'skipped_duplicate_count': payload.get('skipped_duplicate_count'),
                    'include_outcomes': payload.get('include_outcomes'),
                    'source_edge_ledger_path': payload.get('source_edge_ledger_path'),
                    'output_root': payload.get('output_root'),
                    'guardrail': payload.get('guardrail', GUARDRAIL),
                },
            )
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries]


def load_forward_ledger(
    run_name: str,
    *,
    root: Optional[Path | str] = None,
    limit: int = _DEFAULT_LEDGER_LIMIT,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Read forward/paper ledger JSONL rows with a server-computed summary."""
    run_dir = _safe_run_dir(run_name, _resolve_path(root, FORWARD_LEDGER_ROOT))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_LEDGER_LIMIT
    limit = max(0, min(limit, _MAX_LEDGER_LIMIT))
    if status is not None:
        status = str(status).lower()
        if status not in {'pending', 'resolved'}:
            raise ValueError(f"invalid status filter: {status!r} (use pending or resolved)")
    ledger_path = run_dir / 'ledger.jsonl'
    summary_path = run_dir / 'ledger.summary.json'
    if not ledger_path.is_file():
        return {
            'available': False,
            'reason': 'forward_ledger_not_found',
            'run': run_name,
            'guardrail': GUARDRAIL,
        }
    rows = _read_jsonl(ledger_path)
    summary_payload = _read_json(summary_path) if summary_path.is_file() else {}
    status_counts = _status_counts(rows)
    filtered = [row for row in rows if str(row.get('outcome_status')) == status] if status else rows
    return {
        'available': True,
        'run': run_name,
        'guardrail': summary_payload.get('guardrail', GUARDRAIL),
        'summary': {
            'total_rows': len(rows),
            'pending_count': status_counts.get('pending', 0),
            'resolved_count': status_counts.get('resolved', 0),
            'status_counts': status_counts,
            'schema_version': summary_payload.get('schema_version'),
            'duplicate_policy': summary_payload.get('duplicate_policy'),
            'fill_assumption': summary_payload.get('fill_assumption'),
            'cost_bps': summary_payload.get('cost_bps'),
            'model_version': summary_payload.get('model_version'),
            'output_root': summary_payload.get('output_root'),
        },
        'status_filter': status,
        'returned_rows': min(limit, len(filtered)),
        'rows': filtered[:limit],
    }

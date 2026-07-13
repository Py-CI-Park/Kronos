// G003 event-contract mirror (stom_rl/rl_events.py). Truthful metric/action
// metadata rides inside each event's ``info`` dict (and/or run-level
// defaults for archived artifacts that predate the contract). Unknown values
// stay ``null`` so consumers render NOT_RECORDED rather than coercing to
// zero / HOLD / percent. Producers declare truthfully; this module never
// infers a kind/unit that was not declared, and never multiplies a reward by
// 100 unless the declared unit is a fraction (or the value is already a
// percent).
//
// Intentionally dependency-free (no imports from sibling `lib` modules):
// Node's native TypeScript type-stripping runtime (used by
// `node --experimental-strip-types --test`) requires every relative import
// specifier to carry an explicit file extension, while this project's
// `tsconfig.json` (moduleResolution: "bundler", no
// `allowImportingTsExtensions`) rejects explicit `.ts` extensions in import
// specifiers. Keeping this module import-free avoids that structural
// conflict without touching tsconfig.json or any other file outside this
// change's scope.
import type { RlTableRow } from './rlApi';

export type MetricMeta = {
  reward_kind: string | null;
  reward_unit: string | null;
  equity_kind: string | null;
  equity_unit: string | null;
  action_recorded: boolean | null;
  // Not part of the G003 vocabulary proper, but ``metrics_overlay_compatible``
  // (rl_events.py) also accepts an identical explicit ``normalization`` as a
  // compatibility signal; kept optional so the 5 required contract fields
  // stay exactly as specified.
  normalization?: string | null;
};

const METRIC_METADATA_KEYS = [
  'reward_kind',
  'reward_unit',
  'equity_kind',
  'equity_unit',
  'action_recorded',
  'normalization',
] as const;

function emptyMeta(): MetricMeta {
  return {
    reward_kind: null,
    reward_unit: null,
    equity_kind: null,
    equity_unit: null,
    action_recorded: null,
    normalization: null,
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

/**
 * Merge per-event ``info`` metadata over run-level defaults.
 *
 * Precedence: per-event ``info`` > run-level defaults > ``null``. A value is
 * only overridden when it is explicitly declared (non-null/undefined);
 * unknown stays ``null`` so callers render NOT_RECORDED instead of coercing.
 */
export function resolveMetricMetadata(
  row: RlTableRow | null | undefined,
  runDefaults?: Partial<MetricMeta> | Record<string, unknown> | null,
): MetricMeta {
  const meta = emptyMeta();
  const defaults = asRecord(runDefaults);
  if (defaults) {
    for (const key of METRIC_METADATA_KEYS) {
      const value = defaults[key];
      if (value !== null && value !== undefined) {
        (meta as Record<string, unknown>)[key] = value;
      }
    }
  }
  const info = asRecord((row as Record<string, unknown> | null | undefined)?.info);
  if (info) {
    for (const key of METRIC_METADATA_KEYS) {
      const value = info[key];
      if (value !== null && value !== undefined) {
        (meta as Record<string, unknown>)[key] = value;
      }
    }
  }
  return meta;
}

/**
 * Return ``RECORDED`` or ``NOT_RECORDED`` without coercing a null action to
 * HOLD/0. ``info.action_recorded`` (when explicitly declared) wins; absent a
 * declaration, a real (non-null) ``action`` value — including 0 — counts as
 * recorded.
 */
export function actionAvailability(row: RlTableRow | null | undefined): 'RECORDED' | 'NOT_RECORDED' {
  const rec = row as Record<string, unknown> | null | undefined;
  const info = asRecord(rec?.info);
  if (info) {
    const recorded = info.action_recorded;
    if (recorded === true) return 'RECORDED';
    if (recorded === false) return 'NOT_RECORDED';
  }
  const action = rec?.action;
  return action !== null && action !== undefined ? 'RECORDED' : 'NOT_RECORDED';
}

/**
 * Whether two metric series may share one chart axis. Compatible only when
 * both declare the same kind AND unit, or both declare an identical explicit
 * ``normalization``. A missing/unknown kind is never compatible (so a
 * normalized-NAV-vs-KRW overlay is rejected rather than silently mixed).
 */
export function metricsOverlayCompatible(
  a: MetricMeta,
  b: MetricMeta,
  metric: 'equity' | 'reward' = 'equity',
): boolean {
  const kindKey = metric === 'equity' ? 'equity_kind' : 'reward_kind';
  const unitKey = metric === 'equity' ? 'equity_unit' : 'reward_unit';
  const aKind = a[kindKey];
  const bKind = b[kindKey];
  if (aKind === null || aKind === undefined || bKind === null || bKind === undefined) return false;
  if (aKind === bKind && a[unitKey] === b[unitKey]) return true;
  const aNorm = a.normalization;
  const bNorm = b.normalization;
  return Boolean(aNorm) && aNorm === bNorm;
}

function isRecordedNumeric(value: unknown): boolean {
  return value !== null && value !== undefined;
}

/** Korean-locale numeric render matching rlRows.num()'s ko-KR formatting. */
function renderNum(value: unknown, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('ko-KR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

/** Korean-locale percent render matching rlRows.pct()'s ko-KR formatting. */
function renderPct(value: unknown, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return (
    new Intl.NumberFormat('ko-KR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(n) + '%'
  );
}

/**
 * Format a raw reward value under a declared unit contract:
 * - ``percent``  -> value is already a percent; render as-is via renderPct().
 * - ``fraction`` -> value is a fraction (e.g. 0.012); render as percent via
 *   renderPct(value * 100) — the ONLY case that multiplies by 100.
 * - ``score`` / unknown / null -> raw numeric render; NEVER multiplied.
 */
export function formatRewardValue(value: unknown, meta: MetricMeta): string {
  if (!isRecordedNumeric(value)) return 'NOT_RECORDED';
  const unit = meta.reward_unit;
  if (unit === 'percent') return renderPct(value, 4);
  if (unit === 'fraction') return renderPct(Number(value) * 100, 4);
  return renderNum(value, 4);
}

export function formatReward(row: RlTableRow | null | undefined, meta: MetricMeta): string {
  return formatRewardValue((row as Record<string, unknown> | null | undefined)?.reward, meta);
}

export function rewardUnitLabel(meta: MetricMeta): string {
  const unit = meta.reward_unit;
  if (unit === 'percent' || unit === 'fraction') return '%';
  if (unit === 'score') return 'score';
  if (unit === 'krw') return 'KRW';
  if (unit === 'normalized') return 'normalized';
  return 'raw';
}

/**
 * Numeric reward value for PLOTTING under the declared unit contract. Applies
 * the exact same rule as formatRewardValue: x100 ONLY for ``fraction``;
 * ``percent`` as-is; ``score`` / unknown / null raw (never x100). A null or
 * non-finite reward returns ``null`` so the chart draws a gap, not a fake 0.
 */
export function rewardPlotValue(value: unknown, meta: MetricMeta): number | null {
  if (!isRecordedNumeric(value)) return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  if (meta.reward_unit === 'fraction') return n * 100;
  return n;
}

/** Whether the reward axis is a percentage (declared fraction or percent). */
export function rewardAxisIsPercent(meta: MetricMeta): boolean {
  return meta.reward_unit === 'fraction' || meta.reward_unit === 'percent';
}

/** Equity is never x100 regardless of declared unit/kind. */
export function formatEquityValue(value: unknown, _meta: MetricMeta): string {
  if (!isRecordedNumeric(value)) return 'NOT_RECORDED';
  return renderNum(value, 2);
}

export function formatEquity(row: RlTableRow | null | undefined, meta: MetricMeta): string {
  return formatEquityValue((row as Record<string, unknown> | null | undefined)?.equity, meta);
}

export function equityUnitLabel(meta: MetricMeta): string {
  if (meta.equity_kind === 'cumulative_pnl') return 'P&L';
  if (meta.equity_unit === 'krw') return 'KRW';
  if (meta.equity_unit === 'normalized') return 'NAV';
  if (meta.equity_kind === 'normalized_nav') return 'NAV';
  return 'raw';
}

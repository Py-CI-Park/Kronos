// G008 all-tab performance budget gate. Encodes the exact, fixed latency and
// interaction budgets the dashboard must meet across every tab, independent
// of any single tab's implementation.
//
// Design notes:
//  - Every metric MAY be supplied either as a single already-reduced
//    duration (a plain `number`) or as a raw sample array. When an array is
//    supplied the gate always reduces it with the 95th percentile
//    (`percentile95`), never the mean — a slow tail must never be averaged
//    away by fast samples.
//  - Missing, non-finite, negative, or empty-sample metrics are treated as
//    fail-closed `:invalid` / `:missing` failures, never as a silent pass.
//  - `isolatedCardRetryVisible` is a boolean requirement (a visible RETRY
//    affordance must be rendered once the isolated-card timeout elapses),
//    not a duration, and is validated separately from the latency budgets.

export type LatencyMetric = number | readonly number[];

export interface PerformanceBudgetSample {
  /** First critical card rendered, cold load. Budget: <=3000ms. */
  readonly firstCriticalCardColdMs: LatencyMetric;
  /** First critical card rendered, warm load. Budget: <=1500ms. */
  readonly firstCriticalCardWarmMs: LatencyMetric;
  /** Full critical-tab hydration complete, cold load. Budget: <=10000ms. */
  readonly fullCriticalHydrationColdMs: LatencyMetric;
  /** Full critical-tab hydration complete, warm load. Budget: <=6000ms. */
  readonly fullCriticalHydrationWarmMs: LatencyMetric;
  /** Critical API round trip, warm cache, 95th percentile. Budget: <=2000ms. */
  readonly warmCriticalApiMs: LatencyMetric;
  /** Critical API round trip, cold cache. Budget: <=5000ms. */
  readonly coldCriticalApiMs: LatencyMetric;
  /** Isolated (non-critical) card failure timeout before RETRY appears. Budget: <=20500ms. */
  readonly isolatedCardTimeoutMs: LatencyMetric;
  /** Whether a visible RETRY affordance is rendered once the isolated-card timeout elapses. */
  readonly isolatedCardRetryVisible: boolean;
  /** Command palette open-to-interactive, 95th percentile. Budget: <=100ms. */
  readonly commandPaletteOpenMs: LatencyMetric;
  /** 1000-item command/query filter pass, 95th percentile. Budget: <=150ms. */
  readonly thousandItemQueryFilterMs: LatencyMetric;
}

export interface PerformanceBudgetResult {
  readonly pass: boolean;
  readonly failures: readonly string[];
}

export const PERFORMANCE_BUDGET_LIMITS_MS = Object.freeze({
  firstCriticalCardColdMs: 3_000,
  firstCriticalCardWarmMs: 1_500,
  fullCriticalHydrationColdMs: 10_000,
  fullCriticalHydrationWarmMs: 6_000,
  warmCriticalApiMs: 2_000,
  coldCriticalApiMs: 5_000,
  isolatedCardTimeoutMs: 20_500,
  commandPaletteOpenMs: 100,
  thousandItemQueryFilterMs: 150,
} as const);

export const RETRY_VISIBLE_KEY = 'isolatedCardRetryVisible' as const;

type LatencyKey = keyof typeof PERFORMANCE_BUDGET_LIMITS_MS;

const LATENCY_KEYS = Object.keys(PERFORMANCE_BUDGET_LIMITS_MS) as readonly LatencyKey[];

function isFiniteNonNegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

/**
 * Reduce raw latency samples to their 95th percentile using the
 * nearest-rank method. Returns `null` (fail-closed) for an empty, missing,
 * or non-numeric/negative/non-finite sample set instead of coercing it into
 * a passing value.
 */
export function percentile95(samples: readonly number[]): number | null {
  if (!Array.isArray(samples) || samples.length === 0) {
    return null;
  }
  const cleaned: number[] = [];
  for (const sample of samples) {
    if (!isFiniteNonNegative(sample)) {
      return null;
    }
    cleaned.push(sample);
  }
  cleaned.sort((a, b) => a - b);
  const rank = Math.min(cleaned.length, Math.max(1, Math.ceil(0.95 * cleaned.length)));
  return cleaned[rank - 1];
}

function resolveLatencyMetric(value: unknown): number | null {
  if (Array.isArray(value)) {
    return percentile95(value as readonly number[]);
  }
  return isFiniteNonNegative(value) ? (value as number) : null;
}

/**
 * Evaluate a single performance capture against every fixed G008 budget.
 * Fails closed: any missing, non-finite, negative, empty-sample, or
 * over-budget metric is reported as an explicit failure string and the
 * overall gate does not pass. Never averages a metric's samples away — the
 * 95th percentile always governs when raw samples are supplied.
 */
export function evaluatePerformanceBudget(sample: PerformanceBudgetSample): PerformanceBudgetResult {
  const record = sample as unknown as Record<string, unknown>;
  const failures: string[] = [];

  for (const key of LATENCY_KEYS) {
    const resolved = resolveLatencyMetric(record[key]);
    const limit = PERFORMANCE_BUDGET_LIMITS_MS[key];
    if (resolved === null) {
      failures.push(`${key}:invalid`);
    } else if (resolved > limit) {
      failures.push(`${key}:${resolved}>${limit}`);
    }
  }

  if (record[RETRY_VISIBLE_KEY] !== true) {
    failures.push(`${RETRY_VISIBLE_KEY}:missing_or_false`);
  }

  return { pass: failures.length === 0, failures };
}

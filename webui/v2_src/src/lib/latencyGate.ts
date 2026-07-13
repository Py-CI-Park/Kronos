export interface DashboardLatencySample {
  readonly firstMeaningfulCardMs: number;
  readonly fullCriticalHydrationMs: number;
  readonly warmCriticalApiMs: number;
  readonly coldCriticalApiMs: number;
}

export interface DashboardLatencyGateResult {
  readonly pass: boolean;
  readonly failures: readonly string[];
}

export const DASHBOARD_LATENCY_LIMITS_MS = Object.freeze({
  firstMeaningfulCardMs: 3_000,
  fullCriticalHydrationMs: 10_000,
  warmCriticalApiMs: 2_000,
  coldCriticalApiMs: 5_000,
});

export function evaluateDashboardLatency(sample: DashboardLatencySample): DashboardLatencyGateResult {
  const failures: string[] = [];
  for (const key of Object.keys(DASHBOARD_LATENCY_LIMITS_MS) as (keyof DashboardLatencySample)[]) {
    const value = sample[key];
    const limit = DASHBOARD_LATENCY_LIMITS_MS[key];
    if (!Number.isFinite(value) || value < 0) {
      failures.push(`${key}:invalid`);
    } else if (value > limit) {
      failures.push(`${key}:${value}>${limit}`);
    }
  }
  return { pass: failures.length === 0, failures };
}

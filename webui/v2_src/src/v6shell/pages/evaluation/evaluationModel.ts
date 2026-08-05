import type { TelemetryRun, TelemetrySnapshot } from '../../api/telemetryApi';

export type EvaluationEntry = {
  readonly run: TelemetryRun;
  readonly snapshot: TelemetrySnapshot;
};

export type EvaluationSummary = {
  readonly sampleReward: number;
  readonly latestEquity: number | null;
  readonly sampleDrawdownPct: number | null;
  readonly pointCount: number;
  readonly sampling: TelemetrySnapshot['sampling'];
};

export function summarizeSnapshot(snapshot: TelemetrySnapshot): EvaluationSummary {
  const sampleReward = snapshot.points.reduce((sum, point) => sum + (point.reward ?? 0), 0);
  const equities = snapshot.points.flatMap((point) => point.equity === null ? [] : [point.equity]);
  let peak = Number.NEGATIVE_INFINITY;
  let sampleDrawdownPct: number | null = null;
  for (const equity of equities) {
    peak = Math.max(peak, equity);
    const drawdown = peak > 0 ? ((equity / peak) - 1) * 100 : 0;
    sampleDrawdownPct = sampleDrawdownPct === null ? drawdown : Math.min(sampleDrawdownPct, drawdown);
  }
  return {
    sampleReward,
    latestEquity: equities.at(-1) ?? null,
    sampleDrawdownPct,
    pointCount: snapshot.points.length,
    sampling: snapshot.sampling,
  };
}

export function sampleRewardSeries(snapshot: TelemetrySnapshot): readonly (readonly [number, number])[] {
  let cumulative = 0;
  return snapshot.points.map((point) => {
    cumulative += point.reward ?? 0;
    return [point.step, cumulative] as const;
  });
}

export function equityReturnSeries(snapshot: TelemetrySnapshot): readonly (readonly [number, number])[] {
  return snapshot.points.flatMap((point) => point.equity === null ? [] : [[point.step, (point.equity - 1) * 100] as const]);
}

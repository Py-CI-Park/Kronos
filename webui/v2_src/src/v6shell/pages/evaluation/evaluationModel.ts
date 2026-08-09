import type { TelemetryRun, TelemetrySnapshot } from '../../api/telemetryApi';
import { equityPresentation, rewardPresentation } from '../live/telemetryMetricModel';

export type EvaluationEntry = {
  readonly run: TelemetryRun;
  readonly snapshot: TelemetrySnapshot;
};

export type EvaluationSummary = {
  readonly sampleReward: number;
  readonly sampleRewardLabel: string;
  readonly latestEquity: number | null;
  readonly latestEquityLabel: string;
  readonly equityMetricLabel: string;
  readonly sampleDrawdownPct: number | null;
  readonly pointCount: number;
  readonly sampling: TelemetrySnapshot['sampling'];
};

export function summarizeSnapshot(snapshot: TelemetrySnapshot): EvaluationSummary {
  const sampleReward = snapshot.points.reduce((sum, point) => sum + (point.reward ?? 0), 0);
  const equities = snapshot.points.flatMap((point) => point.equity === null ? [] : [point.equity]);
  const equityMetric = equityPresentation(snapshot.points);
  const rewardMetric = rewardPresentation(snapshot.points);
  const sampleDrawdownPct = equityMetric.drawdownRows.length
    ? Math.min(...equityMetric.drawdownRows.map((row) => row[1]))
    : null;
  return {
    sampleReward,
    sampleRewardLabel: rewardMetric.latestLabel,
    latestEquity: equities.at(-1) ?? null,
    latestEquityLabel: equityMetric.latestLabel,
    equityMetricLabel: equityMetric.axisLabel,
    sampleDrawdownPct,
    pointCount: snapshot.points.length,
    sampling: snapshot.sampling,
  };
}

export function sampleRewardSeries(snapshot: TelemetrySnapshot): readonly (readonly [number, number])[] {
  return rewardPresentation(snapshot.points).rows;
}

export function equityMetricSeries(snapshot: TelemetrySnapshot): readonly (readonly [number, number])[] {
  return equityPresentation(snapshot.points).rows;
}

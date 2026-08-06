import type { TelemetryPoint } from '../../api/telemetryApi';

export type ActionDistributionItem = {
  readonly label: string;
  readonly count: number;
  readonly sharePct: number;
};

export type ActionTimelineRow = readonly [string | number, string, number, string];

function normalizedAction(name: string): string {
  const normalized = name.trim().toUpperCase();
  return normalized || 'MISSING';
}

export function actionDistribution(points: readonly TelemetryPoint[]): readonly ActionDistributionItem[] {
  const counts = new Map<string, number>();
  for (const point of points) {
    const action = normalizedAction(point.action_name);
    if (action === 'MISSING') continue;
    counts.set(action, (counts.get(action) ?? 0) + 1);
  }
  const total = [...counts.values()].reduce((sum, count) => sum + count, 0);
  return [...counts.entries()].map(([label, count]) => ({
    label,
    count,
    sharePct: total === 0 ? 0 : Number(((count / total) * 100).toFixed(1)),
  }));
}

export function buildActionTimelineRows(points: readonly TelemetryPoint[]): readonly ActionTimelineRow[] {
  return points.flatMap((point) => {
    const action = normalizedAction(point.action_name);
    if (action === 'MISSING') return [];
    const x: string | number = Number.isNaN(Date.parse(point.timestamp)) ? point.step : point.timestamp;
    return [[x, action, point.step, point.phase] as const];
  });
}

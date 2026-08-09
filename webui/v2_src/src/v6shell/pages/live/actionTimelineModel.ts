import type { TelemetryPoint } from '../../api/telemetryApi';

export type ActionDistributionItem = {
  readonly label: string;
  readonly count: number;
  readonly sharePct: number;
};

export type ActionTimelineRow = readonly [string | number, string, number, string];

export type ActionHourBucket = {
  readonly start: string;
  readonly label: string;
  readonly total: number;
  readonly counts: Readonly<Record<string, number>>;
};

function normalizedAction(name: string): string {
  const normalized = name.trim().toUpperCase();
  return normalized || 'MISSING';
}

export function recordedActionName(point: TelemetryPoint): string | null {
  if (point.action_recorded === false) return null;
  const action = normalizedAction(point.action_name);
  return action === 'MISSING' ? null : action;
}

export function recordedActionPoints(points: readonly TelemetryPoint[]): readonly TelemetryPoint[] {
  return points.filter((point) => recordedActionName(point) !== null);
}

export function actionDistribution(points: readonly TelemetryPoint[]): readonly ActionDistributionItem[] {
  const counts = new Map<string, number>();
  for (const point of points) {
    const action = recordedActionName(point);
    if (action === null) continue;
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
    const action = recordedActionName(point);
    if (action === null) return [];
    const x: string | number = Number.isNaN(Date.parse(point.timestamp)) ? point.step : point.timestamp;
    return [[x, action, point.step, point.phase] as const];
  });
}

function koreanHourLabel(start: string): string {
  const parts = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(start));
  const value = (type: Intl.DateTimeFormatPartTypes): string => parts.find((part) => part.type === type)?.value ?? '--';
  return `${value('month')}. ${value('day')}. ${value('hour')}시`;
}

export function buildActionHourBuckets(points: readonly TelemetryPoint[]): readonly ActionHourBucket[] {
  const buckets = new Map<number, Map<string, number>>();
  for (const point of points) {
    const timestamp = Date.parse(point.timestamp);
    const action = recordedActionName(point);
    if (!Number.isFinite(timestamp) || action === null) continue;
    const start = Math.floor(timestamp / 3_600_000) * 3_600_000;
    const counts = buckets.get(start) ?? new Map<string, number>();
    counts.set(action, (counts.get(action) ?? 0) + 1);
    buckets.set(start, counts);
  }
  return [...buckets.entries()].toSorted(([left], [right]) => left - right).map(([start, counts]) => {
    const iso = new Date(start).toISOString();
    const observedCounts = Object.fromEntries([...counts.entries()].toSorted(([left], [right]) => left.localeCompare(right)));
    return {
      start: iso,
      label: koreanHourLabel(iso),
      total: [...counts.values()].reduce((sum, count) => sum + count, 0),
      counts: observedCounts,
    };
  });
}

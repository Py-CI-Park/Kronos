import type { TelemetryPoint } from '../../api/telemetryApi';
import { runStatusLabel } from '../../runStatusModel';

export type TelemetryMetric = 'reward' | 'equity';
export type MetricIdentity = {
  readonly state: 'declared' | 'missing' | 'mixed';
  readonly kind: string | null;
  readonly unit: string | null;
};

export type MetricPresentation = {
  readonly identity: MetricIdentity;
  readonly rows: readonly (readonly [number, number])[];
  readonly drawdownRows: readonly (readonly [number, number])[];
  readonly title: string;
  readonly axisLabel: string;
  readonly latestLabel: string;
  readonly notice: string;
};

const won = new Intl.NumberFormat('ko-KR', {
  style: 'currency',
  currency: 'KRW',
  maximumFractionDigits: 0,
});
const compactWon = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 });

export function compactRunStatus(status: string | null | undefined): string {
  return runStatusLabel(status);
}

export function compactKrwNavLabel(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'MISSING';
  return `${compactWon.format(Math.round(value / 10_000))}만원`;
}

function metricValue(point: TelemetryPoint, metric: TelemetryMetric): number | null {
  return metric === 'equity' ? point.equity : point.reward;
}

export function metricIdentity(
  points: readonly TelemetryPoint[],
  metric: TelemetryMetric,
): MetricIdentity {
  const populated = points.filter((point) => metricValue(point, metric) !== null);
  if (populated.length === 0) return { state: 'missing', kind: null, unit: null };
  const identities = populated.map((point) => ({
    kind: metric === 'equity' ? point.equity_kind : point.reward_kind,
    unit: metric === 'equity' ? point.equity_unit : point.reward_unit,
  }));
  const complete = identities.filter(({ kind, unit }) => kind !== null && unit !== null && unit !== 'unknown');
  if (complete.length === 0) return { state: 'missing', kind: null, unit: null };
  const signatures = new Set(complete.map(({ kind, unit }) => `${kind}:${unit}`));
  if (complete.length !== identities.length || signatures.size !== 1) {
    return { state: 'mixed', kind: null, unit: null };
  }
  return { state: 'declared', kind: complete[0].kind, unit: complete[0].unit };
}

function rawRows(
  points: readonly TelemetryPoint[],
  metric: TelemetryMetric,
): readonly (readonly [number, number])[] {
  return points.flatMap((point) => {
    const value = metricValue(point, metric);
    return value === null ? [] : [[point.step, value] as const];
  });
}

function drawdownRows(
  rows: readonly (readonly [number, number])[],
): readonly (readonly [number, number])[] {
  let peak = Number.NEGATIVE_INFINITY;
  return rows.flatMap(([step, value]) => {
    peak = Math.max(peak, value);
    if (peak <= 0) return [];
    return [[step, Number((((value / peak) - 1) * 100).toFixed(10))] as const];
  });
}

function rawLabel(value: number | undefined): string {
  return value === undefined
    ? 'MISSING'
    : new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 6 }).format(value);
}

export function equityPresentation(points: readonly TelemetryPoint[]): MetricPresentation {
  const identity = metricIdentity(points, 'equity');
  const raw = rawRows(points, 'equity');
  const latest = raw.at(-1)?.[1];
  if (identity.kind === 'normalized_nav' && identity.unit === 'normalized') {
    const rows = raw.map(([step, value]) => [step, Number(((value - 1) * 100).toFixed(10))] as const);
    return {
      identity,
      rows,
      drawdownRows: drawdownRows(raw),
      title: '정규화 NAV · 낙폭',
      axisLabel: 'NAV 변화 (%)',
      latestLabel: latest === undefined ? 'MISSING' : `${((latest - 1) * 100).toFixed(2)}%`,
      notice: '명시된 normalized_nav/normalized 값만 초기 NAV 1 대비 비율로 변환했습니다.',
    };
  }
  if (identity.kind === 'krw_nav' && identity.unit === 'krw') {
    return {
      identity,
      rows: raw,
      drawdownRows: drawdownRows(raw),
      title: '원화 NAV · 낙폭',
      axisLabel: 'NAV (원)',
      latestLabel: latest === undefined ? 'MISSING' : won.format(latest),
      notice: '명시된 원화 NAV 경로이며 표본 고점 대비 낙폭만 함께 표시합니다.',
    };
  }
  if (identity.kind === 'cumulative_pnl' && identity.unit === 'krw') {
    return {
      identity,
      rows: raw,
      drawdownRows: [],
      title: '누적 손익',
      axisLabel: '누적 손익 (원)',
      latestLabel: latest === undefined ? 'MISSING' : won.format(latest),
      notice: '누적 손익은 NAV가 아니므로 낙폭을 계산하지 않습니다.',
    };
  }
  const state = identity.state === 'mixed' ? 'MIXED' : 'MISSING';
  return {
    identity,
    rows: raw,
    drawdownRows: [],
    title: '기록 equity 원값',
    axisLabel: `원 단위 (${state})`,
    latestLabel: latest === undefined ? 'MISSING' : `${rawLabel(latest)} · 단위 ${state}`,
    notice: `equity kind/unit이 ${state} 상태라 비율·낙폭을 추정하지 않습니다.`,
  };
}

export function rewardPresentation(points: readonly TelemetryPoint[]): MetricPresentation {
  const identity = metricIdentity(points, 'reward');
  let cumulative = 0;
  const rows = points.flatMap((point) => {
    if (point.reward === null) return [];
    cumulative += point.reward;
    return [[point.step, cumulative] as const];
  });
  const state = identity.state === 'declared'
    ? `${identity.kind}/${identity.unit}`
    : identity.state.toUpperCase();
  return {
    identity,
    rows,
    drawdownRows: [],
    title: '표본 누적 보상',
    axisLabel: `누적 reward (${state})`,
    latestLabel: rawLabel(rows.at(-1)?.[1]),
    notice: `표시 point의 reward 누적값 · 단위 ${state} · 경제 수익률 주장이 아닙니다.`,
  };
}

export function metricOverlayCompatible(
  left: readonly TelemetryPoint[],
  right: readonly TelemetryPoint[],
  metric: TelemetryMetric,
): boolean {
  const leftIdentity = metricIdentity(left, metric);
  const rightIdentity = metricIdentity(right, metric);
  return leftIdentity.state === 'declared'
    && rightIdentity.state === 'declared'
    && leftIdentity.kind === rightIdentity.kind
    && leftIdentity.unit === rightIdentity.unit;
}

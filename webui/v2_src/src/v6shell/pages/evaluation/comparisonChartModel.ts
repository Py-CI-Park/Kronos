import { equityPresentation, metricOverlayCompatible, rewardPresentation } from '../live/telemetryMetricModel';
import { equityMetricSeries, sampleRewardSeries, type EvaluationEntry } from './evaluationModel';

export type ComparisonMetric = 'equity' | 'reward';
export type ComparisonAxisMode = 'progress' | 'step';

export function shortRunLabel(name: string, status: string): string {
  const compactName = name.length > 20 ? `…${name.slice(-19)}` : name;
  return `${compactName} · ${status}`;
}

export function normalizedProgressSeries(
  rows: readonly (readonly [number, number])[],
): readonly (readonly [number, number])[] {
  if (rows.length === 0) return [];
  if (rows.length === 1) return [[100, rows[0][1]]];
  return rows.map((row, index) => [Number(((index / (rows.length - 1)) * 100).toFixed(2)), row[1]] as const);
}

function metricSeries(entry: EvaluationEntry, metric: ComparisonMetric): readonly (readonly [number, number])[] {
  return metric === 'equity' ? equityMetricSeries(entry.snapshot) : sampleRewardSeries(entry.snapshot);
}

export function comparisonCompatibility(
  entries: readonly EvaluationEntry[],
  metric: ComparisonMetric,
): { readonly compatible: boolean; readonly message: string; readonly axisLabel: string } {
  const presentation = entries[0]
    ? metric === 'equity'
      ? equityPresentation(entries[0].snapshot.points)
      : rewardPresentation(entries[0].snapshot.points)
    : null;
  if (entries.length < 2) {
    return { compatible: false, message: '비교하려면 같은 lane의 실행 2개가 필요합니다.', axisLabel: '단위 MISSING' };
  }
  const compatible = entries.slice(1).every((entry) => metricOverlayCompatible(
    entries[0].snapshot.points,
    entry.snapshot.points,
    metric,
  ));
  if (!compatible) {
    return {
      compatible: false,
      message: `${metric} kind/unit이 누락·혼합·불일치하여 같은 축 비교를 차단했습니다.`,
      axisLabel: '단위 INCOMPATIBLE',
    };
  }
  return { compatible: true, message: '동일한 kind/unit이 선언된 실행만 같은 축에 표시합니다.', axisLabel: presentation?.axisLabel ?? '값' };
}

export function comparisonChartOptions(
  entries: readonly EvaluationEntry[],
  metric: ComparisonMetric,
  axisMode: ComparisonAxisMode = 'progress',
) {
  const compatibility = comparisonCompatibility(entries, metric);
  return {
    animationDuration: 280,
    tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'cross' } },
    legend: { type: 'scroll', top: 0, left: 8, right: 8 },
    grid: { left: 72, right: 38, top: 72, bottom: 112, containLabel: true },
    xAxis: {
      type: 'value',
      name: axisMode === 'progress' ? '진행률 (%)' : '원본 step',
      nameLocation: 'middle',
      nameGap: 46,
      axisLabel: { hideOverlap: true },
      min: axisMode === 'progress' ? 0 : undefined,
      max: axisMode === 'progress' ? 100 : undefined,
      splitNumber: axisMode === 'progress' ? 4 : 6,
    },
    yAxis: {
      type: 'value',
      name: compatibility.axisLabel,
      nameGap: 48,
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'slider', xAxisIndex: 0, bottom: 20, height: 22, filterMode: 'none' },
    ],
    series: (compatibility.compatible ? entries : []).map((entry) => {
      const rows = metricSeries(entry, metric);
      return {
        name: shortRunLabel(entry.run.name, entry.run.status),
        type: 'line',
        showSymbol: rows.length <= 40,
        symbolSize: 5,
        sampling: 'lttb',
        lineStyle: { width: 3 },
        emphasis: { focus: 'series' },
        data: axisMode === 'progress' ? normalizedProgressSeries(rows) : rows,
      };
    }),
  };
}

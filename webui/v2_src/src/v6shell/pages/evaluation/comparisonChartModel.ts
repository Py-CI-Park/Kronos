import { equityReturnSeries, sampleRewardSeries, type EvaluationEntry } from './evaluationModel';

export type ComparisonMetric = 'equity' | 'reward';

export function shortRunLabel(name: string, status: string): string {
  const compactName = name.length > 20 ? `…${name.slice(-19)}` : name;
  return `${compactName} · ${status}`;
}

export function comparisonChartOptions(entries: readonly EvaluationEntry[], metric: ComparisonMetric) {
  return {
    animationDuration: 250,
    tooltip: { trigger: 'axis', confine: true },
    legend: { type: 'scroll', top: 0, left: 8, right: 8 },
    grid: { left: 66, right: 28, top: 58, bottom: 92, containLabel: true },
    xAxis: {
      type: 'value',
      name: 'step',
      nameLocation: 'middle',
      nameGap: 34,
      axisLabel: { hideOverlap: true },
      splitNumber: 6,
    },
    yAxis: {
      type: 'value',
      name: metric === 'equity' ? '기록 equity (%)' : '표본 reward 누적',
      nameGap: 48,
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'slider', xAxisIndex: 0, bottom: 18, height: 18, filterMode: 'none' },
    ],
    series: entries.map((entry) => ({
      name: shortRunLabel(entry.run.name, entry.run.status),
      type: 'line',
      showSymbol: false,
      sampling: 'lttb',
      emphasis: { focus: 'series' },
      data: metric === 'equity' ? equityReturnSeries(entry.snapshot) : sampleRewardSeries(entry.snapshot),
    })),
  };
}

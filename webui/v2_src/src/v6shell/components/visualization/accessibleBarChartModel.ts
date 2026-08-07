export interface BarChartItem {
  readonly label: string;
  readonly value: number;
  readonly displayValue?: string;
  readonly tone?: 'accent' | 'positive' | 'warning' | 'danger';
}

export interface BarChartRow extends BarChartItem {
  readonly display: string;
  readonly widthPercent: number;
}

export function buildBarChartRows(items: readonly BarChartItem[]): readonly BarChartRow[] {
  const maximum = Math.max(1, ...items.map((item) => Math.max(0, item.value)));
  return items.map((item) => ({
    ...item,
    display: item.displayValue ?? String(item.value),
    widthPercent: Math.max(0, Math.min(100, (item.value / maximum) * 100)),
  }));
}

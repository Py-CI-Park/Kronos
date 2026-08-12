// Chart accessibility helpers (Todo 10 / B2).
//
// EChartsRenderer draws to a <canvas>, which is opaque to assistive tech. These
// pure, deterministic derivations turn an ECharts `option` into (1) an
// accessible name, (2) a spoken trend summary, and (3) a tabular data
// alternative, so every chart satisfies the "accessible name, trend summary,
// and data alternative" contract WITHOUT fabricating values: only real
// series/axis data already present in the option is read. No profit/live claim.

export interface ChartDataTable {
  readonly columns: readonly string[];
  readonly rows: ReadonlyArray<ReadonlyArray<string | number>>;
}

type ChartRecord = Readonly<Record<string, unknown>>;
type AnyOption = ChartRecord | null | undefined;

// Cap the SR data table so a huge series (e.g. a multi-thousand-point loss
// curve) cannot inflate the DOM; the summary still reflects the full series.
const MAX_TABLE_ROWS = 80;

function asArray<T>(value: T | readonly T[] | undefined | null): T[] {
  if (value == null) return [];
  return Array.isArray(value) ? [...value] : [value as T];
}

function chartRecord(value: unknown): ChartRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function seriesList(option: AnyOption): ChartRecord[] {
  return asArray<unknown>(option?.series).flatMap((value) => {
    const series = chartRecord(value);
    return series === null ? [] : [series];
  });
}

function xAxisCategories(option: AnyOption): string[] {
  const axis = chartRecord(asArray<unknown>(option?.xAxis)[0]);
  const data = axis?.data;
  return Array.isArray(data) ? data.map((d: unknown) => String(d)) : [];
}

// Extracts a plotted numeric magnitude from an ECharts data point without
// coercing missing/non-numeric points to a fake 0 (returns null instead).
function numericValue(point: unknown): number | null {
  if (typeof point === 'number') return Number.isFinite(point) ? point : null;
  if (Array.isArray(point)) {
    // ECharts scatter tuples are [x, y, ...metadata]. Metadata may include
    // numeric step identifiers, so the plotted y must be read by position.
    const plotted = point.length >= 2 ? point[1] : point[0];
    return typeof plotted === 'number' && Number.isFinite(plotted) ? plotted : null;
  }
  if (point && typeof point === 'object' && 'value' in (point as Record<string, unknown>)) {
    const v = (point as Record<string, unknown>).value;
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
  }
  return null;
}

function round(n: number): number {
  return Math.round(n * 10000) / 10000;
}

function seriesName(series: ChartRecord, index: number): string {
  const raw = series?.name ?? series?.type;
  const name = raw == null ? '' : String(raw).trim();
  return name || `series ${index + 1}`;
}

export function chartAccessibleName(option: AnyOption, caption?: string): string {
  if (caption && caption.trim()) return caption.trim();
  const title = chartRecord(asArray<unknown>(option?.title)[0]);
  const parts = [title?.text, title?.subtext]
    .map((p) => (p == null ? '' : String(p).trim()))
    .filter((p) => p.length > 0);
  return parts.join(' — ') || '데이터 차트';
}

export function deriveChartSummary(option: AnyOption, caption?: string): string {
  const name = chartAccessibleName(option, caption);
  const series = seriesList(option);
  if (!series.length) return `${name}: 표시할 데이터 없음.`;

  const parts: string[] = [];
  series.forEach((s, index) => {
    const values: number[] = [];
    for (const point of asArray(s.data)) {
      const v = numericValue(point);
      if (v != null) values.push(v);
    }
    if (!values.length) return;
    let min = values[0];
    let max = values[0];
    for (const v of values) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    const first = values[0];
    const last = values[values.length - 1];
    const direction = last > first ? '상승' : last < first ? '하락' : '변화 없음';
    parts.push(
      `${seriesName(s, index)}: ${values.length}개 지점, 처음 ${round(first)} → 마지막 ${round(last)} (${direction}), 최소 ${round(min)}, 최대 ${round(max)}`,
    );
  });

  if (!parts.length) return `${name}: 수치 데이터 없음.`;
  return `${name}. ${parts.join('. ')}.`;
}

export function deriveChartTable(option: AnyOption): ChartDataTable | null {
  const series = seriesList(option);
  if (!series.length) return null;

  const categories = xAxisCategories(option);
  const maxLen = series.reduce((acc, s) => Math.max(acc, asArray(s.data).length), 0);
  if (!maxLen) return null;

  const limited = Math.min(maxLen, MAX_TABLE_ROWS);
  const columns = ['항목', ...series.map((s, i) => seriesName(s, i))];
  const rows: Array<Array<string | number>> = [];
  for (let i = 0; i < limited; i += 1) {
    const row: Array<string | number> = [categories[i] ?? String(i + 1)];
    for (const s of series) {
      const v = numericValue(asArray(s.data)[i]);
      row.push(v == null ? '—' : round(v));
    }
    rows.push(row);
  }
  return { columns, rows };
}

<script lang="ts">
  import type { MetricValue } from '../evidence';

  interface Props {
    label: string;
    metric: MetricValue;
    tone?: 'neutral' | 'positive' | 'warning' | 'danger';
  }

  let { label, metric, tone = 'neutral' }: Props = $props();

  const hasValidPrecision = $derived(
    metric.precision === null ||
      (Number.isFinite(metric.precision) &&
        Number.isInteger(metric.precision) &&
        metric.precision >= 0 &&
        metric.precision <= 12),
  );
  const sourceText = $derived(metric.source.trim() === '' ? 'SOURCE_NOT_RECORDED' : metric.source);
  const formattedValue = $derived.by(() => {
    if (metric.availability === 'INAPPLICABLE') return '해당 없음 · INAPPLICABLE';
    if (metric.availability === 'NOT_RECORDED') return '기록 없음 · NOT_RECORDED';
    if (metric.value === null) return '값 누락 · MISSING_VALUE';
    if (!Number.isFinite(metric.value)) return '값 무효 · INVALID_NONFINITE_VALUE';
    if (!hasValidPrecision) return '정밀도 무효 · INVALID_PRECISION';
    return metric.precision === null ? String(metric.value) : metric.value.toFixed(metric.precision);
  });
</script>

<article class="metric" class:positive={tone === 'positive'} class:warning={tone === 'warning'} class:danger={tone === 'danger'} data-v4-metric>
  <div class="metric-main">
    <p class="label">{label}</p>
    <p class="value">
      <span>{formattedValue}</span>
      {#if metric.value !== null && Number.isFinite(metric.value) && hasValidPrecision && metric.availability === 'RECORDED' && metric.unit}
        <span class="unit">{metric.unit}</span>
      {/if}
    </p>
  </div>

  <dl class="provenance" aria-label={`${label} provenance`}>
    <div>
      <dt>Availability</dt>
      <dd>{metric.availability}</dd>
    </div>
    {#if metric.kind}
      <div>
        <dt>Kind</dt>
        <dd>{metric.kind}</dd>
      </div>
    {/if}
    {#if metric.unit}
      <div>
        <dt>Unit</dt>
        <dd>{metric.unit}</dd>
      </div>
    {/if}
    {#if metric.precision !== null}
      <div>
        <dt>Precision</dt>
        <dd>{metric.precision}</dd>
      </div>
    {/if}
    <div>
      <dt>Source</dt>
      <dd>{sourceText}</dd>
    </div>
  </dl>
</article>

<style>
  .metric {
    display: grid;
    gap: 14px;
    min-width: 0;
    container-type: inline-size;
    padding: 16px;
    border: 1px solid var(--border-faint);
    border-radius: 18px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    color: var(--fg);
    font-family: var(--font-body);
    overflow-wrap: anywhere;
    word-break: auto-phrase;
  }

  .metric-main {
    display: grid;
    gap: 6px;
  }

  .label {
    margin: 0;
    color: var(--muted);
    font: 700 11px/1.2 var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .value {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 7px;
    margin: 0;
    color: var(--fg-strong);
    font: 760 clamp(22px, 10cqi, 34px) / 1 var(--font-display);
    letter-spacing: -0.05em;
  }

  .unit {
    color: var(--muted);
    font: 700 12px/1 var(--font-mono);
    letter-spacing: 0.04em;
  }

  .provenance {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0;
  }

  .provenance div {
    min-width: 0;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-pill);
    padding: 6px 9px;
    background: var(--surface-raised);
  }

  dt {
    color: var(--muted);
    font: 700 9px/1.2 var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  dd {
    margin: 2px 0 0;
    color: var(--fg-strong);
    font: 650 11px/1.25 var(--font-mono);
  }

  .positive {
    border-color: color-mix(in oklab, var(--success) 42%, var(--border));
  }

  .warning {
    border-color: color-mix(in oklab, var(--warn) 48%, var(--border));
  }

  .danger {
    border-color: color-mix(in oklab, var(--danger) 45%, var(--border));
  }

  @media (prefers-reduced-motion: reduce) {
    .metric,
    .metric * {
      scroll-behavior: auto;
    }
  }
</style>

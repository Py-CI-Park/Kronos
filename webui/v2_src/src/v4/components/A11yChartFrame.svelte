<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    name: string;
    summary: string;
    columns: readonly string[];
    rows: ReadonlyArray<ReadonlyArray<string | number | null | undefined>>;
    children?: Snippet;
    idPrefix?: string;
  }

  let { name, summary, columns, rows, children, idPrefix }: Props = $props();
  let tableWrap: HTMLDivElement | null = null;

  const componentId = $props.id();
  const toChartId = (value: string) =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'summary';
  const idBase = $derived(`v4-a11y-chart-${toChartId(idPrefix ?? name)}-${componentId}`);
  const summaryId = $derived(`${idBase}-summary`);
  const tableRegionId = $derived(`${idBase}-table`);

  const displayValue = (value: string | number | null | undefined) => {
    if (value === undefined) return 'MISSING';
    if (value === null) return 'NOT_RECORDED';
    if (value === '') return 'EMPTY_DECLARED';
    return String(value);
  };

  const scrollTable = (left: number) => {
    tableWrap?.scrollBy({ left, behavior: 'smooth' });
  };

  const handleTableScrollKey = (event: KeyboardEvent) => {
    const viewport = tableWrap?.clientWidth ?? 0;
    const step = Math.max(120, Math.round(viewport * 0.8));
    let left = 0;

    if (event.key === 'ArrowLeft') left = -step;
    else if (event.key === 'ArrowRight') left = step;
    else if (event.key === 'Home') left = -(tableWrap?.scrollWidth ?? 0);
    else if (event.key === 'End') left = tableWrap?.scrollWidth ?? 0;
    else return;

    event.preventDefault();
    scrollTable(left);
  };
</script>

<figure class="a11y-chart-frame" aria-label={name} aria-describedby={summaryId} data-v4-a11y-chart>
  <figcaption>
    <span>{name}</span>
    <small>시각 자료와 동일한 표 대체</small>
  </figcaption>
  <p id={summaryId} class="chart-summary">{summary}</p>
  <div class="chart-visual" aria-hidden={children ? undefined : 'true'}>
    {@render children?.()}
  </div>
  <div class="table-controls">
    <button type="button" class="table-scroll-control" aria-controls={tableRegionId} onkeydown={handleTableScrollKey} onclick={() => scrollTable(240)}>
      표 스크롤: ←/→/Home/End
    </button>
  </div>
  <div id={tableRegionId} class="table-wrap" role="region" aria-label={`${name} 표 대체`} bind:this={tableWrap}>
    <table>
      <caption>{summary}</caption>
      <thead>
        <tr>
          {#each columns as column}
            <th scope="col">{column}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr>
            {#each columns as _column, index}
              <td>{displayValue(row[index])}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <p class="chart-note">표 대체는 모든 원자료 행을 숨김 없이 표시합니다. 추세는 원자료에서 선언되지 않으면 만들지 않습니다.</p>
</figure>

<style>
  .a11y-chart-frame {
    margin: 0;
    display: grid;
    gap: 12px;
    border: 1px solid var(--border-faint);
    border-radius: 18px;
    padding: 14px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
  }

  figcaption {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    color: var(--fg-strong);
    font: 750 15px/1.2 var(--font-display);
  }

  figcaption small,
  .chart-summary,
  .chart-note {
    color: var(--muted);
    font: 500 12px/1.5 var(--font-body);
  }

  .chart-summary,
  .chart-note {
    margin: 0;
  }

  .chart-visual {
    min-height: 120px;
    border: 1px dashed var(--border);
    border-radius: 14px;
    padding: 12px;
    background: var(--surface-sunken);
  }

  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
  }

  .table-scroll-control:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .table-controls {
    display: flex;
    justify-content: flex-end;
  }

  .table-scroll-control {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-pill);
    padding: 6px 10px;
    background: var(--surface-raised);
    color: var(--fg-strong);
    font: 650 11px/1.2 var(--font-mono);
    cursor: pointer;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  caption {
    padding: 8px 10px;
    color: var(--muted);
    text-align: left;
  }

  th,
  td {
    padding: 8px 10px;
    border-top: 1px solid var(--border-faint);
    text-align: left;
    white-space: nowrap;
  }

  th {
    color: var(--fg-strong);
    background: var(--surface-sunken);
    font-weight: 750;
  }
</style>

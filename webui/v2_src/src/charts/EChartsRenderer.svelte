<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import * as echarts from 'echarts';

  import { chartAccessibleName, deriveChartSummary, deriveChartTable, type ChartDataTable } from './chartA11y';

  interface Props {
    option: any;
    height?: string;
    className?: string;
    /** Explicit accessible name; falls back to option.title, then a generic label. */
    caption?: string;
    /** Explicit trend summary; falls back to a derivation over the option's series. */
    summary?: string;
    /** Explicit data-table alternative; `undefined` derives from the option, `null` suppresses it. */
    dataTable?: ChartDataTable | null;
  }

  let { option, height = '320px', className = '', caption, summary, dataTable }: Props = $props();

  const accessibleName = $derived(chartAccessibleName(option, caption));
  const trendSummary = $derived(summary ?? deriveChartSummary(option, caption));
  const altTable = $derived(dataTable !== undefined ? dataTable : deriveChartTable(option));
  const hasAlt = $derived(hasRenderableOption(option));

  let container: HTMLDivElement | undefined = $state();
  let chart: echarts.ECharts | null = null;
  let observer: ResizeObserver | null = null;
  let frame: number | null = null;

  function hasRenderableOption(value: any): boolean {
    return value != null && typeof value === 'object' && Object.keys(value).length > 0;
  }

  async function applyOption(): Promise<void> {
    if (!chart || !container || !hasRenderableOption(option)) return;

    await tick();

    if (frame != null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(frame);
    }

    const render = () => {
      if (!chart || !container || !hasRenderableOption(option)) return;
      chart.resize();
      chart.setOption(option, {
        notMerge: false,
        lazyUpdate: true,
        replaceMerge: ['xAxis', 'yAxis', 'series', 'graphic'],
      });
    };

    if (typeof requestAnimationFrame === 'undefined') {
      render();
      return;
    }

    frame = requestAnimationFrame(render);
  }

  function onThemeChange(_e: Event) {
    // 옵션 자체는 CSS 변수를 참조하지 않고 그대로 들어오므로
    // 부모가 option 을 재계산해서 reactive 로 흘려보내면 자동 갱신됨.
    // 여기서는 레이아웃/옵션 재적용을 함께 트리거한다.
    void applyOption();
  }

  onMount(() => {
    if (!container) return;
    chart = echarts.init(container, null, { renderer: 'canvas' });
    observer = new ResizeObserver(() => void applyOption());
    observer.observe(container);
    document.addEventListener('kronos:theme', onThemeChange);
    void applyOption();
  });

  onDestroy(() => {
    if (frame != null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(frame);
    }
    observer?.disconnect();
    chart?.dispose();
    document.removeEventListener('kronos:theme', onThemeChange);
  });

  $effect(() => {
    void option;
    void applyOption();
  });
</script>

<figure class="echarts-figure">
  <div
    bind:this={container}
    class={className}
    role="img"
    aria-label={accessibleName}
    style="width: 100%; height: {height};"
  ></div>
  {#if hasAlt}
    <figcaption class="echarts-a11y-alt">
      <p>{trendSummary}</p>
      {#if altTable}
        <table>
          <caption>{accessibleName} · 데이터 표</caption>
          <thead>
            <tr>
              {#each altTable.columns as col}
                <th scope="col">{col}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each altTable.rows as row}
              <tr>
                {#each row as cell, ci}
                  {#if ci === 0}
                    <th scope="row">{cell}</th>
                  {:else}
                    <td>{cell}</td>
                  {/if}
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </figcaption>
  {/if}
</figure>

<style>
  .echarts-figure {
    margin: 0;
  }
  /* Screen-reader-only data alternative: keeps the accessible name + trend
     summary + data table available to AT without altering visual layout or
     the responsive fit (position:absolute, 1px clip). */
  .echarts-a11y-alt {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }
</style>

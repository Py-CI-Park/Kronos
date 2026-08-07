<script lang="ts">
  import { buildBarChartRows, type BarChartItem } from './accessibleBarChartModel';

  interface Props {
    readonly title: string;
    readonly ariaLabel: string;
    readonly summary: string;
    readonly items: readonly BarChartItem[];
    readonly valueHeader?: string;
  }

  let { title, ariaLabel, summary, items, valueHeader = '값' }: Props = $props();
  const rows = $derived(buildBarChartRows(items));
</script>

<figure data-accessible-bar-chart>
  <header><h3>{title}</h3><span>{items.length} SERIES</span></header>
  <div class="plot" role="img" aria-label={ariaLabel}>
    {#each rows as item}
      <div class="bar-row">
        <span>{item.label}</span>
        <div class="track"><i class={item.tone ?? 'accent'} style:width={`${item.widthPercent}%`}></i></div>
        <strong>{item.display}</strong>
      </div>
    {:else}
      <p>표시할 관측값이 없습니다.</p>
    {/each}
  </div>
  <details>
    <summary>표 데이터 보기</summary>
    <div class="table-wrap"><table><thead><tr><th>항목</th><th>{valueHeader}</th></tr></thead><tbody>{#each rows as item}<tr><td>{item.label}</td><td>{item.display}</td></tr>{/each}</tbody></table></div>
  </details>
  <figcaption>{summary}</figcaption>
</figure>

<style>
  figure{min-width:0;margin:0}header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}h3{margin:0;color:var(--fg-strong);font-size:.88rem}header span{color:var(--dim);font:800 .56rem var(--font-mono);letter-spacing:.08em}.plot{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:minmax(92px,.7fr) minmax(120px,2fr) auto;gap:10px;align-items:center}.bar-row>span{min-width:0;color:var(--fg);font-size:.68rem;overflow-wrap:anywhere}.bar-row strong{color:var(--fg-strong);font:.68rem var(--font-mono)}.track{height:8px;overflow:hidden;border-radius:999px;background:var(--border)}.track i{display:block;height:100%;border-radius:inherit;background:var(--accent)}.track i.positive{background:var(--success)}.track i.warning{background:var(--warn)}.track i.danger{background:var(--danger)}figcaption{margin-top:12px;color:var(--muted);font-size:.66rem;line-height:1.5}details{margin-top:10px}summary{width:max-content;cursor:pointer;color:var(--accent-strong);font-size:.64rem;font-weight:800}.table-wrap{margin-top:8px;overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:.65rem}th,td{border-top:1px solid var(--border);padding:7px;text-align:left}th{color:var(--muted)}td{color:var(--fg)}.plot>p{margin:0;color:var(--muted);font-size:.7rem}@media(max-width:520px){.bar-row{grid-template-columns:1fr auto}.track{grid-column:1/-1;grid-row:2}}
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { v6ChartEpoch, v6CssVar } from '../v6ChartTheme';
  import { getV6InsightFlow, getV6InsightSymbol, insightQuickPickCodes, type V6InsightFlow, type V6InsightSymbol, type V6InsightSeriesRow } from '../v6Api';

  type ChartOption = Record<string, unknown>;
  const formatter = new Intl.NumberFormat('ko-KR');
  let chartEpoch = $state('');
  let code = $state('005930');
  let data = $state<V6InsightSymbol | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);
  let flow = $state<V6InsightFlow | null>(null);
  v6ChartEpoch.subscribe((value) => (chartEpoch = value));

  function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
  const color = v6CssVar;
  function date(value: unknown): string { return finite(value) ? String(value) : 'MISSING'; }
  const rows = $derived((data?.series ?? []).filter((row): row is V6InsightSeriesRow => Boolean(row?.date)));
  const categories = $derived(rows.map((row) => date(row.date)));
  const quickPicks = $derived(insightQuickPickCodes(flow));
  const closeOption = $derived.by<ChartOption>(() => {
    void chartEpoch;
    return { backgroundColor: 'transparent', grid: { left: 76, right: 28, top: 34, bottom: 78 }, tooltip: { trigger: 'axis' }, dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 14 }], xAxis: { type: 'category', data: categories, boundaryGap: false, axisLabel: { color: color('--muted') } }, yAxis: { type: 'value', name: '종가', axisLabel: { color: color('--muted'), formatter: (value: number) => `₩${formatter.format(value)}` }, splitLine: { lineStyle: { color: color('--border') } } }, series: [{ name: '종가', type: 'line', symbol: 'none', connectNulls: false, data: rows.map((row) => finite(row.close) ? row.close : null), lineStyle: { color: color('--accent'), width: 2.5 } }] };
  });
  const flowOption = $derived.by<ChartOption>(() => {
    void chartEpoch;
    return { backgroundColor: 'transparent', grid: { left: 62, right: 78, top: 32, bottom: 30 }, tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: categories, axisLabel: { color: color('--muted'), hideOverlap: true } }, yAxis: [{ type: 'value', name: '외국인 %', axisLabel: { color: color('--muted'), formatter: '{value}%' }, splitLine: { lineStyle: { color: color('--border') } } }, { type: 'value', name: '기관 순매수', axisLabel: { color: color('--muted'), formatter: (value: number) => `₩${formatter.format(value)}` } }], series: [{ name: '외국인 비율', type: 'line', yAxisIndex: 0, symbol: 'none', connectNulls: false, data: rows.map((row) => finite(row.foreign_ratio) ? row.foreign_ratio : null), lineStyle: { color: color('--info'), width: 2.2 } }, { name: '기관 순매수', type: 'bar', yAxisIndex: 1, data: rows.map((row) => finite(row.inst_netbuy) ? row.inst_netbuy : null), itemStyle: { color: (item: { value?: number }) => Number(item.value) >= 0 ? color('--success') : color('--danger') } }] };
  });
  async function load(): Promise<void> {
    const normalized = code.trim();
    if (!/^\d{6}$/.test(normalized)) { error = '종목 코드는 숫자 6자리여야 합니다.'; data = null; return; }
    loading = true; error = null;
    const result = await getV6InsightSymbol(normalized);
    loading = false;
    if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; }
  }
  async function loadQuickPicks(): Promise<void> {
    const result = await getV6InsightFlow(20, 20);
    if (result.ok && result.data) flow = result.data;
  }
  function selectCode(nextCode: string): void {
    code = nextCode;
    void load();
  }
  onMount(() => { void Promise.all([load(), loadQuickPicks()]); });
</script>

<section class="page" aria-labelledby="symbol-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="symbol-title">종목 심층</h1><p>가격과 공시된 수급 열을 연구 관측용으로 표시합니다. 매매 추천이 아닙니다.</p></header>
  <form class="lookup" onsubmit={(event) => { event.preventDefault(); load(); }}><label for="symbol-code">종목 코드</label><input id="symbol-code" bind:value={code} inputmode="numeric" pattern="[0-9]{6}" maxlength="6" aria-describedby="code-help" /><button type="submit">조회</button><small id="code-help">숫자 6자리</small></form>
  {#if quickPicks.length}
    <section class="quick-picks" aria-labelledby="quick-picks-title"><div><p class="eyebrow">MULTI-SYMBOL ENTRY</p><h2 id="quick-picks-title">다른 종목 빠르게 보기</h2><small>수급 관측 목록에서 가져온 탐색 진입점이며 매수 추천이 아닙니다.</small></div><div class="pick-list">{#each quickPicks as pick}<button type="button" class:active={pick === code} onclick={() => selectCode(pick)}>{pick}</button>{/each}</div></section>
  {/if}
  {#if loading}<section class="panel" aria-live="polite">종목 일별 관측값을 읽고 있습니다.</section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>종목 심층을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else if !data || data.status !== 'OK' || !rows.length}<section class="panel empty"><h2>표시할 관측값이 없습니다</h2><p>{data?.reason ?? '요청한 종목의 일별 연구 데이터가 없거나 현재 차단되어 있습니다.'}</p></section>
  {:else}<section class="card"><div class="chart-head"><div><h2>{data.code ?? code}</h2><p>{data.total_rows ?? rows.length}개 일별 행</p></div>{#if data.sampled}<span class="chip">표본화됨 · 원본 전체가 아님</span>{/if}</div><EChartsRenderer option={closeOption} height="380px" caption="종가 · 기간 선택 가능" /><EChartsRenderer option={flowOption} height="200px" caption="외국인 비율과 기관 순매수" /><div class="caveats"><span class="chip">가격 기준 미검증</span><span class="chip">수급 시점 미검증</span></div></section>{/if}
</section>

<style>
  .page { width: 100%; color: var(--fg); } header, .card, .panel, .quick-picks { border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 30px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.9rem, 6vw, 2.7rem); } header > p:last-child, .chart-head p { color: var(--muted); font-size: 1.05rem; } .lookup { display: flex; flex-wrap: wrap; align-items: end; gap: 10px; margin: 18px 0; font-size: 1.05rem; } label { display: grid; gap: 5px; color: var(--muted); } input { width: 8rem; border: 1px solid var(--border-strong); border-radius: 6px; padding: 9px; background: var(--surface-sunken); color: var(--fg-strong); font: inherit; } button { border: 1px solid var(--accent); border-radius: 6px; padding: 9px 13px; background: transparent; color: var(--accent-strong); font: inherit; cursor:pointer }button:focus-visible{outline:2px solid var(--warn);outline-offset:2px} small { color: var(--muted); }.quick-picks { display:grid;grid-template-columns:minmax(180px,.65fr) minmax(0,1.35fr);gap:14px;align-items:center;margin-bottom:18px;background:var(--surface-raised) }.quick-picks h2{margin:5px 0}.pick-list{display:flex;flex-wrap:wrap;gap:8px}.pick-list button{font-family:ui-monospace,monospace;font-weight:800}.pick-list button.active{background:var(--accent-soft);box-shadow:0 0 0 2px var(--accent-soft)}.card, .panel { margin-top: 18px; } .chart-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; } h2 { margin: 0; color: var(--fg-strong); font-size: 1.2rem; } .chart-head p { margin: 5px 0 0; } .chip { display: inline-block; border: 1px solid var(--warn); border-radius: 999px; padding: 4px 8px; color: var(--warn); font-size: .82rem; } .caveats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; } .error { border-color: var(--danger); color: var(--danger); } .empty { border-color: var(--warn); background: var(--warn-soft); }@media(max-width:640px){.quick-picks{grid-template-columns:1fr}}
</style>

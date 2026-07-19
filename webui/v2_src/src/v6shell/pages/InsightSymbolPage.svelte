<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6InsightSymbol, type V6InsightSymbol } from '../v6Api';

  const WIDTH = 900;
  const TOP_Y = 20;
  const TOP_H = 190;
  const BOTTOM_Y = 265;
  const BOTTOM_H = 150;
  let code = $state('005930');
  let data = $state<V6InsightSymbol | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);

  function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
  function points(field: 'close' | 'foreign_ratio'): string {
    const rows = data?.series ?? [];
    const values = rows.map((row) => row[field]).filter(finite);
    if (!values.length) return '';
    const low = Math.min(...values); const high = Math.max(...values); const span = high - low || 1;
    return rows.map((row, index) => {
      const value = row[field];
      return finite(value) ? `${(index / Math.max(rows.length - 1, 1)) * WIDTH},${(field === 'close' ? TOP_Y : BOTTOM_Y) + (1 - (value - low) / span) * (field === 'close' ? TOP_H : BOTTOM_H)}` : '';
    }).filter(Boolean).join(' ');
  }
  function bars(): { x: number; y: number; height: number; positive: boolean }[] {
    const rows = data?.series ?? []; const values = rows.map((row) => row.inst_netbuy).filter(finite); const max = Math.max(...values.map((value) => Math.abs(value)), 1);
    const base = BOTTOM_Y + BOTTOM_H / 2;
    return rows.flatMap((row, index) => !finite(row.inst_netbuy) ? [] : [{ x: (index / Math.max(rows.length - 1, 1)) * WIDTH, y: row.inst_netbuy >= 0 ? base - Math.abs(row.inst_netbuy) / max * (BOTTOM_H / 2) : base, height: Math.abs(row.inst_netbuy) / max * (BOTTOM_H / 2), positive: row.inst_netbuy >= 0 }]);
  }
  function date(value: unknown): string { return finite(value) ? String(value) : 'MISSING'; }
  async function load(): Promise<void> {
    const normalized = code.trim();
    if (!/^\d{6}$/.test(normalized)) { error = '종목 코드는 숫자 6자리여야 합니다.'; data = null; return; }
    loading = true; error = null;
    const result = await getV6InsightSymbol(normalized);
    loading = false;
    if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; }
  }
  onMount(load);
</script>

<section class="page" aria-labelledby="symbol-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="symbol-title">종목 심층</h1><p>가격과 공시된 수급 열을 연구 관측용으로 표시합니다. 매매 추천이 아닙니다.</p></header>
  <form class="lookup" onsubmit={(event) => { event.preventDefault(); load(); }}><label for="symbol-code">종목 코드</label><input id="symbol-code" bind:value={code} inputmode="numeric" pattern="[0-9]{6}" maxlength="6" aria-describedby="code-help" /><button type="submit">조회</button><small id="code-help">숫자 6자리</small></form>
  {#if loading}<section class="panel" aria-live="polite">종목 일별 관측값을 읽고 있습니다.</section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>종목 심층을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else if !data || data.status !== 'OK' || !(data.series?.length)}<section class="panel empty"><h2>표시할 관측값이 없습니다</h2><p>{data?.reason ?? '요청한 종목의 일별 연구 데이터가 없거나 현재 차단되어 있습니다.'}</p></section>
  {:else}
    <section class="card"><div class="chart-head"><div><h2>{data.code ?? code}</h2><p>{data.total_rows ?? data.series.length}개 일별 행</p></div>{#if data.sampled}<span class="chip">표본화됨 · 원본 전체가 아님</span>{/if}</div>
      <svg viewBox={`0 0 ${WIDTH} 450`} preserveAspectRatio="none" role="img" aria-label="종가, 외국인 비율, 기관 순매수 시계열"><rect x="0" y={TOP_Y} width={WIDTH} height={TOP_H} class="pane" /><rect x="0" y={BOTTOM_Y} width={WIDTH} height={BOTTOM_H} class="pane" /><line x1="0" x2={WIDTH} y1={BOTTOM_Y + BOTTOM_H / 2} y2={BOTTOM_Y + BOTTOM_H / 2} class="zero" />{#each bars() as bar}<line x1={bar.x} x2={bar.x} y1={bar.y} y2={bar.y + bar.height} class:positive={bar.positive} class:negative={!bar.positive} />{/each}{#if points('close')}<polyline points={points('close')} class="close" />{/if}{#if points('foreign_ratio')}<polyline points={points('foreign_ratio')} class="foreign" />{/if}<text x="8" y="42">종가</text><text x="8" y="287">외국인 비율 · 기관 순매수 막대</text></svg>
      <div class="dates"><span>{date(data.series[0]?.date)}</span><span>{date(data.series[data.series.length - 1]?.date)}</span></div>
      <p class="legend"><span class="line close-key"></span>종가 <span class="line foreign-key"></span>외국인 비율 <span class="bar-key"></span>기관 순매수/순매도</p>
      <div class="caveats"><p>{data.price_basis_caveat ?? '가격 기준 정보가 제공되지 않았습니다.'}</p><p>{data.flow_caveat ?? '수급 정보의 시차·정정 가능성을 확인해야 합니다.'}</p></div>
    </section>
  {/if}
</section>

<style>
  .page { max-width: 980px; color: var(--fg); } header, .card, .panel { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p:last-child, .chart-head p { color: var(--muted); } .lookup { display: flex; flex-wrap: wrap; align-items: end; gap: 8px; margin: 16px 0; } label { display: grid; gap: 5px; color: var(--muted); font-size: .82rem; } input { width: 8rem; border: 1px solid var(--border-strong); border-radius: 6px; padding: 8px; background: var(--surface-sunken); color: var(--fg-strong); font: inherit; } button { border: 1px solid var(--accent); border-radius: 6px; padding: 8px 12px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; } small { color: var(--muted); }.card, .panel { margin-top: 16px; } .chart-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; } h2 { margin: 0; color: var(--fg-strong); font-size: 1.1rem; } .chart-head p { margin: 5px 0 0; } .chip { border: 1px solid var(--warn); border-radius: 999px; padding: 3px 7px; color: var(--warn); font-size: .72rem; } svg { width: 100%; height: 360px; margin-top: 14px; background: var(--surface-sunken); } .pane { fill: var(--surface-raised); stroke: var(--border); } .zero { stroke: var(--border-strong); stroke-dasharray: 5 5; } polyline { fill: none; stroke-width: 3; vector-effect: non-scaling-stroke; } .close { stroke: var(--accent); } .foreign { stroke: var(--c-5); } line.positive { stroke: var(--success); } line.negative { stroke: var(--danger); } text { fill: var(--muted); font-size: 19px; } .dates, .legend { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: .78rem; overflow-wrap: anywhere; } .legend { justify-content: start; align-items: center; flex-wrap: wrap; } .line { width: 16px; border-top: 3px solid; } .close-key { border-color: var(--accent); } .foreign-key { border-color: var(--c-5); } .bar-key { width: 3px; height: 12px; background: var(--success); } .caveats { margin-top: 12px; border-top: 1px solid var(--border-strong); color: var(--warn); font-size: .83rem; overflow-wrap: anywhere; } .error { border-color: var(--danger); color: var(--danger); } .empty { border-color: var(--warn); background: var(--warn-soft); } @media (max-width: 390px) { svg { height: 300px; } .lookup small { width: 100%; } }
</style>

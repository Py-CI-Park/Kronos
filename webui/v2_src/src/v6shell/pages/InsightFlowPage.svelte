<script lang="ts">
  import { onMount } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { theme } from '$lib/stores';
  import { getV6InsightFlow, type V6InsightFlow, type V6InsightFlowRow } from '../v6Api';
  type ChartOption = Record<string, unknown>;
  let currentTheme = $state<'light' | 'dark'>('light');
  let windowSize = $state(20);
  let data = $state<V6InsightFlow | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);
  const formatter = new Intl.NumberFormat('ko-KR');
  theme.subscribe((value) => (currentTheme = value));
  function color(name: string): string { return typeof document === 'undefined' ? '' : getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function text(value: unknown): string { return value === undefined || value === null || value === '' ? 'MISSING' : String(value); }
  function won(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `₩${formatter.format(value)}` : 'MISSING'; }
  function signed(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? formatter.format(value) : 'MISSING'; }
  function ratio(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)}%p` : 'MISSING'; }
  function chartOption(rows: readonly V6InsightFlowRow[] | undefined, mode: 'institution' | 'foreign'): ChartOption {
    void currentTheme;
    const sample = (rows ?? []).slice(0, 15);
    const values = sample.map((row) => mode === 'institution' ? row.inst_netbuy_sum : row.foreign_ratio_delta);
    return { backgroundColor: 'transparent', grid: { left: mode === 'institution' ? 86 : 64, right: 26, top: 22, bottom: 28 }, tooltip: { trigger: 'axis' }, xAxis: { type: 'value', axisLabel: { color: color('--muted'), formatter: (value: number) => mode === 'institution' ? `₩${formatter.format(value)}` : `${value}%p` }, splitLine: { lineStyle: { color: color('--border') } } }, yAxis: { type: 'category', inverse: true, data: sample.map((row) => text(row.code)), axisLabel: { color: color('--muted') } }, series: [{ name: mode === 'institution' ? '기관 순매수 합계' : '외국인 비율 변화', type: 'bar', data: values, itemStyle: { color: (item: { value?: number }) => Number(item.value) >= 0 ? color('--success') : color('--danger'), borderRadius: [0, 5, 5, 0] } }] };
  }
  async function load(): Promise<void> { loading = true; error = null; const result = await getV6InsightFlow(windowSize); loading = false; if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; } }
  onMount(load);
</script>

<section class="page" aria-labelledby="flow-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="flow-title">수급 흐름</h1><p class="banner">연구 관측용 순위 · 매수 추천 아님</p><p>기관 순매수와 외국인 보유비율 변화를 일별 DB에서 집계합니다. 수급 값은 공시·정정 시차가 있을 수 있습니다.</p></header>
  <div class="controls"><label for="flow-window">집계 기간</label><select id="flow-window" bind:value={windowSize} onchange={load}><option value={20}>20일</option><option value={60}>60일</option><option value={120}>120일</option></select><button type="button" onclick={load}>새로고침</button></div>
  {#if loading}<section class="panel" aria-live="polite"><h2>수급 순위를 계산하고 있습니다</h2><p>최초 스캔은 일별 DB 전체를 확인하므로 몇 초 걸릴 수 있습니다.</p></section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>수급 흐름을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else if !data || data.status !== 'OK'}<section class="panel empty"><h2>표시할 수급 순위가 없습니다</h2><p>{data?.reason ?? '연구용 수급 데이터를 현재 제공할 수 없습니다.'}</p></section>
  {:else}<p class="note">{data.note ?? `${data.window ?? windowSize}일 관측 창의 순위입니다.`}</p><div class="caveats"><p>{data.price_basis_caveat ?? '가격 기준은 검증 전이며 수익률 근거로 사용할 수 없습니다.'}</p><p>{data.flow_caveat ?? '수급 정보에는 공시·정정 시차가 있을 수 있습니다.'}</p></div><div class="grid">{@render Ranking('기관 순매수 상위', data.top_inst_buy, 'institution')}{@render Ranking('기관 순매수 하위', data.top_inst_sell, 'institution')}{@render Ranking('외국인 비율 증가', data.top_foreign_gain, 'foreign')}{@render Ranking('외국인 비율 감소', data.top_foreign_loss, 'foreign')}</div>{/if}
</section>

{#snippet Ranking(title: string, rows: readonly V6InsightFlowRow[] | undefined, mode: 'institution' | 'foreign')}
  <section class="ranking"><h2>{title}</h2>{#if rows?.length}<EChartsRenderer option={chartOption(rows, mode)} height="420px" caption={`${title} · 상위 15개`} /><details><summary>표로 보기</summary><div class="table-wrap"><table><thead><tr><th>코드</th><th>종가</th><th>{mode === 'institution' ? '기관 순매수 합계' : '외국인 비율 변화'}</th><th>기준일</th></tr></thead><tbody>{#each rows.slice(0, 15) as row}<tr><td>{text(row.code)}</td><td>{won(row.last_close)}</td><td>{mode === 'institution' ? signed(row.inst_netbuy_sum) : ratio(row.foreign_ratio_delta)}</td><td>{text(row.last_date)}</td></tr>{/each}</tbody></table></div></details>{:else}<p class="missing">집계된 행이 없습니다.</p>{/if}</section>
{/snippet}

<style>
  .page { width: 100%; color: var(--fg); } header, .panel, .ranking { border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 30px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.9rem, 6vw, 2.7rem); } h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.15rem; } header > p:last-child { color: var(--muted); font-size: 1.05rem; } .banner { display: inline-block; margin: 8px 0; border: 1px solid var(--warn); border-radius: 7px; padding: 9px 11px; background: var(--warn-soft); color: var(--warn); font-weight: 800; }.controls { display: flex; flex-wrap: wrap; align-items: end; gap: 10px; margin: 18px 0; font-size: 1.05rem; } label { display: grid; gap: 5px; color: var(--muted); } select, button { border: 1px solid var(--border-strong); border-radius: 6px; padding: 9px; background: var(--surface-sunken); color: var(--fg-strong); font: inherit; } button { border-color: var(--accent); color: var(--accent-strong); cursor: pointer; } .panel { margin-top: 18px; } .note { border-left: 3px solid var(--accent); padding-left: 10px; color: var(--muted); font-size: 1.05rem; overflow-wrap: anywhere; } .caveats { margin: 14px 0; border-left: 3px solid var(--warn); padding-left: 10px; color: var(--warn); font-size: .93rem; overflow-wrap: anywhere; } .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; } .ranking { min-width: 0; } details { margin-top: 12px; color: var(--muted); } summary { cursor: pointer; color: var(--accent-strong); font-weight: 700; } .table-wrap { max-width: 100%; overflow-x: auto; margin-top: 10px; } table { width: 100%; border-collapse: collapse; font-size: .88rem; } th, td { border-top: 1px solid var(--border); padding: 8px; text-align: left; overflow-wrap: anywhere; } th { color: var(--muted); } .missing { color: var(--muted); } .error { border-color: var(--danger); color: var(--danger); } .empty { border-color: var(--warn); background: var(--warn-soft); }
</style>

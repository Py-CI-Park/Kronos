<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6InsightFlow, type V6InsightFlow, type V6InsightFlowRow } from '../v6Api';
  let windowSize = $state(20);
  let data = $state<V6InsightFlow | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);
  const formatter = new Intl.NumberFormat('ko-KR');
  function text(value: unknown): string { return value === undefined || value === null || value === '' ? 'MISSING' : String(value); }
  function won(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `₩${formatter.format(value)}` : 'MISSING'; }
  function signed(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? formatter.format(value) : 'MISSING'; }
  function ratio(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)}%p` : 'MISSING'; }
  async function load(): Promise<void> { loading = true; error = null; const result = await getV6InsightFlow(windowSize); loading = false; if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; } }
  onMount(load);
</script>

<section class="page" aria-labelledby="flow-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="flow-title">수급 흐름</h1><p class="banner">연구 관측용 순위 · 매수 추천 아님</p><p>기관 순매수와 외국인 보유비율 변화를 일별 DB에서 집계합니다. 수급 값은 공시·정정 시차가 있을 수 있습니다.</p></header>
  <div class="controls"><label for="flow-window">집계 기간</label><select id="flow-window" bind:value={windowSize} onchange={load}><option value={20}>20일</option><option value={60}>60일</option><option value={120}>120일</option></select><button type="button" onclick={load}>새로고침</button></div>
  {#if loading}<section class="panel" aria-live="polite"><h2>수급 순위를 계산하고 있습니다</h2><p>최초 스캔은 일별 DB 전체를 확인하므로 몇 초 걸릴 수 있습니다.</p></section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>수급 흐름을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else if !data || data.status !== 'OK'}<section class="panel empty"><h2>표시할 수급 순위가 없습니다</h2><p>{data?.reason ?? '연구용 수급 데이터를 현재 제공할 수 없습니다.'}</p></section>
  {:else}
    <p class="note">{data.note ?? `${data.window ?? windowSize}일 관측 창의 순위입니다.`}</p>
    <div class="caveats"><p>{data.price_basis_caveat ?? '가격 기준은 검증 전이며 수익률 근거로 사용할 수 없습니다.'}</p><p>{data.flow_caveat ?? '수급 정보에는 공시·정정 시차가 있을 수 있습니다.'}</p></div>
    <div class="grid">{@render Ranking('기관 순매수 상위', data.top_inst_buy, 'institution')}{@render Ranking('기관 순매수 하위', data.top_inst_sell, 'institution')}{@render Ranking('외국인 비율 증가', data.top_foreign_gain, 'foreign')}{@render Ranking('외국인 비율 감소', data.top_foreign_loss, 'foreign')}</div>
  {/if}
</section>

{#snippet Ranking(title: string, rows: readonly V6InsightFlowRow[] | undefined, mode: 'institution' | 'foreign')}
  <section class="ranking"><h2>{title}</h2>{#if rows?.length}<div class="table-wrap"><table><thead><tr><th>코드</th><th>종가</th><th>{mode === 'institution' ? '기관 순매수 합계' : '외국인 비율 변화'}</th><th>기준일</th></tr></thead><tbody>{#each rows as row}<tr><td>{text(row.code)}</td><td>{won(row.last_close)}</td><td>{mode === 'institution' ? signed(row.inst_netbuy_sum) : ratio(row.foreign_ratio_delta)}</td><td>{text(row.last_date)}</td></tr>{/each}</tbody></table></div>{:else}<p class="missing">집계된 행이 없습니다.</p>{/if}</section>
{/snippet}

<style>
  .page { max-width: 1100px; color: #e5e7eb; } header, .panel, .ranking { border: 1px solid #334155; border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: #111827; } .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); } h2 { margin: 0 0 12px; color: #f8fafc; font-size: 1.05rem; } header > p:last-child { color: #cbd5e1; } .banner { display: inline-block; margin: 8px 0; border: 1px solid #f59e0b; border-radius: 7px; padding: 8px 10px; background: #451a03; color: #fef3c7; font-weight: 800; }.controls { display: flex; flex-wrap: wrap; align-items: end; gap: 8px; margin: 16px 0; } label { display: grid; gap: 5px; color: #cbd5e1; font-size: .82rem; } select, button { border: 1px solid #475569; border-radius: 6px; padding: 8px; background: #020617; color: #f8fafc; font: inherit; } button { border-color: #7dd3fc; color: #e0f2fe; cursor: pointer; } .panel { margin-top: 16px; } .note { border-left: 3px solid #38bdf8; padding-left: 10px; color: #cbd5e1; overflow-wrap: anywhere; } .caveats { margin: 12px 0; border-left: 3px solid #f59e0b; padding-left: 10px; color: #fde68a; font-size: .83rem; overflow-wrap: anywhere; } .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; } .ranking { min-width: 0; } .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-size: .78rem; } th, td { border-top: 1px solid #334155; padding: 7px; text-align: left; overflow-wrap: anywhere; } th { color: #94a3b8; } .missing { color: #94a3b8; } .error { border-color: #b91c1c; color: #fecaca; } .empty { border-color: #a16207; background: #1c1910; } @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } } @media (max-width: 390px) { th, td { padding: 6px 4px; font-size: .7rem; } }
</style>

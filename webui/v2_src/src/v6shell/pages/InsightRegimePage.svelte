<script lang="ts">
  import { onMount } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { v6ChartEpoch, v6CssVar } from '../v6ChartTheme';
  import { getV6InsightRegime, type V6InsightRegime } from '../v6Api';
  type ChartOption = Record<string, unknown>;
  let chartEpoch = $state('');
  let data = $state<V6InsightRegime | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  v6ChartEpoch.subscribe((value) => (chartEpoch = value));
  function percent(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)}%` : 'MISSING'; }
  const color = v6CssVar;
  function hasBreadthValue(): boolean { return typeof data?.breadth_proxy?.pct_above_20s_mean === 'number' && Number.isFinite(data.breadth_proxy.pct_above_20s_mean); }
  const breadthOption = $derived.by<ChartOption>(() => {
    void chartEpoch;
    const value = data?.breadth_proxy?.pct_above_20s_mean;
    return { backgroundColor: 'transparent', series: [{ type: 'gauge', min: 0, max: 100, progress: { show: true, width: 16, itemStyle: { color: color('--accent') } }, axisLine: { lineStyle: { width: 16, color: [[0.35, color('--danger-soft')], [0.65, color('--surface-raised')], [1, color('--success-soft')]] } }, axisTick: { lineStyle: { color: color('--border-strong') } }, splitLine: { lineStyle: { color: color('--border-strong') } }, axisLabel: { color: color('--muted') }, pointer: { itemStyle: { color: color('--fg-strong') } }, title: { color: color('--muted'), fontSize: 14 }, detail: { valueAnimation: true, formatter: '{value}%', color: color('--fg-strong'), fontSize: 28 }, data: [{ value, name: '약세 <35 · 중립 35–65 · 강세 >65' }] }] };
  });
  async function load(): Promise<void> { loading = true; error = null; const result = await getV6InsightRegime(); loading = false; if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; } }
  onMount(load);
</script>

<section class="page" aria-labelledby="regime-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="regime-title">시장 국면</h1><p>지수 비교 체계와 종목 단면 대용지표를 분리해 표시합니다. 둘 다 매매 판단이 아닙니다.</p></header>
  {#if loading}<section class="panel" aria-live="polite">시장 국면 연구 상태를 읽고 있습니다.</section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>시장 국면을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else}{@const regime = data?.index_regime}{@const regimePresent = regime?.state === 'PRESENT'}<div class="cards"><section class="card" class:blocked={!regimePresent} class:present={regimePresent}><p class="state">{regime?.state ?? 'BLOCKED'}</p><h2>지수 국면</h2>{#if regimePresent}<dl>{#each Object.entries(regime?.markets ?? {}) as [market, detail]}<dt>{market}</dt><dd>종가 {typeof detail.last_close === 'number' ? new Intl.NumberFormat('ko-KR').format(detail.last_close) : 'MISSING'} · {detail.last_date ?? 'MISSING'} · 20일 평균 대비 {percent(detail.pct_vs_20d_mean)}</dd>{/each}</dl><p class="disclaimer">{regime?.caveat ?? 'pykrx offline artifact index levels only; observation only, not a trading signal'}</p>{:else}<p>{regime?.reason ?? 'KRX 자격증명이 없어 지수 시계열을 수집·검증하지 못했습니다.'}</p><p class="command-label">수집 명령</p><code>py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index</code>{/if}</section><section class="card breadth"><p class="state">BREADTH PROXY</p><h2>20일 평균 초과 비율</h2>{#if hasBreadthValue()}<EChartsRenderer option={breadthOption} height="420px" caption="20일 평균 초과 비율 · 약세/중립/강세 휴리스틱" /><p class="disclaimer">{data?.breadth_proxy?.disclaimer}</p>{:else}<p>종목 단면 대용지표를 계산한 결과가 없습니다.</p>{/if}</section><section class="card scope"><p class="state">EVALUATION SCOPE</p><h2>평가 범위</h2>{#if data?.breadth_proxy}<dl><dt>평가 테이블</dt><dd>{data.breadth_proxy.tables_evaluated ?? 'MISSING'}</dd><dt>기준일</dt><dd>{data.breadth_proxy.as_of_date ?? 'MISSING'}</dd><dt>20일 평균 초과</dt><dd>{percent(data.breadth_proxy.pct_above_20s_mean)}</dd></dl>{:else}<p>평가 범위 데이터가 없습니다.</p>{/if}</section></div>{/if}
</section>

<style>
  .page { width: 100%; color: var(--fg); } header, .panel, .card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 30px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.9rem, 6vw, 2.7rem); } h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.2rem; } header > p:last-child { color: var(--muted); font-size: 1.05rem; } .panel { margin-top: 18px; } .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-top: 18px; } .card { min-width: 0; } .blocked { border-color: var(--danger); background: var(--danger-soft); } .state { margin: 0 0 8px; color: var(--danger); font-size: .84rem; font-weight: 900; letter-spacing: .1em; } .present .state { color: var(--success); } .breadth .state, .scope .state { color: var(--accent); } .command-label { margin: 18px 0 6px; color: var(--danger); font-size: .9rem; font-weight: 800; } code { display: block; overflow-wrap: anywhere; border: 1px solid var(--danger); padding: 10px; background: var(--surface-sunken); color: var(--danger); font-size: .88rem; } dl { display: grid; grid-template-columns: auto 1fr; gap: 10px 18px; border-top: 1px solid var(--border); padding-top: 14px; font-size: 1.05rem; } dt { color: var(--muted); } dd { margin: 0; overflow-wrap: anywhere; } .disclaimer { border-top: 1px solid var(--border-strong); padding-top: 12px; color: var(--warn); font-size: .93rem; overflow-wrap: anywhere; } .error { border-color: var(--danger); color: var(--danger); } button { border: 1px solid var(--accent); border-radius: 6px; padding: 9px 13px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; }
</style>

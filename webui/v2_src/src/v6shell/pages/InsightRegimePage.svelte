<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6InsightRegime, type V6InsightRegime } from '../v6Api';
  let data = $state<V6InsightRegime | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  function percent(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)}%` : 'MISSING'; }
  async function load(): Promise<void> { loading = true; error = null; const result = await getV6InsightRegime(); loading = false; if (result.ok && result.data) data = result.data; else { data = null; error = result.error ?? '알 수 없는 오류가 발생했습니다.'; } }
  onMount(load);
</script>

<section class="page" aria-labelledby="regime-title">
  <header><p class="eyebrow">RESEARCH OBSERVATION</p><h1 id="regime-title">시장 국면</h1><p>지수 비교 체계와 종목 단면 대용지표를 분리해 표시합니다. 둘 다 매매 판단이 아닙니다.</p></header>
  {#if loading}<section class="panel" aria-live="polite">시장 국면 연구 상태를 읽고 있습니다.</section>
  {:else if error}<section class="panel error" aria-live="assertive"><h2>시장 국면을 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else}
    <div class="cards"><section class="card blocked"><p class="state">{data?.index_regime?.state ?? 'BLOCKED'}</p><h2>지수 국면</h2><p>{data?.index_regime?.reason ?? 'KRX 자격증명이 없어 지수 시계열을 수집·검증하지 못했습니다.'}</p><p class="command-label">수집 명령</p><code>py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index</code></section>
      <section class="card breadth"><p class="state">BREADTH PROXY</p><h2>20일 평균 초과 비율</h2>{#if data?.breadth_proxy}<p class="big">{percent(data.breadth_proxy.pct_above_20s_mean)}</p><dl><dt>기준일</dt><dd>{data.breadth_proxy.as_of_date ?? 'MISSING'}</dd><dt>평가 테이블</dt><dd>{data.breadth_proxy.tables_evaluated ?? 'MISSING'}</dd></dl><p class="disclaimer">{data.breadth_proxy.disclaimer}</p>{:else}<p>종목 단면 대용지표를 계산한 결과가 없습니다.</p>{/if}</section></div>
  {/if}
</section>

<style>
  .page { max-width: 980px; color: var(--fg); } header, .panel, .card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); } h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.1rem; } header > p:last-child { color: var(--muted); } .panel { margin-top: 16px; } .cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; } .card { min-width: 0; } .blocked { border-color: var(--danger); background: var(--danger-soft); } .state { margin: 0 0 8px; color: var(--danger); font-size: .74rem; font-weight: 900; letter-spacing: .1em; } .breadth .state { color: var(--accent); } .command-label { margin: 18px 0 6px; color: var(--danger); font-size: .78rem; font-weight: 800; } code { display: block; overflow-wrap: anywhere; border: 1px solid var(--danger); padding: 10px; background: var(--surface-sunken); color: var(--danger); font-size: .78rem; } .big { margin: 12px 0; color: var(--info); font-size: clamp(2.4rem, 9vw, 4.5rem); font-weight: 900; } dl { display: grid; grid-template-columns: auto 1fr; gap: 7px 16px; border-top: 1px solid var(--border); padding-top: 12px; } dt { color: var(--muted); } dd { margin: 0; overflow-wrap: anywhere; } .disclaimer { border-top: 1px solid var(--border-strong); padding-top: 12px; color: var(--warn); font-size: .83rem; overflow-wrap: anywhere; } .error { border-color: var(--danger); color: var(--danger); } button { border: 1px solid var(--accent); border-radius: 6px; padding: 8px 12px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; } @media (max-width: 650px) { .cards { grid-template-columns: 1fr; } }
</style>

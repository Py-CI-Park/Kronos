<script lang="ts">
  import { onMount } from 'svelte';
  import ProcessStepper from '../ProcessStepper.svelte';
  import { V6_RL_STEPS } from '../registry';
  import { getV6DataReadiness, getV6Runs, getV6Status, type V6DataReadiness, type V6Runs, type V6Status } from '../v6Api';

  const INDEX_COMMAND = 'py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index';
  let status = $state<V6Status | null>(null);
  let runs = $state<V6Runs | null>(null);
  let readiness = $state<V6DataReadiness | null>(null);
  let copyMessage = $state<string | null>(null);

  function navigate(tab: string, key?: 'step' | 'sub', value?: string): void {
    const params = new URLSearchParams({ ui: 'v6', tab });
    if (key && value) params.set(key, value);
    history.pushState(history.state, '', `?${params.toString()}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  function stateOf(key: string): string | undefined {
    if (key === 'compare') return status?.journey.data.index_overlay === 'BLOCKED_INDEX_SERIES_SOURCE' ? 'BLOCKED_INDEX' : (status?.journey.evaluation.state ?? 'NOT_RUN');
    return status?.journey[key as keyof V6Status['journey']]?.state;
  }
  function states(): Record<string, string | undefined> { return Object.fromEntries(V6_RL_STEPS.map((step) => [step.id, stateOf(step.id)])); }
  function dataProgress(): number { return status?.journey.data.state === 'PARTIAL' ? 60 : 0; }
  function latestVerdict(): string { return runs?.runs?.[0]?.verdict_candidate?.value ?? 'MISSING'; }
  function verdictClass(): string { const value = latestVerdict(); return value === 'NO_GO' ? 'danger' : value === 'INCONCLUSIVE' ? 'warn' : ''; }
  async function copy(): Promise<void> { try { await navigator.clipboard.writeText(INDEX_COMMAND); copyMessage = '명령을 클립보드에 복사했습니다.'; } catch { copyMessage = '클립보드를 사용할 수 없습니다. 명령을 직접 복사하세요.'; } }
  async function load(): Promise<void> {
    const [statusResult, runsResult, readinessResult] = await Promise.all([getV6Status(), getV6Runs(), getV6DataReadiness()]);
    if (statusResult.ok && statusResult.data) status = statusResult.data;
    if (runsResult.ok && runsResult.data) runs = runsResult.data;
    if (readinessResult.ok && readinessResult.data) readiness = readinessResult.data;
  }
  onMount(() => { void load(); });
</script>

<section class="home" aria-labelledby="home-title">
  <header><p class="eyebrow">COMMAND HOME</p><h1 id="home-title">연구 현황</h1><p>모든 값은 API 응답의 원본 상태를 우선하며, 누락은 MISSING으로 표시합니다.</p></header>
  <div class="kpis">
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'data')}><span>연구 데이터</span><strong>{status?.journey.data.universe_size ?? 'MISSING'}</strong><small>universe · 일봉 {readiness?.daily_db.table_count ?? 'MISSING'} 테이블</small><i><b style={`width: ${dataProgress()}%`}></b></i><em>{status?.journey.data.state ?? 'MISSING'}</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'experiment')}><span>실험 계약</span><strong>{status?.journey.experiment.state ?? 'MISSING'}</strong><small>사전등록 SHA: MISSING</small><i><b style="width: 0%"></b></i><em>원본 상태 토큰</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'training')}><span>학습 상태</span><strong>{runs?.training_state ?? status?.journey.training.state ?? 'MISSING'}</strong><small>실행 {runs?.runs?.length ?? 'MISSING'}개</small><i><b style="width: 0%"></b></i><em>{status?.journey.training.state ?? 'MISSING'}</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'report')}><span>최신 판정</span><strong class={verdictClass()}>{latestVerdict()}</strong><small>가장 최근 API 실행의 판정</small><i><b style="width: 0%"></b></i><em>보고서로 이동</em></button>
  </div>
  {#if status?.journey.data.index_overlay === 'BLOCKED_INDEX_SERIES_SOURCE'}
    <section class="blocker" aria-labelledby="blocker-title"><div><p class="eyebrow">PRIMARY BLOCKER</p><h2 id="blocker-title">KRX 자격증명으로 지수 수집이 차단되었습니다</h2><p>{status.journey.data.index_blocker_reason ?? 'BLOCKED_INDEX_SERIES_SOURCE'}</p><code>{INDEX_COMMAND}</code></div><button type="button" onclick={copy}>명령 복사</button>{#if copyMessage}<small aria-live="polite">{copyMessage}</small>{/if}</section>
  {/if}
  <div class="lower-grid"><section class="journey"><h2>연구 여정 요약</h2><ProcessStepper steps={V6_RL_STEPS} active="" states={states()} onSelect={(id) => navigate('rl', 'step', id)} /></section><section class="quick"><h2>빠른 이동</h2><button type="button" onclick={() => navigate('insight', 'sub', 'symbol')}>종목 심층</button><button type="button" onclick={() => navigate('insight', 'sub', 'flow')}>수급 흐름</button><button type="button" onclick={() => navigate('insight', 'sub', 'regime')}>시장 국면</button><a href="/?ui=v3">V3</a><a href="/?ui=v5">V5</a><button type="button" onclick={() => navigate('settings')}>설정</button></section></div>
  <footer>여섯 안전 잠금: {status && Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '6/6 false · 모든 잠금은 false입니다.' : 'MISSING'}</footer>
</section>

<style>
  .home { width: 100%; min-width: 0; }.eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }h1,h2 { color: var(--fg-strong); }h1 { margin: 6px 0; font-size: clamp(1.9rem, 4vw, 2.6rem); }header > p:last-child { color: var(--muted); }.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-top: 22px; }.kpi { min-height: 184px; display: flex; flex-direction: column; align-items: start; border: 1px solid var(--border-strong); border-radius: 12px; padding: 18px; background: var(--surface-raised); color: var(--fg); font: inherit; text-align: left; cursor: pointer; transition: transform .16s ease, box-shadow .16s ease; }.kpi:hover { transform: translateY(-2px); box-shadow: 0 8px 18px var(--shadow); }.kpi:focus-visible, .quick button:focus-visible, .blocker button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }.kpi > span, small, em { color: var(--muted); font-size: .76rem; }.kpi strong { margin: 8px 0; color: var(--fg-strong); font-size: 1.9rem; overflow-wrap: anywhere; }.kpi strong.danger { color: var(--danger); }.kpi strong.warn { color: var(--warn); }.kpi i { width: 100%; height: 4px; margin-top: auto; overflow: hidden; border-radius: 99px; background: var(--surface-sunken); }.kpi b { display: block; height: 100%; background: var(--accent); }.kpi em { margin-top: 9px; font-style: normal; }.blocker { display: flex; align-items: start; gap: 16px; margin-top: 16px; border: 1px solid var(--danger); border-radius: 12px; padding: 18px; background: var(--danger-soft); }.blocker div { min-width: 0; flex: 1; }.blocker h2 { margin: 5px 0; }.blocker p { color: var(--fg); }.blocker code { display: block; overflow-wrap: anywhere; border: 1px solid var(--danger); border-radius: 6px; padding: 8px; }.blocker button, .quick button { border: 1px solid var(--accent); border-radius: 7px; padding: 8px 10px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; white-space: nowrap; }.lower-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, .75fr); gap: 16px; margin-top: 18px; }.journey, .quick { min-width: 0; border: 1px solid var(--border); border-radius: 12px; padding: 18px; background: var(--surface); }.journey h2, .quick h2 { margin-top: 0; font-size: 1.1rem; }.quick { display: flex; flex-direction: column; gap: 8px; }.quick a { border: 1px solid var(--border-strong); border-radius: 7px; padding: 8px 10px; color: var(--fg); text-decoration: none; }footer { margin-top: 16px; color: var(--muted); font-size: .8rem; }@media (max-width: 900px) { .lower-grid { grid-template-columns: 1fr; } }.blocker small { color: var(--fg); }@media (max-width: 560px) { .blocker { flex-direction: column; } }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import ProcessStepper from '../ProcessStepper.svelte';
  import { V6_RL_STEPS } from '../registry';
  import { getV6DataReadiness, getV6Experiment, getV6RunDetail, getV6Runs, getV6Status, type V6DataReadiness, type V6Experiment, type V6RunDetail, type V6Runs, type V6Status } from '../v6Api';

  let status = $state<V6Status | null>(null);
  let runs = $state<V6Runs | null>(null);
  let readiness = $state<V6DataReadiness | null>(null);
  let experiment = $state<V6Experiment | null>(null);
  let newestDetail = $state<V6RunDetail | null>(null);
  let loading = $state(true);
  let errors = $state<Record<string, string>>({});

  const text = (value: unknown) => value === undefined || value === null || value === '' ? 'MISSING' : String(value);
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
  function progressOf(state: string | undefined): number { return ['FROZEN', 'HAS_RUNS', 'HAS_REPORTS', 'PRESENT', 'OK'].includes(state ?? '') ? 100 : state === 'PARTIAL' ? 60 : 0; }
  function resourceError(resource: string): string | undefined { return errors[resource]; }
  function display(resource: string, value: unknown): string { return loading ? 'LOADING' : resourceError(resource) ? 'UNAVAILABLE' : text(value); }
  const sparkline = $derived.by(() => {
    const perSeed = newestDetail?.manifest?.per_seed ?? {};
    const first = Object.keys(perSeed).sort()[0];
    const curve = ((perSeed as Record<string, { val_nav_curve?: unknown }>)[first]?.val_nav_curve ?? []) as unknown[];
    const values = curve.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    if (values.length < 2) return null;
    const lo = Math.min(...values, 60000000); const hi = Math.max(...values, 60000000);
    const y = (v: number) => hi === lo ? 16 : 30 - ((v - lo) / (hi - lo)) * 28;
    const x = (i: number) => (i / (values.length - 1)) * 118 + 1;
    return { seed: first, points: values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' '), baselineY: y(60000000).toFixed(1) };
  });
  function latestVerdict(): string { return runs?.runs?.[0]?.verdict_candidate?.value ?? (resourceError('runs') ? 'UNAVAILABLE' : 'MISSING'); }
  function verdictClass(): string { const value = latestVerdict(); return value === 'NO_GO' ? 'danger' : value === 'INCONCLUSIVE' ? 'warn' : ''; }
  async function load(): Promise<void> {
    loading = true; errors = {}; newestDetail = null;
    const [statusResult, runsResult, readinessResult, experimentResult] = await Promise.all([getV6Status(), getV6Runs(), getV6DataReadiness(), getV6Experiment()]);
    const nextErrors: Record<string, string> = {};
    if (statusResult.ok && statusResult.data) status = statusResult.data; else nextErrors.status = statusResult.error ?? '상태 API를 불러오지 못했습니다.';
    if (runsResult.ok && runsResult.data) runs = runsResult.data; else nextErrors.runs = runsResult.error ?? '실행 API를 불러오지 못했습니다.';
    if (readinessResult.ok && readinessResult.data) readiness = readinessResult.data; else nextErrors.readiness = readinessResult.error ?? '데이터 API를 불러오지 못했습니다.';
    if (experimentResult.ok && experimentResult.data) experiment = experimentResult.data; else nextErrors.experiment = experimentResult.error ?? '실험 API를 불러오지 못했습니다.';
    const newest = runsResult.ok ? runsResult.data?.runs?.[0] : undefined;
    if (newest?.dataset_run_id && newest.run_id) {
      const detailResult = await getV6RunDetail(newest.dataset_run_id, newest.run_id);
      if (detailResult.ok && detailResult.data) newestDetail = detailResult.data; else nextErrors.detail = detailResult.error ?? '실행 상세 API를 불러오지 못했습니다.';
    }
    errors = nextErrors; loading = false;
  }
  onMount(() => { void load(); });
</script>

<section class="home" aria-labelledby="home-title">
  <header><p class="eyebrow">COMMAND HOME</p><h1 id="home-title">연구 현황</h1><p>성공한 응답에서 없는 값은 MISSING, API 요청 실패는 UNAVAILABLE로 표시합니다.</p></header>
  {#if loading}<p class="notice" role="status">연구 현황을 불러오는 중입니다.</p>{/if}
  {#if Object.keys(errors).length}<section class="notice unavailable" role="alert"><strong>일부 API를 사용할 수 없습니다.</strong><span>{Object.values(errors).join(' ')}</span><button type="button" onclick={() => void load()}>다시 시도</button></section>{/if}
  <div class="kpis">
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'data')}><span>연구 데이터</span><strong>{display('status', status?.journey.data.universe_size)}</strong><small>universe · 일봉 {display('readiness', readiness?.daily_db.table_count)} 테이블</small><i><b style={`width: ${progressOf(status?.journey.data.state)}%`}></b></i><em>{display('status', status?.journey.data.state)}</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'experiment')}><span>실험 계약</span><strong>{display('experiment', experiment?.prereg?.state)}</strong><small>사전등록: {display('experiment', experiment?.prereg?.path)}</small><small>SHA-256: {display('experiment', experiment?.prereg?.sha256)}</small><i><b style={`width: ${progressOf(experiment?.prereg?.state)}%`}></b></i><em>{display('status', status?.journey.experiment.state)}</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'training')}><span>학습 상태</span><strong>{display('runs', runs?.training_state ?? status?.journey.training.state)}</strong><small>실행 {display('runs', runs?.runs?.length)}개</small>{#if sparkline}<svg class="spark" viewBox="0 0 120 32" aria-label={`최신 실행 seed ${sparkline.seed}의 episode별 validation NAV 곡선`}><line x1="0" y1={sparkline.baselineY} x2="120" y2={sparkline.baselineY} class="spark-base" /><polyline points={sparkline.points} class="spark-line" /></svg>{/if}<i><b style={`width: ${progressOf(status?.journey.training.state)}%`}></b></i><em>{loading ? 'LOADING' : resourceError('runs') || resourceError('status') ? 'UNAVAILABLE' : text(status?.journey.training.state)}</em></button>
    <button type="button" class="kpi" onclick={() => navigate('rl', 'step', 'report')}><span>최신 판정</span><strong class={verdictClass()}>{loading ? 'LOADING' : latestVerdict()}</strong><small>가장 최근 API 실행의 판정</small><i><b style={`width: ${progressOf(status?.journey.report.state)}%`}></b></i><em>{loading ? 'LOADING' : resourceError('runs') ? 'UNAVAILABLE' : '보고서로 이동'}</em></button>
  </div>
  <div class="lower-grid"><section class="journey"><h2>연구 여정 요약</h2><ProcessStepper steps={V6_RL_STEPS} active="" states={states()} onSelect={(id) => navigate('rl', 'step', id)} /></section><section class="quick"><h2>빠른 이동</h2><button type="button" onclick={() => navigate('insight', 'sub', 'symbol')}>종목 심층</button><button type="button" onclick={() => navigate('insight', 'sub', 'flow')}>수급 흐름</button><button type="button" onclick={() => navigate('insight', 'sub', 'regime')}>시장 국면</button><a href="/?ui=v3">V3</a><a href="/?ui=v5">V5</a><button type="button" onclick={() => navigate('settings')}>설정</button></section></div>
  <footer>여섯 안전 잠금: {status && Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '6/6 false · 모든 잠금은 false입니다.' : resourceError('status') ? 'UNAVAILABLE' : 'MISSING'}</footer>
</section>

<style>
  .home { width: 100%; min-width: 0; }.eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }h1,h2 { color: var(--fg-strong); }h1 { margin: 6px 0; font-size: clamp(1.9rem, 4vw, 2.6rem); }header > p:last-child { color: var(--muted); }.notice { margin: 16px 0 0; padding: 12px; border: 1px solid var(--border-strong); border-radius: 10px; color: var(--muted); }.unavailable { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; border-color: var(--danger); color: var(--danger); }.unavailable button, .quick button { border: 1px solid var(--accent); border-radius: 7px; padding: 8px 10px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; }.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 14px; margin-top: 22px; }.kpi { min-width: 0; min-height: 184px; display: flex; flex-direction: column; align-items: start; border: 1px solid var(--border-strong); border-radius: 12px; padding: 18px; background: var(--surface-raised); color: var(--fg); font: inherit; text-align: left; cursor: pointer; }.kpi:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-tint); }.kpi:focus-visible, .quick button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }.kpi > span, small, em { color: var(--muted); font-size: .76rem; }.kpi strong { margin: 8px 0; color: var(--fg-strong); font-size: 1.6rem; overflow-wrap: anywhere; }.kpi strong.danger { color: var(--danger); }.kpi strong.warn { color: var(--warn); }.kpi i { width: 100%; height: 4px; margin-top: auto; overflow: hidden; border-radius: 99px; background: var(--surface-sunken); }.kpi b { display: block; height: 100%; background: var(--accent); }.kpi em { margin-top: 9px; font-style: normal; }.lower-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 16px; margin-top: 18px; }.journey, .quick { min-width: 0; border: 1px solid var(--border); border-radius: 12px; padding: 18px; background: var(--surface); }.journey h2, .quick h2 { margin-top: 0; font-size: 1.1rem; }.quick { display: flex; flex-direction: column; gap: 8px; }.quick a { border: 1px solid var(--border-strong); border-radius: 7px; padding: 8px 10px; color: var(--fg); text-decoration: none; }footer { margin-top: 16px; color: var(--muted); font-size: .8rem; }.spark { width: 100%; height: 34px; margin-top: 8px; }.spark-line { fill: none; stroke: var(--accent); stroke-width: 1.6; }.spark-base { stroke: var(--border-strong); stroke-width: 1; stroke-dasharray: 4 3; }
</style>

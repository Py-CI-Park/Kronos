<script lang="ts">
  import { onMount } from 'svelte';
  import ProcessStepper from './ProcessStepper.svelte';
  import { resolveV6Location, V6_RL_STEPS } from './registry';
  import { getV6Runs, getV6Status, type V6Status, type V6TrainingRun } from './v6Api';
  import { rlApi } from '$lib/rlApi';
  import DataPage from './pages/DataPage.svelte';
  import ExperimentPage from './pages/ExperimentPage.svelte';
  import TrainingPage from './pages/TrainingPage.svelte';
  import EvaluationPage from './pages/EvaluationPage.svelte';
  import ComparePage from './pages/ComparePage.svelte';
  import ReportPage from './pages/ReportPage.svelte';
  import DiscoveryPage from './pages/DiscoveryPage.svelte';

  let active = $state('discovery');
  let status = $state<V6Status | null>(null);
  let newestRun = $state<V6TrainingRun | null>(null);
  let discoveryState = $state('NOT_RUN');

  function selectFromLocation(): void {
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), params.get('step'), null);
    active = location.tab === 'rl' && location.step ? location.step : 'discovery';
  }
  function selectStep(id: string): void {
    active = id;
    history.pushState(history.state, '', `?ui=v6&tab=rl&step=${encodeURIComponent(id)}`);
  }
  function states(): Record<string, string | undefined> {
    return {
      discovery: discoveryState,
      data: status?.journey.data.state,
      experiment: status?.journey.experiment.state,
      training: status?.journey.training.state,
      evaluation: status?.journey.evaluation.state,
      compare: status?.journey.data.index_overlay === 'BLOCKED_INDEX_SERIES_SOURCE' ? 'BLOCKED_INDEX' : (status?.journey.evaluation.state ?? 'NOT_RUN'),
      report: status?.journey.report.state,
    };
  }
  async function load(): Promise<void> {
    const [statusResult, runsResult, discoveryRuns] = await Promise.all([getV6Status(), getV6Runs(), rlApi.rlRuns(100)]);
    if (statusResult.ok && statusResult.data) status = statusResult.data;
    if (runsResult.ok && runsResult.data) newestRun = runsResult.data.runs?.[0] ?? null;
    discoveryState = discoveryRuns?.runs.find((run) => run.summary?.research_lane === 'rl_discovery')?.summary?.status?.toString() ?? 'NOT_RUN';
  }

  onMount(() => {
    selectFromLocation();
    void load();
    window.addEventListener('popstate', selectFromLocation);
    return () => window.removeEventListener('popstate', selectFromLocation);
  });
</script>

<section class="workspace" aria-labelledby="rl-title">
  <header>
    <div><p class="eyebrow">RESEARCH WORKSPACE</p><h1 id="rl-title">강화학습</h1><p>연구 단계별 원본 상태 토큰과 읽기 전용 근거를 함께 확인합니다.</p></div>
    {#if newestRun?.verdict_candidate?.value}<span class="verdict">{newestRun.verdict_candidate.value}</span>{/if}
  </header>
  <ProcessStepper steps={V6_RL_STEPS} {active} states={states()} onSelect={selectStep} />
  <div class="step-body">
    {#if active === 'discovery'}<DiscoveryPage />
    {:else if active === 'data'}<DataPage />
    {:else if active === 'experiment'}<ExperimentPage />
    {:else if active === 'training'}<TrainingPage />
    {:else if active === 'evaluation'}<EvaluationPage />
    {:else if active === 'compare'}<ComparePage />
    {:else}<ReportPage />{/if}
  </div>
</section>

<style>
  .workspace { display: flex; flex-direction: column; gap: 18px; min-width: 0; width: 100%; }
  header { display: flex; align-items: end; justify-content: space-between; gap: 16px; }
  .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 5px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 4vw, 2.3rem); }
  header p:last-child { margin: 0; color: var(--muted); }
  .verdict { flex: 0 0 auto; border: 1px solid var(--warn); border-radius: 999px; padding: 5px 9px; color: var(--warn); font-size: .75rem; font-weight: 800; }
  .step-body { min-width: 0; }
  @media (max-width: 560px) { header { align-items: start; flex-direction: column; } }
</style>

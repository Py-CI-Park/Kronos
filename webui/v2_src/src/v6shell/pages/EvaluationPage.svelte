<script lang="ts">
  import { onMount } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { v6ChartEpoch, v6CssVar } from '../v6ChartTheme';
  import {
    getV6RunDetail,
    getV6Runs,
    type V6RunDetail,
    type V6Runs,
    type V6RunSeed,
  } from '../v6Api';
  import {
    TYPE1_FACTS,
    classifyType1State,
    isType1Identity,
    type1StateLabel,
  } from '../type1Presentation';

  const NO_TRADE_CAPITAL = 60_000_000;
  let runsData = $state<V6Runs | null>(null);
  let detail = $state<V6RunDetail | null>(null);
  let selected = $state('');
  let error = $state<string | null>(null);
  let loading = $state(true);
  let detailLoading = $state(false);
  let chartEpoch = $state('');
  v6ChartEpoch.subscribe((value) => (chartEpoch = value));

  const key = (dataset: string | undefined, run: string | undefined): string => `${dataset ?? ''}\u0000${run ?? ''}`;
  const text = (value: unknown): string => value === undefined || value === null || value === '' ? 'MISSING' : String(value);
  const num = (value: unknown): number | undefined => typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  const won = (value: unknown): string => num(value) === undefined ? 'MISSING' : `₩${new Intl.NumberFormat('ko-KR').format(num(value)!)}`;
  const color = v6CssVar;
  const manifest = $derived(detail?.manifest);
  const seedEntries = $derived(Object.entries(manifest?.per_seed ?? {}) as [string, V6RunSeed][]);
  const controlEntries = $derived(Object.entries(manifest?.shuffled_label_control ?? {}) as [string, V6RunSeed][]);
  const events = $derived((detail?.events_tail ?? []).filter((event) => typeof event.episode === 'number' && typeof event.val_nav === 'number'));
  const modelIdentity = $derived(`${detail?.dataset_run_id ?? ''} ${detail?.train_run_id ?? ''} ${manifest?.model_family ?? ''} ${manifest?.algorithm ?? ''} ${manifest?.prereg?.id ?? ''}`);
  const isType1 = $derived(
    isType1Identity(manifest as unknown as Readonly<Record<string, unknown>> | undefined)
      || isType1Identity(modelIdentity),
  );
  const evidenceState = $derived(classifyType1State({
    status: detail?.status,
    verdict: manifest?.verdict_candidate?.value,
    test_state: manifest?.test?.state,
    reason: detail?.reason,
  }, detailLoading));
  const freshOosState = $derived(manifest?.test?.state ?? TYPE1_FACTS.evaluation.freshOos);
  const type1Run = $derived(
    (runsData?.runs ?? []).find((run) =>
      isType1Identity(`${run.dataset_run_id ?? ''} ${run.run_id ?? ''}`),
    ),
  );
  const type1OverviewState = $derived(
    isType1
      ? evidenceState
      : classifyType1State(type1Run) === 'EMPTY'
        ? 'NOT_RUN'
        : classifyType1State(type1Run),
  );

  const navOption = $derived.by(() => {
    void chartEpoch;
    return {
      tooltip: { trigger: 'axis', valueFormatter: (value: number) => won(value) },
      xAxis: { type: 'category', data: events.map((event) => event.episode), axisLabel: { color: color('--muted') } },
      yAxis: { type: 'value', axisLabel: { color: color('--muted'), formatter: (value: number) => won(value) } },
      series: [{ type: 'line', data: events.map((event) => event.val_nav), smooth: false, connectNulls: false, showSymbol: false, itemStyle: { color: color('--accent') }, lineStyle: { color: color('--accent') }, markLine: { silent: true, data: [{ yAxis: NO_TRADE_CAPITAL, label: { formatter: 'no-trade 60M' } }] } }],
    };
  });
  const costOption = $derived.by(() => {
    void chartEpoch;
    return {
      tooltip: { trigger: 'axis', valueFormatter: (value: number) => won(value) },
      legend: { textStyle: { color: color('--muted') } },
      xAxis: { type: 'category', data: ['0.00%', '0.23%', '0.46%'], axisLabel: { color: color('--muted') } },
      yAxis: { type: 'value', axisLabel: { color: color('--muted'), formatter: (value: number) => won(value) } },
      series: seedEntries.map(([seed, value]) => ({ type: 'bar', name: `seed ${seed}`, data: ['0.0000', '0.0023', '0.0046'].map((cost) => value.final_val_metrics?.cost_scenario_navs?.[cost]), markLine: { silent: true, data: [{ yAxis: NO_TRADE_CAPITAL, label: { formatter: 'no-trade 60M' } }] } })),
    };
  });
  const comparisonOption = $derived.by(() => {
    void chartEpoch;
    const primary = new Map(seedEntries.map(([seed, value]) => [seed, value.final_val_metrics?.nav]));
    const control = new Map(controlEntries.map(([seed, value]) => [seed, value.final_val_metrics?.nav]));
    const labels = [...new Set([...primary.keys(), ...control.keys()])];
    return {
      tooltip: { trigger: 'axis', valueFormatter: (value: number) => won(value) },
      legend: { textStyle: { color: color('--muted') } },
      xAxis: { type: 'category', data: labels, axisLabel: { color: color('--muted') } },
      yAxis: { type: 'value', axisLabel: { color: color('--muted'), formatter: (value: number) => won(value) } },
      series: [
        { name: 'validation policy', type: 'bar', data: labels.map((seed) => primary.get(seed)), itemStyle: { color: color('--accent') } },
        { name: 'shuffled-label control', type: 'bar', data: labels.map((seed) => control.get(seed)), itemStyle: { color: color('--warn') } },
        { name: 'no-trade baseline', type: 'line', data: labels.map(() => manifest?.baselines?.no_trade?.nav ?? NO_TRADE_CAPITAL), smooth: false, connectNulls: false, showSymbol: false, lineStyle: { color: color('--muted') } },
      ],
    };
  });

  async function selectRun(): Promise<void> {
    const [dataset, run] = selected.split('\u0000');
    if (!dataset || !run) return;
    detailLoading = true;
    detail = null;
    const response = await getV6RunDetail(dataset, run);
    detailLoading = false;
    if (response.ok && response.data) detail = response.data;
    else error = response.error ?? '알 수 없는 오류가 발생했습니다.';
  }
  async function load(): Promise<void> {
    loading = true;
    error = null;
    const response = await getV6Runs();
    loading = false;
    if (response.ok && response.data) {
      runsData = response.data;
      const run = response.data.runs?.[0];
      if (run) { selected = key(run.dataset_run_id, run.run_id); await selectRun(); }
    } else error = response.error ?? '알 수 없는 오류가 발생했습니다.';
  }
  onMount(load);
</script>

{#if loading}
  <section class="panel" role="status" aria-live="polite">평가 실행 기록을 확인하고 있습니다.</section>
{:else if error && !runsData}
  <section class="panel error" role="alert" aria-live="assertive">{error}</section>
{:else if runsData}
  <section class="evaluation-page">
    <header><p class="eyebrow">EVALUATION EVIDENCE</p><h1>평가</h1><p>선택한 실행의 읽기 전용 manifest에서만 표시합니다.</p></header>
    <section class="card wide type1-overview" role="status" aria-live="polite">
      <p class="eyebrow">TYPE1 STATUS</p>
      <h2>Sequential MaskablePPO</h2>
      <p>Planned: 5 primary + 5 shuffled-label control seeds × 200,000 fixed episodes.</p>
      <p>Current Type1 evidence: <strong>{type1StateLabel(type1OverviewState)}</strong> — no observed completion or validation GO is implied.</p>
      <p>Fresh OOS: <strong>NOT_RUN</strong>. {TYPE1_FACTS.execution.officialCloseStatement} {TYPE1_FACTS.claims.statement}</p>
    </section>
    {#if !(runsData.runs?.length)}
      <section class="empty-state" role="status" aria-live="polite"><h2>아직 평가할 실행이 없습니다</h2><p>NOT_RUN — fresh OOS is unopened.</p></section>
    {:else}
      <section class="card picker"><h2>실행 선택</h2>{#each runsData.runs ?? [] as run}<button class:chosen={selected === key(run.dataset_run_id, run.run_id)} onclick={() => { selected = key(run.dataset_run_id, run.run_id); selectRun(); }}>{text(run.dataset_run_id)} · {text(run.run_id)} · {text(run.state)}</button>{/each}</section>
      {#if detailLoading}
        <section class="card" role="status" aria-live="polite">선택한 실행 manifest를 읽고 있습니다.</section>
      {:else if detail?.manifest}
        <section class="card verdict"><h2>판정 {text(manifest?.verdict_candidate?.value)}</h2>{#each manifest?.verdict_candidate?.reasons ?? [] as reason}<p>{text(reason)}</p>{:else}<p>MISSING verdict reasons</p>{/each}</section>
        {#if isType1}
          <section class="card wide type1-evidence">
            <p class="eyebrow">TYPE1 VALIDATION GATE</p><h2>validation, control, and fresh OOS truth table</h2>
            <div class="table-wrap"><table><thead><tr><th>evidence surface</th><th>observed state</th><th>truth</th></tr></thead><tbody>
              <tr><th>reused validation</th><td>{text(manifest?.verdict_candidate?.value)}</td><td>NO_GO — reused validation cannot yield GO</td></tr>
              <tr><th>shuffled-label control</th><td>{controlEntries.length ? `${controlEntries.length} seed artifacts` : 'MISSING / NOT_RUN'}</td><td>calibration only; never a profitability claim</td></tr>
              <tr><th>fresh OOS</th><td>{text(freshOosState)}</td><td>{freshOosState === 'NOT_RUN' || freshOosState === 'ACCUMULATING_NOT_RUN' ? 'unopened; no OOS result' : 'state preserved from manifest; no GO claim'}</td></tr>
              <tr><th>integrity / missing / block</th><td>{type1StateLabel(evidenceState)}</td><td>missing, tampered, or blocked evidence remains visible and is NO_GO</td></tr>
            </tbody></table></div>
            <p class="note">{TYPE1_FACTS.execution.priceBasis}; {TYPE1_FACTS.execution.roundTripCost}; {TYPE1_FACTS.accounting.initialNav}; max {TYPE1_FACTS.accounting.maxSlots} slots. {TYPE1_FACTS.claims.statement}</p>
          </section>
          <section class="card wide"><h2>seed별 validation / shuffled control / baseline</h2>{#if seedEntries.length || controlEntries.length}<EChartsRenderer option={comparisonOption} height="320px" caption="per-seed validation policy and shuffled-label control; no-trade baseline" />{:else}<p class="absence" role="status">표시할 validation 또는 control seed 증거 없음 · NOT_RUN</p>{/if}</section>
        {/if}
        <section class="card wide"><h2>validation NAV 곡선</h2>{#if events.length}<EChartsRenderer option={navOption} height="320px" caption="episode별 validation NAV · no-trade 60M" />{:else}<p class="absence" role="status">표시할 데이터 없음 · NOT_RUN</p>{/if}</section>
        <section class="card wide"><h2>seed별 비용 민감도</h2>{#if seedEntries.length}<EChartsRenderer option={costOption} height="320px" caption="seed별 final validation NAV · 비용 시나리오" />{:else}<p class="absence" role="status">표시할 데이터 없음 · NOT_RUN</p>{/if}</section>
        <div class="grid">
          <section class="card"><h2>seed별 검증</h2><div class="table-wrap"><table><thead><tr><th>seed</th><th>episodes</th><th>val NAV</th><th>trades</th></tr></thead><tbody>{#each seedEntries as [seed, value]}<tr><th>{seed}</th><td>{text(value.episodes_ran)}</td><td>{won(value.final_val_metrics?.nav)}</td><td>{text(value.final_val_metrics?.trade_count)}</td></tr>{:else}<tr><td colspan="4">표시할 seed 증거 없음 · NOT_RUN</td></tr>{/each}</tbody></table></div></section>
          <section class="card"><h2>shuffled-label control seed</h2><div class="table-wrap"><table><thead><tr><th>seed</th><th>episodes</th><th>val NAV</th><th>trades</th></tr></thead><tbody>{#each controlEntries as [seed, value]}<tr><th>{seed}</th><td>{text(value.episodes_ran)}</td><td>{won(value.final_val_metrics?.nav)}</td><td>{text(value.final_val_metrics?.trade_count)}</td></tr>{:else}<tr><td colspan="4">표시할 control 증거 없음 · NOT_RUN</td></tr>{/each}</tbody></table></div></section>
          <section class="card"><h2>기준선 NAV vs policy</h2><div class="table-wrap"><table><thead><tr><th>전략</th><th>NAV</th></tr></thead><tbody>{#each ['no_trade', 'rule_topk_ret5', 'random_topk'] as name}<tr><th>{name}</th><td>{won(manifest?.baselines?.[name]?.nav)}</td></tr>{/each}</tbody></table></div></section>
        </div>
      {:else if error}
        <section class="card error" role="alert">{error}</section>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .evaluation-page, .panel { width: 100%; border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface); color: var(--fg); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; margin-top: 16px; }
  .card, .empty-state { margin-top: 16px; border: 1px solid var(--border-strong); border-radius: 10px; padding: 16px; background: var(--surface-raised); }
  .wide { grid-column: 1 / -1; }.eyebrow { color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; }h1 { font-size: clamp(1.8rem, 6vw, 2.6rem); }h1, h2 { color: var(--fg-strong); }h2 { font-size: 1.15rem; }
  .picker button { display: block; width: 100%; margin: 6px 0; border: 1px solid var(--border-strong); border-radius: 6px; padding: 8px; background: var(--surface-sunken); color: var(--fg); font: inherit; text-align: left; }.picker .chosen { border-color: var(--accent); }.verdict { border-color: var(--danger); background: var(--danger-soft); }.table-wrap { overflow-x: auto; }table { width: 100%; min-width: 420px; border-collapse: collapse; font-size: .85rem; }th, td { border-top: 1px solid var(--border); padding: 8px; text-align: left; }th { color: var(--muted); }.error { color: var(--danger); }.absence, .note { color: var(--muted); }
  @media (max-width: 420px) { .evaluation-page, .panel { padding: 16px; } table { min-width: 360px; } }
</style>

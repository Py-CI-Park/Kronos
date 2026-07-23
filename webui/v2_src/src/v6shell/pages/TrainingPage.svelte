<script lang="ts">
  import { onMount } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { v6ChartEpoch, v6CssVar } from '../v6ChartTheme';
  import {
    getV6RunDetail,
    getV6Runs,
    type V6RunDetail,
    type V6RunSeed,
    type V6Runs,
  } from '../v6Api';
  import {
    TYPE1_FACTS,
    classifyType1State,
    isType1Identity,
    type1StateLabel,
  } from '../type1Presentation';

  const NO_TRADE_CAPITAL = 60_000_000;
  const SEED_COLORS = ['#49a6ff', '#9b8cff', '#36c6a0', '#f0ae4f', '#e9799a'];

  let runsData = $state<V6Runs | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  let selected = $state('');
  let detail = $state<V6RunDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let copyMessage = $state<string | null>(null);
  let chartEpoch = $state('');

  v6ChartEpoch.subscribe((value) => (chartEpoch = value));

  const text = (value: unknown): string =>
    value === undefined || value === null || value === '' ? 'MISSING' : String(value);
  const finiteNumber = (value: unknown): number | undefined =>
    typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  const won = (value: unknown): string => {
    const amount = finiteNumber(value);
    return amount === undefined ? 'MISSING' : `₩${new Intl.NumberFormat('ko-KR').format(amount)}`;
  };
  const percent = (value: unknown): string => {
    const amount = finiteNumber(value);
    return amount === undefined ? 'MISSING' : `${(amount * 100).toFixed(2)}%`;
  };
  const key = (dataset: string | undefined, run: string | undefined): string =>
    `${dataset ?? ''}\u0000${run ?? ''}`;
  const color = v6CssVar;

  const seedEntries = $derived(
    Object.entries(detail?.manifest?.per_seed ?? {}) as [string, V6RunSeed][],
  );
  const curveSeeds = $derived(
    seedEntries.filter(([, seed]) => (seed.val_nav_curve ?? []).some((value) => finiteNumber(value) !== undefined)),
  );
  const manifest = $derived(detail?.manifest);
  const selectedRun = $derived(
    (runsData?.runs ?? []).find((run) => key(run.dataset_run_id, run.run_id) === selected),
  );
  const modelLabel = $derived(
    manifest?.model_family ?? manifest?.hyperparams?.model_family ?? manifest?.hyperparams?.algorithm ?? manifest?.algorithm,
  );
  const generatedTime = $derived(manifest?.generated_utc ?? selectedRun?.generated_utc);
  const primaryCost = $derived(manifest?.hyperparams?.primary_cost_rate ?? manifest?.primary_cost_rate);
  const shuffledSeedEntries = $derived(
    Object.entries(manifest?.shuffled_label_control ?? {}) as [string, V6RunSeed][],
  );
  const observedEpisodes = $derived(
    seedEntries.reduce((total, [, seed]) => total + (finiteNumber(seed.episodes_ran) ?? 0), 0),
  );
  const observedTrainingState = $derived(detail?.status ?? selectedRun?.state ?? runsData?.training_state);
  const runArtifactPath = $derived(selectedRun?.path);
  const datasetArtifactPath = $derived(
    (runsData?.datasets ?? []).find((dataset) => dataset.run_id === detail?.dataset_run_id)?.path,
  );
  const isCompleted = $derived(
    observedTrainingState === 'COMPLETED' || observedTrainingState === 'COMPLETE',
  );
  const isType1 = $derived(
    isType1Identity(manifest as unknown as Readonly<Record<string, unknown>> | undefined)
      || isType1Identity(`${detail?.dataset_run_id ?? ''} ${detail?.train_run_id ?? ''} ${modelLabel ?? ''} ${manifest?.prereg?.id ?? ''}`),
  );
  const type1EvidenceState = $derived(
    classifyType1State(
      {
        status: observedTrainingState,
        verdict: manifest?.verdict_candidate?.value,
        test_state: manifest?.test?.state,
        reason: detail?.reason,
      },
      detailLoading,
    ),
  );
  const type1Run = $derived(
    (runsData?.runs ?? []).find((run) =>
      isType1Identity(`${run.dataset_run_id ?? ''} ${run.run_id ?? ''}`),
    ),
  );
  const type1OverviewState = $derived(
    isType1
      ? type1EvidenceState
      : classifyType1State(type1Run?.state) === 'EMPTY'
        ? 'NOT_RUN'
        : classifyType1State(type1Run?.state),
  );

  const navOption = $derived.by(() => {
    void chartEpoch;
    const longestCurve = Math.max(0, ...curveSeeds.map(([, seed]) => seed.val_nav_curve?.length ?? 0));
    return {
      tooltip: { trigger: 'axis', valueFormatter: (value: number) => won(value) },
      legend: { textStyle: { color: color('--muted') } },
      grid: { left: 64, right: 24, top: 40, bottom: 48 },
      xAxis: {
        type: 'category',
        name: 'episode',
        data: Array.from({ length: longestCurve }, (_, index) => index + 1),
        axisLabel: { color: color('--muted') },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: color('--muted'), formatter: (value: number) => won(value) },
      },
      series: [
        ...curveSeeds.map(([seed, value], index) => ({
          name: `seed ${seed}`,
          type: 'line',
          data: value.val_nav_curve ?? [],
          smooth: false,
          showSymbol: false,
          connectNulls: false,
          itemStyle: { color: SEED_COLORS[index % SEED_COLORS.length] },
          lineStyle: { color: SEED_COLORS[index % SEED_COLORS.length], width: 2 },
        })),
        {
          name: 'no-trade 60M baseline',
          type: 'line',
          data: [],
          showSymbol: false,
          markLine: {
            silent: true,
            symbol: 'none',
            data: [{ yAxis: NO_TRADE_CAPITAL, label: { formatter: 'no-trade 60M' } }],
          },
        },
      ],
    };
  });

  async function copyManifestSha(): Promise<void> {
    const sha = detail?.manifest_sha256;
    if (!sha) {
      copyMessage = '복사할 manifest SHA가 없습니다.';
      return;
    }
    try {
      await navigator.clipboard.writeText(sha);
      copyMessage = 'Manifest SHA를 클립보드에 복사했습니다.';
    } catch {
      copyMessage = '클립보드를 사용할 수 없습니다. SHA를 직접 복사하세요.';
    }
  }

  async function open(dataset: string | undefined, run: string | undefined): Promise<void> {
    if (!dataset || !run) return;
    selected = key(dataset, run);
    detail = null;
    detailError = null;
    copyMessage = null;
    detailLoading = true;
    const response = await getV6RunDetail(dataset, run);
    detailLoading = false;
    if (response.ok && response.data) detail = response.data;
    else detailError = response.error ?? '실행 상세를 불러오지 못했습니다.';
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const response = await getV6Runs();
    loading = false;
    if (response.ok && response.data) {
      runsData = response.data;
      const run = response.data.runs?.[0];
      if (run) await open(run.dataset_run_id, run.run_id);
    } else {
      error = response.error ?? '알 수 없는 오류가 발생했습니다.';
    }
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" role="status" aria-live="polite">학습 실행 기록을 확인하고 있습니다.</section>
{:else if error}
  <section class="panel error" role="alert" aria-live="assertive">
    <h1>학습 실행 기록을 불러오지 못했습니다</h1>
    <p>{error}</p>
  </section>
{:else if runsData}
  <section class="training-page">
    <header>
      <p class="eyebrow">TRAINING LIFECYCLE</p>
      <h1>학습</h1>
      <p>실행 기록과 상세 manifest는 읽기 전용 API 응답에서만 표시합니다.</p>
    </header>
    <section class="card wide type1-overview" role="status" aria-live="polite">
      <p class="eyebrow">TYPE1 STATUS</p>
      <h2>Sequential MaskablePPO</h2>
      <p>Planned: 5 primary + 5 shuffled-label control seeds × 200,000 fixed episodes.</p>
      <p>Current Type1 evidence: <strong>{type1StateLabel(type1OverviewState)}</strong> — no observed completion is implied without an eligible completed Type1 manifest.</p>
      <p>Fresh OOS: <strong>NOT_RUN</strong>. {TYPE1_FACTS.execution.officialCloseStatement} {TYPE1_FACTS.claims.statement}</p>
    </section>

    {#if runsData.training_state === 'NOT_RUN'}
      <section class="empty-state" role="status" aria-live="polite">
        <h2>아직 어떤 V6 학습도 실행되지 않았습니다</h2>
        <p>승인된 CLI로 학습이 실행되면 증거가 이 화면에 나타납니다.</p>
      </section>
    {/if}

    <div class="grid">
      <section class="card">
        <h2>데이터셋 실행</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>run_id</th><th>generated_utc</th><th>sha256</th></tr></thead>
            <tbody>
              {#each runsData.datasets ?? [] as dataset}
                <tr>
                  <td>{text(dataset.run_id)}</td>
                  <td>{text(dataset.generated_utc)}</td>
                  <td title={dataset.sha256}>{text(dataset.sha256).slice(0, 12)}</td>
                </tr>
              {:else}
                <tr><td colspan="3">표시할 데이터 없음 · NOT_RUN</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="card">
        <h2>학습 실행</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>run_id</th><th>state</th><th>상세</th></tr></thead>
            <tbody>
              {#each runsData.runs ?? [] as run}
                <tr>
                  <td>{text(run.run_id)}</td>
                  <td>{text(run.state)}</td>
                  <td>
                    <button onclick={() => open(run.dataset_run_id, run.run_id)}>
                      {selected === key(run.dataset_run_id, run.run_id) ? '선택됨' : '상세'}
                    </button>
                  </td>
                </tr>
              {:else}
                <tr><td colspan="3">표시할 데이터 없음 · NOT_RUN</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    </div>

    {#if detailLoading}
      <section class="card wide" role="status" aria-live="polite">실행 상세를 읽고 있습니다.</section>
    {:else if detailError}
      <section class="card error" role="alert" aria-live="assertive">{detailError}</section>
    {:else if manifest}
      {#if isType1}
        <section class="card wide type1-evidence">
          <p class="eyebrow">TYPE1 TRAINING CONTRACT</p>
          <h2>Sequential MaskablePPO · 계획과 관측 증거를 분리</h2>
          <div class="lineage-grid">
            <dl><dt>planned primary seeds</dt><dd>{TYPE1_FACTS.evaluation.fixedSeeds}</dd></dl>
            <dl><dt>planned shuffled-label controls</dt><dd>{TYPE1_FACTS.evaluation.fixedSeeds}</dd></dl>
            <dl><dt>planned budget</dt><dd>200,000 episodes fixed</dd></dl>
            <dl><dt>observed run state</dt><dd>{text(observedTrainingState)}</dd></dl>
            <dl><dt>observed completion</dt><dd>{isCompleted ? `${observedEpisodes} seed-episodes evidenced` : 'NOT COMPLETED — completion evidence absent'}</dd></dl>
            <dl><dt>primary seed artifacts</dt><dd>{seedEntries.length} observed</dd></dl>
            <dl><dt>shuffled-control artifacts</dt><dd>{shuffledSeedEntries.length} observed</dd></dl>
            <dl><dt>evidence gate</dt><dd>{type1StateLabel(type1EvidenceState)}</dd></dl>
            <dl><dt>execution</dt><dd>{TYPE1_FACTS.execution.priceBasis}; {TYPE1_FACTS.execution.roundTripCost}</dd></dl>
            <dl><dt>accounting</dt><dd>{TYPE1_FACTS.accounting.initialNav}; max {TYPE1_FACTS.accounting.maxSlots} slots</dd></dl>
            <dl><dt>dataset reload artifact</dt><dd class="sha">{text(datasetArtifactPath)}</dd></dl>
            <dl><dt>training reload artifact</dt><dd class="sha">{text(runArtifactPath)}</dd></dl>
          </div>
          <p class="note">Synthetic overfit or shuffled-label behavior is calibration evidence only; it is not a completion, profitability, or live-trading claim.</p>
          <p class="note">{TYPE1_FACTS.execution.officialCloseStatement} {TYPE1_FACTS.claims.statement}</p>
        </section>
      {/if}
      <section class="card wide lineage">
        <div class="section-heading">
          <div>
            <p class="eyebrow">SELECTED RUN LINEAGE</p>
            <h2>{text(detail?.dataset_run_id)} · {text(detail?.train_run_id)}</h2>
          </div>
          <button class="copy" onclick={copyManifestSha}>manifest SHA 복사</button>
        </div>
        <div class="lineage-grid">
          <dl><dt>trainer version</dt><dd>{text(manifest.trainer_version)}</dd></dl>
          <dl><dt>model family / algorithm</dt><dd>{text(modelLabel)}</dd></dl>
          <dl><dt>prereg ID</dt><dd>{text(manifest.prereg?.id)}</dd></dl>
          <dl><dt>generated_utc</dt><dd>{text(generatedTime)}</dd></dl>
          <dl><dt>seeds</dt><dd>{text(manifest.seeds)}</dd></dl>
          <dl><dt>verdict</dt><dd>{text(manifest.verdict_candidate?.value)}</dd></dl>
          <dl><dt>test state (closed OOS)</dt><dd>{text(manifest.test?.state)}</dd></dl>
          <dl><dt>primary cost</dt><dd>{percent(primaryCost)}</dd></dl>
          <dl><dt>manifest SHA</dt><dd class="sha">{text(detail?.manifest_sha256)}</dd></dl>
        </div>
        <div class="reasons">
          <strong>verdict reasons</strong>
          {#each manifest.verdict_candidate?.reasons ?? [] as reason}
            <p>{text(reason)}</p>
          {:else}
            <p>MISSING</p>
          {/each}
        </div>
        {#if copyMessage}<p class="copy-feedback" role="status" aria-live="polite">{copyMessage}</p>{/if}
      </section>

      <section class="card wide">
        <h2>seed별 validation NAV 곡선</h2>
        <p class="note">각 선은 manifest의 한 seed 전체 val_nav_curve입니다. seed 간 점을 연결하지 않습니다.</p>
        {#if curveSeeds.length}
          <EChartsRenderer option={navOption} height="320px" caption="seed별 validation NAV · no-trade 60M baseline" />
        {:else}
          <p class="absence" role="status" aria-live="polite">
            validation NAV 곡선을 사용할 수 없습니다. manifest.per_seed[*].val_nav_curve가 없습니다.
          </p>
        {/if}
      </section>

      <section class="card wide">
        <h2>seed별 검증</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>seed</th><th>episodes</th><th>final val NAV</th><th>MDD</th><th>trade count</th></tr></thead>
            <tbody>
              {#each seedEntries as [seed, value]}
                <tr>
                  <th>{seed}</th>
                  <td>{text(value.episodes_ran)}</td>
                  <td>{won(value.final_val_metrics?.nav)}</td>
                  <td>{percent(value.final_val_metrics?.max_drawdown)}</td>
                  <td>{text(value.final_val_metrics?.trade_count)}</td>
                </tr>
              {:else}
                <tr><td colspan="5">표시할 seed 증거 없음 · NOT_RUN</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
      {#if isType1}
        <section class="card wide">
          <h2>Type1 shuffled-label control</h2>
          <p class="note">계획된 5개 control은 synthetic-overfit calibration 전용입니다.</p>
          <div class="table-wrap">
            <table>
              <thead><tr><th>seed</th><th>episodes</th><th>final val NAV</th><th>trade count</th></tr></thead>
              <tbody>
                {#each shuffledSeedEntries as [seed, value]}
                  <tr>
                    <th>{seed}</th>
                    <td>{text(value.episodes_ran)}</td>
                    <td>{won(value.final_val_metrics?.nav)}</td>
                    <td>{text(value.final_val_metrics?.trade_count)}</td>
                  </tr>
                {:else}
                  <tr><td colspan="4">표시할 shuffled-label control 증거 없음 · NOT_RUN</td></tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .training-page,
  .panel {
    width: min(100%, 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: clamp(18px, 4vw, 32px);
    background: var(--surface);
    color: var(--fg);
  }

  .grid,
  .lineage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
    gap: 16px;
    margin-top: 16px;
  }

  .card,
  .empty-state {
    min-width: 0;
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    padding: 16px;
    background: var(--surface-raised);
  }

  .wide { margin-top: 16px; }
  .empty-state { margin-top: 16px; border-color: var(--warn); background: var(--warn-soft); }
  .eyebrow { color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; }
  h1 { color: var(--fg-strong); font-size: clamp(1.8rem, 6vw, 2.6rem); }
  h2 { color: var(--fg-strong); font-size: 1.15rem; }
  .absence, .note { color: var(--muted); }
  .table-wrap { overflow-x: auto; }
  table { width: min(100%, 620px); min-width: 420px; border-collapse: collapse; font-size: .85rem; }
  th, td { border-top: 1px solid var(--border); padding: 8px; text-align: left; }
  th { color: var(--muted); }
  button { border: 1px solid var(--accent); border-radius: 6px; padding: 6px 10px; background: transparent; color: var(--accent-strong); font: inherit; }
  .error { color: var(--danger); }
  .section-heading { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: 12px; }
  .lineage-grid dl { min-width: 0; margin: 0; }
  dt { color: var(--muted); font-size: .8rem; }
  dd { margin: 4px 0 0; overflow-wrap: anywhere; }
  .sha { font-family: monospace; font-size: .8rem; }
  .reasons { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 12px; }
  .reasons p { margin: 6px 0; }
  .copy-feedback { color: var(--accent-strong); }

  @media (max-width: 420px) {
    .training-page, .panel { padding: 16px; }
    table { min-width: 360px; }
  }
</style>

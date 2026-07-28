<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { rlApi, type RlProgressResponse, type RlRliableStatsResponse, type RlRunDetail, type RlRunRecord, type RlTableRow } from '$lib/rlApi';
  import { requireJsonPayload } from '$lib/http';
  import { createRequestGate } from '$lib/requestGate';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import EvidenceHeader from '../components/EvidenceHeader.svelte';
  import MetricWithProvenance from '../components/MetricWithProvenance.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import { adaptEvidenceIdentity } from '../evidence';
  import type { EvidenceUiState } from '../evidenceState';
  import {
    DOCUMENTED_RL_FACTS,
    CONFLICT_BLOCKED,
    normalizeRlProgress,
    normalizeRlRunDetail,
    choosePreferredRlRun,
    classifyRlEvidenceLane,
    deriveRlCockpitEvidence,
    normalizeRlRuns,
    normalizeRlRows,
    reconcileRlRunIdentity,
    rlRunIdentityKey,
    normalizeRliableCollections,
    summarizeProgress,
    summarizeRliable,
  } from './rlEvidence';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();

  let runs = $state<readonly RlRunRecord[]>([]);
  let selectedName = $state('');
  let selectedRunUid = $state('');
  let selectedRun = $state<RlRunDetail | null>(null);
  let progress = $state<RlProgressResponse | null>(null);
  let progressState = $state<'recorded' | 'empty' | 'not_recorded'>('not_recorded');
  let rliable = $state<RlRliableStatsResponse | null>(null);
  let rliableError = $state<string | null>(null);
  let runsError = $state<string | null>(null);
  let runCollectionState = $state<'recorded' | 'empty' | 'not_recorded'>('not_recorded');
  let progressError = $state<string | null>(null);
  let rliableCollectionState = $state<'recorded' | 'empty' | 'not_recorded'>('not_recorded');
  let events = $state<readonly RlTableRow[]>([]);
  let eventsError = $state<string | null>(null);
  let eventsCollectionState = $state<'recorded' | 'empty' | 'not_recorded'>('not_recorded');
  let loading = $state(false);
  let detailLoading = $state(false);
  let error = $state<string | null>(null);
  let detailError = $state<string | null>(null);

  const runSelectGate = createRequestGate();

  const selectedListRecords = $derived(selectedRunUid ? runs.filter((run) => rlRunIdentityKey(run) === selectedRunUid) : []);
  const selectedListRecord = $derived(selectedListRecords[0] ?? null);
  const reconciliation = $derived(reconcileRlRunIdentity(selectedListRecord, selectedRun, {
    selectedRunUid,
    selectedName,
    listRecords: selectedListRecords,
    detailRecorded: selectedRun !== null && detailError === null,
  }));
  const conflictBlocked = $derived(selectedName !== '' && !detailLoading && reconciliation.status === CONFLICT_BLOCKED);
  const reconciliationState = $derived(detailLoading ? 'DETAIL_PENDING' : reconciliation.status);
  const evidenceSource = $derived(selectedName ? reconciliation.source : null);
  const cockpit = $derived(deriveRlCockpitEvidence(evidenceSource, { events: reconciliation.usable ? events : [] }));
  const identity = $derived(adaptEvidenceIdentity(evidenceSource ?? { id: 'MISSING_RUN' }, { source_endpoint: selectedName ? `/api/rl/runs/${encodeURIComponent(selectedName)}` : '/api/rl/runs' }));
  const laneRows = $derived([
    classifyRlEvidenceLane({ name: 'RULE lane contract', artifact_type: 'baseline', strategy_context: { line: 'rule_mainline', label: 'RULE baseline', is_reinforcement_learning: false } }),
    classifyRlEvidenceLane({ name: 'Supervised gate contract', artifact_type: 'factory_calibration', strategy_context: { line: 'supervised', label: 'supervised gate', is_reinforcement_learning: false } }),
    cockpit.lane,
  ]);
  const artifactRows = $derived(reconciliation.usable ? selectedRun?.artifacts ?? [] : []);
  const lineage = $derived(reconciliation.usable ? selectedRun?.strategy_context ?? null : null);
  const runStage = $derived(conflictBlocked ? CONFLICT_BLOCKED : String(selectedRun?.detail?.stage ?? selectedRun?.summary?.stage ?? selectedRun?.lifecycle?.last_phase ?? 'STAGE_NOT_RECORDED'));
  const runStatus = $derived(conflictBlocked ? CONFLICT_BLOCKED : String(selectedRun?.detail?.status ?? selectedRun?.summary?.status ?? selectedRun?.lifecycle?.status ?? 'STATUS_NOT_RECORDED'));
  const freshness = $derived(conflictBlocked ? CONFLICT_BLOCKED : identity.freshness_status);
  const conflictSummary = $derived(reconciliation.conflicts.map((item) => `${item.code}: ${item.detail}`).join(' · ') || 'MATCHED');
  const selectedState = $derived.by((): EvidenceUiState => (detailLoading ? 'loading' : conflictBlocked ? 'error' : detailError ? 'error' : selectedRun ? 'completed' : selectedName ? 'missing' : 'empty'));

  onMount(() => {
    void loadConsole();
  });

  function message(caught: unknown, fallback: string): string {
    return caught instanceof Error && caught.message ? caught.message : fallback;
  }

  async function loadConsole(): Promise<void> {
    loading = true;
    error = null;
    runsError = null;
    progressError = null;
    rliableError = null;
    try {
      const [runResult, progressResult, rliableResult] = await Promise.allSettled([
        requireJsonPayload('rl runs', rlApi.rlRuns(80)),
        requireJsonPayload('rl progress', rlApi.rlProgress()),
        requireJsonPayload('rliable stats', rlApi.rliableStats()),
      ] as const);
      if (runResult.status === 'fulfilled') {
        const normalizedRuns = normalizeRlRuns(runResult.value);
        runs = normalizedRuns.runs;
        runCollectionState = normalizedRuns.status;
      } else {
        runs = [];
        runCollectionState = 'not_recorded';
        runsError = message(runResult.reason, 'RL runs evidence fetch failed');
      }
      if (progressResult.status === 'fulfilled') {
        const normalizedProgress = normalizeRlProgress(progressResult.value);
        progress = normalizedProgress.progress;
        progressState = normalizedProgress.status;
      } else {
        progress = null;
        progressState = 'not_recorded';
        progressError = message(progressResult.reason, 'RL progress evidence fetch failed');
      }
      if (rliableResult.status === 'fulfilled') {
        rliable = rliableResult.value;
        rliableCollectionState = normalizeRliableCollections(rliableResult.value).status;
      } else {
        rliable = null;
        rliableCollectionState = 'not_recorded';
        rliableError = message(rliableResult.reason, 'rliable evidence fetch failed');
      }
      const preferred = choosePreferredRlRun(runs);
      if (preferred) await selectRun(rlRunIdentityKey(preferred));
    } catch (caught) {
      error = message(caught, 'RL evidence console load failed');
    } finally {
      loading = false;
    }
  }

  async function selectRun(runUid: string): Promise<void> {
    const token = runSelectGate.next();
    const listRecord = runs.find((run) => rlRunIdentityKey(run) === runUid) ?? null;
    const name = listRecord?.name ?? runUid;
    selectedRunUid = runUid;
    selectedName = name;
    selectedRun = null;
    events = [];
    eventsError = null;
    eventsCollectionState = 'not_recorded';
    detailLoading = true;
    detailError = null;
    if (!listRecord) {
      detailError = `${runUid} list payload not recorded`;
      detailLoading = false;
      return;
    }
    try {
      const [detailResult, eventResult] = await Promise.allSettled([
        requireJsonPayload(`${name} detail`, rlApi.rlRun(name)),
        requireJsonPayload(`${name} events`, rlApi.rlEvents(name, 160)),
      ] as const);
      if (!runSelectGate.isCurrent(token)) return;
      if (detailResult.status === 'fulfilled') {
        const normalizedDetail = normalizeRlRunDetail(detailResult.value, name);
        if (normalizedDetail.status === 'recorded') {
          selectedRun = normalizedDetail.detail;
        } else {
          selectedRun = detailResult.value !== null && typeof detailResult.value === 'object' && !Array.isArray(detailResult.value)
            ? (detailResult.value as RlRunDetail)
            : null;
          detailError = `${name} detail payload not recorded`;
        }
      } else {
        detailError = message(detailResult.reason, `${name} detail load failed`);
      }
      if (eventResult.status === 'fulfilled') {
        const normalizedEvents = normalizeRlRows(eventResult.value);
        events = normalizedEvents.rows;
        eventsCollectionState = normalizedEvents.status;
      } else {
        events = [];
        eventsCollectionState = 'not_recorded';
        eventsError = message(eventResult.reason, `${name} events fetch failed`);
      }
    } catch (caught) {
      if (!runSelectGate.isCurrent(token)) return;
      detailError = message(caught, `${name} detail load failed`);
    } finally {
      if (runSelectGate.isCurrent(token)) detailLoading = false;
    }
  }
</script>

<section class="rl-console" data-v4-rl-console aria-labelledby="v4-rl-console-title">
  <div class="console-intro">
    <p class="eyebrow">RL Evidence Console · research only</p>
    <h2 id="v4-rl-console-title">RL 증거 콘솔은 NO-GO와 blocker를 raw보다 먼저 보여줍니다</h2>
    <p>
      RULE baseline, supervised gate, RL experiment를 분리하고 TEST OOS, cost, split/hash, seed, baseline,
      uncertainty, MDD, trade count를 명시합니다. 이 화면은 live/broker/order/profit/model-build GO를 선언하지 않습니다.
    </p>
  </div>

  {#if error}
    <StateBoundary state="error" title="RL evidence load failed" detail={error} />
  {:else if loading && runs.length === 0}
    <StateBoundary state="loading" title="RL evidence loading" detail="runs, progress, rliable evidence를 읽는 중입니다." />
  {/if}
  <section class="run-selector" data-v4-run-selection aria-label="RL setup and run selection">
    <div>
      <p class="eyebrow">Setup · model/run selection</p>
      <h3>읽기 전용 evidence run 선택</h3>
      <p>선택 변경 시 detail/events 응답 세대를 분리하며, 늦은 이전 응답은 현재 run을 덮어쓰지 못합니다.</p>
    </div>
    <label>
      <span>Run</span>
      <select
        aria-label="RL evidence run"
        value={selectedRunUid}
        disabled={loading || runCollectionState !== 'recorded'}
        onchange={(event) => void selectRun(event.currentTarget.value)}
      >
        {#if runCollectionState !== 'recorded'}
          <option value="">{runCollectionState === 'empty' ? 'RUNS_EMPTY' : 'RUNS_NOT_RECORDED'}</option>
        {:else}
          {#each runs as run, index (run.name + ':' + rlRunIdentityKey(run) + ':' + index)}
            <option value={rlRunIdentityKey(run)}>{run.name} · {classifyRlEvidenceLane(run).kind} · run_uid {rlRunIdentityKey(run)}</option>
          {/each}
        {/if}
      </select>
    </label>
    <dl>
      <div><dt>Available</dt><dd>{runCollectionState === 'not_recorded' ? 'RUNS_NOT_RECORDED' : runCollectionState === 'empty' ? 'RUNS_EMPTY' : `${runs.length} runs`}</dd></div>
      <div><dt>Source</dt><dd data-run-source-state={runsError ? 'error' : runCollectionState}>{runsError ?? (runCollectionState === 'not_recorded' ? 'RUNS_NOT_RECORDED' : 'GET /api/rl/runs')}</dd></div>
      <div><dt>Control</dt><dd>READ_ONLY · GET_ONLY</dd></div>
    </dl>
  </section>


  <EvidenceHeader
    {identity}
    run={cockpit.run}
    eyebrow="Selected RL evidence"
    title="선택 run 식별 · stale response guarded"
    description="선택 run detail/events는 request-generation gate로 보호되어 늦게 도착한 이전 run 응답이 최신 선택을 덮어쓰지 못합니다."
  />

  <section class="selected-run" data-v4-selected-run data-request-gate="createRequestGate:isCurrent" aria-label="Selected run identity">
    <div>
      <span>Run</span>
      <strong>{selectedName || cockpit.run.run_id}</strong>
    </div>
    <div>
      <span>Stage</span>
      <strong>{runStage}</strong>
    </div>
    <div>
      <span>Status</span>
      <strong>{runStatus}</strong>
    </div>
    <div>
      <span>Freshness</span>
      <strong>{freshness}</strong>
    </div>
  </section>

  <section
    class="identity-reconciliation"
    data-v4-rl-identity-reconciliation
    data-identity-state={reconciliationState}
    data-conflict-state={reconciliationState}
    aria-label="List detail provenance reconciliation"
  >
    <div class="section-head">
      <p class="eyebrow">Immutable run identity</p>
      <h3>{detailLoading ? 'DETAIL_PENDING' : conflictBlocked ? CONFLICT_BLOCKED : 'list/detail provenance checked'}</h3>
      <p>run_uid 전체값, revision, source_sha256, protocol을 list/detail 양쪽에서 비교합니다.</p>
    </div>
    <div class="provenance-grid">
      <article data-v4-rl-list-provenance data-provenance-origin="list" data-run-uid={reconciliation.list.run_uid}>
        <span>List provenance</span>
        <strong>{reconciliation.list.run_uid}</strong>
        <p>name {reconciliation.list.name} · revision {reconciliation.list.revision} · source_sha256 {reconciliation.list.source_sha256} · protocol {reconciliation.list.protocol}</p>
        <small>{reconciliation.list.endpoint} · {reconciliation.list.lane}</small>
      </article>
      <article data-v4-rl-detail-provenance data-provenance-origin="detail" data-run-uid={reconciliation.detail.run_uid}>
        <span>Detail provenance</span>
        <strong>{reconciliation.detail.run_uid}</strong>
        <p>name {reconciliation.detail.name} · revision {reconciliation.detail.revision} · source_sha256 {reconciliation.detail.source_sha256} · protocol {reconciliation.detail.protocol}</p>
        <small>{reconciliation.detail.endpoint} · {reconciliation.detail.lane}</small>
      </article>
      <article data-v4-rl-identity-conflicts data-conflict-count={reconciliation.conflicts.length}>
        <span>Reconciliation</span>
        <strong>{reconciliationState}</strong>
        <p>{conflictBlocked ? `${CONFLICT_BLOCKED} · ${conflictSummary}` : detailLoading ? 'DETAIL_PENDING · locks remain fail-closed' : 'MATCHED · detail evidence usable'}</p>
        <small>Unsafe actions and optimistic model/GO copy are suppressed unless identity is MATCHED.</small>
      </article>
    </div>
  </section>

  <section class="lane-grid" aria-label="RULE supervised gate RL lane separation">
    {#each laneRows as lane}
      <article class="lane-card" data-v4-rl-lane data-lane={lane.kind}>
        <span>{lane.kind}</span>
        <strong>{lane.label}</strong>
        <p>{lane.reason}</p>
      </article>
    {/each}
  </section>

  <PromotionLocksGrid result={cockpit.run.promotion_locks} compact />
  <p class="lock-boundary" data-v4-effective-lock-boundary>
    Source true unlock fields are provenance attempts only; V4 effective promotion locks remain false/blocked without separate reviewed authority.
  </p>

  <section class="metrics" aria-label="Explicit cockpit metrics before charts and raw">
    {#each cockpit.metrics as item}
      <div class="metric-shell" data-metric-key={item.key} data-behavior={item.behavior}>
        <MetricWithProvenance label={item.label} metric={item.metric} tone={item.behavior === 'recorded' ? 'neutral' : 'warning'} />
        <p>{item.display}</p>
      </div>
    {/each}
    <article class="never-trade" data-never-trade={cockpit.neverTradeStatus}>
      <span>Never-trade status</span>
      <strong>{cockpit.neverTradeStatus}</strong>
      <p>trade_count가 0이면 NEVER_TRADE, 누락이면 NOT_RECORDED로 표시합니다.</p>
    </article>
  </section>

  <section class="metadata" aria-label="Actual split seed baseline metadata before charts and raw">
    {#each cockpit.metadata as item}
      <div class="metadata-shell" data-metadata-key={item.key} data-behavior={item.behavior}>
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        <p>source: {item.source}</p>
      </div>
    {/each}
  </section>

  <section class="facts" data-v4-rl-facts aria-label="Documented RL model health facts">
    <div class="section-head">
      <p class="eyebrow">Model health facts</p>
      <h3>정적 문서화 posture · live data 아님</h3>
    </div>
    <div class="facts-grid">
      {#each DOCUMENTED_RL_FACTS as fact}
        <article data-fact-key={fact.key}>
          <span>{fact.status}</span>
          <strong>{fact.label}</strong>
          <p>{fact.detail}</p>
          <small>{fact.staticResearchPosture ? 'DOCUMENTED_RESEARCH_POSTURE_NOT_LIVE_DATA' : 'LIVE_DATA'}</small>
        </article>
      {/each}
    </div>
  </section>

  <EvidenceDisclosure summary="Artifacts · events · lineage · rliable summaries" meta="before raw audit" open>
    <div class="summary-grid">
      <article>
        <span>Artifacts</span>
        <strong>{artifactRows.length}</strong>
        <p>{artifactRows.map((artifact) => artifact.name).slice(0, 6).join(' · ') || 'ARTIFACTS_NOT_RECORDED'}</p>
      </article>
      <article data-events-source-state={eventsError ? 'error' : eventsCollectionState}>
        <span>Events</span>
        <strong>{eventsError ? 'EVENTS_FETCH_FAILED' : eventsCollectionState === 'not_recorded' ? 'EVENTS_NOT_RECORDED' : events.length}</strong>
        <p>{eventsError ?? (eventsCollectionState === 'not_recorded' ? 'events collection not recorded' : events.length > 0 ? 'events loaded through GET API' : 'EVENTS_EMPTY')}</p>
      </article>
      <article>
        <span>Lineage</span>
        <strong>{lineage?.line ?? cockpit.run.line}</strong>
        <p>{lineage?.label ?? cockpit.run.strategy_label}</p>
      </article>
      <article data-progress-source-state={progressError ? 'error' : progressState}>
        <span>Progress</span>
        <strong>{progressError ? 'PROGRESS_FETCH_FAILED' : progressState === 'empty' ? 'PROGRESS_EMPTY' : progressState === 'not_recorded' ? 'PROGRESS_NOT_RECORDED' : summarizeProgress(progress)}</strong>
        <p>{progressError ?? (progressState === 'not_recorded' ? 'PROGRESS_NOT_RECORDED' : 'progress evidence is read-only and cannot unlock promotion.')}</p>
      </article>
      <article data-rliable-source-state={rliableError ? 'error' : rliableCollectionState}>
        <span>Rliable</span>
        <strong>{rliableError ? 'RLIABLE_FETCH_FAILED' : rliableCollectionState === 'not_recorded' ? 'RLIABLE_NOT_RECORDED' : summarizeRliable(rliable)}</strong>
        <p>{rliableError ?? (rliableCollectionState === 'not_recorded' ? 'rliable collections not recorded' : 'rliable summary is uncertainty evidence, not a profitability claim.')}</p>
      </article>
    </div>
  </EvidenceDisclosure>

  <StateBoundary state={selectedState} title={conflictBlocked ? CONFLICT_BLOCKED : 'Selected detail state'} detail={conflictBlocked ? conflictSummary : detailError ?? '선택 run detail/events state'} />

  <EvidenceDisclosure summary="Raw audit · legacy/full RL surface" meta="last disclosure only" open={!reconciliation.usable} lazy>
    <div
      data-v4-raw-audit
      data-raw-audit-trust={reconciliation.usable ? 'MATCHED' : 'UNTRUSTED'}
      data-legacy-child-state={reconciliation.usable ? 'MATCHED' : CONFLICT_BLOCKED}
    >
      {#if reconciliation.usable}
        {#if children}
          {@render children()}
        {:else}
          <p class="raw-empty">Legacy RL audit child surface not supplied. Raw audit remains last.</p>
        {/if}
      {:else}
        <div class="raw-untrusted" role="alert" data-v4-raw-audit-untrusted data-raw-audit-state={CONFLICT_BLOCKED}>
          <strong>UNTRUSTED · {CONFLICT_BLOCKED}</strong>
          <p>Legacy RL audit child surface is fenced until reconciliation.usable is true. Independent child state is not trusted during {reconciliationState}.</p>
          <small>{conflictSummary}</small>
        </div>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .rl-console {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    min-width: 0;
    gap: 16px;
    width: min(100%, var(--content-max));
    margin-inline: auto;
    color: var(--fg);
  }

  .console-intro,
  .run-selector,
  .selected-run,
  .identity-reconciliation,
  .lane-card,
  .facts,
  .metric-shell,
  .metadata-shell,
  .never-trade {
    border: 1px solid var(--border-faint);
    border-radius: 22px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .console-intro,
  .run-selector,
  .identity-reconciliation,
  .facts {
    padding: 18px 20px;
  }

  .eyebrow,
  .selected-run span,
  .identity-reconciliation article span,
  .lane-card span,
  .facts article span,
  .summary-grid span,
  .never-trade span {
    color: var(--accent-strong);
    font: 760 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin: 0;
  }

  h2,
  h3,
  strong {
    color: var(--fg-strong);
  }

  h2 {
    margin-top: 6px;
    font: 780 clamp(24px, 4vw, 38px) / 1.05 var(--font-display);
    letter-spacing: -0.05em;
  }

  h3 {
    font: 760 18px/1.2 var(--font-display);
  }

  p {
    color: var(--muted);
    line-height: 1.55;
  }

  .console-intro p {
    max-width: 86ch;
    margin-top: 10px;
  }
  .run-selector {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(220px, 0.8fr);
    gap: 14px;
    align-items: end;
  }

  .run-selector label {
    display: grid;
    gap: 7px;
    color: var(--fg-strong);
    font: 730 12px/1.2 var(--font-display);
  }

  .run-selector select {
    width: 100%;
    min-width: 0;
    min-height: 42px;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 8px 10px;
    color: var(--fg-strong);
    background: var(--surface-raised);
    font: 650 12px/1.2 var(--font-mono);
  }

  .run-selector select:focus-visible {
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }

  .run-selector dl {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin: 0;
  }

  .run-selector dl div {
    min-width: 0;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    padding: 10px;
    background: var(--surface-raised);
  }

  .run-selector dt {
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    text-transform: uppercase;
  }

  .run-selector dd {
    margin: 5px 0 0;
    color: var(--fg-strong);
    font: 700 11px/1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  @media (max-width: 680px) {
    .run-selector,
    .run-selector dl {
      grid-template-columns: 1fr;
    }

    .run-selector dl {
      grid-column: auto;
    }
  }

  .selected-run,
  .lane-grid,
  .provenance-grid,
  .metrics,
  .metadata,
  .facts-grid,
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
    gap: 12px;
  }

  .selected-run {
    padding: 14px;
  }

  .selected-run div,
  .provenance-grid article,
  .summary-grid article,
  .facts article,
  .metadata-shell,
  .never-trade {
    min-width: 0;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    padding: 12px;
    background: var(--surface-raised);
  }

  .selected-run strong,
  .provenance-grid strong,
  .lane-card strong,
  .summary-grid strong,
  .never-trade strong {
    display: block;
    margin-top: 5px;
    font: 750 13px/1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .metadata-shell span {
    color: var(--accent-strong);
    font: 760 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .metadata-shell strong {
    display: block;
    margin-top: 5px;
    color: var(--fg-strong);
    font: 750 13px/1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }
  .metadata-shell p,
  .facts-grid article,
  .facts-grid article span,
  .facts-grid article strong,
  .facts-grid article p,
  .facts-grid article small {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .lane-card,
  .metric-shell,
  .metadata-shell,
  .never-trade {
    padding: 14px;
  }

  .identity-reconciliation[data-conflict-state='CONFLICT_BLOCKED'] {
    border-color: color-mix(in oklab, var(--danger) 56%, var(--border));
  }

  .lane-card[data-lane='RULE'],
  .lane-card[data-lane='SUPERVISED_GATE'] {
    border-color: color-mix(in oklab, var(--warn) 46%, var(--border));
  }

  .lane-card[data-lane='RL'] {
    border-color: color-mix(in oklab, var(--danger) 46%, var(--border));
  }

  .metric-shell {
    display: grid;
    gap: 8px;
  }

  .metric-shell[data-behavior='not_recorded'],
  .metric-shell[data-behavior='incompatible_unit'],
  .metadata-shell[data-behavior='not_recorded'] {
    border-color: color-mix(in oklab, var(--warn) 46%, var(--border));
  }

  .section-head {
    margin-bottom: 12px;
  }

  .facts-grid article {
    display: grid;
    min-width: 0;
    gap: 6px;
    overflow-wrap: anywhere;
  }

  .facts-grid small {
    min-width: 0;
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .raw-empty {
    padding: 14px;
    border: 1px dashed var(--border);
    border-radius: 14px;
    background: var(--surface-raised);
  }

  .lock-boundary {
    margin: 0;
    padding: 12px 14px;
    border: 1px solid var(--danger);
    border-radius: 14px;
    background: var(--danger-soft);
    color: var(--danger);
    font-weight: 720;
  }

  .raw-untrusted {
    display: grid;
    gap: 6px;
    padding: 14px;
    border: 1px solid var(--danger);
    border-radius: 14px;
    background: var(--danger-soft);
    color: var(--danger);
  }

  .raw-untrusted p,
  .raw-untrusted small {
    margin: 0;
    color: var(--danger);
  }

  .raw-untrusted strong {
    color: var(--danger);
  }
</style>

<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { dailyOhlcvApi, type DailyCloseSlotLatestResponse, type DailyProgressResponse, type DailyRegistryResponse } from '$lib/dailyOhlcvApi';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import { adaptDailyResearchEvidence } from './dailyEvidence';

  interface Props {
    children?: Snippet;
  }

  type SourceState<T> = {
    data: T | null;
    loading: boolean;
    error: string | null;
    loaded: boolean;
  };

  let { children }: Props = $props();

  let progress = $state<SourceState<DailyProgressResponse>>({ data: null, loading: false, error: null, loaded: false });
  let closeSlotLatest = $state<SourceState<DailyCloseSlotLatestResponse>>({ data: null, loading: false, error: null, loaded: false });
  let registryLatest = $state<SourceState<DailyRegistryResponse>>({ data: null, loading: false, error: null, loaded: false });
  const CRITICAL_TIMEOUT_MS = 5000;

  const evidence = $derived(adaptDailyResearchEvidence(progress.data, closeSlotLatest.data, registryLatest.data));
  const criticalSources = $derived([
    { key: 'progress', label: '진행 현황', endpoint: '/api/daily-ohlcv/progress', state: progress },
    { key: 'closeSlotLatest', label: '종가 슬롯 최신', endpoint: '/api/daily-ohlcv/close-slot/latest?limit=15', state: closeSlotLatest },
    { key: 'registryLatest', label: '레지스트리 최신', endpoint: '/api/daily-ohlcv/registry/latest?limit=15', state: registryLatest },
  ]);

  onMount(() => {
    void loadProgress();
    void loadCloseSlotLatest();
    void loadRegistryLatest();
  });

  function message(caught: unknown, fallback: string): string {
    return caught instanceof Error && caught.message ? caught.message : fallback;
  }
  async function loadCritical<T>(
    label: string,
    request: (signal: AbortSignal) => Promise<T | null>,
  ): Promise<T | null> {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        reject(new Error(`${label} GET timed out after ${CRITICAL_TIMEOUT_MS}ms`));
      }, CRITICAL_TIMEOUT_MS);
    });
    try {
      return await Promise.race([request(controller.signal), timeout]);
    } finally {
      if (timer !== undefined) clearTimeout(timer);
    }
  }


  async function loadProgress(): Promise<void> {
    progress = { data: null, loading: true, error: null, loaded: false };
    try {
      progress = { data: await loadCritical('progress', (signal) => dailyOhlcvApi.progress(signal)), loading: false, error: null, loaded: true };
    } catch (caught) {
      progress = { data: null, loading: false, error: message(caught, 'progress GET failed'), loaded: true };
    }
  }

  async function loadCloseSlotLatest(): Promise<void> {
    closeSlotLatest = { data: null, loading: true, error: null, loaded: false };
    try {
      closeSlotLatest = { data: await loadCritical('close-slot latest', (signal) => dailyOhlcvApi.closeSlotLatest(signal)), loading: false, error: null, loaded: true };
    } catch (caught) {
      closeSlotLatest = { data: null, loading: false, error: message(caught, 'close-slot latest GET failed'), loaded: true };
    }
  }

  async function loadRegistryLatest(): Promise<void> {
    registryLatest = { data: null, loading: true, error: null, loaded: false };
    try {
      registryLatest = { data: await loadCritical('registry latest', (signal) => dailyOhlcvApi.registryLatest(signal)), loading: false, error: null, loaded: true };
    } catch (caught) {
      registryLatest = { data: null, loading: false, error: message(caught, 'registry latest GET failed'), loaded: true };
    }
  }

  function stateLabel(state: SourceState<unknown>): string {
    if (state.loading) return 'LOADING';
    if (state.error) return 'ERROR';
    if (state.data) return 'RECORDED';
    if (state.loaded) return 'MISSING';
    return 'NOT_REQUESTED';
  }
</script>

<section class="daily-research" data-v4-daily-research aria-labelledby="v4-daily-research-title">
  <div class="intro">
    <p class="eyebrow">V4 Daily Research · GET-only evidence</p>
    <h2 id="v4-daily-research-title">일간 리서치 증거는 차트보다 권한·TEST OOS·blocker를 먼저 표시합니다</h2>
    <p>
      progress, close-slot latest, registry latest를 독립 GET으로 읽고 하나의 timeout/error가 다른 증거를 숨기지 않게 합니다.
      smoke/unknown artifact는 canonical로 승격하지 않으며 live/broker/order/profit/model-promotion GO를 추론하지 않습니다.
    </p>
  </div>

  <section class="source-grid" aria-label="critical daily GET evidence states">
    {#each criticalSources as source (source.key)}
      <article data-source={source.key} data-state={stateLabel(source.state)}>
        <span>{source.label}</span>
        <strong>{stateLabel(source.state)}</strong>
        <p>{source.state.error ?? source.endpoint}</p>
      </article>
    {/each}
  </section>

  <section class="authority-panel" data-v4-daily-authority data-authority-level={evidence.authority.level} aria-label="daily authority hierarchy">
    <div>
      <p class="eyebrow">Authority hierarchy</p>
      <h3>{evidence.authority.label}</h3>
      <p>{evidence.authority.source} · {evidence.authority.reason}</p>
    </div>
    <dl>
      <div><dt>TEST OOS</dt><dd>{evidence.testOosStatus}</dd></div>
      <div><dt>Latest selection</dt><dd>{evidence.latestSelection}</dd></div>
      <div><dt>Source run</dt><dd>{evidence.sourceRunId}</dd></div>
      <div><dt>Freshness</dt><dd>{evidence.freshness}</dd></div>
    </dl>
  </section>

  <section class="evidence-grid" aria-label="daily mandatory evidence before charts">
    <article>
      <span>Cost</span>
      <strong>{evidence.roundTripCost.label}</strong>
      <p>{evidence.roundTripCost.status} · exact 23bp only when source declares it</p>
    </article>
    <article>
      <span>Cost controls</span>
      <strong>{evidence.costControls.label}</strong>
      <p>{evidence.costControls.status} · 0bp/46bp controls are shown only when declared by source</p>
    </article>
    <article>
      <span>Split / hash / code</span>
      <strong>{evidence.split}</strong>
      <p>{evidence.splitHash} · {evidence.sourceCode}</p>
    </article>
    <article>
      <span>Seed</span>
      <strong>{evidence.seed}</strong>
      <p>leading-zero identifiers remain strings; missing seed is NOT_RECORDED</p>
    </article>
    <article>
      <span>Slot controls</span>
      <strong>{evidence.slotControls.label}</strong>
      <p>{evidence.slotControls.status} · selected/max slots only when declared</p>
    </article>
  </section>

  <section class="blockers" data-v4-daily-blockers aria-label="complete daily blockers">
    <div class="section-head">
      <p class="eyebrow">Blockers before charts</p>
      <h3>NO-GO는 기본값이며 blocker는 전체 출처에서 dedupe합니다</h3>
    </div>
    <ul>
      {#each evidence.blockers as blocker (blocker)}
        <li>{blocker}</li>
      {/each}
    </ul>
  </section>

  <PromotionLocksGrid result={evidence.promotionLocks} compact />

  <EvidenceDisclosure summary="Raw audit · critical GET payload states" meta="selectors: data-v4-daily-raw-audit" open>
    <div class="raw-audit" data-v4-daily-raw-audit>
      <dl>
        <div><dt>progress_status</dt><dd>{evidence.rawAudit.progressStatus}</dd></div>
        <div><dt>close_slot_status</dt><dd>{evidence.rawAudit.closeSlotStatus}</dd></div>
        <div><dt>registry_status</dt><dd>{evidence.rawAudit.registryStatus}</dd></div>
        <div><dt>artifact_status</dt><dd>{evidence.rawAudit.artifactStatus}</dd></div>
      </dl>
      {#each criticalSources as source (source.key)}
        {#if source.state.error}
          <StateBoundary state="error" title={`${source.label} failed`} detail={source.state.error} />
        {:else if source.state.loading}
          <StateBoundary state="loading" title={`${source.label} loading`} detail={source.endpoint} />
        {:else if source.state.loaded && !source.state.data}
          <StateBoundary state="missing" title={`${source.label} missing`} detail="GET completed without recorded payload" />
        {/if}
      {/each}
    </div>
  </EvidenceDisclosure>

  <EvidenceDisclosure summary="Legacy Daily functions · lazy child surface" meta="final disclosure; no duplicate initial storm" open={false} lazy>
    <div class="legacy-child" data-v4-daily-legacy-child data-v4-raw-audit>
      {#if children}
        {@render children()}
      {:else}
        <p>Legacy Daily child surface not supplied. V4 critical evidence remains GET-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .daily-research {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
  }
  .daily-research > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .authority-panel,
  .blockers,
  .source-grid article,
  .evidence-grid article {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .intro,
  .authority-panel,
  .blockers {
    padding: 18px 20px;
  }

  .eyebrow,
  .source-grid span,
  .evidence-grid span,
  dt {
    margin: 0;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin-block: 0;
  }

  h2,
  h3,
  strong {
    color: var(--fg-strong);
    overflow-wrap: anywhere;
  }

  .intro,
  .authority-panel > div,
  .section-head,
  .source-grid article,
  .evidence-grid article {
    display: grid;
    gap: 8px;
  }
  .source-grid article,
  .evidence-grid article {
    min-width: 0;
  }

  .source-grid,
  .evidence-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .source-grid article,
  .evidence-grid article {
    padding: 14px;
    background: var(--surface-raised);
  }

  .source-grid article[data-state='ERROR'],
  .source-grid article[data-state='MISSING'] {
    border-color: var(--danger);
    background: var(--danger-soft);
  }

  .source-grid p,
  .evidence-grid p,
  .intro p,
  .authority-panel p,
  .legacy-child,
  dd {
    color: var(--muted);
    line-height: 1.55;
  }
  .source-grid p,
  .evidence-grid p,
  .intro p,
  .authority-panel p,
  .blockers li {
    overflow-wrap: anywhere;
  }

  .authority-panel {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(320px, 1fr);
    gap: 16px;
    border-color: var(--warn);
  }

  .authority-panel[data-authority-level='canonical'] {
    border-color: var(--success);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin: 0;
  }

  dl div {
    display: grid;
    gap: 4px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    padding: 10px;
    background: var(--surface-sunken);
  }

  dd {
    margin: 0;
    font: 720 var(--t-body) / 1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .blockers ul {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 14px 0 0;
    padding: 0;
    list-style: none;
  }

  .blockers li {
    border: 1px solid var(--danger);
    border-radius: var(--r-pill);
    padding: 7px 10px;
    background: var(--danger-soft);
    color: var(--danger);
    font: 760 var(--t-caption) / 1.2 var(--font-mono);
  }

  .raw-audit,
  .legacy-child {
    display: grid;
    gap: 12px;
  }

  @media (max-width: 980px) {
    .source-grid,
    .evidence-grid,
    .authority-panel {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  @media (max-width: 620px) {
    dl {
      grid-template-columns: 1fr;
    }
  }
</style>

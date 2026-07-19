<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { api, type ArtifactsResponse, type HistoryResponse, type TrainingStatus } from '$lib/api';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import LifecyclePill from '../components/LifecyclePill.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import { adaptTrainingOpsEvidence, type LoadState } from './systemEvidence';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();

  function emptyState<T>(): LoadState<T> {
    return { data: null, loading: false, error: null, loaded: false };
  }

  let status = $state<LoadState<TrainingStatus>>(emptyState());
  let history = $state<LoadState<HistoryResponse>>(emptyState());
  let artifacts = $state<LoadState<ArtifactsResponse>>(emptyState());

  const evidence = $derived(adaptTrainingOpsEvidence(status.data, history.data, artifacts.data, status));

  const sources = $derived([
    { key: 'status', label: 'Training status', endpoint: '/api/training/status', state: status },
    { key: 'history', label: 'Training history', endpoint: '/api/training/history', state: history },
    { key: 'artifacts', label: 'Training artifacts', endpoint: '/api/training/artifacts', state: artifacts },
  ]);

  onMount(() => {
    void loadStatus();
    void loadHistory();
    void loadArtifacts();
  });

  function message(caught: unknown, fallback: string): string {
    return caught instanceof Error && caught.message ? caught.message : fallback;
  }

  async function loadStatus(): Promise<void> {
    status = { data: null, loading: true, error: null, loaded: false };
    try {
      status = { data: await api.status(), loading: false, error: null, loaded: true };
    } catch (caught) {
      status = { data: null, loading: false, error: message(caught, 'training status GET failed'), loaded: true };
    }
  }

  async function loadHistory(): Promise<void> {
    history = { data: null, loading: true, error: null, loaded: false };
    try {
      history = { data: await api.history(), loading: false, error: null, loaded: true };
    } catch (caught) {
      history = { data: null, loading: false, error: message(caught, 'training history GET failed'), loaded: true };
    }
  }

  async function loadArtifacts(): Promise<void> {
    artifacts = { data: null, loading: true, error: null, loaded: false };
    try {
      artifacts = { data: await api.artifacts(), loading: false, error: null, loaded: true };
    } catch (caught) {
      artifacts = { data: null, loading: false, error: message(caught, 'training artifacts GET failed'), loaded: true };
    }
  }

  function stateLabel(state: LoadState<unknown>): string {
    if (state.loading) return 'LOADING';
    if (state.error) return 'ERROR';
    if (state.data) return 'RECORDED';
    if (state.loaded) return 'MISSING';
    return 'NOT_REQUESTED';
  }
</script>

<section class="training-ops" data-v4-training-ops aria-labelledby="v4-training-ops-title">
  <div class="intro">
    <p class="eyebrow">V4 Training Ops · GET-only evidence</p>
    <h2 id="v4-training-ops-title">학습 운영 화면은 authority·stage·status·run·freshness를 legacy 상세보다 먼저 표시합니다</h2>
    <p>
      status, history, artifacts를 독립 GET으로 읽고 하나의 timeout/error가 다른 증거를 숨기지 않게 합니다.
      model-health posture는 읽기 전용이며 승격/라이브/브로커/주문/수익성을 선언하지 않습니다.
    </p>
  </div>

  <section class="source-grid" aria-label="critical training GET evidence states">
    {#each sources as source (source.key)}
      <article data-source={source.key} data-state={stateLabel(source.state)}>
        <span>{source.label}</span>
        <strong>{stateLabel(source.state)}</strong>
        <p>{source.state.error ?? source.endpoint}</p>
      </article>
    {/each}
  </section>

  <section class="lifecycle-panel" data-v4-training-lifecycle aria-label="training lifecycle state">
    <LifecyclePill state={evidence.lifecycleState} detail={evidence.run.status} />
  </section>

  <section class="authority-panel" data-v4-training-authority data-authority-level={evidence.authority.level} aria-label="training authority">
    <div>
      <p class="eyebrow">Authority</p>
      <h3>{evidence.authority.label}</h3>
      <p>{evidence.authority.source} · {evidence.authority.reason}</p>
    </div>
    <dl>
      <div><dt>Run</dt><dd>{evidence.run.runName}</dd></div>
      <div><dt>Stage</dt><dd>{evidence.run.stage}</dd></div>
      <div><dt>Status</dt><dd>{evidence.run.status}</dd></div>
      <div><dt>Overall %</dt><dd>{evidence.run.overallPercent === null ? 'NOT_RECORDED' : `${evidence.run.overallPercent}%`}</dd></div>
      <div><dt>Freshness</dt><dd>{evidence.run.freshness}</dd></div>
    </dl>
  </section>

  <section class="model-health" data-v4-training-model-health data-status={evidence.modelHealth.status} aria-label="read-only model health posture">
    <div class="section-head">
      <p class="eyebrow">Model health posture · read-only</p>
      <h3>{evidence.modelHealth.disclosure}</h3>
    </div>
    <dl>
      <div><dt>Checkpoint ready</dt><dd>{evidence.modelHealth.checkpointReady ? 'true' : 'false'}</dd></div>
      <div><dt>Predictor started</dt><dd>{evidence.modelHealth.predictorStarted ? 'true' : 'false'}</dd></div>
      <div><dt>Label</dt><dd>{evidence.modelHealth.label}</dd></div>
      <div><dt>Message</dt><dd>{evidence.modelHealth.message}</dd></div>
    </dl>
  </section>

  <section class="blockers" data-v4-training-blockers aria-label="training operations blockers">
    <div class="section-head">
      <p class="eyebrow">Blockers before charts</p>
      <h3>승격/빌드 GO는 기본값이 아니며 blocker는 전체 출처에서 dedupe합니다</h3>
    </div>
    <ul>
      {#each evidence.blockers as blocker (blocker)}
        <li>{blocker}</li>
      {/each}
    </ul>
  </section>

  <PromotionLocksGrid result={evidence.promotionLocks} compact />

  <EvidenceDisclosure summary="Raw audit · critical GET payload states" meta="selectors: data-v4-training-raw-audit" open>
    <div class="raw-audit" data-v4-training-raw-audit>
      {#each sources as source (source.key)}
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

  <EvidenceDisclosure summary="Legacy Live Training functions · lazy child surface" meta="final disclosure; no duplicate initial storm" open={false} lazy>
    <div class="legacy-child" data-v4-training-legacy-child>
      {#if children}
        {@render children()}
      {:else}
        <p>Legacy Live Training child surface not supplied. V4 critical evidence remains GET-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .training-ops {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
  }
  .training-ops > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .authority-panel,
  .model-health,
  .blockers,
  .lifecycle-panel,
  .source-grid article {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .intro,
  .authority-panel,
  .model-health,
  .blockers,
  .lifecycle-panel {
    padding: 18px 20px;
  }

  .eyebrow,
  .source-grid span,
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
  .model-health .section-head,
  .blockers .section-head,
  .source-grid article {
    display: grid;
    gap: 8px;
  }
  .source-grid article {
    min-width: 0;
  }

  .source-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .source-grid article {
    padding: 14px;
    background: var(--surface-raised);
  }

  .source-grid article[data-state='ERROR'],
  .source-grid article[data-state='MISSING'] {
    border-color: var(--danger);
    background: var(--danger-soft);
  }

  .source-grid p,
  .intro p,
  .authority-panel p,
  .model-health p,
  .legacy-child,
  dd {
    max-width: 60ch;
    color: var(--muted);
    line-height: 1.5;
    overflow-wrap: anywhere;
  }

  .authority-panel,
  .model-health {
    display: grid;
    gap: 14px;
  }

  .authority-panel dl,
  .model-health dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
    gap: 10px;
    margin: 0;
  }

  .authority-panel dl div,
  .model-health dl div {
    display: grid;
    gap: 4px;
    padding: 10px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface-raised);
  }

  dd {
    color: var(--fg-strong);
    font: 650 var(--t-body) / 1.35 var(--font-mono);
  }

  .blockers ul {
    margin: 0;
    padding-inline-start: 18px;
    color: var(--fg);
    line-height: 1.5;
  }

  .lifecycle-panel {
    display: flex;
    align-items: center;
  }

  @media (max-width: 760px) {
    .source-grid {
      grid-template-columns: 1fr;
    }
    .authority-panel dl,
    .model-health dl {
      grid-template-columns: 1fr;
    }
  }
</style>

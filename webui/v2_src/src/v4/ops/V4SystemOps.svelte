<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { api, type GpuResponse, type SystemResponse } from '$lib/api';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import LifecyclePill from '../components/LifecyclePill.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import { adaptSystemOpsEvidence, type LoadState } from './systemEvidence';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();

  function emptyState<T>(): LoadState<T> {
    return { data: null, loading: false, error: null, loaded: false };
  }

  let gpu = $state<LoadState<GpuResponse>>(emptyState());
  let system = $state<LoadState<SystemResponse>>(emptyState());

  const evidence = $derived(adaptSystemOpsEvidence(gpu.data, gpu, system.data, system));

  onMount(() => {
    void loadGpu();
    void loadSystem();
  });

  function message(caught: unknown, fallback: string): string {
    return caught instanceof Error && caught.message ? caught.message : fallback;
  }

  async function loadGpu(): Promise<void> {
    gpu = { data: null, loading: true, error: null, loaded: false };
    try {
      gpu = { data: await api.gpu(), loading: false, error: null, loaded: true };
    } catch (caught) {
      gpu = { data: null, loading: false, error: message(caught, 'GPU telemetry GET failed'), loaded: true };
    }
  }

  async function loadSystem(): Promise<void> {
    system = { data: null, loading: true, error: null, loaded: false };
    try {
      system = { data: await api.system(), loading: false, error: null, loaded: true };
    } catch (caught) {
      system = { data: null, loading: false, error: message(caught, 'system telemetry GET failed'), loaded: true };
    }
  }
</script>

<section class="system-ops" data-v4-system-ops aria-labelledby="v4-system-ops-title">
  <div class="intro">
    <p class="eyebrow">V4 System Ops · GET-only evidence</p>
    <h2 id="v4-system-ops-title">시스템 운영 화면은 출처별 가용성·freshness를 legacy 상세보다 먼저 표시합니다</h2>
    <p>
      GPU, CPU/메모리 텔레메트리를 독립 GET으로 읽고 하나의 endpoint 실패가 다른 출처를 가리지 않습니다.
      프로세스 제어, 서버 시작, 환경변수 수정 등 어떠한 mutation도 수행하지 않습니다.
    </p>
  </div>

  <section class="source-grid" data-v4-system-sources aria-label="per-source availability and freshness">
    {#each evidence.sources as source (source.key)}
      <article data-source={source.key} data-availability={source.availability} data-freshness={source.freshness}>
        <span>{source.label}</span>
        <LifecyclePill state={source.lifecycleState} detail={source.availability} />
        <strong>{source.freshness}</strong>
        <p>{source.detail}</p>
      </article>
    {/each}
  </section>

  <section class="telemetry-grid" aria-label="typed telemetry snapshots">
    <article data-v4-system-gpu-snapshot>
      <span>GPU</span>
      <dl>
        <div><dt>Available</dt><dd>{evidence.gpu.available ? 'true' : 'false'}</dd></div>
        <div><dt>Utilization %</dt><dd>{evidence.gpu.utilizationPercent === null ? 'NOT_RECORDED' : `${evidence.gpu.utilizationPercent}%`}</dd></div>
        <div><dt>Memory used %</dt><dd>{evidence.gpu.memoryUsedPercent === null ? 'NOT_RECORDED' : `${evidence.gpu.memoryUsedPercent}%`}</dd></div>
        <div><dt>Temperature C</dt><dd>{evidence.gpu.temperatureC === null ? 'NOT_RECORDED' : evidence.gpu.temperatureC}</dd></div>
        <div><dt>Generated at</dt><dd>{evidence.gpu.generatedAt}</dd></div>
      </dl>
    </article>
    <article data-v4-system-cpu-memory-snapshot>
      <span>CPU / Memory</span>
      <dl>
        <div><dt>Available</dt><dd>{evidence.cpuMemory.available ? 'true' : 'false'}</dd></div>
        <div><dt>CPU utilization %</dt><dd>{evidence.cpuMemory.cpuUtilizationPercent === null ? 'NOT_RECORDED' : `${evidence.cpuMemory.cpuUtilizationPercent}%`}</dd></div>
        <div><dt>Memory used %</dt><dd>{evidence.cpuMemory.memoryUsedPercent === null ? 'NOT_RECORDED' : `${evidence.cpuMemory.memoryUsedPercent}%`}</dd></div>
        <div><dt>Generated at</dt><dd>{evidence.cpuMemory.generatedAt}</dd></div>
      </dl>
    </article>
  </section>

  <PromotionLocksGrid result={evidence.promotionLocks} compact />

  <EvidenceDisclosure summary="Raw audit · per-source GET payload states" meta="selectors: data-v4-system-raw-audit" open>
    <div class="raw-audit" data-v4-system-raw-audit>
      {#each evidence.sources as source (source.key)}
        {#if source.availability === 'ERROR'}
          <StateBoundary state="error" title={`${source.label} failed`} detail={source.detail} />
        {:else if source.availability === 'NOT_RECORDED'}
          <StateBoundary state="missing" title={`${source.label} missing`} detail="GET completed without recorded payload" />
        {/if}
      {/each}
    </div>
  </EvidenceDisclosure>

  <EvidenceDisclosure summary="Legacy System Health functions · lazy child surface" meta="final disclosure; no duplicate initial storm" open={false} lazy>
    <div class="legacy-child" data-v4-system-legacy-child>
      {#if children}
        {@render children()}
      {:else}
        <p>Legacy System Health child surface not supplied. V4 critical evidence remains GET-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .system-ops {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
  }
  .system-ops > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .source-grid article,
  .telemetry-grid article {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .intro {
    display: grid;
    gap: 8px;
    padding: 18px 20px;
  }

  .eyebrow,
  .source-grid span,
  .telemetry-grid span,
  dt {
    margin: 0;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  p {
    margin-block: 0;
  }

  h2,
  strong {
    color: var(--fg-strong);
    overflow-wrap: anywhere;
  }

  .source-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .source-grid article {
    display: grid;
    gap: 8px;
    padding: 14px;
    background: var(--surface-raised);
    min-width: 0;
  }

  .source-grid article[data-availability='ERROR'],
  .source-grid article[data-availability='NOT_RECORDED'] {
    border-color: var(--danger);
    background: var(--danger-soft);
  }

  .source-grid article[data-freshness='STALE'] {
    border-color: var(--warn);
  }

  .source-grid p,
  .intro p,
  .legacy-child {
    max-width: 60ch;
    color: var(--muted);
    line-height: 1.5;
    overflow-wrap: anywhere;
  }

  .telemetry-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .telemetry-grid article {
    display: grid;
    gap: 10px;
    padding: 16px;
  }

  .telemetry-grid dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
    gap: 10px;
    margin: 0;
  }

  .telemetry-grid dl div {
    display: grid;
    gap: 4px;
    padding: 10px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface-raised);
  }

  dd {
    margin: 0;
    color: var(--fg-strong);
    font: 650 var(--t-body) / 1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  @media (max-width: 760px) {
    .source-grid,
    .telemetry-grid {
      grid-template-columns: 1fr;
    }
    .telemetry-grid dl {
      grid-template-columns: 1fr;
    }
  }
</style>

<script lang="ts">
  import { onDestroy } from 'svelte';
  import { gpuStatus, metricsLatest, systemStatus, trainingStatus } from '$lib/stores';
  import { navigateToTab } from '$lib/routes';

  type WorkspaceDomain = 'kronos' | 'rl' | 'training-system';

  interface RouteButton {
    readonly id: string;
    readonly label: string;
    readonly detail: string;
  }

  interface WorkspaceConfig {
    readonly eyebrow: string;
    readonly title: string;
    readonly description: string;
    readonly routes: readonly RouteButton[];
  }

  interface Props {
    domain: WorkspaceDomain;
    selectedRouteId: string;
  }

  let { domain, selectedRouteId }: Props = $props();

  const WORKSPACES: Record<WorkspaceDomain, WorkspaceConfig> = {
    kronos: {
      eyebrow: 'KRONOS',
      title: 'Kronos Research',
      description:
        'Forecast generation and prediction diagnostics are grouped into one visible V5.1 workspace while each deep-link panel remains route-gated.',
      routes: [
        { id: 'forecast', label: 'Forecast Workbench', detail: 'Forecast evidence' },
        { id: 'stom', label: 'Prediction Diagnostics', detail: 'STOM diagnostics' },
      ],
    },
    rl: {
      eyebrow: 'REINFORCEMENT LEARNING',
      title: 'RL Research & Evidence',
      description:
        'RL evidence, daily close research, and the guide share one V5.1 entry point without merging their underlying panels or evidence contracts.',
      routes: [
        { id: 'rl', label: 'RL Evidence Console', detail: 'Runs and evidence' },
        { id: 'daily-ohlcv', label: 'Daily Close RL', detail: 'Daily close pipeline' },
        { id: 'daily-rl-guide', label: 'RL Guide', detail: 'Workflow guide' },
      ],
    },
    'training-system': {
      eyebrow: 'OPERATIONS',
      title: 'Training & System',
      description:
        'Live training progress and host health are grouped for observation only; runs/reports and artifacts remain separate sidebar routes.',
      routes: [
        { id: 'live-training', label: 'Live Training', detail: 'Fine-tuning monitor' },
        { id: 'system-health', label: 'System Health', detail: 'GPU and host telemetry' },
      ],
    },
  };

  let config = $derived(WORKSPACES[domain]);

  let training = $state<any>(null);
  const unsubscribeTrainingStatus = trainingStatus.subscribe((value) => (training = value));

  let gpu = $state<any>(null);
  const unsubscribeGpuStatus = gpuStatus.subscribe((value) => (gpu = value));

  let system = $state<any>(null);
  const unsubscribeSystemStatus = systemStatus.subscribe((value) => (system = value));

  let metrics = $state<any>({});
  const unsubscribeMetricsLatest = metricsLatest.subscribe((value) => (metrics = value));

  let runLabel = $derived(metrics?.runName ?? training?.run_name ?? 'No active run reported');
  let trainingLabel = $derived(training?.readiness?.label ?? training?.status ?? 'Training status unavailable');
  let stageLabel = $derived.by(() => {
    const stage = training?.latest_stage;
    if (!stage) return 'Stage not reported';
    const name = stage.train_stage ?? 'stage';
    const percent = pct(stage.overall_percent, 1);
    return percent === '—' ? name : `${name} · ${percent}`;
  });
  let gpuLabel = $derived.by(() => {
    if (gpu?.available === false) return 'GPU status unavailable';
    const firstGpu = gpu?.gpus?.[0];
    if (!firstGpu) return 'GPU source pending';
    return `${firstGpu.name ?? 'GPU'} · util ${pct(firstGpu.utilization_gpu_percent)} · VRAM ${pct(firstGpu.memory_used_percent)}`;
  });
  let systemLabel = $derived.by(() => {
    if (system?.available === false) return 'System status unavailable';
    if (!system) return 'System source pending';
    return `CPU ${pct(system?.cpu?.utilization_percent)} · RAM ${pct(system?.memory?.used_percent)}`;
  });

  onDestroy(() => {
    unsubscribeTrainingStatus();
    unsubscribeGpuStatus();
    unsubscribeSystemStatus();
    unsubscribeMetricsLatest();
  });

  function pct(value: number | null | undefined, digits = 0): string {
    if (value == null) return '—';
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${numeric.toFixed(digits)}%` : '—';
  }

  function openRoute(routeId: string): void {
    navigateToTab(routeId);
  }
</script>

<section class="v51-workspace-nav" data-v51-workspace-nav={domain} aria-labelledby="v51-workspace-title">
  <div class="workspace-copy">
    <p class="workspace-eyebrow">{config.eyebrow}</p>
    <h1 id="v51-workspace-title">{config.title}</h1>
    <p class="workspace-description">{config.description}</p>
    <p class="workspace-boundary">
      Kronos fine-tuning and RL evidence remain separate lanes. This V5.1 workspace is read-only research and
      operations context; it does not imply live trading, broker connectivity, or order execution.
    </p>
  </div>

  <div class="route-segments" role="group" aria-label={`${config.title} route selector`}>
    {#each config.routes as route}
      <button
        type="button"
        class="route-segment"
        class:active={route.id === selectedRouteId}
        data-route-id={route.id}
        data-active={route.id === selectedRouteId ? 'true' : 'false'}
        aria-pressed={route.id === selectedRouteId}
        onclick={() => openRoute(route.id)}
      >
        <span class="route-label">{route.label}</span>
        <span class="route-detail">{route.detail}</span>
      </button>
    {/each}
  </div>

  {#if domain === 'training-system'}
    <section class="live-summary" aria-label="Training and system read-only summary">
      <article>
        <span>Training</span>
        <strong>{trainingLabel}</strong>
        <p>{runLabel}</p>
      </article>
      <article>
        <span>Stage</span>
        <strong>{stageLabel}</strong>
        <p>Fine-tuning lane only</p>
      </article>
      <article>
        <span>GPU</span>
        <strong>{gpuLabel}</strong>
        <p>Read-only telemetry</p>
      </article>
      <article>
        <span>Host</span>
        <strong>{systemLabel}</strong>
        <p>Read-only telemetry</p>
      </article>
    </section>
  {/if}
</section>

<style>
  .v51-workspace-nav {
    display: grid;
    gap: 16px;
    padding: 22px;
    border: 1px solid var(--border-faint);
    border-radius: 24px;
    background:
      radial-gradient(circle at top left, color-mix(in oklab, var(--accent) 12%, transparent), transparent 38%),
      color-mix(in oklab, var(--surface) 94%, transparent);
    box-shadow: var(--shadow-sm);
    color: var(--fg);
  }

  .workspace-copy {
    display: grid;
    gap: 8px;
  }

  .workspace-eyebrow,
  .live-summary span {
    margin: 0;
    color: var(--accent-strong);
    font: 760 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h1,
  p {
    margin: 0;
  }

  h1 {
    color: var(--fg-strong);
    font: 800 clamp(30px, 4.6vw, 54px) / 0.98 var(--font-display);
    letter-spacing: -0.06em;
  }

  .workspace-description,
  .workspace-boundary,
  .live-summary p,
  .route-detail {
    color: var(--muted);
  }

  .workspace-description {
    max-width: 88ch;
    font-size: 15px;
    line-height: 1.55;
  }

  .workspace-boundary {
    max-width: 92ch;
    font-size: 13px;
    line-height: 1.5;
  }

  .route-segments {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 6px;
    border: 1px solid var(--border-faint);
    border-radius: 18px;
    background: var(--surface-sunken);
  }

  .route-segment {
    display: grid;
    gap: 4px;
    min-width: min(100%, 180px);
    flex: 1 1 0;
    padding: 12px 14px;
    border: 1px solid transparent;
    border-radius: 14px;
    background: transparent;
    color: var(--fg);
    text-align: left;
    cursor: pointer;
  }

  .route-segment:hover,
  .route-segment.active {
    border-color: var(--border);
    background: color-mix(in oklab, var(--surface) 90%, var(--accent) 10%);
  }

  .route-label {
    color: var(--fg-strong);
    font: 760 14px/1.2 var(--font-display);
  }

  .route-detail {
    font-size: 12px;
    line-height: 1.35;
  }

  .live-summary {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }

  .live-summary article {
    display: grid;
    gap: 6px;
    min-width: 0;
    padding: 12px;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    background: color-mix(in oklab, var(--surface-sunken) 88%, transparent);
  }

  .live-summary strong,
  .live-summary p {
    min-width: 0;
    overflow-wrap: anywhere;
    white-space: normal;
  }

  .live-summary strong {
    color: var(--fg-strong);
    font: 740 13px/1.25 var(--font-display);
  }

  .live-summary p {
    font-size: 12px;
    line-height: 1.35;
  }

  @media (max-width: 1100px) {
    .live-summary {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .v51-workspace-nav {
      padding: 16px;
      border-radius: 20px;
    }

    .route-segment,
    .live-summary {
      grid-template-columns: 1fr;
    }
  }
</style>

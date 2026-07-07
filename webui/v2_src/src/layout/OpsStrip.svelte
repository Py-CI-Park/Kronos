<script lang="ts">
  // Persistent ambient OPS STRIP — compute + data-freshness at a glance.
  // Honest-state / fail-closed: a missing source renders an EXPLICIT empty
  // state ("—", "no data", "stale") — never a fabricated green/normal value.
  // Theming is handled by core.css custom properties under [data-theme];
  // no JS theme subscription is required.
  import { onMount, onDestroy } from 'svelte';
  import { gpuStatus, systemStatus, refreshSeconds, lastUpdatedAt } from '$lib/stores';

  // Same subscribe + $state pattern SystemHealthTab uses.
  let gpu = $state<any>(null);
  gpuStatus.subscribe((v) => (gpu = v));

  let system = $state<any>(null);
  systemStatus.subscribe((v) => (system = v));

  let sec = $state(5);
  refreshSeconds.subscribe((v) => (sec = v));

  // `lastUpdatedAt` is a localized display string (not a timestamp), so we
  // anchor a real epoch every time it changes to derive "Xs ago" honestly.
  let lastTs = $state<number | null>(null);
  lastUpdatedAt.subscribe((v) => {
    if (v && v !== '-') lastTs = Date.now();
  });

  // 1s ticker keeps freshness + stale detection live between polls.
  let nowTick = $state(Date.now());
  let timer: number | undefined;
  onMount(() => {
    timer = window.setInterval(() => (nowTick = Date.now()), 1000);
  });
  onDestroy(() => {
    if (timer != null) clearInterval(timer);
  });

  // ── Compute readouts — null-safe, no fabrication ──
  let gpuUtil = $derived(gpu?.gpus?.[0]?.utilization_gpu_percent);
  let ramPct = $derived(system?.memory?.used_percent);

  // Data freshness derived from the lastUpdatedAt anchor.
  let ageSec = $derived(
    lastTs == null ? null : Math.max(0, Math.round((nowTick - lastTs) / 1000)),
  );
  // Stale once the last screen refresh is older than 3× the poll interval.
  let staleThreshold = $derived(Math.max(3, sec * 3));
  let freshness = $derived.by(() => {
    if (ageSec == null) return { text: 'no data', tone: 'warn' as const, live: false };
    if (ageSec > staleThreshold) return { text: 'stale', tone: 'warn' as const, live: false };
    return { text: `${ageSec}s ago`, tone: 'ok' as const, live: true };
  });

  function pct(v: number | null | undefined): string {
    return v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(0);
  }
</script>

<div class="ops-strip" data-ops-strip aria-label="시스템 운영 상태 요약">
  <div class="ops-row">
    <span class="ops-lead" title="라이브 상태">
      <span class="ops-pulse" class:live={freshness.live}></span>
      <span class="ops-lead-text">OPS</span>
    </span>

    <span class="ops-cell" title="GPU 활용률 (/api/training/gpu)">
      <span class="ops-key">GPU</span>
      <span class="ops-val tnum">{pct(gpuUtil)}<span class="ops-unit">%</span></span>
    </span>

    <span class="ops-cell" title="RAM 사용률 (/api/training/system)">
      <span class="ops-key">RAM</span>
      <span class="ops-val tnum">{pct(ramPct)}<span class="ops-unit">%</span></span>
    </span>

    <span class="ops-cell" title="폴링 간격">
      <span class="ops-key">POLL</span>
      <span class="ops-val tnum">{sec}<span class="ops-unit">s</span></span>
    </span>

    <span class="ops-cell" title="마지막 화면 갱신 이후 경과 (데이터 신선도)">
      <span class="ops-key">DATA</span>
      <span class="ops-val tnum" data-tone={freshness.tone}>{freshness.text}</span>
    </span>

    <span class="ops-chip" title="연구 전용 — 실거래·브로커·주문 없음">RESEARCH_ONLY</span>
  </div>
</div>

<style>
  .ops-strip {
    border-bottom: 1px solid var(--border);
    background: color-mix(in oklab, var(--surface-sunken) 85%, transparent);
    backdrop-filter: saturate(1.1) blur(6px);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .ops-strip::-webkit-scrollbar {
    display: none;
  }
  .ops-row {
    display: flex;
    align-items: center;
    gap: 18px;
    max-width: var(--content-max);
    margin: 0 auto;
    padding: 7px 28px;
    width: max-content;
    min-width: 100%;
    white-space: nowrap;
  }
  .ops-lead {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    flex: 0 0 auto;
  }
  .ops-lead-text {
    font: 600 var(--t-eyebrow)/1 var(--font-display);
    letter-spacing: 0.14em;
    color: var(--dim);
  }
  .ops-pulse {
    width: 7px;
    height: 7px;
    border-radius: var(--r-pill);
    background: var(--warn);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--warn) 22%, transparent);
    flex: 0 0 auto;
  }
  .ops-pulse.live {
    background: var(--success);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--success) 22%, transparent);
    animation: ops-pulse 2s var(--ease-out) infinite;
  }
  .ops-cell {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    flex: 0 0 auto;
  }
  .ops-cell + .ops-cell,
  .ops-chip {
    position: relative;
  }
  .ops-cell + .ops-cell::before {
    content: '';
    position: absolute;
    left: -9px;
    top: 50%;
    width: 1px;
    height: 12px;
    transform: translateY(-50%);
    background: var(--border);
  }
  .ops-key {
    font: 600 var(--t-eyebrow)/1 var(--font-display);
    letter-spacing: 0.08em;
    color: var(--muted);
    text-transform: uppercase;
  }
  .ops-val {
    font-family: var(--font-mono);
    font-size: var(--t-caption);
    font-weight: 600;
    color: var(--fg-strong);
    font-variant-numeric: tabular-nums;
  }
  .ops-unit {
    color: var(--dim);
    font-size: 10px;
    margin-left: 1px;
  }
  .ops-val[data-tone='ok'] {
    color: var(--success);
  }
  .ops-val[data-tone='warn'] {
    color: var(--warn);
  }
  .ops-chip {
    flex: 0 0 auto;
    margin-left: auto;
    padding: 2px 10px;
    border-radius: var(--r-pill);
    border: 1px solid var(--accent-tint);
    background: var(--accent-soft);
    color: var(--accent-strong);
    font: 600 10px/1.6 var(--font-mono);
    letter-spacing: 0.06em;
    font-variant-numeric: tabular-nums;
  }
  @keyframes ops-pulse {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.5;
      transform: scale(0.72);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ops-pulse.live {
      animation: none;
    }
  }
  @media (max-width: 900px) {
    .ops-row {
      padding: 7px 16px;
      gap: 14px;
    }
    .ops-cell + .ops-cell::before {
      left: -7px;
    }
  }
</style>

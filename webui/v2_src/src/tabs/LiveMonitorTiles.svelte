<script lang="ts">
  // G3 — report-style live-monitor tile row (LOSS / GPU / RAM / RL EQUITY).
  // Each tile: label + big tabular-nums value + compact sparkline.
  // Fail-closed / honest-state: a null/missing source or a stale poll renders an
  // explicit "확인 중" state (never a fabricated normal-looking value). Staleness
  // mirrors OpsStrip's freshness rule (last screen refresh older than 3× the poll
  // interval). RL EQUITY has NO global signal — equity only exists inside
  // RLTradingTab when a run is selected — so its tile is an honest not-available
  // state rather than a fabricated number. RESEARCH_ONLY — no live/broker/order.
  import { onMount, onDestroy } from 'svelte';
  import {
    lossPoints,
    gpuStatus,
    gpuRing,
    systemStatus,
    systemRing,
    refreshSeconds,
    lastUpdatedAt,
  } from '$lib/stores';
  import MiniSparkline from '../charts/MiniSparkline.svelte';

  // Same subscribe + $state pattern SystemHealthTab / OpsStrip use.
  let pts = $state<{ step: number; loss: number }[]>([]);
  lossPoints.subscribe((v) => (pts = v));

  let gpu = $state<any>(null);
  gpuStatus.subscribe((v) => (gpu = v));

  let gRing = $state<any[]>([]);
  gpuRing.subscribe((v) => (gRing = v));

  let system = $state<any>(null);
  systemStatus.subscribe((v) => (system = v));

  let sRing = $state<any[]>([]);
  systemRing.subscribe((v) => (sRing = v));

  let sec = $state(5);
  refreshSeconds.subscribe((v) => (sec = v));

  // ── Freshness anchor — identical idiom to OpsStrip ──
  // lastUpdatedAt is a display string, so anchor a real epoch when it changes.
  let lastTs = $state<number | null>(null);
  lastUpdatedAt.subscribe((v) => {
    if (v && v !== '-') lastTs = Date.now();
  });
  let nowTick = $state(Date.now());
  let timer: number | undefined;
  onMount(() => {
    timer = window.setInterval(() => (nowTick = Date.now()), 1000);
  });
  onDestroy(() => {
    if (timer != null) clearInterval(timer);
  });

  let ageSec = $derived(
    lastTs == null ? null : Math.max(0, Math.round((nowTick - lastTs) / 1000)),
  );
  // Stale once the last screen refresh is older than 3× the poll interval.
  let staleThreshold = $derived(Math.max(3, sec * 3));
  let fresh = $derived(ageSec != null && ageSec <= staleThreshold);

  type Status = 'live' | 'stale' | 'nodata';

  function statusOf(value: number | null | undefined): Status {
    if (value == null || Number.isNaN(Number(value))) return 'nodata';
    return fresh ? 'live' : 'stale';
  }

  function badgeText(s: Status): string {
    if (s === 'live') return 'LIVE';
    if (s === 'stale') return 'STALE';
    return '데이터 없음';
  }

  function badgeTone(s: Status): 'ok' | 'warn' {
    return s === 'live' ? 'ok' : 'warn';
  }

  function fmtVal(value: number | null | undefined, digits: number, s: Status): string {
    return s === 'live' && value != null ? Number(value).toFixed(digits) : '확인 중';
  }

  function finiteNums(arr: (number | null | undefined)[]): number[] {
    return arr.filter((v): v is number => v != null && Number.isFinite(Number(v))).map(Number);
  }

  // ── LOSS ── source: lossPoints store (latest point)
  let lossVal = $derived(pts.length ? pts[pts.length - 1].loss : null);
  let lossStatus = $derived(statusOf(lossVal));
  let lossSeries = $derived.by(() => finiteNums(pts.slice(-60).map((p) => p.loss)));

  // ── GPU ── source: gpuStatus.gpus[0].utilization_gpu_percent
  let gpuVal = $derived(gpu?.gpus?.[0]?.utilization_gpu_percent ?? null);
  let gpuStat = $derived(statusOf(gpuVal));
  let gpuSeries = $derived.by(() => finiteNums(gRing.slice(-60).map((p) => p?.util)));

  // ── RAM ── source: systemStatus.memory.used_percent
  let ramVal = $derived(system?.memory?.used_percent ?? null);
  let ramStat = $derived(statusOf(ramVal));
  let ramSeries = $derived.by(() => finiteNums(sRing.slice(-60).map((p) => p?.ram)));
</script>

<section class="live-monitor-tiles" data-live-monitor-tiles aria-label="라이브 모니터 타일 (손실·GPU·RAM·RL 에쿼티)">
  <!-- LOSS -->
  <div class="lm-tile" data-tile="loss" data-status={lossStatus}>
    <div class="lm-head">
      <span class="lm-label">LOSS</span>
      <span class="lm-badge" data-tone={badgeTone(lossStatus)}>{badgeText(lossStatus)}</span>
    </div>
    <div class="lm-value tnum" data-status={lossStatus}>
      {fmtVal(lossVal, 4, lossStatus)}
    </div>
    <div class="lm-spark">
      <MiniSparkline values={lossStatus === 'live' ? lossSeries : []} colorVar="--accent" height="40px" />
    </div>
    <div class="lm-foot">학습 손실 · lossPoints</div>
  </div>

  <!-- GPU -->
  <div class="lm-tile" data-tile="gpu" data-status={gpuStat}>
    <div class="lm-head">
      <span class="lm-label">GPU</span>
      <span class="lm-badge" data-tone={badgeTone(gpuStat)}>{badgeText(gpuStat)}</span>
    </div>
    <div class="lm-value tnum" data-status={gpuStat}>
      {fmtVal(gpuVal, 1, gpuStat)}{#if gpuStat === 'live'}<span class="lm-unit">%</span>{/if}
    </div>
    <div class="lm-spark">
      <MiniSparkline values={gpuStat === 'live' ? gpuSeries : []} colorVar="--c-3" height="40px" />
    </div>
    <div class="lm-foot">GPU 활용률 · /api/training/gpu</div>
  </div>

  <!-- RAM -->
  <div class="lm-tile" data-tile="ram" data-status={ramStat}>
    <div class="lm-head">
      <span class="lm-label">RAM</span>
      <span class="lm-badge" data-tone={badgeTone(ramStat)}>{badgeText(ramStat)}</span>
    </div>
    <div class="lm-value tnum" data-status={ramStat}>
      {fmtVal(ramVal, 1, ramStat)}{#if ramStat === 'live'}<span class="lm-unit">%</span>{/if}
    </div>
    <div class="lm-spark">
      <MiniSparkline values={ramStat === 'live' ? ramSeries : []} colorVar="--success" height="40px" />
    </div>
    <div class="lm-foot">메모리 사용률 · /api/training/system</div>
  </div>

  <!-- RL EQUITY — no global signal; honest not-available -->
  <div class="lm-tile" data-tile="rl-equity" data-status="unavailable">
    <div class="lm-head">
      <span class="lm-label">RL EQUITY</span>
      <span class="lm-badge" data-tone="warn">선택된 run 없음</span>
    </div>
    <div class="lm-value tnum" data-status="unavailable">확인 중</div>
    <div class="lm-spark">
      <MiniSparkline values={[]} colorVar="--c-2" height="40px" />
    </div>
    <div class="lm-foot">RL 탭에서 run 선택 시 라이브 에쿼티 제공 · 전역 신호 없음</div>
  </div>
</section>

<style>
  .live-monitor-tiles {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
  }
  .lm-tile {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
    padding: 14px 16px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface-raised);
    overflow: hidden;
  }
  .lm-tile[data-status='stale'],
  .lm-tile[data-status='nodata'],
  .lm-tile[data-status='unavailable'] {
    border-color: color-mix(in oklab, var(--warn) 26%, var(--border-faint));
    background: color-mix(in oklab, var(--surface-raised) 82%, var(--warn-soft));
  }
  .lm-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .lm-label {
    font: 700 11px/1 var(--font-mono);
    letter-spacing: 0.1em;
    color: var(--muted);
    text-transform: uppercase;
  }
  .lm-badge {
    padding: 2px 8px;
    border-radius: var(--r-pill);
    font: 700 9px/1.5 var(--font-mono);
    letter-spacing: 0.06em;
    color: var(--muted);
    background: var(--surface-sunken);
    white-space: nowrap;
  }
  .lm-badge[data-tone='ok'] {
    color: var(--success);
    background: var(--success-soft);
  }
  .lm-badge[data-tone='warn'] {
    color: var(--warn);
    background: var(--warn-soft);
  }
  .lm-value {
    color: var(--fg-strong);
    font: 800 28px/1.05 var(--font-display);
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .lm-value[data-status='stale'],
  .lm-value[data-status='nodata'],
  .lm-value[data-status='unavailable'] {
    color: var(--muted);
    font-size: 20px;
    font-weight: 700;
  }
  .lm-unit {
    margin-left: 3px;
    color: var(--dim);
    font-size: 13px;
    font-weight: 600;
  }
  .lm-spark {
    width: 100%;
    min-width: 0;
  }
  .lm-foot {
    color: var(--muted);
    font: 600 11px/1.4 var(--font-display);
    overflow-wrap: anywhere;
  }

  @media (max-width: 900px) {
    .live-monitor-tiles {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 560px) {
    .live-monitor-tiles {
      grid-template-columns: 1fr;
    }
  }
</style>

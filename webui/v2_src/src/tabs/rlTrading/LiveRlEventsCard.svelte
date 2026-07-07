<script lang="ts">
  // P7 — REALTIME RL performance card.
  // 이미 존재하지만 연결되지 않았던 rl_events tail 스트림을 라이브 reward/equity 뷰로 배선한다.
  // 백엔드 변경 없음: rlApi.rlEvents(run, limit) → GET /api/rl/runs/<run>/events (bounded tail snapshot).
  // RESEARCH_ONLY — 실행/브로커/주문/수익/GO 근거가 아니다.
  import { onDestroy } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { rlApi, type RlTableRow } from '$lib/rlApi';
  import { errorMessage, num, pct, rowNumber, text } from '$lib/rlRows';
  import { tooltipLines, tooltipText, tooltipTitle } from '$lib/safeHtml';
  import { theme } from '$lib/stores';

  interface Props {
    // 현재 선택된 run 이름 (RLTradingTab 의 selectedName 을 그대로 전달받는다).
    readonly run: string;
    // 폴링 주기(초). 앱 관례에 맞춰 3~5s 범위, 기본 4s.
    readonly pollSeconds?: number;
  }
  let { run, pollSeconds = 4 }: Props = $props();

  let events = $state<readonly RlTableRow[]>([]);
  let truncated = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let lastUpdated = $state<string | null>(null);
  let polling = $state(false);

  // F2: 색상은 하드코딩하지 않고 canonical CSS 변수에서 render time 에 읽는다.
  // theme store 를 구독해 [data-theme] 플립 시 차트 옵션을 재계산한다.
  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));

  let timer: number | null = null;
  let activeRun = '';

  const latest = $derived(events.length ? events[events.length - 1] : null);
  const latestStep = $derived(latest ? num(rowNumber(latest, 'global_step'), 0) : '—');
  const latestReward = $derived(latest ? pct(rowNumber(latest, 'reward') * 100, 4) : '—');
  const latestEquity = $derived(latest ? num(rowNumber(latest, 'equity'), 2) : '—');
  const latestPhase = $derived(latest ? text(latest, 'phase', 'research') : '—');
  const latestAlgorithm = $derived(latest ? text(latest, 'algorithm', 'research') : '—');

  async function refresh(): Promise<void> {
    if (!run) {
      events = [];
      truncated = false;
      return;
    }
    loading = true;
    try {
      const payload = await rlApi.rlEvents(run, 240);
      events = payload?.rows ?? [];
      truncated = Boolean(payload?.truncated);
      error = null;
      lastUpdated = new Date().toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul' });
    } catch (caught) {
      error = errorMessage(caught, `${run} live events load failed`);
      events = [];
      truncated = false;
    } finally {
      loading = false;
    }
  }

  function stopTimer(): void {
    if (timer != null) {
      clearInterval(timer);
      timer = null;
    }
    polling = false;
  }

  function startTimer(): void {
    stopTimer();
    if (!run || typeof window === 'undefined') return;
    polling = true;
    void refresh();
    timer = window.setInterval(() => void refresh(), Math.max(3, pollSeconds) * 1000);
  }

  // run 이 바뀌면 폴링을 재시작한다 (setInterval, onDestroy 에서 정리).
  $effect(() => {
    if (run === activeRun) return;
    activeRun = run;
    startTimer();
  });

  onDestroy(() => {
    stopTimer();
    unsubscribeTheme();
  });

  function paramIndex(params: unknown): number {
    if (Array.isArray(params)) {
      const first = params[0];
      if (first && typeof first === 'object' && 'dataIndex' in first) {
        return Number((first as { dataIndex?: number }).dataIndex ?? 0);
      }
    }
    return 0;
  }

  const liveChartOption = $derived.by(() => {
    void currentTheme;
    if (!events.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#38bdf8';
    const success = cs.getPropertyValue('--success').trim() || '#22c55e';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const dim = cs.getPropertyValue('--dim').trim() || '#64748b';
    const rows = events;
    return {
      backgroundColor: 'transparent',
      grid: { left: 62, right: 62, top: 42, bottom: 40 },
      legend: { top: 0, textStyle: { color: dim } },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const row = rows[paramIndex(params)];
          return tooltipLines([
            tooltipTitle(`step ${num(rowNumber(row, 'global_step'), 0)}`),
            tooltipText(`reward evidence ${pct(rowNumber(row, 'reward') * 100, 4)}`),
            tooltipText(`equity evidence ${num(rowNumber(row, 'equity'), 2)}`),
            tooltipText(`phase ${text(row, 'phase', 'research')}`),
          ]);
        },
      },
      xAxis: {
        type: 'category',
        data: rows.map((row, idx) => String(rowNumber(row, 'global_step', idx + 1))),
        axisLabel: { color: dim },
      },
      yAxis: [
        { type: 'value', name: 'reward %', position: 'left', axisLabel: { formatter: '{value}%', color: dim }, splitLine: { lineStyle: { color: grid } } },
        { type: 'value', name: 'equity', position: 'right', axisLabel: { color: dim }, splitLine: { show: false } },
      ],
      series: [
        { name: 'reward over step', type: 'line', smooth: 0.2, symbol: 'none', yAxisIndex: 0, data: rows.map((row) => rowNumber(row, 'reward') * 100), lineStyle: { color: accent, width: 2.2 }, itemStyle: { color: accent } },
        { name: 'equity over step', type: 'line', smooth: 0.2, symbol: 'none', yAxisIndex: 1, data: rows.map((row) => rowNumber(row, 'equity')), lineStyle: { color: success, width: 2.2 }, itemStyle: { color: success } },
      ],
    };
  });
</script>

<section class="card live-rl-events-card" data-rl-live-events-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">REALTIME RL EVENTS · RESEARCH_ONLY</div>
      <div class="card-title">실시간 리워드·에쿼티 라이브 tail</div>
    </div>
    <span class="pill {polling && events.length ? 'accent' : 'warn'}">
      {#if polling && events.length}
        <span class="live-dot" aria-hidden="true"></span>LIVE
      {:else}
        <span class="dot"></span>IDLE
      {/if}
    </span>
  </div>

  {#if events.length}
    <div class="live-readouts">
      <div><span>Step</span><b class="mono">{latestStep}</b></div>
      <div><span>Reward</span><b class="mono">{latestReward}</b></div>
      <div><span>Equity</span><b class="mono">{latestEquity}</b></div>
      <div><span>Phase</span><b class="mono">{latestPhase}</b></div>
      <div><span>Algorithm</span><b class="mono">{latestAlgorithm}</b></div>
    </div>
    <div class="live-chart" data-rl-live-events-chart>
      <EChartsRenderer option={liveChartOption} height="300px" />
    </div>
    {#if truncated}
      <p class="text-caption tail-note">bounded tail window · 최근 이벤트만 표시하며 전체 에피소드가 아닙니다.</p>
    {/if}
  {:else}
    <div class="live-empty">{loading ? '이벤트 로딩 중 · 연구 전용' : '이벤트 없음 · 연구 전용'}</div>
  {/if}

  {#if error}
    <p class="text-caption tail-note">{error}</p>
  {/if}

  <p class="text-caption safety-note">
    RESEARCH_ONLY · {run || '선택된 run 없음'} · {lastUpdated ? `updated ${lastUpdated}` : 'polling…'} · NO live / broker / order / profit / GO. 이 라이브 tail은 학습 이벤트 로그의 bounded snapshot이며 실행·수익 근거가 아닙니다.
  </p>
  <!-- TODO(P7 overlay): 2번째 run equity 오버레이 셀렉터는 additive follow-up. live-tail diff 를 최소로 유지하려고 single-run 으로 출고. -->
</section>

<style>
  .live-rl-events-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
  }
  .live-readouts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
  }
  .live-readouts div {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 10px 12px;
    background: var(--card-grad);
  }
  .live-readouts span {
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 4px;
  }
  .mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum', 'zero';
    color: var(--fg);
  }
  .live-chart {
    width: 100%;
    min-width: 0;
    overflow-x: auto;
  }
  .live-empty {
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    padding: 28px 12px;
    text-align: center;
    color: var(--muted);
    background: var(--surface);
  }
  .tail-note {
    color: var(--warn);
    margin: 0;
  }
  .safety-note {
    margin: 0;
  }
  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 0 var(--accent);
    animation: live-pulse 1.4s ease-out infinite;
  }
  @keyframes live-pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 55%, transparent); }
    70% { box-shadow: 0 0 0 6px color-mix(in oklab, var(--accent) 0%, transparent); }
    100% { box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 0%, transparent); }
  }
  @media (prefers-reduced-motion: reduce) {
    .live-dot { animation: none; }
  }
</style>

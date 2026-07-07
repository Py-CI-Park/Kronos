<script lang="ts">
  // P7 — REALTIME RL performance card.
  // 이미 존재하지만 연결되지 않았던 rl_events tail 스트림을 라이브 reward/equity 뷰로 배선한다.
  // 백엔드 변경 없음: rlApi.rlEvents(run, limit) → GET /api/rl/runs/<run>/events (bounded tail snapshot).
  // RESEARCH_ONLY — 실행/브로커/주문/수익/GO 근거가 아니다.
  //
  // G4 — compareRuns 오버레이(다중 run equity 비교)와 G5 — rollout replay scrubber(이미
  // 메모리에 있는 bounded tail 위의 프레임 윈도우)를 additive 로 추가한다. 백엔드 변경 없음.
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
    // G4 — primary run 위에 equity 를 겹쳐 그릴 추가 run 이름들(비교/오버레이).
    // 없으면 single-run 경로가 이전과 정확히 동일하게 렌더된다.
    readonly compareRuns?: readonly string[];
  }
  let { run, pollSeconds = 4, compareRuns = [] }: Props = $props();

  let events = $state<readonly RlTableRow[]>([]);
  let truncated = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let lastUpdated = $state<string | null>(null);
  let polling = $state(false);
  // G4 — compareRuns 각각의 tail rows (primary 와 동일한 폴링 사이클에서 갱신).
  let compareSeries = $state<readonly { name: string; rows: readonly RlTableRow[] }[]>([]);
  // G5 — replay scrubber. null 이면 라이브 head(전체 프레임)를 따라간다.
  let frameOverride = $state<number | null>(null);

  // F2: 색상은 하드코딩하지 않고 canonical CSS 변수에서 render time 에 읽는다.
  // theme store 를 구독해 [data-theme] 플립 시 차트 옵션을 재계산한다.
  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));

  let timer: number | null = null;
  let activeRun = '';
  let activeCompareKey = '';

  // primary 와 겹치지 않는 유효한 오버레이 run 이름만 남긴다.
  const overlayNames = $derived(compareRuns.filter((name) => name !== '' && name !== run));
  const isOverlay = $derived(overlayNames.length > 0);

  // G5 — 프레임 윈도우. frameOverride 가 null 이면 전체(라이브 head)를 본다.
  const totalFrames = $derived(events.length);
  const frame = $derived(
    totalFrames === 0
      ? 0
      : frameOverride == null
        ? totalFrames
        : Math.min(Math.max(1, frameOverride), totalFrames)
  );
  const visibleEvents = $derived(events.slice(0, frame));
  const isLiveFrame = $derived(frameOverride == null || frame >= totalFrames);

  const latest = $derived(visibleEvents.length ? visibleEvents[visibleEvents.length - 1] : null);
  const latestStep = $derived(latest ? num(rowNumber(latest, 'global_step'), 0) : '—');
  const latestReward = $derived(latest ? pct(rowNumber(latest, 'reward') * 100, 4) : '—');
  const latestEquity = $derived(latest ? num(rowNumber(latest, 'equity'), 2) : '—');
  const latestPhase = $derived(latest ? text(latest, 'phase', 'research') : '—');
  const latestAlgorithm = $derived(latest ? text(latest, 'algorithm', 'research') : '—');

  async function refresh(): Promise<void> {
    if (!run) {
      events = [];
      truncated = false;
      compareSeries = [];
      return;
    }
    loading = true;
    try {
      const extras = compareRuns.filter((name) => name !== '' && name !== run);
      const payloads = await Promise.all([
        rlApi.rlEvents(run, 240),
        ...extras.map((name) => rlApi.rlEvents(name, 240)),
      ]);
      const primary = payloads[0];
      events = primary?.rows ?? [];
      truncated = Boolean(primary?.truncated);
      compareSeries = extras.map((name, idx) => ({ name, rows: payloads[idx + 1]?.rows ?? [] }));
      error = null;
      lastUpdated = new Date().toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul' });
    } catch (caught) {
      error = errorMessage(caught, `${run} live events load failed`);
      events = [];
      truncated = false;
      compareSeries = [];
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

  // G4 — compareRuns 가 바뀌면 다음 폴링을 기다리지 않고 즉시 tail 을 다시 가져온다.
  $effect(() => {
    const key = compareRuns.join('|');
    if (key === activeCompareKey) return;
    activeCompareKey = key;
    if (activeRun) void refresh();
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
    if (!visibleEvents.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#38bdf8';
    const success = cs.getPropertyValue('--success').trim() || '#22c55e';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const dim = cs.getPropertyValue('--dim').trim() || '#64748b';

    // G4 — 오버레이 모드: run 별 equity 를 한 차트에 겹쳐 legend + theme-distinct 색으로 그린다.
    if (isOverlay) {
      const palette = ['--accent', '--warn', '--info', '--success', '--danger']
        .map((token) => cs.getPropertyValue(token).trim())
        .filter((color) => color !== '');
      const colorAt = (idx: number): string => (palette.length ? palette[idx % palette.length] : accent);
      const primaryRows = visibleEvents;
      const seriesDefs = [
        { name: run, rows: primaryRows },
        ...overlayNames.map((name) => ({
          name,
          rows: (compareSeries.find((entry) => entry.name === name)?.rows ?? []).slice(0, frame),
        })),
      ];
      return {
        backgroundColor: 'transparent',
        grid: { left: 62, right: 24, top: 42, bottom: 40 },
        legend: { top: 0, textStyle: { color: dim } },
        tooltip: {
          trigger: 'axis',
          formatter: (params: unknown) => {
            const list = Array.isArray(params) ? params : [params];
            const idx = paramIndex(params);
            const stepRow = primaryRows[idx];
            const lines = [
              tooltipTitle(`step ${stepRow ? num(rowNumber(stepRow, 'global_step'), 0) : idx + 1}`),
            ];
            for (const item of list) {
              if (item && typeof item === 'object') {
                const seriesName =
                  'seriesName' in item ? String((item as { seriesName?: unknown }).seriesName ?? '') : '';
                const value = 'value' in item ? (item as { value?: unknown }).value : null;
                lines.push(tooltipText(`${seriesName} equity ${num(value, 2)}`));
              }
            }
            return tooltipLines(lines);
          },
        },
        xAxis: {
          type: 'category',
          data: primaryRows.map((row, idx) => String(rowNumber(row, 'global_step', idx + 1))),
          axisLabel: { color: dim },
        },
        yAxis: {
          type: 'value',
          name: 'equity',
          axisLabel: { color: dim },
          splitLine: { lineStyle: { color: grid } },
        },
        series: seriesDefs.map((def, idx) => ({
          name: def.name,
          type: 'line',
          smooth: 0.2,
          symbol: 'none',
          data: def.rows.map((row) => rowNumber(row, 'equity')),
          lineStyle: { color: colorAt(idx), width: 2.2 },
          itemStyle: { color: colorAt(idx) },
        })),
      };
    }

    // single-run 경로 — compareRuns 가 없으면 이전과 정확히 동일하게 렌더한다.
    const rows = visibleEvents;
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
    {#if isOverlay}
      <p class="text-caption overlay-note" data-rl-live-events-overlay>
        equity 오버레이 · {run} vs {overlayNames.join(' · ')} · run 별 색상 비교 (research-only, 실행/수익 근거 아님)
      </p>
    {/if}
    <div class="frame-scrubber" data-rl-frame-scrubber>
      <input
        type="range"
        min="1"
        max={Math.max(1, totalFrames)}
        step="1"
        value={frame}
        aria-label="rollout replay frame"
        oninput={(evt) => (frameOverride = Number(evt.currentTarget.value))}
      />
      <div class="frame-meta">
        <span class="mono">frame {frame} / {totalFrames}</span>
        {#if isLiveFrame}
          <span class="pill accent">live head</span>
        {:else}
          <button type="button" class="frame-live-btn" onclick={() => (frameOverride = null)}>↺ 라이브 head</button>
        {/if}
      </div>
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
  <!-- P7 overlay(RESOLVED, G4): compareRuns prop 으로 2번째 이상 run 의 equity 를 legend 와
       theme-distinct 색으로 오버레이한다. single-run 경로는 이전과 동일하게 유지된다. -->
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
  .overlay-note {
    color: var(--info);
    margin: 0;
  }
  .frame-scrubber {
    display: flex;
    flex-direction: column;
    gap: 6px;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 10px 12px;
    background: var(--surface);
  }
  .frame-scrubber input[type='range'] {
    width: 100%;
    accent-color: var(--accent);
  }
  .frame-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: var(--muted);
    font-size: 12px;
  }
  .frame-live-btn {
    border: 1px solid var(--border);
    border-radius: var(--r-md, 10px);
    background: var(--card-grad);
    color: var(--fg);
    padding: 4px 10px;
    cursor: pointer;
    font-size: 12px;
  }
  .frame-live-btn:hover {
    border-color: var(--accent);
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

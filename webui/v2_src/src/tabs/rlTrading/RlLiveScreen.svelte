<script lang="ts">
  // WP-S1 — "RL 학습 라이브" 화면 (plan §10). RESEARCH_ONLY, 백엔드 변경 없음.
  // RLTradingTab 최상단(Disclosure 스택 위)에 마운트되어 현행 LiveRlEventsCard 슬롯을
  // 대체한다. LiveRlEventsCard의 readouts/reward+equity 차트/프레임 스크러버/안전 문구를
  // 이식하고(:27-134, :146-248, :251-314), 신규로 (3) portfolio 런 일별 수익/에쿼티
  // 곡선, (4) 에피소드 티커, (5) 액션 피드 레일을 추가한다.
  // 데이터 출처는 전부 기존: rlApi.rlEvents(run, 240) 4s 폴링 + RLTradingTab이 이미
  // selectRun()에서 로드해 전달하는 rlApi.rlEquity rows. 신규 /api/* 없음 (C7).
  import { onDestroy } from 'svelte';
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import { rlApi, type RlTableRow } from '$lib/rlApi';
  import { deriveDisplayStatus, statusLabel, statusTone, isLive as isRunning, type RunLifecycle } from '$lib/runLifecycle';
  import { errorMessage, num, pct, rowNumber, text } from '$lib/rlRows';
  import { tooltipLines, tooltipText, tooltipTitle } from '$lib/safeHtml';
  import { theme } from '$lib/stores';
  import { equityChartOption } from './chartOptions';

  interface Props {
    // 현재 선택된 run 이름 (RLTradingTab의 selectedName 을 그대로 전달받는다).
    readonly run: string;
    // 폴링 주기(초). LiveRlEventsCard 관례에 맞춰 기본 4s.
    readonly pollSeconds?: number;
    // G4 계승 — primary run 위에 equity 를 겹쳐 그릴 추가 run 이름들(비교/오버레이).
    readonly compareRuns?: readonly string[];
    // RLTradingTab.selectRun()이 이미 로드한 rlApi.rlEquity rows(portfolio 런의 일별
    // 수익/에쿼티 곡선). 이 화면은 별도로 재요청하지 않는다 — 항목 (3).
    readonly equityRows?: readonly RlTableRow[];
    // 착수 전 체크(감사 F) — daily/opening_30m 계열 run 은 rl_events.py 라이브 로그를
    // 방출하지 않을 수 있다. RLTradingTab.selectRun()이 이미 로드한 rlApi.rlEpisodes
    // (또는 opening_30m 대체 테이블) rows 를 에피소드 티커의 정직한 CSV 폴백으로 쓴다.
    readonly episodeRows?: readonly RlTableRow[];
  }
  let { run, pollSeconds = 4, compareRuns = [], equityRows = [], episodeRows = [] }: Props = $props();

  // --- 라이브 이벤트 tail (LiveRlEventsCard:27-134 이식) ---
  let events = $state<readonly RlTableRow[]>([]);
  let truncated = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  // 백엔드가 이벤트 로그 부재 시 돌려주는 정직한 메시지
  // ("live event log is not available for this run")를 fail-closed 로 그대로 표기한다.
  let emptyMessage = $state<string | null>(null);
  let lastUpdated = $state<string | null>(null);
  let polling = $state(false);
  let compareSeries = $state<readonly { name: string; rows: readonly RlTableRow[] }[]>([]);
  let frameOverride = $state<number | null>(null);

  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));

  let timer: number | null = null;
  let activeRun = '';
  let activeCompareKey = '';
  // WP-S1/Todo6 — lifecycle 스냅샷(백엔드 단일 스냅샷은 RUNNING/STALE 을 절대 방출하지
  // 않는다) + cross-poll 관측(prevStep/wasRunning)으로 client 가 RUNNING/STALE 을
  // 도출한다. run 이 바뀌면 관측 상태를 리셋한다.
  let lifecycle = $state<RunLifecycle | null>(null);
  let prevStep = $state<number | null>(null);
  let wasRunning = $state(false);

  const overlayNames = $derived(compareRuns.filter((name) => name !== '' && name !== run));
  const isOverlay = $derived(overlayNames.length > 0);

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
  // WP-S1/Todo6 — 파생 상태: 백엔드 스냅샷 + cross-poll 관측을 결합한 정직한 상태.
  // RUNNING 은 오직 polling && step advancing && event freshness 조건을 모두
  // 만족할 때만 성립한다 (row-존재/polling 만으로는 절대 LIVE 로 표기하지 않는다).
  let currentStep = $state<number | null>(null);
  const displayStatus = $derived(
    deriveDisplayStatus(lifecycle, { prevStep, currentStep, polling, wasRunning })
  );
  const displayLive = $derived(isRunning(displayStatus));

  async function refresh(): Promise<void> {
    if (!run) {
      events = [];
      truncated = false;
      compareSeries = [];
      emptyMessage = null;
      lifecycle = null;
      prevStep = null;
      currentStep = null;
      return;
    }
    loading = true;
    try {
      const extras = overlayNames;
      const [payloads, detail] = await Promise.all([
        Promise.all([
          rlApi.rlEvents(run, 240),
          ...extras.map((name) => rlApi.rlEvents(name, 240)),
        ]),
        rlApi.rlRun(run).catch(() => null),
      ]);
      const primary = payloads[0];
      const rows = primary?.rows ?? [];
      events = rows;
      truncated = Boolean(primary?.truncated);
      // rows 가 있으면 message 는 무시(정상 tail); rows 가 비어 있을 때만 백엔드
      // fail-closed 문구를 그대로 노출한다.
      emptyMessage = rows.length ? null : (primary?.message ?? null);
      compareSeries = extras.map((name, idx) => ({ name, rows: payloads[idx + 1]?.rows ?? [] }));
      error = null;
      lastUpdated = new Date().toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul' });
      lifecycle = detail?.lifecycle ?? null;
      const newStepRaw = rows.length ? rowNumber(rows[rows.length - 1], 'global_step', NaN) : NaN;
      prevStep = currentStep;
      currentStep = Number.isFinite(newStepRaw) ? newStepRaw : null;
      if (displayStatus === 'RUNNING') wasRunning = true;
    } catch (caught) {
      error = errorMessage(caught, `${run} live events load failed`);
      events = [];
      truncated = false;
      compareSeries = [];
      emptyMessage = null;
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

  // run 이 바뀌면 폴링을 재시작한다 (setInterval, onDestroy 에서 정리) — 이전 run 의
  // lifecycle 관측(prevStep/currentStep/wasRunning)은 새 run 에 이월하지 않는다.
  $effect(() => {
    if (run === activeRun) return;
    activeRun = run;
    lifecycle = null;
    prevStep = null;
    currentStep = null;
    wasRunning = false;
    startTimer();
  });

  // compareRuns 가 바뀌면 다음 폴링을 기다리지 않고 즉시 tail 을 다시 가져온다.
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

  // (1)+(2) 헤더 readouts 는 아래 템플릿에서 latestStep 등을 직접 사용하고,
  // reward+equity 듀얼 라이브 차트 + 스크러버는 LiveRlEventsCard:146-248 을 이식한다.
  // 오버레이 분기는 F23 수정을 반영해 처음부터 value-x축 [global_step, equity]
  // 튜플로 작성한다 (LiveRlEventsCard 쪽 동일 수정은 별도 owned-file 변경 참조).
  const liveChartOption = $derived.by(() => {
    void currentTheme;
    if (!visibleEvents.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#38bdf8';
    const success = cs.getPropertyValue('--success').trim() || '#22c55e';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const dim = cs.getPropertyValue('--dim').trim() || '#64748b';

    if (isOverlay) {
      const palette = ['--accent', '--warn', '--info', '--success', '--danger']
        .map((token) => cs.getPropertyValue(token).trim())
        .filter((color) => color !== '');
      const colorAt = (idx: number): string => (palette.length ? palette[idx % palette.length] : accent);
      // F23 — 각 시리즈는 자신의 [global_step, equity] 좌표를 쓴다. run 마다 길이/step
      // 간격이 다를 수 있어 공유 category index 로 그리면 서로 다른 step 을 같은 x
      // 위치에 겹쳐 그리는 정렬 오류가 나므로, primary 의 frame index 를 compare
      // run 에 그대로 적용(slice)하지 않는다 — 각 시리즈는 자신의 로드된 step 범위
      // 전체(이미 API limit 로 bounded)를 그린다.
      const seriesDefs = [
        { name: run, rows: visibleEvents },
        ...overlayNames.map((name) => ({
          name,
          rows: compareSeries.find((entry) => entry.name === name)?.rows ?? [],
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
            const lines = [tooltipTitle('global_step')];
            for (const item of list) {
              if (item && typeof item === 'object') {
                const seriesName =
                  'seriesName' in item ? String((item as { seriesName?: unknown }).seriesName ?? '') : '';
                const value = 'value' in item ? (item as { value?: unknown }).value : null;
                const stepVal = Array.isArray(value) ? value[0] : null;
                const equityVal = Array.isArray(value) ? value[1] : value;
                lines.push(tooltipText(`${seriesName} step ${num(stepVal, 0)} · equity ${num(equityVal, 2)}`));
              }
            }
            return tooltipLines(lines);
          },
        },
        xAxis: { type: 'value', name: 'global_step', axisLabel: { color: dim } },
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
          data: def.rows.map((row) => [rowNumber(row, 'global_step'), rowNumber(row, 'equity')]),
          lineStyle: { color: colorAt(idx), width: 2.2 },
          itemStyle: { color: colorAt(idx) },
        })),
      };
    }

    // single-run 경로 — LiveRlEventsCard:216-247 과 동일하게 렌더한다.
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

  // (3) 일별 수익/에쿼티 곡선 (portfolio 런) — RLTradingTab 이 이미 로드한 rlApi.rlEquity
  // rows 를 그대로 재사용한다 (chartOptions.ts:60-70).
  const dailyEquityOption = $derived(equityChartOption(equityRows));

  // (4) 에피소드 티커 — events rows 를 episode_id 로 그룹핑해 "나아지는가" 장기 추이를
  // 보여준다. episode_id 가 없는 레거시 run 은 episode(정수) 로 폴백한다.
  interface EpisodeBucket {
    readonly key: string;
    readonly label: string;
    // 부호 보존 크기 지표. metricLabel 에 따라 단위가 다르다.
    readonly totalReward: number;
    readonly stepCount: number;
    // 'Σreward' = 라이브 이벤트 reward 합(raw, ×100 후 pct 표기) ·
    // 'return' = CSV 폴백 episode_return_pct(이미 % 값, 그대로 pct 표기).
    readonly metricLabel: 'Σreward' | 'return';
  }
  const episodeBuckets = $derived.by((): EpisodeBucket[] => {
    const buckets: EpisodeBucket[] = [];
    const indexByKey = new Map<string, number>();
    for (const row of events) {
      const episodeId = text(row, 'episode_id', '');
      const episodeNum = rowNumber(row, 'episode', NaN);
      const key = episodeId || (Number.isFinite(episodeNum) ? `ep-${episodeNum}` : '');
      if (!key) continue;
      const existingIdx = indexByKey.get(key);
      if (existingIdx === undefined) {
        const label = Number.isFinite(episodeNum) ? `EP ${episodeNum}` : `EP ${buckets.length + 1}`;
        indexByKey.set(key, buckets.length);
        buckets.push({ key, label, totalReward: rowNumber(row, 'reward'), stepCount: 1, metricLabel: 'Σreward' });
      } else {
        const prior = buckets[existingIdx];
        buckets[existingIdx] = {
          ...prior,
          totalReward: prior.totalReward + rowNumber(row, 'reward'),
          stepCount: prior.stepCount + 1,
        };
      }
    }
    return buckets;
  });
  // CSV 폴백 (착수 전 체크, 감사 F) — events 가 비어 있으면 RLTradingTab 이 이미 로드한
  // rlApi.rlEpisodes(또는 opening_30m 대체 테이블) rows 로 정직하게 대체한다.
  const csvEpisodeBuckets = $derived.by((): EpisodeBucket[] =>
    episodeRows
      .map((row, idx): EpisodeBucket | null => {
        const episodeId = text(row, 'episode_id', '');
        if (!episodeId) return null;
        const returnPct = rowNumber(row, 'episode_return_pct', rowNumber(row, 'baseline_net_return_pct', 0));
        return { key: episodeId, label: `EP ${idx + 1}`, totalReward: returnPct, stepCount: 1, metricLabel: 'return' };
      })
      .filter((bucket): bucket is EpisodeBucket => bucket !== null)
  );
  const effectiveEpisodeBuckets = $derived(episodeBuckets.length ? episodeBuckets : csvEpisodeBuckets);
  const usingCsvEpisodeFallback = $derived(episodeBuckets.length === 0 && csvEpisodeBuckets.length > 0);
  const episodeMaxAbsReward = $derived(
    effectiveEpisodeBuckets.reduce((max, bucket) => Math.max(max, Math.abs(bucket.totalReward)), 0)
  );
  const visibleEpisodeBuckets = $derived(effectiveEpisodeBuckets.slice(-24));
  function episodeBarHeightPct(bucket: EpisodeBucket): number {
    if (episodeMaxAbsReward <= 0) return 6;
    return Math.max(6, Math.round((Math.abs(bucket.totalReward) / episodeMaxAbsReward) * 100));
  }
  function episodeRewardText(bucket: EpisodeBucket): string {
    return bucket.metricLabel === 'Σreward'
      ? `Σ${pct(bucket.totalReward * 100, 3)}`
      : `return ${pct(bucket.totalReward, 3)}`;
  }

  // (5) 액션 피드 레일 — 최근 ~20행을 최신순으로 표기한다. action_name 은 이미
  // /events 응답에 포함되어 있다 (rl_events.py:81).
  const actionFeedRows = $derived(events.slice(-20).reverse());
  function actionTone(row: RlTableRow): string {
    const name = text(row, 'action_name', '').toLowerCase();
    if (name === 'buy') return 'action-buy';
    if (name === 'sell') return 'action-sell';
    return 'action-hold';
  }
  // statusTone() vocabulary (accent/warn/ok/danger/idle) maps onto this file's
  // existing `.pill.*` CSS classes (success/warn/danger/accent; idle -> no
  // extra class, matches the plain default pill look).
  function statusPillClass(tone: ReturnType<typeof statusTone>): string {
    if (tone === 'ok') return 'success';
    if (tone === 'idle') return '';
    return tone;
  }

  const emptyStateText = $derived(loading ? '이벤트 로딩 중 · 연구 전용' : (emptyMessage ?? '이벤트 없음 · 연구 전용'));
</script>

<section class="card rl-live-screen" data-rl-live-screen>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">RL LIVE MONITOR · RESEARCH_ONLY</div>
      <div class="card-title">학습 라이브 (연구 전용)</div>
    </div>
    <div class="live-screen-status">
      <span class="pill" data-rl-live-screen-run>{run || '선택된 run 없음'}</span>
      <span class="pill {statusPillClass(statusTone(displayStatus))}" data-rl-live-screen-pill>
        {#if displayLive}
          <span class="live-dot" aria-hidden="true"></span>{statusLabel(displayStatus)}
        {:else}
          <span class="dot"></span>{statusLabel(displayStatus)}
        {/if}
      </span>
    </div>
  </div>

  {#if events.length}
    <div class="live-readouts" data-rl-live-screen-readouts>
      <div><span>Step</span><b class="mono">{latestStep}</b></div>
      <div><span>Reward</span><b class="mono">{latestReward}</b></div>
      <div><span>Equity</span><b class="mono">{latestEquity}</b></div>
      <div><span>Phase</span><b class="mono">{latestPhase}</b></div>
      <div><span>Algorithm</span><b class="mono">{latestAlgorithm}</b></div>
    </div>
    <div class="live-chart" data-rl-live-screen-chart>
      <EChartsRenderer option={liveChartOption} height="300px" />
    </div>
    {#if isOverlay}
      <p class="text-caption overlay-note" data-rl-live-screen-overlay>
        equity 오버레이 · {run} vs {overlayNames.join(' · ')} · run 별 색상 비교 (research-only, 실행/수익 근거 아님)
      </p>
    {/if}
    <div class="frame-scrubber" data-rl-live-screen-scrubber>
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
    <div class="live-empty" data-rl-live-screen-empty>{emptyStateText}</div>
  {/if}

  {#if error}
    <p class="text-caption tail-note">{error}</p>
  {/if}

  <div class="live-screen-section" data-rl-live-screen-daily-equity>
    <div class="text-eyebrow">일별 수익/에쿼티 곡선 · portfolio 런 · research-only</div>
    {#if equityRows.length}
      <EChartsRenderer option={dailyEquityOption} height="220px" />
    {:else}
      <div class="live-empty">일별 에쿼티 곡선 없음 · 연구 전용</div>
    {/if}
  </div>

  <div class="live-screen-section" data-rl-episode-ticker>
    <div class="text-eyebrow">에피소드 티커 · 나아지는가 (연구용 추세)</div>
    {#if usingCsvEpisodeFallback}
      <p class="text-caption overlay-note">
        events 로그 없음 · rlApi.rlEpisodes(CSV) 폴백 · episode_return_pct 기준 (research-only)
      </p>
    {/if}
    {#if visibleEpisodeBuckets.length}
      <div class="episode-row">
        {#each visibleEpisodeBuckets as bucket (bucket.key)}
          <div class="episode-chip">
            <div class="episode-bar-track">
              <div
                class="episode-bar {bucket.totalReward >= 0 ? 'positive' : 'negative'}"
                style={`height:${episodeBarHeightPct(bucket)}%`}
              ></div>
            </div>
            <span class="episode-label mono">{bucket.label}</span>
            <span class="episode-reward mono">{episodeRewardText(bucket)}</span>
          </div>
        {/each}
      </div>
    {:else}
      <div class="live-empty">{emptyStateText}</div>
    {/if}
  </div>

  <div class="live-screen-section" data-rl-action-feed>
    <div class="text-eyebrow">액션 피드 · 최근 스텝 (연구용)</div>
    {#if actionFeedRows.length}
      <ul class="action-feed-list">
        {#each actionFeedRows as row, idx (`${text(row, 'global_step', String(idx))}-${idx}`)}
          <li class="action-feed-row {actionTone(row)}">
            <span class="mono">step {num(rowNumber(row, 'global_step'), 0)}</span>
            <span class="action-name">{text(row, 'action_name', 'hold')}</span>
            <span class="mono">reward {pct(rowNumber(row, 'reward') * 100, 3)}</span>
            <span class="mono">equity {num(rowNumber(row, 'equity'), 2)}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <div class="live-empty">{emptyStateText}</div>
    {/if}
  </div>

  <p class="text-caption safety-note" data-rl-live-screen-safety-note>
    RESEARCH_ONLY · {run || '선택된 run 없음'} · {lastUpdated ? `updated ${lastUpdated}` : 'polling…'} · NO live / broker / order / profit / GO. 이 라이브 tail은 학습 이벤트 로그의 bounded snapshot이며 실행·수익 근거가 아닙니다.
  </p>
</section>

<style>
  .rl-live-screen {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }
  .live-screen-status {
    display: flex;
    align-items: center;
    gap: 8px;
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

  .live-screen-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 12px;
    background: var(--surface);
  }

  /* 에피소드 티커 — 신규 (4) */
  .episode-row {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .episode-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    min-width: 60px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-md, 10px);
    background: var(--card-grad);
  }
  .episode-bar-track {
    width: 18px;
    height: 48px;
    display: flex;
    align-items: flex-end;
    background: var(--surface-sunken, rgba(148, 163, 184, 0.08));
    border-radius: 4px;
    overflow: hidden;
  }
  .episode-bar {
    width: 100%;
    border-radius: 3px 3px 0 0;
  }
  .episode-bar.positive { background: var(--success); }
  .episode-bar.negative { background: var(--danger); }
  .episode-label { font-size: 11px; color: var(--muted); white-space: nowrap; }
  .episode-reward { font-size: 11px; color: var(--fg); white-space: nowrap; }

  /* 액션 피드 레일 — 신규 (5) */
  .action-feed-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 280px;
    overflow-y: auto;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .action-feed-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    align-items: center;
    padding: 6px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-md, 10px);
    background: var(--card-grad);
    font-size: 12px;
  }
  .action-feed-row .action-name {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
  }
  .action-feed-row.action-buy .action-name { color: var(--success); }
  .action-feed-row.action-sell .action-name { color: var(--danger); }
  .action-feed-row.action-hold .action-name { color: var(--muted); }
</style>

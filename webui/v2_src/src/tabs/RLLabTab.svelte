<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type RlCostGateResponse, type RlLiveEventsResponse, type RlRunDetail, type RlRunRecord } from '$lib/api';
  import { fmt } from '$lib/format';
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';

  type DetailView = 'overview' | 'live' | 'leaderboard' | 'trades' | 'artifacts';

  let runs = $state<RlRunRecord[]>([]);
  let selectedName = $state('');
  let selectedRun = $state<RlRunDetail | null>(null);
  let costGate = $state<RlCostGateResponse | null>(null);
  let costGateRunName = $state('');
  let leaderboard = $state<Array<Record<string, any>>>([]);
  let trades = $state<Array<Record<string, any>>>([]);
  let equity = $state<Array<Record<string, any>>>([]);
  let episodes = $state<Array<Record<string, any>>>([]);
  let liveEvents = $state<Array<Record<string, any>>>([]);
  let liveEventPayload = $state<RlLiveEventsResponse | null>(null);
  let view = $state<DetailView>('overview');
  let loading = $state(false);
  let detailLoading = $state(false);
  let error = $state<string | null>(null);

  onMount(() => {
    void loadDashboard();
  });

  async function loadDashboard(): Promise<void> {
    loading = true;
    error = null;
    try {
      const payload = await api.rlRuns(30);
      runs = payload?.runs ?? [];
      const preferred =
        runs.find((run) => run.artifact_type === 'performance_leaderboard') ??
        runs.find((run) => run.artifact_type === 'sb3_smoke') ??
        runs.find((run) => run.artifact_type === 'contextual_bandit') ??
        runs.find((run) => run.artifact_type === 'cost_gate') ??
        runs[0];
      if (preferred) {
        await selectRun(preferred.name, runs);
      }
    } catch (e: any) {
      error = e?.message ?? '강화학습 산출물 조회 실패';
    } finally {
      loading = false;
    }
  }

  async function selectRun(name: string, runPool: RlRunRecord[] = runs): Promise<void> {
    if (!name) return;
    selectedName = name;
    detailLoading = true;
    error = null;
    leaderboard = [];
    trades = [];
    equity = [];
    episodes = [];
    liveEvents = [];
    liveEventPayload = null;
    selectedRun = null;
    try {
      const detail = await api.rlRun(name);
      selectedRun = detail;

      const [leaderboardPayload, tradePayload, equityPayload, episodePayload, eventPayload] = await Promise.all([
        detail?.artifact_type === 'performance_leaderboard'
          ? api.rlTable(name, 'leaderboard', 200)
          : Promise.resolve(null),
        api.rlTrades(name, 120),
        api.rlEquity(name, 360),
        api.rlEpisodes(name, 120),
        api.rlEvents(name, 500),
      ]);
      const detailLeaderboard = detail?.detail?.leaderboard;
      leaderboard = leaderboardPayload?.rows ?? (Array.isArray(detailLeaderboard) ? detailLeaderboard : []);
      trades = tradePayload?.rows ?? [];
      equity = equityPayload?.rows ?? [];
      episodes = episodePayload?.rows ?? [];
      liveEventPayload = eventPayload;
      liveEvents = eventPayload?.rows ?? [];

      const gateRun = detail?.artifact_type === 'cost_gate'
        ? name
        : runPool.find((run) => run.artifact_type === 'cost_gate')?.name;
      costGateRunName = gateRun ?? '';
      costGate = gateRun ? await api.rlCostGate(gateRun, 80) : null;
    } catch (e: any) {
      error = e?.message ?? `${name} 상세 조회 실패`;
    } finally {
      detailLoading = false;
    }
  }

  const selectedSummary = $derived(selectedRun?.summary ?? {});
  const gateRows = $derived<any[]>(costGate?.gate?.rows ?? selectedRun?.summary?.gate_rows ?? selectedRun?.detail?.summary?.gate_rows ?? []);
  const passingGateRows = $derived(gateRows.filter((row: any) => Boolean(row?.passes_cost_gate)));
  const leaderboardRows = $derived.by(() => {
    const detailLeaderboard = selectedRun?.detail?.leaderboard;
    return leaderboard.length ? leaderboard : Array.isArray(detailLeaderboard) ? detailLeaderboard : [];
  });
  const modelFeatures = $derived(selectedRun?.model?.feature_columns ?? []);
  const latestLiveEvent = $derived(liveEvents.at(-1) ?? null);
  const liveActionCounts = $derived.by(() => {
    const counts: Record<string, number> = { hold: 0, buy: 0, sell: 0 };
    for (const row of liveEvents) {
      const label = String(row.action_name ?? row.action ?? 'unknown');
      counts[label] = (counts[label] ?? 0) + 1;
    }
    return counts;
  });
  const artifactCount = $derived(selectedRun?.artifacts?.length ?? 0);
  const isSb3Smoke = $derived(selectedRun?.artifact_type === 'sb3_smoke');
  const hasModel = $derived(selectedRun?.artifact_type === 'contextual_bandit' || isSb3Smoke);
  const hasLeaderboard = $derived(selectedRun?.artifact_type === 'performance_leaderboard' || leaderboardRows.length > 0);
  const selectedNetPct = $derived(
    selectedSummary.avg_episode_net_return_pct ??
      selectedSummary.buy_and_hold_avg_episode_net_return_pct ??
      selectedSummary.no_trade_avg_episode_net_return_pct
  );

  const equityChartOption = $derived.by(() => {
    const rows = equity;
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 54, right: 24, top: 34, bottom: 42 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          const row = rows[p?.dataIndex ?? 0] ?? {};
          return [
            `<strong>${row.symbol ?? row.policy ?? selectedName}</strong>`,
            row.timestamp ? `시각 ${String(row.timestamp).slice(0, 19)}` : '',
            `누적 수익률 ${fmt.pct(p?.value ?? 0, 3)}`,
            row.trade_count != null ? `거래 ${row.trade_count}` : '',
          ].filter(Boolean).join('<br/>');
        },
      },
      xAxis: {
        type: 'category',
        data: rows.map((row: any, idx: number) => row.timestamp ? String(row.timestamp).slice(11, 19) : String(idx + 1)),
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        name: '누적 수익률 %',
        scale: true,
        axisLabel: { formatter: '{value}%', color: '#64748b' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } },
      },
      series: [
        {
          name: 'Equity',
          type: 'line',
          smooth: 0.25,
          symbol: 'none',
          data: rows.map((row: any) => (Number(row.equity ?? 1) - 1) * 100),
          lineStyle: { color: '#0f766e', width: 2.6 },
          areaStyle: { color: 'rgba(20,184,166,.12)' },
        },
      ],
    };
  });


  const liveRewardChartOption = $derived.by(() => {
    const rows = liveEvents.slice(-240);
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 54, right: 24, top: 34, bottom: 42 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          const row = rows[p?.dataIndex ?? 0] ?? {};
          return [
            `<strong>${row.phase ?? 'event'} #${row.global_step ?? '-'}</strong>`,
            row.timestamp ? `time ${String(row.timestamp).slice(0, 19)}` : '',
            `action ${row.action_name ?? row.action ?? '-'}`,
            `reward ${num(row.reward, 6)}`,
            row.equity != null ? `equity ${num(row.equity, 5)}` : '',
          ].filter(Boolean).join('<br/>');
        },
      },
      xAxis: {
        type: 'category',
        data: rows.map((row: any, idx: number) => String(row.global_step ?? idx + 1)),
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        name: 'reward',
        scale: true,
        axisLabel: { color: '#64748b' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } },
      },
      series: [
        {
          name: 'Reward',
          type: 'line',
          smooth: 0.2,
          symbol: 'none',
          data: rows.map((row: any) => Number(row.reward ?? 0)),
          lineStyle: { color: '#7c3aed', width: 2.4 },
          areaStyle: { color: 'rgba(124,58,237,.12)' },
        },
      ],
    };
  });

  const liveActionChartOption = $derived.by(() => {
    const labels = Object.keys(liveActionCounts);
    if (!labels.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 42, right: 20, top: 28, bottom: 34 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels, axisLabel: { color: '#64748b' } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } } },
      series: [
        {
          name: 'Actions',
          type: 'bar',
          data: labels.map((label) => liveActionCounts[label]),
          itemStyle: { color: '#2563eb', borderRadius: [5, 5, 0, 0] },
        },
      ],
    };
  });

  const tradeChartOption = $derived.by(() => {
    const rows = trades.slice(0, 80);
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 54, right: 24, top: 34, bottom: 42 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          const row = rows[p?.dataIndex ?? 0] ?? {};
          return [
            `<strong>${row.symbol ?? row.policy ?? 'trade'}</strong>`,
            row.entry_timestamp ? `진입 ${String(row.entry_timestamp).slice(0, 19)}` : '',
            row.exit_timestamp ? `청산 ${String(row.exit_timestamp).slice(0, 19)}` : '',
            `순수익 ${fmt.pct(row.net_return_pct, 3)}`,
          ].filter(Boolean).join('<br/>');
        },
      },
      xAxis: {
        type: 'category',
        data: rows.map((row: any, idx: number) => String(row.symbol ?? row.policy ?? idx + 1)),
        axisLabel: { color: '#64748b', rotate: rows.length > 18 ? 40 : 0 },
      },
      yAxis: {
        type: 'value',
        name: '거래별 순수익 %',
        axisLabel: { formatter: '{value}%', color: '#64748b' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } },
      },
      series: [
        {
          name: 'Net return',
          type: 'bar',
          data: rows.map((row: any) => Number(row.net_return_pct ?? 0)),
          itemStyle: {
            color: (p: any) => Number(rows[p.dataIndex]?.net_return_pct ?? 0) >= 0 ? '#16a34a' : '#dc2626',
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    };
  });

  const costGateChartOption = $derived.by(() => {
    const rows = gateRows;
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 56, right: 28, top: 48, bottom: 42 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: 'inherit' } },
      xAxis: {
        type: 'category',
        data: rows.map((row: any) => String(row.policy ?? '-')),
        axisLabel: { color: '#64748b', rotate: rows.length > 5 ? 24 : 0 },
      },
      yAxis: [
        {
          type: 'value',
          name: '순수익/MDD %',
          axisLabel: { formatter: '{value}%', color: '#64748b' },
          splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } },
        },
        {
          type: 'value',
          name: '적중률 %',
          min: 0,
          max: 100,
          axisLabel: { formatter: '{value}%', color: '#64748b' },
        },
      ],
      series: [
        {
          name: '평균 episode net',
          type: 'bar',
          data: rows.map((row: any) => Number(row.avg_episode_net_return_pct ?? 0)),
          itemStyle: {
            color: (p: any) => rows[p.dataIndex]?.passes_cost_gate ? '#16a34a' : '#94a3b8',
            borderRadius: [4, 4, 0, 0],
          },
        },
        {
          name: 'MDD',
          type: 'bar',
          data: rows.map((row: any) => Number(row.max_drawdown_pct ?? 0)),
          itemStyle: { color: '#ef4444', borderRadius: [4, 4, 0, 0] },
        },
        {
          name: 'Hit rate',
          type: 'line',
          yAxisIndex: 1,
          data: rows.map((row: any) => normalizeRatio(row.hit_rate)),
          lineStyle: { color: '#2563eb', width: 2.4 },
          symbolSize: 7,
        },
      ],
    };
  });

  const leaderboardChartOption = $derived.by(() => {
    const rows = leaderboardRows.slice(0, 12);
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 58, right: 28, top: 48, bottom: 54 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          const row = rows[items[0]?.dataIndex ?? 0] ?? {};
          return [
            `<strong>#${row.rank ?? '-'} ${row.model ?? row.policy ?? '-'}</strong>`,
            row.source ? `구분 ${row.source}` : '',
            `평균 net ${pct(row.avg_episode_net_return_pct, 3)}`,
            `MDD ${pct(row.max_drawdown_pct, 2)}`,
            `거래 ${fmt.int(row.trade_count ?? 0)}건`,
            row.usability ? `판정 ${row.usability}` : '',
          ].filter(Boolean).join('<br/>');
        },
      },
      legend: { top: 0, textStyle: { color: 'inherit' } },
      xAxis: {
        type: 'category',
        data: rows.map((row: any) => String(row.model ?? row.policy ?? '-')),
        axisLabel: { color: '#64748b', rotate: rows.length > 5 ? 24 : 0 },
      },
      yAxis: [
        {
          type: 'value',
          name: '수익/MDD %',
          axisLabel: { formatter: '{value}%', color: '#64748b' },
          splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } },
        },
        {
          type: 'value',
          name: '거래/episode',
          axisLabel: { color: '#64748b' },
        },
      ],
      series: [
        {
          name: '평균 episode net',
          type: 'bar',
          data: rows.map((row: any) => Number(row.avg_episode_net_return_pct ?? 0)),
          itemStyle: {
            color: (p: any) => rows[p.dataIndex]?.source === 'rl_model' ? '#2563eb' : '#0f766e',
            borderRadius: [5, 5, 0, 0],
          },
        },
        {
          name: 'MDD',
          type: 'bar',
          data: rows.map((row: any) => Number(row.max_drawdown_pct ?? 0)),
          itemStyle: { color: '#ef4444', borderRadius: [5, 5, 0, 0] },
        },
        {
          name: '거래/episode',
          type: 'line',
          yAxisIndex: 1,
          data: rows.map((row: any) => Number(row.trades_per_episode ?? 0)),
          lineStyle: { color: '#f59e0b', width: 2.4 },
          symbolSize: 7,
        },
      ],
    };
  });

  function typeLabel(type: string | undefined): string {
    if (type === 'performance_leaderboard') return '성과 리더보드';
    if (type === 'sb3_smoke') return 'SB3 smoke';
    if (type === 'contextual_bandit') return '1차 RL 모델';
    if (type === 'cost_gate') return '비용 관문';
    if (type === 'baseline') return 'Baseline';
    if (type === 'episode_manifest') return 'Episode manifest';
    return type ?? 'unknown';
  }

  function typeTone(type: string | undefined): string {
    if (type === 'performance_leaderboard') return 'success';
    if (type === 'sb3_smoke') return 'accent';
    if (type === 'contextual_bandit') return 'accent';
    if (type === 'cost_gate') return 'success';
    if (type === 'baseline') return 'info';
    return '';
  }

  function normalizeRatio(value: unknown): number {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.abs(n) <= 1 ? n * 100 : n;
  }

  function pct(value: unknown, digits = 2): string {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return fmt.pct(n, digits);
  }

  function ratioPct(value: unknown, digits = 1): string {
    const n = normalizeRatio(value);
    if (!Number.isFinite(n)) return '—';
    return fmt.pct(n, digits);
  }

  function num(value: unknown, digits = 2): string {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return fmt.num(n, digits);
  }

  function boolLabel(value: unknown): string {
    return Boolean(value) ? '통과' : '실패';
  }

  function fileSize(bytes: number | undefined): string {
    if (bytes == null || !Number.isFinite(bytes)) return '—';
    if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
    return `${bytes} B`;
  }

  function runLabel(run: RlRunRecord): string {
    return run.name.replace(/^stom_1s_2025_/, '');
  }
</script>

<section class="page-hero" data-rl-lab-tab>
  <div class="row" style="gap:10px;flex-wrap:wrap">
    <span class="text-eyebrow">RL LAB · Kronos 비의존</span>
    <span class="pill accent"><span class="dot"></span>STOM 1초봉 read-only</span>
    <span class="pill info"><span class="dot"></span>/api/rl/*</span>
    <span class="pill {passingGateRows.length ? 'success' : 'warn'}"><span class="dot"></span>25bp cost gate</span>
  </div>
  <h1 class="text-h2" style="margin-top:8px">강화학습 실험실</h1>
  <p class="text-muted" style="margin-top:6px">
    STOM tick/back 데이터로 생성한 episode, baseline, 비용 관문, contextual bandit, DQN/PPO SB3 smoke, 통합 성과 리더보드를 한 화면에서 비교합니다.
    이 탭은 학습 산출물을 읽기 전용으로 시각화하며, 실제 매매 투입 전에는 전체 test split과 rolling 검증을 추가로 통과해야 합니다.
  </p>
</section>

{#if error}
  <section class="card error-card">
    <div class="card-title">강화학습 대시보드 조회 실패</div>
    <p class="text-muted">{error}</p>
    <button type="button" class="btn sm" onclick={() => void loadDashboard()}>다시 불러오기</button>
  </section>
{/if}

{#if loading && !runs.length}
  <section class="card">
    <div class="text-muted">강화학습 산출물을 불러오는 중...</div>
  </section>
{:else if !runs.length}
  <section class="empty">
    <strong>아직 표시할 강화학습 산출물이 없습니다.</strong>
    <span>먼저 episode manifest, baseline, cost gate, contextual bandit 또는 DQN/PPO SB3 smoke 학습을 실행하세요.</span>
  </section>
{:else}
  <section class="rl-kpi-grid">
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">RL runs</span>
        <span class="pill info">runtime</span>
      </div>
      <div><span class="metric-value">{fmt.int(runs.length)}</span><span class="metric-unit">개</span></div>
      <div class="metric-foot">webui/rl_runs read-only</div>
    </div>
    <div class="metric" class:glow={hasModel}>
      <div class="metric-head">
        <span class="metric-label">선택 모델</span>
        <span class="pill {typeTone(selectedRun?.artifact_type)}">{typeLabel(selectedRun?.artifact_type)}</span>
      </div>
      <div><span class="metric-value">{pct(selectedNetPct, 2)}</span></div>
      <div class="metric-foot">
        {#if selectedRun?.artifact_type === 'performance_leaderboard'}
          best {selectedSummary.best_policy ?? '-'} · RL {selectedSummary.best_rl_usability ?? '-'}
        {:else}
          평균 episode net · 선택 run 기준
        {/if}
      </div>
    </div>
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">거래 수</span>
        <span class="pill">cost {num(selectedSummary.cost_bps ?? selectedSummary.target_cost_bps, 0)}bp</span>
      </div>
      <div><span class="metric-value">{fmt.int(selectedSummary.trade_count ?? trades.length)}</span><span class="metric-unit">건</span></div>
      <div class="metric-foot">hit rate {ratioPct(selectedSummary.hit_rate, 1)}</div>
    </div>
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">비용 관문</span>
        <span class="pill {passingGateRows.length ? 'success' : 'warn'}">{passingGateRows.length ? '통과 정책 있음' : '추가 검증 필요'}</span>
      </div>
      <div><span class="metric-value">{fmt.int(passingGateRows.length)}</span><span class="metric-unit">개</span></div>
      <div class="metric-foot">{costGateRunName || 'cost gate run 없음'}</div>
    </div>
  </section>

  <section class="rl-layout">
    <aside class="card run-panel">
      <div class="card-header">
        <div>
          <div class="card-eyebrow">RUN SELECTOR</div>
          <div class="card-title">강화학습 산출물</div>
        </div>
        <button type="button" class="btn sm ghost" onclick={() => void loadDashboard()}>새로고침</button>
      </div>
      <div class="run-list">
        {#each runs as run}
          <button
            type="button"
            class="run-item"
            data-active={selectedName === run.name ? 'true' : 'false'}
            onclick={() => void selectRun(run.name)}
            title={run.name}
          >
            <span class="pill {typeTone(run.artifact_type)}">{typeLabel(run.artifact_type)}</span>
            <strong>{runLabel(run)}</strong>
            <small>{fmt.kst(run.modified_at)}</small>
            {#if run.summary?.avg_episode_net_return_pct != null}
              <span class="run-return {Number(run.summary.avg_episode_net_return_pct) >= 0 ? 'positive' : 'negative'}">
                {pct(run.summary.avg_episode_net_return_pct, 2)}
              </span>
            {/if}
          </button>
        {/each}
      </div>
    </aside>

    <div class="stack" style="--gap:16px;min-width:0">
      <section class="card">
        <div class="card-header">
          <div>
            <div class="card-eyebrow">SELECTED RUN</div>
            <div class="card-title">{selectedName || '선택 없음'}</div>
          </div>
          {#if detailLoading}
            <span class="pill info"><span class="dot"></span>불러오는 중</span>
          {:else if selectedRun}
            <span class="pill {typeTone(selectedRun.artifact_type)}">{typeLabel(selectedRun.artifact_type)}</span>
          {/if}
        </div>

        {#if selectedRun}
          <div class="summary-grid">
            <div>
              <span>Compounded</span>
              <strong>{pct(selectedSummary.compounded_return_pct, 2)}</strong>
            </div>
            <div>
              <span>MDD</span>
              <strong class={Number(selectedSummary.max_drawdown_pct ?? 0) < 0 ? 'negative' : ''}>
                {pct(selectedSummary.max_drawdown_pct, 2)}
              </strong>
            </div>
            <div>
              <span>Episode</span>
              <strong>{fmt.int(selectedSummary.episode_count ?? episodes.length)}</strong>
            </div>
            <div>
              <span>Artifact</span>
              <strong>{fmt.int(artifactCount)}</strong>
            </div>
          </div>

          {#if hasModel}
            <div class="model-note">
              <div>
                <div class="card-eyebrow">MODEL USAGE FLOW</div>
                <strong>{selectedRun.model?.model_type ?? (isSb3Smoke ? 'Stable-Baselines3 smoke' : 'contextual bandit')}</strong>
                <p class="text-caption">
                  {#if isSb3Smoke}
                    Gymnasium check_env를 통과한 STOM env에서 DQN/PPO를 짧게 학습하고 test episode에 적용한 smoke 결과입니다.
                  {:else}
                    저장된 `model.json`을 다시 로드해 test episode에 적용한 결과입니다.
                  {/if}
                  현재는 수익 가능성 확인용 smoke이며, buy-and-hold와 전체 test split을 이긴 최종 모델이라는 뜻은 아닙니다.
                </p>
              </div>
              <span class="pill accent">feature {fmt.int(modelFeatures.length)}</span>
            </div>
            {#if modelFeatures.length}
              <div class="feature-cloud">
                {#each modelFeatures.slice(0, 18) as feature}
                  <span>{feature}</span>
                {/each}
                {#if modelFeatures.length > 18}
                  <span>+{modelFeatures.length - 18}</span>
                {/if}
              </div>
            {/if}
          {/if}
          {#if hasLeaderboard}
            <div class="model-note leaderboard-note">
              <div>
                <div class="card-eyebrow">PERFORMANCE LEADERBOARD</div>
                <strong>full test split 기준 모델/정책 비교표</strong>
                <p class="text-caption">
                  buy-and-hold, no-trade, 단순 매매 baseline과 contextual bandit/DQN/PPO RL 모델을 같은 25bp 비용 기준으로 정렬합니다.
                  현재 RL 모델은 watch 상태이며, buy-and-hold를 이기거나 cost gate를 통과해야 실사용 후보가 됩니다.
                </p>
              </div>
              <span class="pill success">rows {fmt.int(leaderboardRows.length)}</span>
            </div>
          {/if}
        {/if}
      </section>

      <section class="row" style="gap:10px;flex-wrap:wrap">
        <div class="tabs" data-tab-group="rl-lab">
          <button data-active={view === 'overview' ? 'true' : 'false'} onclick={() => (view = 'overview')}>성과 개요</button>
          <button data-active={view === 'leaderboard' ? 'true' : 'false'} onclick={() => (view = 'leaderboard')}>리더보드</button>
          <button data-active={view === 'trades' ? 'true' : 'false'} onclick={() => (view = 'trades')}>거래/자산곡선</button>
          <button data-active={view === 'artifacts' ? 'true' : 'false'} onclick={() => (view = 'artifacts')}>아티팩트</button>
        </div>
        <span class="text-caption" style="margin-left:auto">선택 run 기준 · 표시는 최대 120~360행</span>
      </section>

      {#if view === 'overview'}
        {#if leaderboardRows.length}
          <section class="card" data-rl-leaderboard-chart>
            <div class="card-header">
              <div>
                <div class="card-eyebrow">FULL TEST LEADERBOARD</div>
                <div class="card-title">모델/정책별 비용 후 성과 비교</div>
              </div>
              <span class="pill success">best {selectedSummary.best_policy ?? leaderboardRows[0]?.model ?? '-'}</span>
            </div>
            <EChartsRenderer option={leaderboardChartOption} height="330px" />
          </section>
        {/if}

        <section class="chart-grid">
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">COST GATE</div>
                <div class="card-title">baseline / policy 비용 통과 비교</div>
              </div>
              <span class="pill {passingGateRows.length ? 'success' : 'warn'}">{passingGateRows.length ? '통과' : '보류'}</span>
            </div>
            {#if gateRows.length}
              <EChartsRenderer option={costGateChartOption} height="310px" />
            {:else}
              <div class="empty">cost gate 표가 없습니다.</div>
            {/if}
          </div>
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">EQUITY CURVE</div>
                <div class="card-title">선택 run 자산곡선</div>
              </div>
              <span class="pill">rows {fmt.int(equity.length)}</span>
            </div>
            {#if equity.length}
              <EChartsRenderer option={equityChartOption} height="310px" />
            {:else}
              <div class="empty">자산곡선 표가 없습니다.</div>
            {/if}
          </div>
        </section>

        <section class="card" data-rl-cost-gate-table>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">25BP TARGET GATE</div>
              <div class="card-title">비용 차감 후 살아남는 정책</div>
            </div>
            <span class="text-caption">source: {costGateRunName || selectedName}</span>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>정책</th>
                  <th class="num">평균 net</th>
                  <th class="num">Hit rate</th>
                  <th class="num">MDD</th>
                  <th class="num">거래/episode</th>
                  <th>판정</th>
                </tr>
              </thead>
              <tbody>
                {#each gateRows as row}
                  <tr>
                    <td class="mono">{row.policy ?? '-'}</td>
                    <td class="num {Number(row.avg_episode_net_return_pct ?? 0) >= 0 ? 'positive' : 'negative'}">
                      {pct(row.avg_episode_net_return_pct, 3)}
                    </td>
                    <td class="num">{ratioPct(row.hit_rate, 1)}</td>
                    <td class="num negative">{pct(row.max_drawdown_pct, 2)}</td>
                    <td class="num">{num(row.trades_per_episode, 2)}</td>
                    <td><span class="pill {row.passes_cost_gate ? 'success' : 'warn'}">{boolLabel(row.passes_cost_gate)}</span></td>
                  </tr>
                {/each}
                {#if !gateRows.length}
                  <tr><td colspan="6" class="text-muted">표시할 gate row가 없습니다.</td></tr>
                {/if}
              </tbody>
            </table>
          </div>
        </section>

      {:else if view === 'live'}
        <section class="card" data-rl-live-safety>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">REALTIME RL EVENTS</div>
              <div class="card-title">SB3 ?? ??? ???</div>
            </div>
            <span class="pill warn">??? ??</span>
          </div>
          <p class="text-caption">
            ? ??? historical replay / smoke / short training ???? JSONL artifact?? ?? ??????.
            ?? ?? ???? ????? ???? ????.
          </p>
          <div class="summary-grid">
            <div>
              <span>Events</span>
              <strong>{fmt.int(liveEventPayload?.row_count ?? liveEvents.length)}</strong>
            </div>
            <div>
              <span>Latest phase</span>
              <strong>{latestLiveEvent?.phase ?? '-'}</strong>
            </div>
            <div>
              <span>Latest action</span>
              <strong>{latestLiveEvent?.action_name ?? latestLiveEvent?.action ?? '-'}</strong>
            </div>
            <div>
              <span>Latest equity</span>
              <strong>{latestLiveEvent?.equity != null ? num(latestLiveEvent.equity, 5) : '-'}</strong>
            </div>
          </div>
        </section>

        <section class="chart-grid">
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">REWARD STREAM</div>
                <div class="card-title">step reward tail</div>
              </div>
              <span class="pill">rows {fmt.int(liveEvents.length)}</span>
            </div>
            {#if liveEvents.length}
              <EChartsRenderer option={liveRewardChartOption} height="320px" />
            {:else}
              <div class="empty">live event log? ?? ????. SB3 smoke? ?? ???? ?????.</div>
            {/if}
          </div>
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">ACTION DISTRIBUTION</div>
                <div class="card-title">hold / buy / sell</div>
              </div>
              <span class="pill accent">JSONL</span>
            </div>
            {#if liveEvents.length}
              <EChartsRenderer option={liveActionChartOption} height="320px" />
            {:else}
              <div class="empty">??? action ???? ????.</div>
            {/if}
          </div>
        </section>

        <section class="card" data-rl-live-events-table>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">EVENT LOG</div>
              <div class="card-title">?? ???? ???</div>
            </div>
            <span class="text-caption">source: {liveEventPayload?.source_file ?? 'none'}</span>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="num">step</th>
                  <th>phase</th>
                  <th>algorithm</th>
                  <th>time</th>
                  <th>action</th>
                  <th class="num">reward</th>
                  <th class="num">equity</th>
                  <th class="num">position</th>
                </tr>
              </thead>
              <tbody>
                {#each liveEvents.slice(-80).reverse() as row}
                  <tr>
                    <td class="num">{fmt.int(row.global_step ?? 0)}</td>
                    <td><span class="pill {row.phase === 'eval' ? 'success' : 'accent'}">{row.phase ?? '-'}</span></td>
                    <td class="mono">{row.algorithm ?? '-'}</td>
                    <td class="mono">{row.timestamp ? String(row.timestamp).slice(11, 19) : '-'}</td>
                    <td>{row.action_name ?? row.action ?? '-'}</td>
                    <td class="num">{num(row.reward, 6)}</td>
                    <td class="num">{row.equity != null ? num(row.equity, 5) : '-'}</td>
                    <td class="num">{row.position ?? '-'}</td>
                  </tr>
                {/each}
                {#if !liveEvents.length}
                  <tr><td colspan="8" class="text-muted">??? live event row? ????.</td></tr>
                {/if}
              </tbody>
            </table>
          </div>
        </section>

      {:else if view === 'leaderboard'}
        <section class="card" data-rl-leaderboard-table>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">MODEL PERFORMANCE</div>
              <div class="card-title">full test split 성과 리더보드</div>
            </div>
            <span class="text-caption">source: {selectedName}</span>
          </div>
          {#if leaderboardRows.length}
            <EChartsRenderer option={leaderboardChartOption} height="330px" />
          {:else}
            <div class="empty">성과 리더보드 row가 없습니다.</div>
          {/if}
          <div class="table-wrap leaderboard-table">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="num">순위</th>
                  <th>구분</th>
                  <th>모델/정책</th>
                  <th class="num">평균 net</th>
                  <th class="num">MDD</th>
                  <th class="num">거래</th>
                  <th class="num">거래/episode</th>
                  <th>buy&hold</th>
                  <th>cost gate</th>
                  <th>판정</th>
                  <th>근거</th>
                </tr>
              </thead>
              <tbody>
                {#each leaderboardRows as row}
                  <tr>
                    <td class="num">{fmt.int(row.rank)}</td>
                    <td><span class="pill {row.source === 'rl_model' ? 'accent' : 'info'}">{row.source ?? '-'}</span></td>
                    <td class="mono">{row.model ?? row.policy ?? '-'}</td>
                    <td class="num {Number(row.avg_episode_net_return_pct ?? 0) >= 0 ? 'positive' : 'negative'}">
                      {pct(row.avg_episode_net_return_pct, 3)}
                    </td>
                    <td class="num negative">{pct(row.max_drawdown_pct, 2)}</td>
                    <td class="num">{fmt.int(row.trade_count ?? 0)}</td>
                    <td class="num">{num(row.trades_per_episode, 3)}</td>
                    <td><span class="pill {row.beats_buy_and_hold ? 'success' : 'warn'}">{boolLabel(row.beats_buy_and_hold)}</span></td>
                    <td><span class="pill {row.passes_cost_gate ? 'success' : 'warn'}">{boolLabel(row.passes_cost_gate)}</span></td>
                    <td><span class="pill {row.usability === 'candidate' ? 'success' : row.usability === 'watch' ? 'accent' : 'info'}">{row.usability ?? '-'}</span></td>
                    <td class="wrap">{row.decision_reason ?? '-'}</td>
                  </tr>
                {/each}
                {#if !leaderboardRows.length}
                  <tr><td colspan="11" class="text-muted">표시할 leaderboard row가 없습니다.</td></tr>
                {/if}
              </tbody>
            </table>
          </div>
        </section>
      {:else if view === 'trades'}
        <section class="chart-grid">
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">TRADES</div>
                <div class="card-title">거래별 순수익 분포</div>
              </div>
              <span class="pill">rows {fmt.int(trades.length)}</span>
            </div>
            {#if trades.length}
              <EChartsRenderer option={tradeChartOption} height="320px" />
            {:else}
              <div class="empty">거래 내역이 없습니다.</div>
            {/if}
          </div>
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-eyebrow">EQUITY</div>
                <div class="card-title">시간순 자산곡선</div>
              </div>
              <span class="pill">rows {fmt.int(equity.length)}</span>
            </div>
            {#if equity.length}
              <EChartsRenderer option={equityChartOption} height="320px" />
            {:else}
              <div class="empty">자산곡선 내역이 없습니다.</div>
            {/if}
          </div>
        </section>

        <section class="card" data-rl-trade-table>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">RECENT TRADES</div>
              <div class="card-title">실제 거래 위치 확인</div>
            </div>
            <span class="text-caption">진입/청산 timestamp 기준</span>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>종목/정책</th>
                  <th>진입</th>
                  <th>청산</th>
                  <th class="num">예측 net</th>
                  <th class="num">실현 net</th>
                </tr>
              </thead>
              <tbody>
                {#each trades.slice(0, 60) as row}
                  <tr>
                    <td class="mono">{row.symbol ?? row.policy ?? '-'}</td>
                    <td class="mono">{String(row.entry_timestamp ?? '-').slice(0, 19)}</td>
                    <td class="mono">{String(row.exit_timestamp ?? '-').slice(0, 19)}</td>
                    <td class="num">{pct(row.predicted_net_return_pct, 3)}</td>
                    <td class="num {Number(row.net_return_pct ?? 0) >= 0 ? 'positive' : 'negative'}">{pct(row.net_return_pct, 3)}</td>
                  </tr>
                {/each}
                {#if !trades.length}
                  <tr><td colspan="5" class="text-muted">표시할 거래 row가 없습니다.</td></tr>
                {/if}
              </tbody>
            </table>
          </div>
        </section>
      {:else}
        <section class="card" data-rl-artifact-table>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">ARTIFACTS</div>
              <div class="card-title">재현 가능한 런타임 산출물</div>
            </div>
            <span class="pill">files {fmt.int(artifactCount)}</span>
          </div>
          <div class="artifact-list">
            {#each selectedRun?.artifacts ?? [] as file}
              <div class="artifact-row">
                <div>
                  <strong class="text-mono">{file.name}</strong>
                  <span class="text-caption">{file.suffix || 'file'} · {fmt.kst(file.modified_at)}</span>
                </div>
                <span class="text-mono">{fileSize(file.size_bytes)}</span>
              </div>
            {/each}
            {#if !(selectedRun?.artifacts?.length)}
              <div class="empty">아티팩트 목록이 없습니다.</div>
            {/if}
          </div>
        </section>
      {/if}
    </div>
  </section>
{/if}

<style>
  .rl-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  }
  .rl-layout {
    display: grid;
    grid-template-columns: 340px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
  }
  .run-panel {
    position: sticky;
    top: calc(var(--header-h) + 18px);
    max-height: calc(100vh - var(--header-h) - 40px);
    overflow: hidden;
  }
  .run-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: auto;
    padding-right: 2px;
  }
  .run-item {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 7px 10px;
    text-align: left;
    padding: 12px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface);
    transition: background var(--d-fast), border-color var(--d-fast), transform var(--d-fast);
  }
  .run-item:hover {
    background: var(--surface-sunken);
    border-color: var(--border-strong);
  }
  .run-item[data-active="true"] {
    background: var(--accent-soft);
    border-color: var(--accent-tint);
  }
  .run-item strong {
    grid-column: 1 / -1;
    color: var(--fg-strong);
    font-size: 13px;
    word-break: break-all;
  }
  .run-item small {
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .run-return {
    justify-self: end;
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 12px;
  }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  .summary-grid > div {
    padding: 14px;
    border-radius: var(--r-md);
    background: var(--surface-sunken);
    border: 1px solid var(--border-faint);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .summary-grid span {
    color: var(--muted);
    font-size: 12px;
  }
  .summary-grid strong {
    color: var(--fg-strong);
    font-family: var(--font-mono);
    font-size: 20px;
  }
  .model-note {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    padding: 14px;
    border-radius: var(--r-md);
    background: linear-gradient(135deg, var(--accent-soft), var(--surface));
    border: 1px solid var(--accent-tint);
  }
  .model-note p {
    margin-top: 6px;
    line-height: 1.55;
  }
  .leaderboard-note {
    margin-top: 12px;
    background: linear-gradient(135deg, rgba(22, 163, 74, .10), var(--surface));
    border-color: rgba(22, 163, 74, .22);
  }
  .feature-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .feature-cloud span {
    padding: 5px 8px;
    border-radius: var(--r-pill);
    background: var(--surface-sunken);
    border: 1px solid var(--border-faint);
    color: var(--muted);
    font: 600 11px/1 var(--font-mono);
  }
  .chart-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
  .table-wrap {
    overflow: auto;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
  }
  .leaderboard-table {
    margin-top: 14px;
  }
  .wrap {
    min-width: 180px;
    white-space: normal;
  }
  .positive {
    color: var(--success) !important;
    font-weight: 700;
  }
  .negative {
    color: var(--danger) !important;
    font-weight: 700;
  }
  .artifact-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .artifact-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface-sunken);
  }
  .artifact-row > div {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .artifact-row strong {
    word-break: break-all;
    color: var(--fg-strong);
  }
  .error-card {
    border-color: var(--danger-soft);
    background: var(--danger-soft);
  }
  @media (max-width: 1180px) {
    .rl-kpi-grid,
    .summary-grid,
    .chart-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .rl-layout {
      grid-template-columns: 1fr;
    }
    .run-panel {
      position: static;
      max-height: none;
    }
  }
  @media (max-width: 760px) {
    .rl-kpi-grid,
    .summary-grid,
    .chart-grid {
      grid-template-columns: 1fr;
    }
    .artifact-row {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>

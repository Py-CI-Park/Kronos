<script lang="ts">
  import { onMount } from 'svelte';
  import {
    rlApi,
    type RlCostGateResponse,
    type RlProgressResponse,
    type RlRunDetail,
    type RlRunRecord,
    type RlTableRow,
  } from '$lib/rlApi';
  import { errorMessage } from '$lib/rlRows';
  import RLHero from './rlTrading/RLHero.svelte';
  import OrderbookReadinessCard from './rlTrading/OrderbookReadinessCard.svelte';
  import RiskSummaryCard from './rlTrading/RiskSummaryCard.svelte';
  import RunSelector from './rlTrading/RunSelector.svelte';
  import RunDetailCard from './rlTrading/RunDetailCard.svelte';
  import OpeningWorkflowCard from './rlTrading/OpeningWorkflowCard.svelte';
  import ParticipantProxyCard from './rlTrading/ParticipantProxyCard.svelte';
  import EvidenceCharts from './rlTrading/EvidenceCharts.svelte';
  import RunTables from './rlTrading/RunTables.svelte';
  import { costGatePassCount } from './rlTrading/chartOptions';
  import ResearchStatusShell from './ResearchStatusShell.svelte';

  let runs = $state<readonly RlRunRecord[]>([]);
  let selectedName = $state('');
  let selectedRun = $state<RlRunDetail | null>(null);
  let progress = $state<RlProgressResponse | null>(null);
  let costGate = $state<RlCostGateResponse | null>(null);
  let leaderboardRows = $state<readonly RlTableRow[]>([]);
  let trades = $state<readonly RlTableRow[]>([]);
  let actions = $state<readonly RlTableRow[]>([]);
  let equity = $state<readonly RlTableRow[]>([]);
  let episodes = $state<readonly RlTableRow[]>([]);
  let participantProxyRows = $state<readonly RlTableRow[]>([]);
  let orderbookPersistenceRows = $state<readonly RlTableRow[]>([]);
  let participantStudyRows = $state<readonly RlTableRow[]>([]);
  let featureAblationRows = $state<readonly RlTableRow[]>([]);
  let ruleFilterControlRows = $state<readonly RlTableRow[]>([]);
  let ruleFilterAblationRows = $state<readonly RlTableRow[]>([]);
  let ruleFilterFailureRows = $state<readonly RlTableRow[]>([]);
  let loading = $state(false);
  let detailLoading = $state(false);
  let error = $state<string | null>(null);
  const detailField = (key: string): unknown => selectedRun?.summary?.[key] ?? selectedRun?.detail?.[key];
  const textValue = (value: unknown, fallback = '—'): string => value == null || value === '' ? fallback : String(value);

  const ruleRun = $derived(
    runs.find((run) => run.strategy_context?.line === 'rule_mainline' || run.artifact_type === 'baseline') ?? null
  );
  const openingCandidateRun = $derived(
    runs.find((run) => run.artifact_type === 'opening_30m_rl_workflow' && run.name.includes('oos_candidate')) ??
      runs.find((run) => run.artifact_type === 'opening_30m_rl_workflow') ??
      null
  );
  const readinessRun = $derived(runs.find((run) => run.artifact_type === 'orderbook_rl_readiness') ?? null);
  const gateRows = $derived<readonly RlTableRow[]>(costGate?.gate?.rows ?? []);
  const progressPct = $derived(progress?.overall_progress_pct ?? 0);
  const selectedLabel = $derived(
    selectedRun?.strategy_context?.label ?? ruleRun?.strategy_context?.label ?? 'RULE MAINLINE'
  );
  const selectedVerdict = $derived(
    textValue(
      selectedRun?.strategy_context?.readiness_status ??
        detailField('verdict') ??
        detailField('status') ??
        detailField('promotion_status'),
      'unknown'
    )
  );
  const selectedLine = $derived(
    selectedRun?.strategy_context?.line === 'rule_mainline' || selectedRun?.artifact_type === 'baseline'
      ? 'RULE baseline / not RL'
      : selectedRun?.strategy_context?.is_reinforcement_learning
        ? 'RL experiment / research-only'
        : 'evidence artifact / research-only'
  );
  const selectedCost = $derived(
    textValue(selectedRun?.strategy_context?.risk_policy_summary?.cost_bps ?? detailField('cost_bps') ?? detailField('cost_round_trip_bp'), '23') + 'bp'
  );
  const selectedBaseline = $derived(textValue(selectedRun?.strategy_context?.primary_baseline ?? detailField('baseline') ?? 'ts_imb RULE baseline'));
  const selectedDrawdown = $derived(textValue(detailField('max_drawdown_pct') ?? detailField('max_drawdown') ?? detailField('max_dd_pct')));
  const selectedTradeCount = $derived(textValue(detailField('trade_count') ?? detailField('trades') ?? trades.length));

  const rlStatusLocks = [
    { label: 'live trading', value: 'false', tone: 'danger' },
    { label: 'broker/order/account', value: 'false', tone: 'danger' },
    { label: 'paper forward', value: 'false', tone: 'danger' },
    { label: 'model build unlock', value: 'false', tone: 'danger' },
    { label: 'profit readiness', value: 'false', tone: 'danger' },
    { label: 'cost assumption', value: '23bp', tone: 'warn' },
  ] as const;
  const rlStatusBlockers = [
    'ts_imb는 RL이 아니라 RULE baseline이며, RL 실험은 비교·반증 산출물입니다.',
    'NO-GO, baseline delta, drawdown, trade count, cost gate를 먼저 확인해야 합니다.',
    'opening_30m/factory 산출물은 별도 검증 lane이며 live-ready 근거가 아닙니다.',
  ] as const;
  const rlNextInspection = [
    '선택 run의 verdict와 strategy_context를 먼저 확인합니다.',
    '23bp cost gate, baseline 대비, drawdown, trade count를 확인합니다.',
    '원시 테이블은 마지막에 열어 원인 분석용으로만 사용합니다.',
  ] as const;
  onMount(() => {
    void loadDashboard();
  });

  function choosePreferredRun(candidates: readonly RlRunRecord[]): RlRunRecord | undefined {
    return (
      candidates.find((run) => run.artifact_type === 'opening_30m_rule_filter') ??
      candidates.find((run) => run.artifact_type === 'opening_30m_rl_workflow' && run.name.includes('oos_candidate')) ??
      candidates.find((run) => run.artifact_type === 'opening_30m_rl_workflow') ??
      candidates.find((run) => run.strategy_context?.line === 'rule_mainline') ??
      candidates.find((run) => run.artifact_type === 'baseline') ??
      candidates.find((run) => run.artifact_type === 'performance_leaderboard') ??
      candidates[0]
    );
  }

  async function loadDashboard(): Promise<void> {
    loading = true;
    error = null;
    try {
      const [runPayload, progressPayload] = await Promise.all([rlApi.rlRuns(50), rlApi.rlProgress()]);
      runs = runPayload?.runs ?? [];
      progress = progressPayload;
      const preferred = choosePreferredRun(runs);
      if (preferred) await selectRun(preferred.name, runs);
    } catch (caught) {
      error = errorMessage(caught, 'RL dashboard load failed');
    } finally {
      loading = false;
    }
  }

  async function loadOptionalRows(name: string, table: string): Promise<readonly RlTableRow[]> {
    try {
      return (await rlApi.rlTable(name, table, 200)).rows ?? [];
    } catch (caught) {
      if (caught instanceof Error) return [];
      throw caught;
    }
  }

  async function selectRun(name: string, runPool: readonly RlRunRecord[] = runs): Promise<void> {
    selectedName = name;
    detailLoading = true;
    error = null;
    try {
      const costRun = runPool.find((run) => run.artifact_type === 'cost_gate');
      const leaderboardRun = runPool.find((run) => run.artifact_type === 'performance_leaderboard');
      const [detail, leaderboard, tradePayload, actionPayload, equityPayload, episodePayload, gatePayload] =
        await Promise.all([
          rlApi.rlRun(name),
          leaderboardRun ? rlApi.rlTable(leaderboardRun.name, 'leaderboard', 200) : Promise.resolve(null),
          rlApi.rlTrades(name, 160),
          rlApi.rlActions(name, 2000),
          rlApi.rlEquity(name, 360),
          rlApi.rlEpisodes(name, 160),
          costRun ? rlApi.rlCostGate(costRun.name, 120) : Promise.resolve(null),
        ]);
      selectedRun = detail;
      ruleFilterControlRows = [];
      ruleFilterAblationRows = [];
      ruleFilterFailureRows = [];
      if (detail.artifact_type === 'opening_30m_rule_filter') {
        const [ruleEquity, ruleBuckets, ruleControls, ruleAblations, ruleFailures, ruleOpportunity, proxyRows, orderbookRows] = await Promise.all([
          loadOptionalRows(name, 'rule_filter_equity_curve'),
          loadOptionalRows(name, 'rule_filter_time_buckets'),
          loadOptionalRows(name, 'rule_filter_controls'),
          loadOptionalRows(name, 'rule_filter_ablations'),
          loadOptionalRows(name, 'rule_filter_failure_reasons'),
          loadOptionalRows(name, 'rule_filter_opportunity_cost'),
          loadOptionalRows(name, 'rule_filter_proxy_availability'),
          loadOptionalRows(name, 'rule_filter_orderbook_persistence'),
        ]);
        leaderboardRows = [];
        costGate = null;
        trades = ruleBuckets;
        actions = ruleFailures;
        equity = ruleEquity;
        episodes = ruleOpportunity;
        participantProxyRows = proxyRows;
        orderbookPersistenceRows = orderbookRows;
        participantStudyRows = [];
        featureAblationRows = ruleAblations;
        ruleFilterControlRows = ruleControls;
        ruleFilterAblationRows = ruleAblations;
        ruleFilterFailureRows = ruleFailures;
      } else if (detail.artifact_type === 'opening_30m_rl_workflow') {
        const [candidateEquity, candidateBuckets, candidateControls, candidateAblations, proxyRows, orderbookRows, studyRows, ablationRows] = await Promise.all([
          loadOptionalRows(name, 'candidate_equity_curve'),
          loadOptionalRows(name, 'candidate_time_buckets'),
          loadOptionalRows(name, 'candidate_controls'),
          loadOptionalRows(name, 'candidate_ablations'),
          loadOptionalRows(name, 'proxy_availability'),
          loadOptionalRows(name, 'orderbook_persistence'),
          loadOptionalRows(name, 'participant_study_groups'),
          loadOptionalRows(name, 'feature_ablation'),
        ]);
        leaderboardRows = [];
        costGate = null;
        trades = candidateBuckets;
        actions = [];
        equity = candidateEquity;
        episodes = candidateControls;
        participantProxyRows = proxyRows;
        orderbookPersistenceRows = orderbookRows;
        participantStudyRows = studyRows;
        featureAblationRows = candidateAblations.length ? candidateAblations : ablationRows;
      } else {
        leaderboardRows = leaderboard?.rows ?? [];
        trades = tradePayload?.rows ?? [];
        actions = actionPayload?.rows ?? [];
        equity = equityPayload?.rows ?? [];
        episodes = episodePayload?.rows ?? [];
        costGate = gatePayload;
        participantProxyRows = [];
        orderbookPersistenceRows = [];
        participantStudyRows = [];
        featureAblationRows = [];
        ruleFilterControlRows = [];
        ruleFilterAblationRows = [];
        ruleFilterFailureRows = [];
      }
    } catch (caught) {
      error = errorMessage(caught, `${name} detail load failed`);
    } finally {
      detailLoading = false;
    }
  }
</script>

<RLHero progressPct={progressPct} costGatePassCount={costGatePassCount(gateRows)} />
<ResearchStatusShell
  pageId="rl-trading"
  eyebrow="Trading · Research Command Center"
  title="RL Trading은 증거 검토 화면입니다"
  verdict="NO-GO / NOT LIVE-READY / RULE baseline first"
  summary="이 화면은 RULE baseline, RL experiment, cost gate, drawdown, trade count를 비교해 실패와 blocker를 먼저 보여줍니다. 매매 실행·브로커·계좌·수익 보장 기능은 없습니다."
  locks={rlStatusLocks}
  blockers={rlStatusBlockers}
  nextActions={rlNextInspection}
/>
<section class="card rl-command-cockpit" data-rl-evidence-command-cockpit>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">Review flow · before raw tables</div>
      <h2 class="text-h3">선택 산출물 판정 먼저 보기</h2>
      <p class="text-muted">raw table을 열기 전에 RULE/RL 구분, selected verdict, 23bp cost, baseline, drawdown, trade count를 확인합니다.</p>
    </div>
    <span class="pill danger"><span class="dot"></span>NOT LIVE-READY</span>
  </div>
  <div class="mini-grid" style="margin-top:14px">
    <div><span>Rule/RL distinction</span><b>{selectedLine}</b></div>
    <div><span>Selected verdict</span><b>{selectedVerdict}</b></div>
    <div><span>Cost assumption</span><b>{selectedCost}</b></div>
    <div><span>Baseline</span><b>{selectedBaseline}</b></div>
    <div><span>Drawdown</span><b>{selectedDrawdown}</b></div>
    <div><span>Trade count</span><b>{selectedTradeCount}</b></div>
  </div>
  <p class="text-muted safety-note">model/live/paper/profit locks remain false. 이 요약은 evidence triage이며 실행·주문·수익성 판단이 아닙니다.</p>
</section>
{#if error}
  <section class="card error-card">
    <div class="card-title">강화학습 대시보드 조회 실패</div>
    <p class="text-muted">{error}</p>
  </section>
{/if}
<OrderbookReadinessCard run={readinessRun ?? openingCandidateRun} />
<section class="rl-layout">
  <RunSelector runs={runs} selectedName={selectedName} onSelect={(name) => void selectRun(name)} />
  <div class="stack" style="--gap:16px;min-width:0">
    {#if loading && !runs.length}
      <section class="card"><p class="text-muted">강화학습 산출물을 불러오는 중...</p></section>
    {/if}
    <RiskSummaryCard ruleRun={ruleRun} selectedLabel={selectedLabel} />
    <RunDetailCard run={selectedRun} loading={detailLoading} />
    <OpeningWorkflowCard run={selectedRun} {progress} />
    <ParticipantProxyCard
      run={selectedRun}
      proxyRows={participantProxyRows}
      orderbookRows={orderbookPersistenceRows}
      studyRows={participantStudyRows}
      ablationRows={featureAblationRows}
    />
    <EvidenceCharts
      {leaderboardRows}
      gateRows={gateRows}
      equityRows={equity}
      actionRows={actions}
      episodeRows={episodes}
      tradeRows={trades}
      {selectedName}
    />
    <RunTables leaderboardRows={leaderboardRows} tradeRows={trades} ruleFilterControlRows={ruleFilterControlRows} ruleFilterAblationRows={ruleFilterAblationRows} ruleFilterFailureRows={ruleFilterFailureRows} />
  </div>
</section>

<style>
  .rl-layout {
    display: grid;
    grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }
  :global(.run-list) {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 620px;
    overflow: auto;
  }
  :global(.run-list button) {
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--card);
    padding: 10px;
    text-align: left;
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  :global(.run-list button.active) {
    border-color: #14b8a6;
    box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.16);
  }
  :global(.mini-grid) {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
  }
  :global(.mini-grid div) {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 10px;
    background: rgba(148, 163, 184, 0.06);
  }
  :global(.mini-grid span) {
    display: block;
    color: var(--text-muted);
    font-size: 12px;
    margin-bottom: 4px;
  }
  :global(.chart-grid) {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
  }
  :global(.safety-note) {
    margin-top: 10px;
  }
  @media (max-width: 900px) {
    .rl-layout {
      grid-template-columns: 1fr;
    }
  }
</style>

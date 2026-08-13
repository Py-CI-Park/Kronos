<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import { loadTelemetry, loadTelemetryRuns, type TelemetryRun, type TelemetrySnapshot } from '../../api/telemetryApi';
  import ComparisonCharts from './ComparisonCharts.svelte';
  import DailyCloseProcessFlow from './DailyCloseProcessFlow.svelte';
  import { summarizeSnapshot, type EvaluationEntry } from './evaluationModel';

  let runs = $state<readonly TelemetryRun[]>([]);
  let leftId = $state('');
  let rightId = $state('');
  let left = $state<TelemetrySnapshot | null>(null);
  let right = $state<TelemetrySnapshot | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let refreshGeneration = 0;

  const leftRun = $derived(runs.find((run) => run.run_id === leftId) ?? null);
  const rightRun = $derived(runs.find((run) => run.run_id === rightId) ?? null);
  const sameLaneRuns = $derived(leftRun ? runs.filter((run) => run.lane === leftRun.lane) : []);
  const entries = $derived.by(() => {
    const rows: EvaluationEntry[] = [];
    if (leftRun && left) rows.push({ run: leftRun, snapshot: left });
    if (rightRun && right) rows.push({ run: rightRun, snapshot: right });
    return rows;
  });
  const noGoCount = $derived(entries.filter((entry) => entry.run.status.includes('NO')).length);
  const kpis = $derived([
    { label: '비교 LANE', value: leftRun?.lane ?? 'MISSING', detail: '서로 다른 lane은 비교 차단', tone: 'neutral' as const },
    { label: '선택 RUN', value: String(entries.length), detail: '최대 2개 실행', tone: 'neutral' as const },
    { label: 'NO-GO', value: String(noGoCount), detail: '실패 판정을 그대로 보존', tone: noGoCount > 0 ? 'danger' as const : 'neutral' as const },
    { label: '비교 성격', value: 'DESCRIPTIVE', detail: '표본 기술 비교 · 순위가 아님', tone: 'warning' as const },
  ]);

  async function refresh(): Promise<void> {
    const generation = ++refreshGeneration;
    const requestedLeftId = leftId;
    const requestedRightId = rightId;
    if (!leftId) {
      left = null;
      right = null;
      error = null;
      loading = false;
      return;
    }
    loading = true;
    if (!rightId) {
      const leftResult = await loadTelemetry(requestedLeftId);
      if (generation !== refreshGeneration) return;
      if (leftResult.ok === false) {
        left = null;
        error = leftResult.message;
      } else {
        left = leftResult.data;
        error = null;
      }
      right = null;
      loading = false;
      return;
    }
    const [leftResult, rightResult] = await Promise.all([loadTelemetry(requestedLeftId), loadTelemetry(requestedRightId)]);
    if (generation !== refreshGeneration) return;
    if (leftResult.ok === false) {
      left = null;
      right = null;
      error = leftResult.message;
    } else if (rightResult.ok === false) {
      left = null;
      right = null;
      error = rightResult.message;
    }
    else {
      left = leftResult.data;
      right = rightResult.data;
      error = null;
    }
    loading = false;
  }

  function selectLeft(): void {
    const candidates = runs.filter((run) => run.lane === leftRun?.lane && run.run_id !== leftId);
    rightId = candidates[0]?.run_id ?? '';
    void refresh();
  }

  onMount(async () => {
    const result = await loadTelemetryRuns();
    if (result.ok === false) {
      error = result.message;
      loading = false;
      return;
    }
    runs = result.data.items;
    leftId = runs.find((run) => run.run_id === 'stom_orderbook_dqn_smoke')?.run_id ?? runs[0]?.run_id ?? '';
    const lane = runs.find((run) => run.run_id === leftId)?.lane;
    rightId = runs.find((run) => run.lane === lane && run.run_id !== leftId)?.run_id ?? '';
    await refresh();
  });
</script>

<div class="evaluation v6-page" data-evaluation-workspace>
  <PageHeader eyebrow="EVALUATION" title="같은 증거 lane에서만 비교" description="공식 판정과 기록 텔레메트리를 함께 보되, 표본 차이를 수익 모델 순위로 바꾸지 않습니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'DESCRIPTIVE'} />
  <KpiStrip items={kpis} />
  <DailyCloseProcessFlow />

  <ResearchPanel title="비교 실행 선택" description="왼쪽 실행과 같은 lane의 실행만 오른쪽 후보로 허용합니다.">
    <div class="selectors"><label>기준 실행<select bind:value={leftId} onchange={selectLeft}>{#each runs as run}<option value={run.run_id}>{run.lane} · {run.status} · {run.name}</option>{/each}</select></label><label>비교 실행<select bind:value={rightId} onchange={() => void refresh()} disabled={sameLaneRuns.length < 2}>{#each sameLaneRuns as run}<option value={run.run_id} disabled={run.run_id === leftId}>{run.status} · {run.name}</option>{/each}</select></label><button type="button" onclick={() => void refresh()} disabled={loading}>{rightId ? '비교 새로고침' : '기준 실행 새로고침'}</button></div>
  </ResearchPanel>

  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if leftRun && sameLaneRuns.length < 2}<p class="notice" role="status">같은 lane의 두 번째 실행이 아직 없습니다. 기준 실행 1건의 기록은 아래에서 확인할 수 있으며 비교 순위는 만들지 않습니다.</p>{/if}
  {#if entries.length}
    <ResearchPanel title="동일 lane 텔레메트리" description="그래프의 point 수·표본 방식이 다르면 직접 우열을 판정하지 않습니다."><ComparisonCharts {entries} /></ResearchPanel>
    <ResearchPanel title="표본 지표 매트릭스" description="공식 OOS 통계가 아니라 선택된 telemetry point의 기술 요약입니다.">
      <div class="table-wrap"><table><thead><tr><th>실행</th><th>판정</th><th>알고리즘</th><th>표본 reward</th><th>최근 equity</th><th>단위 계약</th><th>표본 낙폭</th><th>point</th><th>sampling</th></tr></thead><tbody>{#each entries as entry}{@const summary = summarizeSnapshot(entry.snapshot)}<tr><th>{entry.run.name}</th><td data-status={entry.run.status}>{entry.run.status}</td><td>{entry.run.algorithm}</td><td>{summary.sampleRewardLabel}</td><td>{summary.latestEquityLabel}</td><td>{summary.equityMetricLabel}</td><td>{summary.sampleDrawdownPct === null ? 'NOT_CALCULATED' : `${summary.sampleDrawdownPct.toFixed(2)}%`}</td><td>{summary.pointCount}</td><td>{summary.sampling}</td></tr>{/each}</tbody></table></div>
    </ResearchPanel>
  {/if}
</div>

<style>
  .evaluation{display:flex;flex-direction:column;gap:16px;min-width:0}.selectors{display:grid;grid-template-columns:1fr 1fr auto;gap:12px;align-items:end}.selectors label{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:.68rem;font-weight:800}select,button{min-width:0;height:40px;border:1px solid var(--border-strong);border-radius:8px;padding:0 10px;background:var(--surface-sunken);color:var(--fg);font:inherit}button{background:var(--accent);color:var(--on-accent);font-weight:900;cursor:pointer}.table-wrap{max-width:100%;overflow:auto}table{width:100%;border-collapse:collapse;font-size:.7rem}th,td{padding:9px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}thead th{color:var(--muted)}tbody th{color:var(--fg-strong)}td[data-status*=NO]{color:var(--danger);font-weight:900}.error,.notice{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}.notice{border-color:var(--warn);background:var(--surface-sunken);color:var(--warn);font-size:.72rem;line-height:1.55}
  @media(max-width:760px){.selectors{grid-template-columns:1fr}.selectors button{width:100%}}
</style>

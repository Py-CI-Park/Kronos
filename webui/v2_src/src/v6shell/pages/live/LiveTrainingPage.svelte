<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import { loadTelemetry, loadTelemetryRuns, type TelemetryRun, type TelemetrySnapshot } from '../../api/telemetryApi';
  import ActionTimeline from './ActionTimeline.svelte';
  import TelemetryCharts from './TelemetryCharts.svelte';
  import { equityPresentation, rewardPresentation } from './telemetryMetricModel';

  let runs = $state<readonly TelemetryRun[]>([]);
  let selected = $state('');
  let snapshot = $state<TelemetrySnapshot | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let autoRefresh = $state(true);
  let timer: ReturnType<typeof setInterval> | null = null;

  const latest = $derived(snapshot?.points.at(-1) ?? null);
  const selectedRun = $derived(runs.find((run) => run.run_id === selected) ?? null);
  const equityMetric = $derived(snapshot ? equityPresentation(snapshot.points) : null);
  const rewardMetric = $derived(snapshot ? rewardPresentation(snapshot.points) : null);
  const kpis = $derived([
    { label: '최근 STEP', value: latest ? new Intl.NumberFormat('ko-KR').format(latest.step) : 'MISSING', detail: latest?.phase ?? 'phase 없음', tone: 'neutral' as const },
    { label: '실행 판정', value: selectedRun?.status ?? 'MISSING', detail: selectedRun?.algorithm ?? 'algorithm 없음', tone: selectedRun?.status.includes('NO') ? 'danger' as const : 'neutral' as const },
    { label: equityMetric?.title ?? '기록 equity', value: equityMetric?.latestLabel ?? 'MISSING', detail: equityMetric?.notice ?? '단위 정보 없음', tone: equityMetric?.latestLabel.startsWith('-') ? 'danger' as const : 'neutral' as const },
    { label: '표본 보상 합계', value: rewardMetric?.latestLabel ?? 'MISSING', detail: rewardMetric?.notice ?? '단위 정보 없음', tone: rewardMetric?.latestLabel.startsWith('-') ? 'warning' as const : 'neutral' as const },
    { label: '표시 POINT', value: String(snapshot?.points.length ?? 0), detail: snapshot?.sampling ?? 'MISSING', tone: 'neutral' as const },
  ]);

  async function refresh(): Promise<void> {
    if (!selected) return;
    const result = await loadTelemetry(selected);
    if (result.ok === false) error = result.message;
    else {
      snapshot = result.data;
      error = null;
    }
    loading = false;
  }

  async function initialize(): Promise<void> {
    const result = await loadTelemetryRuns();
    if (result.ok === false) {
      error = result.message;
      loading = false;
      return;
    }
    runs = result.data.items;
    selected = runs.find((run) => run.run_id === 'stom_orderbook_dqn_smoke')?.run_id ?? runs[0]?.run_id ?? '';
    await refresh();
  }

  function selectRun(): void {
    snapshot = null;
    loading = true;
    void refresh();
  }

  function modeMessage(mode: TelemetrySnapshot['follow_mode']): string {
    if (mode === 'FOLLOWING_FILE') return '최근 30초 안에 event 파일이 변경되어 추적 중입니다.';
    if (mode === 'HISTORICAL_SNAPSHOT') return '실시간 스트림이 아님 · 기록된 과거 실행 스냅샷입니다.';
    return '알 수 없는 텔레메트리 상태입니다.';
  }

  onMount(() => {
    void initialize();
    timer = setInterval(() => { if (autoRefresh) void refresh(); }, 5_000);
  });
  onDestroy(() => { if (timer !== null) clearInterval(timer); });
</script>

<div class="live-page v6-page" data-live-training>
  <PageHeader eyebrow="RL TELEMETRY" title="학습 진행과 성과를 한 화면에서" description="실행 파일에 실제로 기록된 reward·equity·loss·exploration만 읽습니다." status={loading ? 'LOADING' : snapshot?.follow_mode ?? 'UNAVAILABLE'} />
  <KpiStrip items={kpis} />

  <ResearchPanel title="실행 선택" description="event 파일이 존재하는 연구 실행만 표시합니다.">
    <div class="controls">
      <label>연구 실행<select bind:value={selected} onchange={selectRun} disabled={loading}>{#each runs as run}<option value={run.run_id}>{run.status} · {run.name} · {(run.event_bytes / 1_048_576).toFixed(1)} MB</option>{/each}</select></label>
      <label class="toggle"><input type="checkbox" bind:checked={autoRefresh} />5초마다 변경 확인</label>
      <button type="button" onclick={() => void refresh()} disabled={loading || !selected}>지금 새로고침</button>
    </div>
  </ResearchPanel>

  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if snapshot}
    <aside class:following={snapshot.follow_mode === 'FOLLOWING_FILE'}>
      <strong>{snapshot.follow_mode}</strong>
      <span>{modeMessage(snapshot.follow_mode)}</span>
      <small>{snapshot.updated_at} · {snapshot.sampling} · 오류 행 {snapshot.invalid_lines}</small>
    </aside>
    <section class="reading-order" aria-label="학습 화면 읽는 순서">
      <article><span>01</span><div><b>학습 신호</b><small>reward·loss·exploration이 안정되는지 봅니다.</small></div></article>
      <article><span>02</span><div><b>경제 경로</b><small>단위가 선언된 NAV에만 drawdown을 계산합니다.</small></div></article>
      <article><span>03</span><div><b>정책 행동</b><small>시간대별 행동·쏠림·최근 결정을 확인합니다.</small></div></article>
      <article><span>04</span><div><b>공식 판정</b><small>이 화면만으로 GO·수익성을 판정하지 않습니다.</small></div></article>
    </section>
    <ResearchPanel title="학습·성과 곡선" description="보상 개선과 경제적 성과를 분리해 읽습니다."><TelemetryCharts points={snapshot.points} /></ResearchPanel>
    <ResearchPanel title="행동 분석" description="기록 시각·step·행동 분포·최근 결정을 하나의 표본으로 봅니다."><ActionTimeline points={snapshot.points} /></ResearchPanel>
  {/if}
</div>

<style>
  .live-page{display:flex;flex-direction:column;gap:16px;min-width:0}.controls{display:grid;grid-template-columns:minmax(260px,1fr) auto auto;gap:14px;align-items:end}.controls label{display:flex;flex-direction:column;gap:6px;color:var(--muted);font-size:.68rem;font-weight:800}.controls select,.controls button{min-width:0;height:40px;border:1px solid var(--border-strong);border-radius:8px;padding:0 10px;background:var(--surface-sunken);color:var(--fg);font:inherit}.controls button{background:var(--accent);color:var(--on-accent);font-weight:900;cursor:pointer}.controls .toggle{height:40px;flex-direction:row;align-items:center}.toggle input{accent-color:var(--accent)}aside{display:grid;grid-template-columns:auto 1fr auto;gap:8px 14px;align-items:center;border:1px solid var(--warn);border-radius:10px;padding:12px 14px;background:var(--surface-raised)}aside.following{border-color:var(--success)}aside strong{color:var(--warn);font:900 .68rem var(--font-mono)}aside.following strong{color:var(--success)}aside span{color:var(--fg);font-size:.74rem}aside small{color:var(--muted);font:.61rem var(--font-mono)}.reading-order{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.reading-order article{display:grid;grid-template-columns:auto 1fr;gap:8px;border:1px solid var(--border);border-radius:9px;padding:10px;background:var(--surface-raised)}.reading-order span{color:var(--accent);font:900 .58rem var(--font-mono)}.reading-order div{display:flex;min-width:0;flex-direction:column;gap:3px}.reading-order b{color:var(--fg-strong);font-size:.7rem}.reading-order small{color:var(--muted);font-size:.61rem;line-height:1.45}.error{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}
  @media(max-width:900px){.reading-order{grid-template-columns:1fr 1fr}}
  @media(max-width:760px){.controls{grid-template-columns:1fr}.controls button{width:100%}aside{grid-template-columns:1fr}.reading-order{grid-template-columns:1fr}}
</style>

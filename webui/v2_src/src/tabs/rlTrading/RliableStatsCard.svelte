<script lang="ts">
  // G6 — rliable reliability statistics (IQM / mean / median / optimality gap with
  // 95% stratified-bootstrap CIs) across recorded RL runs, grouped by algorithm.
  // 백엔드 read-only 예외 라우트 GET /api/rl/rliable-stats (offline artifact) 를 그대로 읽는다.
  // RESEARCH_ONLY — 수익성/GO 근거가 아니라 run 간 분산(reliability)만 정량화한다.
  import { onMount } from 'svelte';
  import { rlApi, type RlRliableMetric, type RlRliableStatsResponse } from '$lib/rlApi';
  import { num } from '$lib/rlRows';

  let stats = $state<RlRliableStatsResponse | null>(null);
  let loading = $state(true);
  let requestError = $state<string | null>(null);
  let unavailableReason = $state<string | null>(null);

  const algorithms = $derived(stats?.algorithms ?? []);
  const aggregates = $derived(stats?.aggregates ?? {});
  const metadata = $derived(stats?.metadata ?? {});
  const hasStats = $derived(algorithms.length > 0 && Object.keys(aggregates).length > 0);
  const confidencePct = $derived(Math.round((stats?.confidence_interval ?? 0.95) * 100));

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    requestError = null;
    unavailableReason = null;
    try {
      const payload = await rlApi.rliableStats();
      if (payload === null) {
        throw new Error('Reliability statistics request returned no payload.');
      }
      stats = payload;
      unavailableReason = payload.available === false
        ? (payload.error ?? payload.note ?? 'The backend marked reliability statistics unavailable.')
        : null;
    } catch (error) {
      requestError = error instanceof Error ? error.message : 'Reliability statistics request failed.';
    } finally {
      loading = false;
    }
  }

  function point(metric: RlRliableMetric | undefined): string {
    return metric ? num(metric.point, 4) : '-';
  }

  function interval(metric: RlRliableMetric | undefined): string {
    if (!metric) return '-';
    return `[${num(metric.ci_lower, 4)}, ${num(metric.ci_upper, 4)}]`;
  }

  function costLabel(values: readonly number[] | null | undefined): string {
    if (!values || values.length === 0) return '-';
    return values.map((value) => num(value, 1)).join(' / ');
  }
</script>

<section class="card" data-rl-rliable-stats-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">RLIABLE RELIABILITY STATS · RESEARCH_ONLY</div>
      <div class="card-title">알고리즘별 IQM·mean·median·optimality gap ({confidencePct}% CI)</div>
    </div>
    <span class="pill warn"><span class="dot"></span>RESEARCH_ONLY</span>
  </div>
  <p class="text-caption safety-note">
    stratified-bootstrap reliability 통계입니다. 수익성 추정치나 GO/NO-GO 판정이 아니며, live/broker/order/profit
    근거가 아닙니다. 점수는 run별 정규화 terminal-equity 배수(final/first equity)이며 알고리즘별 run을 seed로 집계합니다.
  </p>
  {#if loading}
    <p class="text-muted">reliability 통계 로딩 중 · 연구 전용...</p>
  {:else if requestError}
    <p class="text-muted">reliability 통계 요청 실패: {requestError}</p>
    <button type="button" class="retry-btn" onclick={() => void load()}>Retry</button>
  {:else if unavailableReason}
    <p class="text-muted">통계 사용 불가 · 연구 전용: {unavailableReason}</p>
  {:else if !hasStats}
    <p class="text-muted">통계 없음 · 연구 전용 (백엔드가 rliable 산출물을 반환하지 않았습니다).</p>
  {:else}
    <div class="table-wrap rliable-wrap">
      <table>
        <thead>
          <tr>
            <th>algorithm</th>
            <th>IQM (point)</th>
            <th>IQM {confidencePct}% CI</th>
            <th>mean</th>
            <th>median</th>
            <th>optimality gap</th>
            <th>seeds</th>
            <th>cost_bps</th>
          </tr>
        </thead>
        <tbody>
          {#each algorithms as algorithm}
            {@const agg = aggregates[algorithm]}
            {@const meta = metadata[algorithm]}
            <tr>
              <td class="algo-cell">{algorithm}</td>
              <td class="mono">{point(agg?.iqm)}</td>
              <td class="mono">{interval(agg?.iqm)}</td>
              <td class="mono">{point(agg?.mean)}</td>
              <td class="mono">{point(agg?.median)}</td>
              <td class="mono">{point(agg?.optimality_gap)}</td>
              <td class="mono">{meta?.seed_count ?? '-'}</td>
              <td class="mono">{costLabel(meta?.cost_bps)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-caption" style="margin-top:6px">
      IQM(interquartile mean)은 outlier에 강건한 rliable 권장 지표입니다. CI가 넓거나 겹치면 run 간 분산이 커서 결론을
      내리기 어렵다는 뜻이며, 이 표만으로 알고리즘 우열이나 수익성을 주장하지 않습니다.
    </p>
  {/if}
</section>

<style>
  .rliable-wrap {
    max-height: 320px;
    overflow: auto;
  }
  .algo-cell {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum', 'zero';
  }
  .retry-btn {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface);
    padding: 4px 12px;
    font: 600 11px/1 var(--font-display);
    cursor: pointer;
  }
</style>

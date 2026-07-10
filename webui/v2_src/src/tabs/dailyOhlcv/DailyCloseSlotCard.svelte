<script lang="ts">
  import type {
    DailyCloseSlotArtifactsResponse,
    DailyCloseSlotEquityResponse,
    DailyCloseSlotLatestResponse,
    DailyCloseSlotSelectionResponse,
  } from '$lib/dailyOhlcvApi';
  import Disclosure from '$lib/Disclosure.svelte';
  import { humanizeVerdict } from '$lib/verdictLabel';
  import CostSensitivityChart from '../../charts/CostSensitivityChart.svelte';
  import EquityDrawdownChart from '../../charts/EquityDrawdownChart.svelte';

  interface Props {
    latest: DailyCloseSlotLatestResponse | null;
    gate: DailyCloseSlotLatestResponse | null;
    artifacts: DailyCloseSlotArtifactsResponse | null;
    equity: DailyCloseSlotEquityResponse | null;
    selection: DailyCloseSlotSelectionResponse | null;
  }

  let { latest, gate, artifacts, equity, selection }: Props = $props();

  const requiredFallbackLabels = [
    'RESEARCH_ONLY',
    'EXPERIMENTAL_ONLY',
    'NO-GO_RESEARCH_ONLY/WATCH_RESEARCH_ONLY',
    'close_to_next_close_research_label',
    'non_executable upper bound',
    'price_basis unknown',
    'universe WATCH',
    '23bp round trip cost',
    'D3 re-ledgered when applicable',
  ] as const;
  const falseLockKeys = [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
  ] as const;

  const displayStatus = $derived(latest?.status ?? gate?.status ?? 'NOT_STARTED');
  const displayReadiness = $derived(latest?.readiness_status ?? gate?.readiness_status ?? 'NOT_STARTED');
  const labels = $derived(Array.from(new Set([...(latest?.labels ?? []), ...requiredFallbackLabels])));
  const sourceIds = $derived(latest?.source_run_ids ?? {});
  const gateReport = $derived((latest?.gate_report ?? gate?.gate_report ?? {}) as Record<string, unknown>);
  const d3Comparator = $derived((latest?.d3_comparator ?? {}) as Record<string, unknown>);
  const datasetLineage = $derived((latest?.dataset_lineage ?? {}) as Record<string, unknown>);
  const sampleScores = $derived(((latest?.samples?.policy_scores ?? []) as readonly Record<string, unknown>[]).slice(0, 5));
  const selectionRows = $derived((selection?.selection_rows ?? []).slice(0, 8));
  const equityPoints = $derived((equity?.series?.[0]?.points ?? []).slice(0, 8));
  const artifactRows = $derived((artifacts?.runs ?? []).slice(0, 5));
  const blockerRows = $derived(latest?.artifact_selection_errors ?? latest?.current_required_blockers ?? latest?.upstream_gate_blockers ?? []);
  const flagRows = $derived(falseLockKeys.map((key) => ({ key, value: flagText(latest?.[key] ?? gate?.[key] ?? equity?.[key] ?? selection?.[key]) })));
  const costScenarios = $derived(latest?.cost_scenarios ?? selection?.cost_scenarios ?? {});
  const zeroCost = $derived(costScenarios.zero_control_0bp ?? {});
  const baseCost = $derived(costScenarios.base_23bp ?? {});
  const stressCost = $derived(costScenarios.stress_46bp ?? {});
  const costComponents = $derived(latest?.cost_components ?? selection?.cost_components ?? []);
  const thresholdSelection = $derived(latest?.threshold_selection ?? selection?.threshold_selection ?? {});
  const walkForwardSummary = $derived(latest?.walk_forward_summary ?? {});
  const replaySummary = $derived(latest?.replay_summary ?? {});
  const selectedHoldSummary = $derived(latest?.selected_hold_summary ?? selection?.selected_hold_summary ?? {});
  const selectedHoldRows = $derived((selectedHoldSummary.rows ?? []).slice(0, 8));
  const replaySplitRows = $derived(Object.entries(replaySummary.split_counts ?? {}));
  const noClaimLabels = $derived(Array.from(new Set([...(latest?.no_claim_labels ?? []), ...(selection?.no_claim_labels ?? [])])));
  const dbAccess = $derived(latest?.daily_db_access ?? latest?.dataset_db_access ?? {});
  const sourceCounts = $derived(latest?.dataset_source_counts ?? {});
  const boundedScope = $derived(latest?.bounded_research_scope ?? {});

  // 0-symbol defect gloss (WP-S3): only rendered when the primary base_23bp
  // row actually selected 0 symbols. After WP-R1 the manifest may carry
  // chosen_is_no_trade_sentinel — branch the wording when readable, else
  // keep the known-defect copy (MissionControl.svelte wording, reused verbatim).
  const primarySelectedCount = $derived.by(() => {
    const rows = selectedHoldSummary.rows ?? [];
    const primaryId = selectedHoldSummary.primary_cost_scenario_id ?? latest?.primary_cost_scenario_id ?? 'base_23bp';
    const match = rows.find((row) => row.cost_scenario_id === primaryId) ?? rows[0];
    return match?.selected_count;
  });
  const isZeroSelectionDefect = $derived(typeof primarySelectedCount === 'number' && primarySelectedCount === 0);
  const sentinelValue = $derived((thresholdSelection as unknown as Record<string, unknown>)?.chosen_is_no_trade_sentinel);
  const zeroSelectionGloss = $derived(
    sentinelValue === true
      ? '23bp 하 무거래가 정직한 최적 (chosen_is_no_trade_sentinel=true)'
      : '피처 정규화 버그 · contextual_bandit 0종목 선택 (알려진 결함, FACT)'
  );

  function flagText(value: unknown): string {
    return value === false ? 'false' : value === true ? 'true' : 'MISSING';
  }

  function text(value: unknown, fallback = '—'): string {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function numberText(value: unknown): string {
    return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ko-KR') : text(value);
  }

  function costScenarioText(scenario: Partial<Record<'sell_tax_bp' | 'buy_commission_bp' | 'sell_commission_bp' | 'buy_slippage_bp' | 'sell_slippage_bp' | 'total_bp', unknown>>): string {
    return [
      `tax ${numberText(scenario.sell_tax_bp)}bp`,
      `buy_comm ${numberText(scenario.buy_commission_bp)}bp`,
      `sell_comm ${numberText(scenario.sell_commission_bp)}bp`,
      `buy_slip ${numberText(scenario.buy_slippage_bp)}bp`,
      `sell_slip ${numberText(scenario.sell_slippage_bp)}bp`,
      `total ${numberText(scenario.total_bp)}bp`,
    ].join(' · ');
  }

  function tone(status: string | undefined): string {
    if (!status) return '';
    if (status.includes('BLOCK')) return 'danger';
    if (status.includes('NO-GO')) return 'danger';
    if (status.includes('WATCH') || status.includes('RESEARCH_ONLY')) return 'warn';
    if (status === 'PASS') return 'success';
    return '';
  }
</script>

<!--
  Remodel: summary-first (status pill + guardrail notice + 4 KPIs + threshold/cost/policy)
  with all heavy evidence tucked into a Disclosure. Every data-daily-close-slot-* marker
  is preserved (QA contract) — only visual hierarchy changed.
-->
<section class="panel" data-daily-close-slot-card>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">Close-slot max-10 threshold/replay experiment · read-only evidence</div>
      <h2 class="text-h3">종가 매수 → 익일 종가 매도 10-slot 실험 증거</h2>
    </div>
    <span class="pill {tone(displayStatus)}" data-daily-close-slot-status><span class="dot"></span>연구용 · {humanizeVerdict(displayStatus)} · 실거래 아님</span>
  </div>

  <p class="text-muted" style="font-size:12px; margin-top:-4px">서버가 검증한 close-slot 산출물만 표시 · no live/broker/account/order/paper-forward/profitability/model-build/GO claim.</p>

  <div class="notice warn" data-daily-close-slot-guardrail>
    <span aria-hidden="true">⚠️</span>
    <div>
      <b>execution_realism={text(latest?.execution_realism, 'non_executable_upper_bound_without_preclose_features')}</b>
      · price_basis {text(latest?.price_basis, 'unknown')} · universe {text(latest?.universe_verdict, 'WATCH')} · D3 re-ledgered={text(d3Comparator.reledgered_through_close_slot_accounting ?? d3Comparator.present, 'when applicable')}
    </div>
  </div>

  <div class="grid-4-kpi" data-daily-close-slot-contract>
    <div class="metric"><div class="metric-label">readiness</div><div class="metric-value" style="font-size:17px">{displayReadiness}</div></div>
    <div class="metric"><div class="metric-label">slot / capital</div><div class="metric-value" style="font-size:15px">{numberText(latest?.slot_count)} slots · {numberText(latest?.total_capital_krw)} KRW</div></div>
    <div class="metric"><div class="metric-label">cost</div><div class="metric-value" style="font-size:18px">{numberText(latest?.round_trip_cost_bp)}bp<span class="metric-unit"> [{(latest?.cost_sensitivity_bp ?? [0, 23, 46]).join('/')}]</span></div></div>
    <div class="metric"><div class="metric-label">fill</div><div class="metric-value" style="font-size:13px">{text(latest?.fill_mode, 'close_to_next_close_research_label')}</div></div>
  </div>

  <div class="evidence-grid" data-daily-close-slot-v2-evidence>
    <div class="evidence-box" data-daily-close-slot-threshold-contract>
      <div class="text-eyebrow">max-10 threshold / cash-hold contract</div>
      <div class="mini-kv"><span>policy</span><strong>{text(thresholdSelection.policy, 'contextual_bandit_linear_train_only_score_and_pick')}</strong></div>
      <div class="mini-kv"><span>split / OOS fit rows</span><strong>{text(thresholdSelection.split, 'train')} · {numberText(thresholdSelection.oos_rows_used_for_fit ?? 0)}</strong></div>
      <div class="mini-kv"><span>threshold</span><strong>{text(thresholdSelection.threshold_text ?? thresholdSelection.threshold)} · metric {text(thresholdSelection.metric, 'mean_daily_reward_base_23bp')}</strong></div>
      <div class="mini-kv"><span>cardinality</span><strong>{numberText(thresholdSelection.max_slot_count ?? latest?.max_slot_count ?? latest?.slot_count ?? 10)} slots · {text(thresholdSelection.selection_cardinality ?? latest?.selection_cardinality, 'threshold_selected_0_to_10')} · hold_cash_action={text(thresholdSelection.hold_cash_action ?? latest?.hold_cash_action, 'true')}</strong></div>
      {#if isZeroSelectionDefect}
        <div class="notice warn" style="margin-top:8px; font-size:11.5px">{zeroSelectionGloss}</div>
      {/if}
    </div>

    <div class="evidence-box" data-daily-close-slot-cost-components>
      <div class="text-eyebrow">componentized costs · zero/base/stress</div>
      <div class="mini-kv"><span>zero_control_0bp</span><strong>{costScenarioText(zeroCost)}</strong></div>
      <div class="mini-kv"><span>base_23bp</span><strong>{costScenarioText(baseCost)}</strong></div>
      <div class="mini-kv"><span>stress_46bp</span><strong>{costScenarioText(stressCost)}</strong></div>
      <div class="mini-kv"><span>components</span><strong>{costComponents.join(', ') || 'sell_tax_bp, buy_commission_bp, sell_commission_bp, buy_slippage_bp, sell_slippage_bp'}</strong></div>
    </div>

    <div class="evidence-box" data-daily-close-slot-policy-scores>
      <div class="text-eyebrow">policy scores sample</div>
      {#each sampleScores as row}
        <div class="mini-kv"><span>{text(row.date)} · {text(row.code)}</span><strong>{text(row.policy)} · score {text(row.score)}</strong></div>
      {:else}
        <div class="notice">policy score sample 없음 · fail-closed or NOT_STARTED일 수 있습니다.</div>
      {/each}
    </div>
  </div>

  <div class="evidence-grid" data-daily-close-slot-report-charts>
    <div class="evidence-box">
      <div class="text-eyebrow">비용 민감도 · 0/23/46bp (base_23bp 기준 · 통제군 대비)</div>
      <CostSensitivityChart
        rows={selectedHoldSummary.rows ?? []}
        primaryScenarioId={selectedHoldSummary.primary_cost_scenario_id ?? latest?.primary_cost_scenario_id ?? 'base_23bp'}
        {costScenarios}
      />
    </div>
    <div class="evidence-box">
      <div class="text-eyebrow">research equity + drawdown · 누적 순손익</div>
      <EquityDrawdownChart {equity} />
    </div>
  </div>

  <Disclosure summary="세부 증거 (재현 · 선택/보유 · no-claim · 범위 · DB · 잠금 · 계보 · 라벨 · 선택코드 · equity · 산출물)" meta="threshold/replay evidence only">
    <div class="evidence-grid">
      <div class="evidence-box" data-daily-close-slot-replay-walk-forward>
        <div class="text-eyebrow">train-only replay / frozen validation-test</div>
        <div class="mini-kv"><span>walk-forward mode</span><strong>{text(walkForwardSummary.mode_id)}</strong></div>
        <div class="mini-kv"><span>windows / threshold grid</span><strong>{numberText(walkForwardSummary.window_count)} · {numberText(walkForwardSummary.threshold_grid_count)}</strong></div>
        <div class="mini-kv"><span>held-out splits</span><strong>{(walkForwardSummary.held_out_replay_splits ?? ['val', 'test']).join(', ')}</strong></div>
        <div class="mini-kv"><span>replay episodes / leaked fit feedback</span><strong>{numberText(replaySummary.episode_count)} · {numberText(replaySummary.held_out_feedback_used_for_fit_count ?? 0)}</strong></div>
        <div class="mini-list" style="margin-top:8px">
          {#each replaySplitRows as [split, count]}
            <div><span>{split}</span><strong>{numberText(count)} episode(s)</strong></div>
          {:else}
            <div><span>val/test</span><strong>frozen replay required</strong></div>
          {/each}
        </div>
      </div>

      <div class="evidence-box" data-daily-close-slot-selected-hold>
        <div class="text-eyebrow">selected / hold-cash counts</div>
        <div class="mini-kv"><span>primary cost</span><strong>{text(selectedHoldSummary.primary_cost_scenario_id ?? latest?.primary_cost_scenario_id, 'base_23bp')}</strong></div>
        <div class="mini-kv"><span>contract</span><strong>max {numberText(selectedHoldSummary.max_slot_count ?? 10)} · {text(selectedHoldSummary.selection_cardinality, 'threshold_selected_0_to_10')} · hold_cash_action={text(selectedHoldSummary.hold_cash_action, 'true')}</strong></div>
        {#each selectedHoldRows as row}
          <div class="mini-kv"><span>{text(row.split)} · {text(row.policy)}</span><strong>{text(row.cost_scenario_id)} · selected {numberText(row.selected_count)} / hold {numberText(row.hold_cash_count)} · {numberText(row.total_component_bp)}bp</strong></div>
        {:else}
          <div class="notice">selected/hold count summary 없음 · backend fail-closed 상태를 확인합니다.</div>
        {/each}
      </div>

      <div class="evidence-box" data-daily-close-slot-no-claims>
        <div class="text-eyebrow">required no-claim labels</div>
        <div class="tag-row">
          {#each noClaimLabels as label}
            <span class="pill"><span class="dot"></span>{label}</span>
          {:else}
            <span class="pill"><span class="dot"></span>NO_LIVE_BROKER_ORDER_ACCOUNT_SURFACE</span>
            <span class="pill"><span class="dot"></span>NO_PAPER_FORWARD_EXECUTION</span>
            <span class="pill"><span class="dot"></span>NO_MODEL_BUILD_GO</span>
            <span class="pill"><span class="dot"></span>NO_PROFITABILITY_CLAIM</span>
          {/each}
        </div>
        <div class="notice warn" style="margin-top:10px">threshold/replay evidence only · shuffle is baseline/control only · no broker/live/order/account/paper-forward/profitability/model-build/GO unlock.</div>
      </div>
    </div>

    <div class="evidence-grid" style="margin-top:12px">
      <div class="evidence-box" data-daily-close-slot-source-scope>
        <div class="text-eyebrow">bounded latest-evidence scope</div>
        <div class="mini-kv"><span>scope label</span><strong>{text(boundedScope.scope_label, 'bounded_latest_evidence_not_full_universe_or_decision_grade')}</strong></div>
        <div class="mini-kv"><span>max symbols / rows per symbol</span><strong>{numberText(boundedScope.max_symbols ?? sourceCounts.max_symbols)} · {numberText(boundedScope.max_rows_per_symbol ?? sourceCounts.max_rows_per_symbol)}</strong></div>
        <div class="mini-kv"><span>included / total universe</span><strong>{numberText(sourceCounts.included_symbols_used)} / {numberText(sourceCounts.universe_symbols_total)}</strong></div>
        <div class="notice warn" style="margin-top:10px">bounded research artifact only · full-universe/decision-grade/profit claim 아님.</div>
      </div>

      <div class="evidence-box" data-daily-close-slot-db-access>
        <div class="text-eyebrow">DB access proof</div>
        <div class="mini-kv"><span>access / uri mode</span><strong>{text(dbAccess.access_mode, 'read_only')} · {text(dbAccess.sqlite_uri_mode, 'ro')}</strong></div>
        <div class="mini-kv"><span>PRAGMA query_only</span><strong>{text(dbAccess.pragma_query_only, 'true')}</strong></div>
        <div class="mini-kv"><span>mutation allowed</span><strong>{text(dbAccess.mutation_allowed, 'false')}</strong></div>
        <div class="mini-kv"><span>helper</span><strong>{text(dbAccess.connection_helper, 'stom_rl.daily_ohlcv_db.connect_readonly')}</strong></div>
      </div>

      <div class="evidence-box" data-daily-close-slot-locks>
        <div class="text-eyebrow">machine-readable locks</div>
        {#each flagRows as row}
          <div class="mini-kv"><span>{row.key}</span><strong>{row.value}</strong></div>
        {/each}
      </div>
    </div>

    <div class="evidence-grid" style="margin-top:12px">
      <div class="evidence-box" data-daily-close-slot-lineage>
        <div class="text-eyebrow">lineage / gate</div>
        <div class="mini-kv"><span>gate</span><strong>{text(sourceIds.gate_run_id ?? latest?.run_id)}</strong></div>
        <div class="mini-kv"><span>train</span><strong>{text(sourceIds.train_run_id)}</strong></div>
        <div class="mini-kv"><span>dataset</span><strong>{text(sourceIds.dataset_run_id)}</strong></div>
        <div class="mini-kv"><span>dataset_lineage</span><strong>{text(datasetLineage.status ?? latest?.lineage_validation_status)}</strong></div>
        <div class="mini-kv"><span>gate_report</span><strong>{text(gateReport.status ?? latest?.dashboard_validation_status)}</strong></div>
        <div class="mini-kv"><span>baseline controls</span><strong>{(latest?.required_baselines ?? ['no_trade_control', 'deterministic_shuffle_top10_control']).join(', ')}</strong></div>
      </div>

      <div class="evidence-box" data-daily-close-slot-labels>
        <div class="text-eyebrow">required labels</div>
        <div class="tag-row">
          {#each labels as label}
            <span class="pill"><span class="dot"></span>{label}</span>
          {/each}
        </div>
        {#if blockerRows.length > 0}
          <div class="mini-list" style="margin-top:10px">
            {#each blockerRows.slice(0, 6) as blocker}
              <div><span>blocker</span><strong>{blocker}</strong></div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="evidence-box" data-daily-close-slot-selection>
        <div class="text-eyebrow">selected-code replay adapter</div>
        <div class="mini-kv"><span>code contract</span><strong>codes stay string-preserved (e.g. 000250) · never coerce to int</strong></div>
        {#each selectionRows as row}
          <div class="mini-kv"><span>{text(row.date)} · slot {text(row.slot)}</span><strong>{text(row.code)} · shares {text(row.shares)} · {text(row.fill_mode)}</strong></div>
        {:else}
          <div class="notice">selected-code replay evidence 없음 · live/order surface가 아닙니다.</div>
        {/each}
      </div>
    </div>

    <div class="evidence-grid" style="margin-top:12px">
      <div class="evidence-box" data-daily-close-slot-equity>
        <div class="text-eyebrow">research equity / reward</div>
        {#each equityPoints as row}
          <div class="mini-kv"><span>{text(row.date)}</span><strong>net {numberText(row.net_pnl_krw)} · reward {numberText(row.reward)} · filled {text(row.filled_slots)}</strong></div>
        {:else}
          <div class="notice">equity series 없음 · 수익성 주장으로 해석하지 않습니다.</div>
        {/each}
      </div>
    </div>

    <div class="table-wrap" style="margin-top:12px; max-height:220px; overflow:auto" data-daily-close-slot-artifacts>
      <table>
        <thead><tr><th>run</th><th>status</th><th>train</th><th>dataset</th><th>errors</th></tr></thead>
        <tbody>
          {#each artifactRows as row}
            <tr>
              <td class="mono">{text(row.run_id)}</td>
              <td>{text(row.status)}</td>
              <td class="mono">{text(row.train_run_id)}</td>
              <td class="mono">{text(row.dataset_run_id)}</td>
              <td>{Array.isArray(row.artifact_selection_errors) ? row.artifact_selection_errors.join(', ') : '—'}</td>
            </tr>
          {:else}
            <tr><td colspan="5">close-slot generated artifact 없음 · NOT_STARTED로 표시합니다.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  </Disclosure>
</section>

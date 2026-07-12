<script lang="ts">
  // WP-S3 — "종가매매 에이전트" 화면 (백엔드 변경 0).
  // 전부 기존 close-slot API(selection/policy_score_sample/closeSlotEquity)에서만 파생합니다.
  // 신규 /api/* 없음 · 종목코드는 문자열 보존(C2) · ts_imb 등 RULE 라벨은 이 화면과 무관.
  // 데이터가 없으면 합성하지 않고 fail-closed('—'/MISSING pill)로 표시합니다.
  import type {
    DailyCloseSlotDataRecency,
    DailyCloseSlotEquityResponse,
    DailyCloseSlotLatestResponse,
    DailyCloseSlotLatestSelection,
    DailyCloseSlotPolicyScoreRow,
    DailyCloseSlotSelectionResponse,
    DailyCloseSlotSelectionRow,
  } from '$lib/dailyOhlcvApi';
  import { humanizeVerdict } from '$lib/verdictLabel';
  import EquityDrawdownChart from '../../charts/EquityDrawdownChart.svelte';

  interface Props {
    latest: DailyCloseSlotLatestResponse | null;
    gate: DailyCloseSlotLatestResponse | null;
    equity: DailyCloseSlotEquityResponse | null;
    selection: DailyCloseSlotSelectionResponse | null;
  }

  let { latest, gate, equity, selection }: Props = $props();

  const KRW_NOTE = '연구 환산 · 수익 주장 아님';

  const falseLockKeys = [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
  ] as const;

  // ── local formatters (mirrors DailyCloseSlotCard.svelte's own local helpers —
  //    each close-slot card keeps its own trivial formatters by design) ──
  function text(value: unknown, fallback = '—'): string {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function numberText(value: unknown): string {
    return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ko-KR') : text(value);
  }

  function krw(value: unknown): string {
    return `${numberText(value)} KRW`;
  }

  function toNumberOrNull(value: unknown): number | null {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function flagText(value: unknown): string {
    return value === false ? 'false' : value === true ? 'true' : 'MISSING';
  }

  function hasCode(row: DailyCloseSlotSelectionRow | null | undefined): boolean {
    const code = row?.code;
    return code !== null && code !== undefined && String(code).trim() !== '';
  }

  function tone(status: string | undefined): string {
    if (!status) return '';
    if (status.includes('BLOCK')) return 'danger';
    if (status.includes('NO-GO')) return 'danger';
    if (status.includes('WATCH') || status.includes('RESEARCH_ONLY')) return 'warn';
    if (status === 'PASS') return 'success';
    return '';
  }

  // ── status / guardrail ──────────────────────────────────────────────
  const displayStatus = $derived(latest?.status ?? gate?.status ?? selection?.status ?? 'NOT_STARTED');
  const thresholdSelection = $derived(latest?.threshold_selection ?? selection?.threshold_selection ?? {});
  const sentinelValue = $derived((thresholdSelection as unknown as Record<string, unknown> | undefined)?.chosen_is_no_trade_sentinel);

  // ── authoritative latest/date-recency/blocker evidence (WP — de-hardcode) ──
  // These come straight from the backend's structured latest_selection /
  // data_recency / close_slot_blockers / chosen_is_no_trade_sentinel fields
  // (selection endpoint primary, latest endpoint fallback). Nothing here is
  // invented client-side; a missing field renders as '—' / an empty list.
  const dataRecency = $derived(
    (selection?.data_recency ?? latest?.data_recency ?? null) as DailyCloseSlotDataRecency | null
  );
  const recencyLabel = $derived(dataRecency?.label ?? (dataRecency?.is_today ? '오늘' : '기록된 replay 날짜 확인 불가'));
  const closeSlotBlockers = $derived.by(() =>
    Array.from(new Set([
      ...(selection?.close_slot_blockers ?? latest?.close_slot_blockers ?? []),
      ...(latest?.artifact_selection_errors ?? []),
      ...(gate?.artifact_selection_errors ?? []),
      ...(selection?.artifact_selection_errors ?? []),
    ]))
  );
  const chosenIsNoTradeSentinel = $derived(
    (selection?.chosen_is_no_trade_sentinel ?? latest?.chosen_is_no_trade_sentinel ?? sentinelValue) as
      | boolean
      | null
      | undefined
  );
  const latestSelection = $derived(
    (selection?.latest_selection ?? latest?.latest_selection ?? null) as DailyCloseSlotLatestSelection | null
  );

  // ── (1) hero — AUTHORITATIVE selected count from selected_hold_summary ──
  //    selection_rows is a paginated sample (closeSlotSelection ?limit=20 ->
  //    the OLDEST dates only, since load_close_slot_selection iterates dates
  //    ascending and stops at the limit), so it must NEVER be treated as
  //    "today". The 0-symbol decision uses the non-truncated selected_hold_
  //    summary aggregate (identical derivation to DailyCloseSlotCard); the
  //    selection_rows sample is shown separately, honestly labeled as a sample.
  const selectedHoldSummary = $derived(latest?.selected_hold_summary ?? selection?.selected_hold_summary ?? {});
  const primarySelectedCount = $derived.by(() => {
    const rows = selectedHoldSummary.rows ?? [];
    const primaryId = selectedHoldSummary.primary_cost_scenario_id ?? latest?.primary_cost_scenario_id ?? 'base_23bp';
    const match = rows.find((row) => row.cost_scenario_id === primaryId) ?? rows[0];
    return match?.selected_count;
  });
  const isZeroSelectionDefect = $derived(typeof primarySelectedCount === 'number' && primarySelectedCount === 0);

  const allSelectionRows = $derived((selection?.selection_rows ?? []) as readonly DailyCloseSlotSelectionRow[]);
  const sampledLatestDate = $derived.by(() => {
    let max = '';
    for (const row of allSelectionRows) {
      const d = String(row?.date ?? '');
      if (d && d > max) max = d;
    }
    return max;
  });
  const sampledLatestRows = $derived(
    sampledLatestDate ? allSelectionRows.filter((row) => String(row?.date ?? '') === sampledLatestDate) : []
  );
  const sampledSelectedRows = $derived(sampledLatestRows.filter((row) => hasCode(row)));

  // 0-selection copy is derived from the structured sentinel/blocker evidence
  // — never a hardcoded 'normalization bug' claim. When the backend marks the
  // zero selection as the honest no-trade sentinel, say so explicitly; when it
  // does not, point at the live close_slot_blockers/verdict instead of
  // inventing a defect label the backend never asserted.
  const zeroDefectCopy = $derived(
    chosenIsNoTradeSentinel === true
      ? '0종목 선택 — 23bp 하 무거래가 정직한 최적 (chosen_is_no_trade_sentinel=true)'
      : '0종목 선택 — 원인은 아래 blocker/verdict 참조'
  );

  // ── (2) 종목별 판단 — score vs threshold ────────────────────────────
  const policyScoreRows = $derived(
    ((selection?.policy_score_sample ?? latest?.samples?.policy_scores ?? []) as readonly DailyCloseSlotPolicyScoreRow[]).slice(0, 20)
  );
  const thresholdNumeric = $derived.by(() => {
    const raw = thresholdSelection?.threshold;
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
    const parsed = thresholdSelection?.threshold_text != null ? Number(thresholdSelection.threshold_text) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  });
  const scoreRange = $derived.by(() => {
    const values: number[] = [];
    for (const row of policyScoreRows) {
      const n = toNumberOrNull(row?.score);
      if (n != null) values.push(n);
    }
    if (thresholdNumeric != null) values.push(thresholdNumeric);
    if (!values.length) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    return min === max ? { min: min - 1, max: max + 1 } : { min, max };
  });
  function barPercent(value: number | null): number {
    if (value == null || !scoreRange) return 0;
    const { min, max } = scoreRange;
    return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  }

  // ── (3) 익일 결과 원장 스테퍼 — SessionReplayCard의 prev/slider/next 인터랙션 이식 ──
  let ledgerDate = $state('');
  let ledgerStepIndex = $state(0);

  const ledgerDates = $derived.by(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const row of allSelectionRows) {
      const d = String(row?.date ?? '');
      if (!d || seen.has(d)) continue;
      seen.add(d);
      out.push(d);
    }
    return out.sort();
  });

  $effect(() => {
    if (ledgerDates.length && !ledgerDates.includes(ledgerDate)) {
      ledgerDate = ledgerDates[ledgerDates.length - 1] ?? '';
      ledgerStepIndex = 0;
    }
  });

  const ledgerRowsForDate = $derived(allSelectionRows.filter((row) => String(row?.date ?? '') === ledgerDate));
  const ledgerMaxIndex = $derived(Math.max(ledgerRowsForDate.length - 1, 0));
  const ledgerRevealed = $derived(ledgerRowsForDate.slice(0, Math.min(ledgerStepIndex, ledgerMaxIndex) + 1));
  const ledgerRunningNet = $derived(
    ledgerRevealed.reduce((acc, row) => acc + (toNumberOrNull(row?.net_pnl_krw) ?? 0), 0)
  );

  function chooseLedgerDate(next: string): void {
    ledgerDate = next;
    ledgerStepIndex = 0;
  }

  function ledgerStep(delta: number): void {
    ledgerStepIndex = Math.max(0, Math.min(ledgerMaxIndex, ledgerStepIndex + delta));
  }

  // ── false-lock grid + no-claim labels (DailyCloseSlotCard 이식) ──────
  const flagRows = $derived(
    falseLockKeys.map((key) => ({ key, value: flagText(latest?.[key] ?? selection?.[key] ?? equity?.[key]) }))
  );
  const noClaimLabels = $derived(
    Array.from(new Set([...(latest?.no_claim_labels ?? []), ...(selection?.no_claim_labels ?? [])]))
  );
</script>

<section class="panel" data-close-slot-agent-screen>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">Close-slot agent · {recencyLabel} 선택 재현 (read-only)</div>
      <h2 class="text-h3">종가매매 에이전트 — {recencyLabel} 선택 종목 · 판단 근거 · 익일 결과</h2>
    </div>
    <span class="pill {tone(displayStatus)}" data-close-slot-agent-status>
      <span class="dot"></span>연구용 · {humanizeVerdict(displayStatus)} · 실거래 아님
    </span>
  </div>
  <p class="text-muted" style="font-size:12px; margin-top:-4px">
    기존 close-slot selection/policy-score/equity API만 사용 · no live/broker/account/order/paper-forward/profitability/model-build/GO claim.
  </p>

  <!-- (0) 권위 latest_selection — test OOS는 PRIMARY, train/val은 secondary -->
  <div class="agent-section evidence-box" data-close-slot-agent-latest-selection>
    <div class="text-eyebrow">latest_selection (authoritative) · test OOS = PRIMARY</div>
    <div class="mini-grid">
      <div><span>date</span><strong>{text(latestSelection?.date)}</strong></div>
      <div><span>policy</span><strong>{text(latestSelection?.policy)}</strong></div>
      <div><span>split</span><strong>{text(latestSelection?.split)}{latestSelection?.split === 'test' ? ' · PRIMARY' : ''}</strong></div>
      <div><span>cost_scenario_id</span><strong>{text(latestSelection?.cost_scenario_id)}</strong></div>
      <div><span>artifact_age_seconds</span><strong>{numberText(latestSelection?.artifact_age_seconds)}</strong></div>
      <div><span>source_run_id</span><strong>{text(latestSelection?.source_run_id)}</strong></div>
      <div><span>seed</span><strong>{latestSelection?.seed == null ? '— (close-slot manifest에 미영속)' : text(latestSelection?.seed)}</strong></div>
    </div>
    {#if !latestSelection}
      <div class="notice danger" style="margin-top:8px">latest_selection 없음 · PRIMARY OOS 결과 미확인 (fail-closed).</div>
    {/if}
    {#if latestSelection?.missing_test_split_evidence}
      <div class="notice warn" style="margin-top:8px">test split evidence 없음 · PRIMARY OOS 결과 미확인 (fail-closed).</div>
    {/if}
    <div class="text-caption" style="margin-top:10px">secondary (참고용 · PRIMARY 아님)</div>
    <div class="mini-grid">
      <div><span>train</span><strong>{text(latestSelection?.secondary?.train?.date)}</strong></div>
      <div><span>val</span><strong>{text(latestSelection?.secondary?.val?.date)}</strong></div>
      <div><span>val+test</span><strong>{text(latestSelection?.secondary?.val_plus_test?.date)}</strong></div>
    </div>
    <div class="text-caption" style="margin-top:10px">
      data_recency: {recencyLabel} · latest_data_date {text(dataRecency?.latest_data_date)} · is_today {flagText(dataRecency?.is_today)}
    </div>
  </div>

  <!-- close_slot_blockers — full dynamic deduped list, count is never hardcoded -->
  <div class="agent-section evidence-box" data-close-slot-agent-blockers>
    <div class="text-eyebrow">close_slot_blockers / artifact_selection_errors · {closeSlotBlockers.length}건</div>
    {#each closeSlotBlockers as blocker}
      <div class="notice warn" style="margin-top:6px" data-close-slot-blocker>{blocker}</div>
    {:else}
      <div class="notice success">현재 dedup된 blocker 없음.</div>
    {/each}
  </div>

  <!-- (1) 선택 요약 (권위 집계 selected_hold_summary) + 표본 재현 -->
  <div class="agent-section" data-close-slot-agent-hero>
    <div class="text-eyebrow">선택 요약 · primary {text(selectedHoldSummary.primary_cost_scenario_id, 'base_23bp')} · {isZeroSelectionDefect ? '0' : text(primarySelectedCount)}종목</div>
    {#if isZeroSelectionDefect}
      <div class="notice danger zero-defect-card" data-close-slot-agent-zero-defect>
        <div class="zero-defect-title">{zeroDefectCopy}</div>
        <div class="mini-kv"><span>policy</span><strong>{text(thresholdSelection.policy, 'linear_score_and_pick_train_only')}</strong></div>
        <div class="mini-kv"><span>threshold</span><strong>{text(thresholdSelection.threshold_text ?? thresholdSelection.threshold)} · metric {text(thresholdSelection.metric, 'mean_daily_reward_base_23bp')}</strong></div>
        <div class="mini-kv"><span>hold_cash_action</span><strong>{text(thresholdSelection.hold_cash_action, 'true')}</strong></div>
        <div class="mini-kv"><span>cardinality</span><strong>max {numberText(thresholdSelection.max_slot_count ?? 10)} slots · {text(thresholdSelection.selection_cardinality, 'threshold_selected_0_to_10')}</strong></div>
        <div class="mini-kv"><span>chosen_is_no_trade_sentinel</span><strong>{flagText(chosenIsNoTradeSentinel)}</strong></div>
        <p class="text-caption" style="margin-top:8px">모든 슬롯이 cash-hold 상태입니다 · 매매 신호 아님 · 연구 전용(RESEARCH_ONLY).</p>
        {#if chosenIsNoTradeSentinel !== true}
          <p class="text-caption" style="margin-top:4px">근거: close_slot_blockers {closeSlotBlockers.length}건 · verdict {humanizeVerdict(displayStatus)} (위 close_slot_blockers 섹션 참조).</p>
        {/if}
      </div>
    {:else if primarySelectedCount == null && sampledSelectedRows.length === 0}
      <div class="notice">선택 데이터 없음 · NOT_STARTED 또는 fail-closed 상태입니다.</div>
    {:else}
      <div class="text-caption" style="margin:2px 0 8px">표본 선택 재현 ({text(selection?.selection_rows_label, 'sample_only_not_authoritative_latest')}) · 표본일 {text(sampledLatestDate)} <span class="krw-note">· selection_rows는 제한된 표본이라 최신 거래일이 아닐 수 있음 (권위 latest는 위 latest_selection 참조)</span></div>
      <div class="agent-picks-grid" data-close-slot-agent-picks>
        {#each sampledSelectedRows as row}
          <div class="agent-pick-card">
            <div class="pick-head"><span class="mono">{text(row.code)}</span><span class="pill"><span class="dot"></span>{text(row.action_label, 'selected')}</span></div>
            <div class="mini-kv"><span>slot</span><strong>{text(row.slot)}</strong></div>
            <div class="mini-kv"><span>entry_close</span><strong>{krw(row.entry_close)} <span class="krw-note">· {KRW_NOTE}</span></strong></div>
            <div class="mini-kv"><span>next_close</span><strong>{krw(row.next_close)} <span class="krw-note">· {KRW_NOTE}</span></strong></div>
            <div class="mini-kv"><span>net_pnl_krw</span><strong>{krw(row.net_pnl_krw)} <span class="krw-note">· {KRW_NOTE}</span></strong></div>
          </div>
        {:else}
          <div class="notice">표본 최신일에 선택 종목 없음 · 아래 원장 스테퍼에서 다른 표본일을 확인하세요.</div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- (2) 종목별 판단 — score vs threshold -->
  <div class="agent-section evidence-box" data-close-slot-agent-scores>
    <div class="text-eyebrow">종목별 판단 · score vs threshold ({text(thresholdSelection.threshold_text ?? thresholdSelection.threshold)})</div>
    {#each policyScoreRows as row}
      {@const scoreNum = toNumberOrNull(row.score)}
      {@const passed = scoreNum != null && thresholdNumeric != null && scoreNum >= thresholdNumeric}
      <div class="score-row">
        <div class="score-row-label"><span class="mono">{text(row.date)}</span><span class="mono">{text(row.code)}</span></div>
        <div class="score-bar-track">
          <div class="score-bar-fill {passed ? 'pass' : 'fail'}" style="width:{barPercent(scoreNum)}%"></div>
          {#if thresholdNumeric != null}
            <div class="score-bar-threshold" style="left:{barPercent(thresholdNumeric)}%"></div>
          {/if}
        </div>
        <div class="score-row-value tnum">{text(row.score)}</div>
      </div>
    {:else}
      <div class="notice">policy score sample 없음 · fail-closed 상태일 수 있습니다.</div>
    {/each}
  </div>

  <!-- (3) 익일 결과 원장 스테퍼 -->
  <div class="agent-section evidence-box" data-close-slot-agent-ledger>
    <div class="text-eyebrow">익일 결과 원장 · entry_close → next_close → net_pnl_krw / cost_krw</div>
    {#if !ledgerDates.length}
      <div class="notice">selection ledger 없음 · replay 불가.</div>
    {:else}
      <div class="replay-controls">
        <select aria-label="원장 날짜" value={ledgerDate} onchange={(event) => chooseLedgerDate((event.currentTarget as HTMLSelectElement).value)}>
          {#each ledgerDates as d}<option value={d}>{d}</option>{/each}
        </select>
        <button type="button" class="step-btn" onclick={() => ledgerStep(-1)} disabled={ledgerStepIndex <= 0}>prev</button>
        <input
          type="range"
          aria-label="원장 공개 단계"
          min="0"
          max={ledgerMaxIndex}
          value={Math.min(ledgerStepIndex, ledgerMaxIndex)}
          oninput={(event) => (ledgerStepIndex = Number((event.currentTarget as HTMLInputElement).value))}
        />
        <button type="button" class="step-btn" onclick={() => ledgerStep(1)} disabled={ledgerStepIndex >= ledgerMaxIndex}>next</button>
      </div>
      <div class="mini-grid" style="margin-top:10px">
        <div><span>revealed slots</span><strong>{ledgerRevealed.length} / {ledgerRowsForDate.length}</strong></div>
        <div><span>Running TAKE net (23bp) 누적</span><strong>{krw(ledgerRunningNet)} <span class="krw-note">· {KRW_NOTE}</span></strong></div>
      </div>
      <div class="table-wrap" style="margin-top:10px; max-height:260px; overflow:auto">
        <table>
          <thead><tr><th>#</th><th>code</th><th>entry_close</th><th>next_close</th><th>net_pnl_krw</th><th>cost_krw</th></tr></thead>
          <tbody>
            {#each ledgerRevealed as row, idx}
              <tr>
                <td>{idx + 1}</td>
                <td class="mono">{text(row.code, 'hold_cash')}</td>
                <td class="tnum">{krw(row.entry_close)} <span class="krw-note">{KRW_NOTE}</span></td>
                <td class="tnum">{krw(row.next_close)} <span class="krw-note">{KRW_NOTE}</span></td>
                <td class="tnum">{krw(row.net_pnl_krw)} <span class="krw-note">{KRW_NOTE}</span></td>
                <td class="tnum">{krw(row.cost_krw)} <span class="krw-note">{KRW_NOTE}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="text-caption" style="margin-top:6px">close-to-next-close 재현 스테퍼입니다 · 실거래/체결 보장 아님 · 모든 KRW 값은 {KRW_NOTE}.</p>
    {/if}
  </div>

  <!-- (4) 누적 연구용 에쿼티 -->
  <div class="agent-section evidence-box" data-close-slot-agent-equity>
    <div class="text-eyebrow">누적 연구용 에쿼티 · {KRW_NOTE}</div>
    <EquityDrawdownChart {equity} autoLoad={false} />
  </div>

  <div class="evidence-grid" style="margin-top:12px">
    <div class="evidence-box" data-close-slot-agent-locks>
      <div class="text-eyebrow">machine-readable locks</div>
      {#each flagRows as row}
        <div class="mini-kv"><span>{row.key}</span><strong>{row.value}</strong></div>
      {/each}
    </div>

    <div class="evidence-box" data-close-slot-agent-no-claims>
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
      <div class="notice warn" style="margin-top:10px">selection/policy-score/equity read-only evidence only · no broker/live/order/account/paper-forward/profitability/model-build/GO unlock.</div>
    </div>
  </div>
</section>

<style>
  .agent-section {
    margin-top: 14px;
  }
  .mono {
    font-family: var(--font-mono);
  }
  .krw-note {
    font-family: var(--font-mono);
    font-size: 10.5px;
    font-weight: 500;
    color: var(--muted);
  }
  .zero-defect-card {
    display: block;
    padding: 16px;
  }
  .zero-defect-title {
    font: 700 15px/1.35 var(--font-display);
    color: var(--danger);
    margin-bottom: 8px;
  }
  .agent-picks-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px;
    margin-top: 8px;
  }
  .agent-pick-card {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    padding: 12px;
    background: var(--surface-sunken);
  }
  .pick-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
    font: 600 13px/1.2 var(--font-mono);
  }
  .score-row {
    display: grid;
    grid-template-columns: 130px 1fr 64px;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    border-bottom: 1px solid var(--border-faint);
  }
  .score-row:last-child {
    border-bottom: 0;
  }
  .score-row-label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 11px;
    color: var(--muted);
  }
  .score-bar-track {
    position: relative;
    height: 8px;
    border-radius: 999px;
    background: var(--surface-sunken);
    overflow: visible;
  }
  .score-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--danger);
  }
  .score-bar-fill.pass {
    background: var(--success);
  }
  .score-bar-threshold {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 2px;
    background: var(--fg-strong);
  }
  .score-row-value {
    text-align: right;
    font-size: 12px;
    color: var(--fg);
  }
  .replay-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    flex-wrap: wrap;
  }
  .replay-controls select {
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    padding: 6px 8px;
    font: inherit;
    min-width: 130px;
  }
  .replay-controls input[type='range'] {
    flex: 1;
    min-width: 100px;
  }
  .step-btn {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface);
    padding: 4px 12px;
    font: 600 11px/1 var(--font-display);
    cursor: pointer;
  }
  .step-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .mini-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 8px;
    font-size: 12px;
  }
  .mini-grid > div {
    min-width: 0;
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-sm);
    background: var(--surface-sunken);
  }
  .mini-grid span {
    color: var(--muted);
    flex: 0 0 auto;
  }
  .mini-grid strong {
    min-width: 0;
    overflow-wrap: anywhere;
    text-align: right;
  }
</style>

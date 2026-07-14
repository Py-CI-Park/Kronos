<script lang="ts">
  import { PROMOTION_LOCK_KEYS, type PromotionLockKey, type PromotionLocksResult, type PromotionLockState } from '../evidence';

  interface Props {
    result: PromotionLocksResult;
    compact?: boolean;
  }

  let { result, compact = false }: Props = $props();
  const componentId = $props.id();
  const titleId = $derived(`promotion-locks-title-${componentId}`);

  const lockLabels: Record<PromotionLockKey, string> = {
    promotion_allowed: '승격 허용',
    model_build_allowed: '모델 빌드 허용',
    paper_forward_allowed: '페이퍼 포워드 허용',
    live_broker_order_allowed: '라이브 브로커 주문 허용',
    profitability_claim_allowed: '수익성 주장 허용',
    go_summary_allowed: 'GO 요약 허용',
  };

  const reasonLabels: Record<PromotionLockState['reason'], string> = {
    UNLOCKED_BY_SOURCE: '출처가 허용을 선언함',
    LOCKED_BY_SOURCE: '출처가 잠금을 선언함',
    LOCK_SOURCE_MISSING: '잠금 출처 누락',
    LOCK_SOURCE_INVALID: '잠금 출처 무효',
  };

  const statusLabels: Record<PromotionLockState['sourceStatus'], string> = {
    declared: 'declared',
    missing: 'missing',
    invalid: 'invalid',
  };

  function fallbackState(key: PromotionLockKey): PromotionLockState {
    return {
      key,
      allowed: false,
      sourceStatus: 'missing',
      reason: 'LOCK_SOURCE_MISSING',
    };
  }

  function stateFor(key: PromotionLockKey): PromotionLockState {
    return result.states[key] ?? fallbackState(key);
  }

  function effectiveAllowed(state: PromotionLockState): boolean {
    return state.sourceStatus === 'declared' && state.allowed === true;
  }
</script>

<section
  class:compact
  class="promotion-locks"
  data-v4-promotion-locks
  aria-labelledby={titleId}
>
  <div class="locks-header">
    <div>
      <p class="eyebrow">Promotion locks</p>
      <h2 id={titleId}>승격 잠금 6종</h2>
    </div>
    <span class="summary" data-locked={result.allLocked ? 'true' : 'false'}>
      {result.allLocked ? 'ALL LOCKED' : 'SOURCE UNLOCKED'}
    </span>
  </div>

  {#if result.hasInvalidSource}
    <p class="invalid-note" role="alert">무효한 잠금 출처가 있어 GO로 표시하지 않습니다.</p>
  {/if}

  <div class="locks-table" role="table" aria-label="승격 잠금 상태">
    <div class="locks-row locks-row-head" role="row">
      <span role="columnheader">잠금</span>
      <span role="columnheader">허용</span>
      <span role="columnheader">출처</span>
      <span role="columnheader">사유</span>
    </div>

    {#each PROMOTION_LOCK_KEYS as key (key)}
      {@const state = stateFor(key)}
      {@const allowed = effectiveAllowed(state)}
      <div class="locks-row" role="row" data-lock-key={key} data-source-status={state.sourceStatus} data-allowed={allowed ? 'true' : 'false'}>
        <span class="lock-name" role="cell">
          <span class="cell-label">잠금</span>
          <span>{lockLabels[key]}</span>
          <code>{key}</code>
        </span>
        <span class="allowed-cell" role="cell" data-value={allowed ? 'true' : 'false'}>
          <span class="cell-label">허용</span>
          <span>{allowed ? 'true' : 'false'}</span>
        </span>
        <span class="source-cell" role="cell">
          <span class="cell-label">출처</span>
          <span>{statusLabels[state.sourceStatus]}</span>
        </span>
        <span class="reason-cell" role="cell">
          <span class="cell-label">사유</span>
          <span>{reasonLabels[state.reason]}</span>
        </span>
      </div>
    {/each}
  </div>
</section>

<style>
  .promotion-locks {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    padding: 18px;
    color: var(--fg);
    overflow-wrap: anywhere;
    word-break: keep-all;
  }

  .promotion-locks.compact {
    padding: 14px;
  }

  .locks-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 14px;
  }

  .eyebrow {
    margin: 0 0 4px;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    color: var(--fg-strong);
    font: 760 var(--t-h5) / 1.2 var(--font-display);
    letter-spacing: -0.02em;
  }

  .summary {
    flex: 0 0 auto;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 7px 10px;
    background: var(--surface-raised);
    color: var(--muted);
    font: 760 var(--t-eyebrow) / 1 var(--font-mono);
    letter-spacing: 0.04em;
  }

  .summary[data-locked='true'] {
    border-color: var(--danger);
    background: var(--danger-soft);
    color: var(--danger);
  }

  .summary[data-locked='false'] {
    border-color: var(--warn);
    background: var(--warn-soft);
    color: var(--warn);
  }

  .invalid-note {
    margin: 0 0 12px;
    border: 1px solid var(--danger);
    border-radius: var(--r-md);
    padding: 9px 11px;
    background: var(--danger-soft);
    color: var(--danger);
    font-weight: 720;
  }

  .locks-table {
    display: grid;
    gap: 8px;
  }

  .locks-row {
    display: grid;
    grid-template-columns: minmax(180px, 1.4fr) minmax(72px, 0.5fr) minmax(90px, 0.6fr) minmax(160px, 1.2fr);
    gap: 10px;
    align-items: center;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    padding: 10px 12px;
    background: var(--surface-raised);
  }

  .locks-row-head {
    border: 0;
    padding-block: 0;
    background: transparent;
    color: var(--muted);
    font: 760 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .lock-name {
    display: grid;
    gap: 3px;
    color: var(--fg-strong);
    font-weight: 740;
  }

  code {
    color: var(--muted);
    font: 650 var(--t-caption) / 1.35 var(--font-mono);
  }

  .allowed-cell,
  .source-cell {
    justify-self: start;
    border-radius: var(--r-pill);
    padding: 5px 8px;
    background: var(--surface-sunken);
    color: var(--muted);
    font: 760 var(--t-caption) / 1 var(--font-mono);
  }

  .allowed-cell[data-value='true'] {
    background: var(--success-soft);
    color: var(--success);
  }

  .allowed-cell[data-value='false'] {
    background: var(--danger-soft);
    color: var(--danger);
  }

  .locks-row[data-source-status='missing'] .source-cell,
  .locks-row[data-source-status='invalid'] .source-cell {
    background: var(--danger-soft);
    color: var(--danger);
  }

  .reason-cell {
    color: var(--fg);
    font-size: var(--t-caption);
    line-height: 1.45;
  }

  .cell-label {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  @media (max-width: 760px) {
    .locks-header {
      flex-direction: column;
    }

    .locks-row,
    .locks-row-head {
      grid-template-columns: 1fr;
    }

    .locks-row-head {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }

    .cell-label {
      position: static;
      width: auto;
      height: auto;
      margin: 0 0 3px;
      overflow: visible;
      clip: auto;
      color: var(--muted);
      font: 760 var(--t-eyebrow) / 1.2 var(--font-mono);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .allowed-cell,
    .source-cell,
    .reason-cell {
      display: grid;
      gap: 3px;
    }
  }
</style>

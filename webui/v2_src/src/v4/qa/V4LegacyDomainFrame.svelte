<script lang="ts">
  import type { Snippet } from 'svelte';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import { adaptPromotionLocks } from '../evidence';
  import { PROMOTION_LOCK_KEYS } from '../evidence';
  import { V4_QA_FALSE_LOCK_KEYS, V4_QA_STATE_LEGEND, assertValidFixtureSet } from './stateFixtures';

  /**
   * Consistency guard: this frame's locks vocabulary MUST stay the exact six
   * false locks shared across every V4 domain frame. If either list drifts,
   * fail fast instead of silently rendering a mismatched lock count.
   */
  if (
    V4_QA_FALSE_LOCK_KEYS.length !== 6 ||
    PROMOTION_LOCK_KEYS.length !== 6 ||
    !V4_QA_FALSE_LOCK_KEYS.every((key) => (PROMOTION_LOCK_KEYS as readonly string[]).includes(key))
  ) {
    throw new Error('V4LegacyDomainFrame lock vocabulary mismatch: expected exactly six shared false locks');
  }

  interface Props {
    surface: 'diagnostics' | 'daily-guide';
    children?: Snippet;
  }

  let { surface, children }: Props = $props();

  /**
   * Locks are always evaluated against an empty source, exactly like
   * V4AdminWorkspace, so this frame can never display an unlocked state
   * independent of any caller-supplied data. Six locks, always false.
   */
  const locks = $derived(adaptPromotionLocks(null));

  /**
   * Fail closed at render time: an invalid canonical fixture matrix must
   * never silently render. This throws instead of hiding a broken state
   * legend behind a fallback UI.
   */
  const legend = $derived.by(() => {
    assertValidFixtureSet();
    return V4_QA_STATE_LEGEND;
  });

  const surfaceCopy = $derived(
    surface === 'diagnostics'
      ? {
          eyebrow: 'Diagnostics · research-only',
          title: '진단 표면은 모든 상태를 숨기지 않고 있는 그대로 보여줍니다',
          description: '로딩/오류/오래됨/누락/NO-GO를 포함한 9개 상태 전부가 동일한 우선순위로 표시되며 낙관적 기본값은 없습니다.',
        }
      : {
          eyebrow: 'Daily guide · research-only',
          title: '일간 가이드 표면은 승격·주문·수익성 판단을 내리지 않습니다',
          description: '표시되는 모든 상태는 기록된 증거에서만 파생되며, 숨겨진 증거나 낙관적 잠금을 포함하지 않습니다.',
        },
  );
</script>

<section class="v4-legacy-domain-frame" data-v4-legacy-domain-frame={surface} data-surface={surface} aria-label="V4 legacy domain frame">
  <div class="intro">
    <p class="eyebrow">{surfaceCopy.eyebrow}</p>
    <h2>{surfaceCopy.title}</h2>
    <p>{surfaceCopy.description}</p>
  </div>

  <section class="locks" data-v4-legacy-domain-locks aria-label="Exact six false promotion locks">
    <PromotionLocksGrid result={locks} compact />
  </section>

  <section class="legend" data-v4-legacy-domain-legend aria-label="9-state lifecycle legend">
    <div class="section-head">
      <p class="eyebrow">State legend</p>
      <h3>9개 필수 상태: 로딩 · 비어 있음 · 오류 · 오래됨 · 실시간 · 리플레이 · 완료 · 누락 · NO-GO</h3>
    </div>
    <ul class="legend-list" role="list">
      {#each legend as row (row.stateId)}
        <li data-state={row.stateId} data-tone={row.tone} data-blocking={row.blocking ? 'true' : 'false'}>
          <span class="state-id">{row.stateId}</span>
          <strong class="state-label">{row.labelKo}</strong>
          <p class="safety-note">{row.safetyNoteKo}</p>
        </li>
      {/each}
    </ul>
  </section>

  <section class="posture" data-v4-legacy-domain-posture aria-label="Research-only, no-hidden-evidence posture">
    <div class="section-head">
      <p class="eyebrow">Posture</p>
      <h3>연구용 read-only · 숨겨진 증거 없음 · 승격/주문/수익성 주장 없음</h3>
    </div>
    <dl>
      <div><dt>Research only</dt><dd data-posture-key="researchOnly">true</dd></div>
      <div><dt>No hidden evidence</dt><dd data-posture-key="noHiddenEvidence">true</dd></div>
      <div><dt>No optimistic locks</dt><dd data-posture-key="noOptimisticLocks">true</dd></div>
      <div><dt>No live/profit/order claim</dt><dd data-posture-key="noUnsafeClaims">true</dd></div>
    </dl>
  </section>

  <EvidenceDisclosure summary="Legacy child · always visible" meta="rendered open, never hidden" open>
    <div class="legacy-child" data-v4-legacy-domain-legacy aria-label="Legacy child content, visible by default">
      {#if children}
        <div
          class="legacy-child-scroll"
          data-v4-legacy-domain-legacy-scroll
          tabindex="0"
          role="tabpanel"
          aria-label="Legacy visualization, horizontally scrollable when wider than the available space"
        >
          {@render children()}
        </div>
      {:else}
        <p>Legacy child surface not supplied. V4 QA posture remains research-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .v4-legacy-domain-frame {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
    overflow-wrap: anywhere;
    word-break: keep-all;
  }

  .v4-legacy-domain-frame > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .locks,
  .legend,
  .posture {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    padding: 18px 20px;
  }

  .eyebrow {
    margin: 0 0 4px;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin-block: 0;
  }

  h2,
  h3,
  strong {
    color: var(--fg-strong);
    overflow-wrap: anywhere;
  }

  h2 {
    margin: 0 0 6px;
    font: 760 var(--t-h5) / 1.2 var(--font-display);
    letter-spacing: -0.02em;
  }

  .intro p:last-child {
    color: var(--muted);
    line-height: 1.5;
  }

  .section-head {
    margin-bottom: 10px;
  }

  h3 {
    font: 720 12.5px/1.3 var(--font-display);
  }

  .legend-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .legend-list li {
    display: grid;
    gap: 4px;
    min-width: 0;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    padding: 12px;
    background: var(--surface-raised);
  }

  .state-id {
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .safety-note {
    color: var(--muted);
    font-size: var(--t-caption);
    line-height: 1.45;
    overflow-wrap: anywhere;
  }

  .legend-list li[data-tone='danger'] {
    border-color: var(--danger);
    background: var(--danger-soft);
  }

  .legend-list li[data-tone='warning'] {
    border-color: var(--warn);
    background: var(--warn-soft);
  }

  .legend-list li[data-tone='positive'] {
    border-color: var(--success);
    background: var(--success-soft);
  }

  .legend-list li[data-tone='info'] {
    border-color: var(--info);
    background: var(--info-soft);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
  }

  dl div {
    min-width: 0;
    padding: 10px;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    background: color-mix(in oklab, var(--surface-raised) 72%, transparent);
  }

  dt {
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  dd {
    margin: 5px 0 0;
    color: var(--fg-strong);
    font: 650 12px/1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .legacy-child {
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
    color: var(--fg);
    line-height: 1.55;
    overflow-wrap: anywhere;
    word-break: keep-all;
  }

  /*
   * Legacy visualizations sometimes carry an intrinsic min-content width
   * (tables, dense charts) wider than the viewport. Contain that overflow
   * to a local, keyboard-accessible horizontal scroll region instead of
   * letting it widen the document, and never clip it out of view.
   */
  .legacy-child-scroll {
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
    overflow-x: auto;
    overflow-y: visible;
  }

  :global(.v4-legacy-domain-frame > .evidence-disclosure),
  :global(.v4-legacy-domain-frame > .evidence-disclosure > .content) {
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
  }

  .legacy-child-scroll:focus-visible {
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }

  :global(.v4-legacy-domain-frame :focus-visible) {
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }

  @media (max-width: 900px) {
    .intro,
    .locks,
    .legend,
    .posture {
      padding: 14px 16px;
    }

    .legend-list {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 560px) {
    dl {
      grid-template-columns: 1fr;
    }
  }
</style>

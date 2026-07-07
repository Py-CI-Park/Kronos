<script lang="ts">
  import type { DailyProgressResponse } from '$lib/dailyOhlcvApi';

  interface Props {
    progress: DailyProgressResponse | null;
  }
  let { progress }: Props = $props();

  type LadderTone = 'pass' | 'watch' | 'danger' | 'muted';

  interface GateMeta {
    readonly id: string;
    readonly label: string;
    readonly rl?: boolean;
    readonly blocker?: string;
  }

  // Static gate scaffold: the D0-D9 order + short labels are fixed research IA.
  // D4 carries the RL stage + 종가매매(close-slot) sub-lane; D0/D1/D5 are the
  // documented persistent blockers of the current research posture.
  const GATES: readonly GateMeta[] = [
    { id: 'D0', label: '가격기준 · DB', blocker: 'price_basis' },
    { id: 'D1', label: '유니버스', blocker: 'universe' },
    { id: 'D2', label: '데이터셋' },
    { id: 'D3', label: '예측 베이스라인' },
    { id: 'D4', label: '포트폴리오 RL', rl: true },
    { id: 'D5', label: '워크포워드 게이트', blocker: 'walk-forward NO-GO' },
    { id: 'D6', label: '시각화' },
    { id: 'D7', label: '연구 진단' },
    { id: 'D8', label: '레지스트리' },
    { id: 'D9', label: '페이퍼 포워드' },
  ];

  // Map the live status vocabulary onto the status ramp. Missing/unknown stays
  // neutral (muted) — never fabricated green.
  function toneFor(status: string | undefined): LadderTone {
    const s = (status ?? '').toUpperCase();
    if (s === 'PASS') return 'pass';
    if (s === 'WATCH' || s === 'RUNNING' || s === 'RESEARCH_ONLY') return 'watch';
    if (s === 'NO-GO' || s === 'BLOCKED') return 'danger';
    return 'muted';
  }

  const ladder = $derived(
    GATES.map((gate) => {
      const stage = progress?.stages?.find((s) => s.id === gate.id);
      const status = stage?.status ?? 'NOT_STARTED';
      return { ...gate, status, tone: toneFor(status) };
    })
  );

  const tally = $derived({
    pass: ladder.filter((g) => g.tone === 'pass').length,
    watch: ladder.filter((g) => g.tone === 'watch').length,
    danger: ladder.filter((g) => g.tone === 'danger').length,
    muted: ladder.filter((g) => g.tone === 'muted').length,
  });

  const legend: readonly { tone: LadderTone; label: string }[] = [
    { tone: 'pass', label: 'PASS' },
    { tone: 'watch', label: 'WATCH / RESEARCH_ONLY' },
    { tone: 'danger', label: 'NO-GO / BLOCKED' },
    { tone: 'muted', label: 'NOT_STARTED' },
  ];
</script>

<section class="panel gate-ladder" data-daily-gate-ladder aria-labelledby="daily-gate-ladder-title">
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">D0–D9 Gate Ladder · 한눈 요약</div>
      <h2 class="text-h3" id="daily-gate-ladder-title">게이트 사다리 상태를 먼저 읽습니다</h2>
      <p class="text-muted">14개 카드 벽을 펼치기 전에, 각 게이트의 통과·관찰·차단 상태를 한 줄로 확인합니다.</p>
    </div>
    <span class="pill warn"><span class="dot"></span>{progress?.overall_status ?? 'RESEARCH_ONLY'}</span>
  </div>

  <div class="gate-rail" role="group" aria-label="D0 to D9 gate status ladder">
    <ol class="gate-track">
      {#each ladder as gate, i (gate.id)}
        <li
          class="gate-node"
          data-tone={gate.tone}
          data-rl={gate.rl ? 'true' : undefined}
          style="--i:{i}"
          aria-label={`${gate.id} ${gate.label} status ${gate.status}`}
        >
          <div class="gate-head">
            <span class="gate-code">{gate.id}</span>
            {#if gate.rl}<span class="gate-tag rl">RL</span>{/if}
          </div>
          <div class="gate-rail-cell"><span class="gate-signal"></span></div>
          <div class="gate-label">{gate.label}</div>
          <div class="gate-status tnum">{gate.status}</div>
          {#if gate.blocker}<span class="gate-tag block">blocker</span>{/if}
        </li>
      {/each}
    </ol>
  </div>

  <div class="gate-footer">
    <div class="gate-tally" aria-label="gate status tally">
      <span class="tally-item" data-tone="pass"><b class="tnum">{tally.pass}</b> pass</span>
      <span class="tally-item" data-tone="watch"><b class="tnum">{tally.watch}</b> watch</span>
      <span class="tally-item" data-tone="danger"><b class="tnum">{tally.danger}</b> no-go</span>
      <span class="tally-item" data-tone="muted"><b class="tnum">{tally.muted}</b> not-started</span>
    </div>
    <ul class="gate-legend">
      {#each legend as item}
        <li data-tone={item.tone}><span class="legend-swatch"></span>{item.label}</li>
      {/each}
    </ul>
  </div>

  <p class="gate-note text-muted">
    D4에는 강화학습(RL) 스테이지와 종가매매(close-slot) 서브레인이 포함됩니다. 색상은 progress 페이로드의 실제 게이트 상태만 반영하며, 값이 없으면 중립(NOT_STARTED)으로 둡니다. no live / broker / profit / GO claim.
  </p>
</section>

<style>
  .gate-ladder { gap: 18px; }

  /* Rail: horizontal scroll on narrow screens, never breaks the page. */
  .gate-rail {
    overflow-x: auto;
    overflow-y: hidden;
    margin: 2px -4px 0;
    padding: 4px 4px 6px;
    scrollbar-width: thin;
  }
  .gate-track {
    display: flex;
    gap: 16px;
    align-items: stretch;
    min-width: max-content;
  }

  .gate-node {
    position: relative;
    flex: 1 1 0;
    min-width: 108px;
    display: grid;
    grid-template-rows: 26px 16px auto auto;
    gap: 7px;
    padding: 12px 12px 13px;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-xs);
    transition: transform var(--d-fast) var(--ease-out),
      box-shadow var(--d-fast) var(--ease-out),
      border-color var(--d-fast) var(--ease-out);
    animation: gate-rise var(--d-base) var(--ease-out) backwards;
    animation-delay: calc(var(--i) * 42ms);
  }
  .gate-node:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
  }

  /* Connector track: a tinted line between consecutive gate signals. */
  .gate-node:not(:first-child)::before {
    content: '';
    position: absolute;
    top: 51px; /* center of .gate-rail-cell (26 + 7 gap + 8) */
    left: -17px;
    width: 17px;
    height: 2px;
    border-radius: 2px;
    background: var(--track, var(--border-strong));
    z-index: 0;
  }

  .gate-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .gate-code {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.02em;
    font-feature-settings: 'tnum', 'zero';
    color: var(--fg-strong);
  }

  .gate-rail-cell {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: flex-start;
  }
  .gate-signal {
    position: relative;
    z-index: 1;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--sig);
    box-shadow: 0 0 0 4px var(--sig-halo), 0 0 10px -1px var(--sig-glow);
  }

  .gate-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--fg);
    line-height: 1.3;
    word-break: keep-all;
  }
  .gate-status {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.02em;
    color: var(--muted);
    text-transform: uppercase;
  }

  .gate-tag {
    justify-self: start;
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: var(--r-pill);
    line-height: 1;
  }
  .gate-tag.rl {
    color: var(--accent-strong);
    background: var(--accent-soft);
    box-shadow: 0 0 0 1px var(--accent-tint) inset;
  }
  .gate-tag.block {
    color: var(--danger);
    background: var(--danger-soft);
  }

  /* Tone → status ramp (signal color, halo, border accent). */
  .gate-node[data-tone='pass'] {
    --sig: var(--success);
    --sig-halo: color-mix(in oklab, var(--success) 20%, transparent);
    --sig-glow: color-mix(in oklab, var(--success) 55%, transparent);
    --track: color-mix(in oklab, var(--success) 45%, var(--border));
    border-color: color-mix(in oklab, var(--success) 32%, var(--border));
  }
  .gate-node[data-tone='watch'] {
    --sig: var(--warn);
    --sig-halo: color-mix(in oklab, var(--warn) 20%, transparent);
    --sig-glow: color-mix(in oklab, var(--warn) 55%, transparent);
    --track: color-mix(in oklab, var(--warn) 45%, var(--border));
    border-color: color-mix(in oklab, var(--warn) 34%, var(--border));
  }
  .gate-node[data-tone='danger'] {
    --sig: var(--danger);
    --sig-halo: color-mix(in oklab, var(--danger) 20%, transparent);
    --sig-glow: color-mix(in oklab, var(--danger) 55%, transparent);
    --track: color-mix(in oklab, var(--danger) 45%, var(--border));
    border-color: color-mix(in oklab, var(--danger) 36%, var(--border));
  }
  .gate-node[data-tone='muted'] {
    --sig: var(--faint);
    --sig-halo: color-mix(in oklab, var(--faint) 16%, transparent);
    --sig-glow: transparent;
    --track: var(--border-strong);
    border-color: var(--border);
  }

  /* D4 RL highlight: accent rim + gradient lift, independent of status color. */
  .gate-node[data-rl='true'] {
    background: linear-gradient(180deg, var(--accent-soft) 0%, var(--surface) 62%);
    box-shadow: var(--shadow-sm), 0 0 0 1px var(--accent-tint) inset;
  }
  .gate-node[data-rl='true'] .gate-code { color: var(--accent-strong); }

  .gate-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
    border-top: 1px solid var(--border-faint);
  }
  .gate-tally {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }
  .tally-item {
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .tally-item b {
    font-size: 15px;
    font-weight: 700;
    color: var(--fg-strong);
    font-family: var(--font-mono);
  }
  .tally-item[data-tone='pass'] b { color: var(--success); }
  .tally-item[data-tone='watch'] b { color: var(--warn); }
  .tally-item[data-tone='danger'] b { color: var(--danger); }

  .gate-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 11px;
  }
  .gate-legend li {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
  }
  .legend-swatch {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    background: var(--faint);
  }
  .gate-legend li[data-tone='pass'] .legend-swatch { background: var(--success); }
  .gate-legend li[data-tone='watch'] .legend-swatch { background: var(--warn); }
  .gate-legend li[data-tone='danger'] .legend-swatch { background: var(--danger); }

  .gate-note {
    font-size: 12px;
    line-height: 1.5;
    margin: 0;
  }

  @keyframes gate-rise {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    .gate-node { animation: none; }
    .gate-node:hover { transform: none; }
  }
</style>

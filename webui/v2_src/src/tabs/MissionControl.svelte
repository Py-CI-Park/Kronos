<script lang="ts">
  // Mission Control — unified research-line landing. Pulls real daily/close-slot
  // status where available; RL/blockers/locks are guardrail facts (always true).
  import { onMount } from 'svelte';
  import { dailyOhlcvApi } from '$lib/dailyOhlcvApi';
  import { trainingStatus, metricsLatest } from '$lib/stores';
  import { navigateToTab } from '$lib/routes';

  let progress = $state<any>(null);
  let closeSlot = $state<any>(null);
  let train = $state<any>(null);
  let metrics = $state<any>({});
  trainingStatus.subscribe((v) => (train = v));
  metricsLatest.subscribe((v) => (metrics = v));

  onMount(() => {
    void (async () => {
      try {
        const [p, cs] = await Promise.all([dailyOhlcvApi.progress(), dailyOhlcvApi.closeSlotLatest()]);
        progress = p;
        closeSlot = cs;
      } catch {
        /* fail-closed: static guardrail facts below remain accurate */
      }
    })();
  });

  const dailyVerdict = $derived((progress?.overall_status ?? 'WATCH') as string);
  const closeStatus = $derived((closeSlot?.status ?? closeSlot?.readiness_status ?? 'NOT_STARTED') as string);
  const trainOk = $derived(Boolean(train?.status));

  const locks = ['실거래', '브로커', '주문', '계좌', '페이퍼', '모델빌드', '수익주장'] as const;

  interface Line {
    tab: string;
    nm: string;
    sub: string;
    tone: 'warn' | 'danger' | 'good' | 'idle' | 'accent';
    verdict: string;
    big: string;
    foot: string;
  }
  const lines = $derived<Line[]>([
    { tab: 'daily-ohlcv', nm: '일봉 연구 D0–D9', sub: 'daily-ohlcv', tone: 'warn', verdict: dailyVerdict.includes('PASS') ? 'PASS' : 'WATCH', big: 'D5 · NO-GO locked', foot: 'blocker 2 · D0·D1' },
    { tab: 'daily-ohlcv', nm: '종가매매 (close-slot)', sub: '일봉 D4 · contextual bandit', tone: 'warn', verdict: closeStatus.includes('WATCH') ? 'WATCH' : closeStatus, big: '10 slots · 23bp', foot: '⚠ contextual_bandit 정규화 필요' },
    { tab: 'rl', nm: '강화학습 · 트레이딩', sub: 'intraday · ts_imb RULE baseline', tone: 'danger', verdict: 'NO-GO', big: '23bp · D9 gate', foot: 'locks 7 off · RESEARCH_ONLY' },
    { tab: 'forecast', nm: '예측 · Kronos', sub: 'K-line 추론 · foundation', tone: 'accent', verdict: 'inference', big: 'Kronos predictor', foot: 'tokenizer → predictor' },
    { tab: 'system-health', nm: '시스템 · 학습', sub: 'predictor', tone: 'good', verdict: trainOk ? 'ok' : '확인 중', big: metrics?.runName ? '100.0%' : '—', foot: metrics?.runName ?? 'stom predictor' },
  ]);

  function open(tab: string) {
    navigateToTab(tab);
  }
</script>

<section class="mc" data-mission-control>
  <div class="text-eyebrow">Mission Control · 전 연구 라인 통합 상태</div>
  <h1 class="mc-h1">모든 연구 라인을 한 화면에서</h1>
  <p class="text-muted mc-lede">각 라인의 판정·핵심 지표·미해결 blocker를 한눈에 보고, 카드를 눌러 상세로 들어갑니다. 실거래·수익 경로는 전부 잠금입니다.</p>

  <div class="mc-posture" data-mission-posture>
    <div class="pp"><span class="dot"></span>연구 전용 · 실거래 경로 전부 잠금</div>
    <div class="locks">
      {#each locks as l}<span class="lock">{l} ✕</span>{/each}
    </div>
  </div>

  <div class="mc-grid">
    <div>
      <div class="mc-sec"><h2>연구 라인</h2><span>{lines.length} lines · posture</span></div>
      <div class="mc-lines">
        {#each lines as ln}
          <button type="button" class="mc-line" data-v={ln.tone} onclick={() => open(ln.tab)}>
            <div class="top">
              <div><div class="nm">{ln.nm}</div><div class="sub">{ln.sub}</div></div>
              <span class="pill {ln.tone === 'good' ? 'success' : ln.tone === 'idle' ? '' : ln.tone}"><span class="dot"></span>{ln.verdict}</span>
            </div>
            <div class="big">{ln.big}</div>
            <div class="foot"><span class="bk">{ln.foot}</span><span class="go">열기 →</span></div>
          </button>
        {/each}
      </div>
    </div>

    <div class="mc-rail">
      <div class="panel">
        <h3>미해결 blocker 전체</h3>
        <div class="blk"><span class="g">D0</span><span>price_basis 미검증 — 조정가격 증거 필요 (일봉·종가매매)</span></div>
        <div class="blk"><span class="g">D1</span><span>universe 비공식 — governance 증거·Q-products 격리</span></div>
        <div class="blk"><span class="g">D5</span><span>walk-forward NO-GO — 사전등록 증거 통과 전 잠금</span></div>
      </div>
      <div class="panel">
        <h3>다음 확인</h3>
        <div class="nx"><span class="n">1</span><span>D0–D9 게이트에서 PASS/WATCH/NOT_STARTED 먼저 확인</span></div>
        <div class="nx"><span class="n">2</span><span>close-slot 피처 정규화 버그 — contextual_bandit 0종목</span></div>
        <div class="nx"><span class="n">3</span><span>artifact hash·stale/malformed fail-closed 상태 점검</span></div>
      </div>
      <div class="panel">
        <h3>시스템</h3>
        <div class="kv"><span>predictor</span><strong>{trainOk ? 'ok' : '확인 중'}</strong></div>
        <div class="kv"><span>run</span><strong>{metrics?.runName ?? '—'}</strong></div>
      </div>
    </div>
  </div>
</section>

<style>
  .mc { display: flex; flex-direction: column; gap: 4px; }
  .mc-h1 { font: 700 27px/1.15 var(--font-display); letter-spacing: -0.022em; color: var(--fg-strong); margin: 6px 0 4px; }
  .mc-lede { max-width: 74ch; }
  .mc-posture { display: flex; align-items: center; gap: 16px; padding: 13px 18px; margin-top: 16px;
    border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--border); box-shadow: var(--shadow-sm); flex-wrap: wrap; }
  .mc-posture .pp { font: 700 14px/1.1 var(--font-display); display: flex; align-items: center; gap: 10px; }
  .mc-posture .pp .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--warn); box-shadow: 0 0 0 4px var(--warn-soft); }
  .mc-posture .locks { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
  .mc-posture .lock { font: 600 10px/1 var(--font-mono); padding: 5px 9px; border-radius: var(--r-pill); background: var(--danger-soft); color: var(--danger); }
  .mc-grid { display: grid; grid-template-columns: 1.7fr 1fr; gap: 18px; margin-top: 18px; align-items: start; }
  @media (max-width: 1100px) { .mc-grid { grid-template-columns: 1fr; } }
  .mc-sec { display: flex; align-items: baseline; gap: 10px; margin: 2px 0 12px; }
  .mc-sec h2 { font: 650 15px/1 var(--font-display); letter-spacing: -0.01em; color: var(--fg-strong); }
  .mc-sec span { font: 500 12px/1 var(--font-mono); color: var(--muted); }
  .mc-lines { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  @media (max-width: 820px) { .mc-lines { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 560px) { .mc-lines { grid-template-columns: 1fr; } }
  .mc-line { text-align: left; cursor: pointer; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
    padding: 15px 15px 13px; position: relative; overflow: hidden; box-shadow: var(--shadow-sm);
    transition: transform var(--d-fast) var(--ease-out), box-shadow var(--d-fast) var(--ease-out), border-color var(--d-fast) var(--ease-out); }
  .mc-line:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: var(--border-strong); }
  .mc-line::after { content: ''; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--warn); }
  .mc-line[data-v="danger"]::after { background: var(--danger); }
  .mc-line[data-v="good"]::after { background: var(--success); }
  .mc-line[data-v="idle"]::after { background: var(--dim); }
  .mc-line[data-v="accent"]::after { background: var(--accent); }
  .mc-line .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
  .mc-line .nm { font: 650 14px/1.25 var(--font-display); color: var(--fg-strong); }
  .mc-line .sub { font: 500 11px/1.3 var(--font-mono); color: var(--muted); margin-top: 3px; }
  .mc-line .big { font: 700 20px/1.1 var(--font-display); letter-spacing: -0.02em; color: var(--fg-strong); margin: 14px 0 2px; }
  .mc-line .foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 12px; font: 600 11px/1.3 var(--font-mono); }
  .mc-line .bk { color: var(--muted); } .mc-line .go { color: var(--accent-strong); }
  .mc-rail { display: flex; flex-direction: column; gap: 16px; }
  .mc-rail .panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 16px 18px; box-shadow: var(--shadow-sm); }
  .mc-rail h3 { font: 650 13px/1 var(--font-display); color: var(--fg-strong); margin: 0 0 12px; }
  .mc-rail .blk { display: flex; gap: 11px; padding: 9px 0; border-bottom: 1px dashed var(--border-faint); font-size: 12.5px; color: var(--muted); }
  .mc-rail .blk:last-child { border-bottom: 0; } .mc-rail .blk .g { font: 700 10px/1.6 var(--font-mono); color: var(--danger); }
  .mc-rail .nx { display: flex; gap: 9px; padding: 8px 0; font-size: 12.5px; color: var(--muted); border-bottom: 1px dashed var(--border-faint); }
  .mc-rail .nx:last-child { border-bottom: 0; } .mc-rail .nx .n { color: var(--accent-strong); font-weight: 700; }
  .mc-rail .kv { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; padding: 5px 0; }
  .mc-rail .kv span { color: var(--muted); } .mc-rail .kv strong { color: var(--fg); font-family: var(--font-mono); font-weight: 600; word-break: break-all; }
</style>

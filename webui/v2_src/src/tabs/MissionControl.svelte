<script lang="ts">
  // Mission Control — 전 연구 라인 통합 계기판(instrument panel).
  // 원칙: 라이브 값은 API/스토어에서 파생하고 fail-open 시 '확인 중'을 노출.
  //       가드레일 사실(연구 전용 posture, 7 false-lock, D5 NO-GO)은 파생하지
  //       않고 FACT 로 라벨링해 정직하게 표기. close-slot 0종목 선택 사유는
  //       하드코딩하지 않고 API의 data_recency/close_slot_blockers/
  //       chosen_is_no_trade_sentinel에서 라이브로 파생한다(closeSlotFoot).
  import { onMount } from 'svelte';
  import { dailyOhlcvApi } from '$lib/dailyOhlcvApi';
  import { rlApi } from '$lib/rlApi';
  import { num, rowNumber } from '$lib/rlRows';
  import { formatReward, resolveMetricMetadata } from '$lib/runMetrics';
  import { trainingStatus, metricsLatest } from '$lib/stores';
  import { navigateToTab } from '$lib/routes';
  import { humanizeVerdict } from '$lib/verdictLabel';
  import { deriveDisplayStatus, statusLabel, statusTone, type LifecycleStatus } from '$lib/runLifecycle';

  type Tone = 'warn' | 'danger' | 'success' | 'accent' | 'idle';
  type Src = 'live' | 'fact';

  let progress = $state<any>(null);
  let closeSlot = $state<any>(null);
  let train = $state<any>(null);
  let metrics = $state<any>({});
  // WP-S4(A) — RL 인트라데이 카드의 LIVE 서브라인. rlApi.rlEvents tail의 마지막
  // 행(latest global_step + reward)만 읽는다. NO-GO FACT 판정과는 무관한 관측치.
  let rlLiveEvent = $state<{ step: string; reward: string } | null>(null);
  // Todo6 — 최신 run 의 backend lifecycle 스냅샷으로부터 도출한 정직한 상태.
  // Mission Control 은 cross-poll 관측(step 진행)을 하지 않으므로 polling=false 로
  // 고정한다 — 즉 이 화면은 절대 RUNNING(LIVE)을 표기하지 않고, 백엔드 스냅샷 그대로
  // COMPLETED/REPLAY/IDLE/MISSING 중 하나만 정직하게 보여준다.
  let rlLifecycleStatus = $state<LifecycleStatus>('MISSING');
  trainingStatus.subscribe((v) => (train = v));
  metricsLatest.subscribe((v) => (metrics = v));

  onMount(() => {
    void (async () => {
      try {
        const [p, cs] = await Promise.all([dailyOhlcvApi.progress(), dailyOhlcvApi.closeSlotLatest()]);
        progress = p;
        closeSlot = cs;
      } catch {
        /* fail-open: 라이브 값은 '확인 중'으로 남고 가드레일 사실은 아래에서 그대로 유효 */
      }
    })();
    void (async () => {
      try {
        const runsResp = await rlApi.rlRuns(5);
        const latestRun = runsResp?.runs?.[0];
        rlLifecycleStatus = deriveDisplayStatus(latestRun?.lifecycle ?? null, {
          prevStep: null,
          currentStep: null,
          polling: false,
          wasRunning: false,
        });
        const latestRunName = latestRun?.name;
        if (!latestRunName) return;
        const eventsResp = await rlApi.rlEvents(latestRunName, 20);
        const latestRow = eventsResp?.rows?.length ? eventsResp.rows[eventsResp.rows.length - 1] : null;
        if (latestRow) {
          rlLiveEvent = {
            step: num(rowNumber(latestRow, 'global_step'), 0),
            reward: formatReward(latestRow, resolveMetricMetadata(latestRow)),
          };
        }
      } catch {
        /* fail-open: rl runs/events 조회 실패 시 rlLiveEvent는 null로 남고 아래에서 PENDING('확인 중')으로 표시.
           rlLifecycleStatus 는 초기값 'MISSING' 으로 남는다(정직한 fail-closed). */
      }
    })();
  });

  const PENDING = '확인 중';
  function toneOf(s: string): Tone {
    const t = (s ?? '').toUpperCase();
    if (t.includes('NO-GO') || t.includes('BLOCK') || t.includes('FAIL')) return 'danger';
    if (t.includes('WATCH') || t.includes('RESEARCH') || t.includes('PENDING') || t.includes('확인')) return 'warn';
    if (t.includes('PASS') || t.includes('READY') || t.includes('OK')) return 'success';
    return 'idle';
  }

  // ── 라이브 파생 (fail-open → PENDING) ─────────────────────────────
  const dailyVerdict = $derived((progress?.overall_status ?? PENDING) as string);
  const closeVerdict = $derived((closeSlot?.status ?? closeSlot?.readiness_status ?? PENDING) as string);
  const trainState = $derived((train?.readiness?.label ?? train?.status ?? PENDING) as string);
  const closeMetric = $derived(
    closeSlot ? `${closeSlot.max_slot_count ?? 10} slot · ${closeSlot.round_trip_cost_bp ?? 23}bp` : PENDING
  );
  // Authoritative structured evidence from the backend's data_recency /
  // close_slot_blockers / chosen_is_no_trade_sentinel fields (never a
  // hardcoded blocker count or an invented 'normalization bug' claim).
  const closeSlotRecencyLabel = $derived((closeSlot?.data_recency?.label ?? PENDING) as string);
  const closeSlotBlockerList = $derived((closeSlot?.close_slot_blockers ?? []) as string[]);
  const closeSlotIsNoTradeSentinel = $derived(closeSlot?.chosen_is_no_trade_sentinel === true);
  const closeSlotFoot = $derived(
    closeSlot == null
      ? PENDING
      : closeSlotIsNoTradeSentinel
        ? `${closeSlotRecencyLabel} · 0종목 선택 — 무거래가 정직한 최적 (sentinel=true)`
        : closeSlotBlockerList.length
          ? `${closeSlotRecencyLabel} · blocker ${closeSlotBlockerList.length}건`
          : `${closeSlotRecencyLabel} · blocker 없음`
  );
  const trainMetric = $derived(
    train?.overall_percent != null
      ? `${Number(train.overall_percent).toFixed(1)}%`
      : (train?.status ?? PENDING) as string
  );
  const runName = $derived((metrics?.runName ?? null) as string | null);
  // WP-S4(A) — RL LIVE 서브라인 표시 문자열. rlLiveEvent가 없으면(로딩 중/실패)
  // 기존 PENDING 패턴('확인 중')으로 fail-open한다. NO-GO FACT 판정에는 영향 없음.
  const rlLiveLine = $derived(rlLiveEvent ? `step ${rlLiveEvent.step} · reward ${rlLiveEvent.reward}` : PENDING);
  // Todo6 — 서브라인 태그 문구/톤은 하드코딩 'LIVE' 대신 백엔드 lifecycle 스냅샷에서
  // 정직하게 도출한다(polling=false 이므로 절대 RUNNING 이 아님 — COMPLETED/REPLAY/
  // IDLE/MISSING 중 하나).
  const rlLifecycleLabel = $derived(statusLabel(rlLifecycleStatus));
  const rlLifecycleTone = $derived(statusTone(rlLifecycleStatus));

  // ── 계기판 게이지 (한눈 스캔) ────────────────────────────────────
  const locks = ['실거래', '브로커', '주문', '계좌', '페이퍼', '모델빌드', '수익주장'] as const;

  interface Gauge { k: string; v: string; tone: Tone; src: Src; }
  const gauges = $derived<Gauge[]>([
    { k: '일봉 D0–D9', v: dailyVerdict, tone: toneOf(dailyVerdict), src: 'live' },
    { k: '종가 close-slot', v: closeVerdict, tone: toneOf(closeVerdict), src: 'live' },
    { k: 'RL 인트라데이', v: 'NO-GO', tone: 'danger', src: 'fact' },
    { k: '학습 predictor', v: trainState, tone: toneOf(trainState), src: 'live' },
  ]);

  // ── 연구 라인 카드 · 단일 통합 그리드 (한눈 스캔) ────────────────
  interface Card {
    tab: string; nm: string; sub: string; tone: Tone;
    verdict: string; vsrc: Src; big: string; bsrc: Src; foot: string;
    scroll?: string;
    // WP-S4(A) — optional LIVE sub-line (RL 카드 전용: latest step/reward) + 두 번째
    // 클릭 타깃(가이드 보기). 지정되지 않은 카드는 기존 렌더링과 동일하게 유지된다.
    liveSub?: string;
    // Todo6 — liveSub 태그의 정직한 라벨/톤. lifecycle 도출값이 'accent'(RUNNING)일
    // 때만 눈에 띄는 live 스타일을 쓰고, 그 외에는 FACT 톤 스타일로 표기한다.
    liveSubLabel?: string;
    liveSubTone?: 'accent' | 'warn' | 'ok' | 'danger' | 'idle';
    guideTab?: string;
  }

  // 미해결 blocker — D0–D9 게이트 롤업(FACT). 요약 카드와 상세 rail 이 같은 원천을 공유.
  interface Blocker { g: string; id: string; text: string; }
  const blockers: Blocker[] = [
    { g: 'D0', id: 'price_basis', text: 'price_basis 미검증 — 조정가격 증거 필요 (일봉·종가매매)' },
    { g: 'D1', id: 'universe', text: 'universe 비공식 — governance 증거 · Q-products 격리' },
    { g: 'D5', id: 'WF', text: 'walk-forward NO-GO — 사전등록 증거 통과 전 잠금' },
  ];
  const blockerSummary = blockers.map((b) => b.id).join(' · ');

  // 모든 연구 라인 + blocker 롤업을 동일 가중치 카드로 한 배열에 통합.
  // 데이터 파생(LIVE dailyVerdict/closeVerdict/trainState, FACT 가드레일)은 그대로 보존.
  const lines = $derived<Card[]>([
    { tab: 'forecast', nm: '예측 워크벤치', sub: 'Kronos · K-line 추론', tone: 'accent',
      verdict: '추론', vsrc: 'fact', big: 'Kronos predictor', bsrc: 'fact',
      foot: 'tokenizer → predictor · 독립 축' },
    { tab: 'daily-ohlcv', nm: '일봉 연구 D0–D9', sub: 'daily-ohlcv · 파이프라인 게이트', tone: toneOf(dailyVerdict),
      verdict: dailyVerdict, vsrc: 'live', big: 'D5 · NO-GO', bsrc: 'fact',
      foot: 'blocker · D0 price_basis / D1 universe' },
    { tab: 'daily-ohlcv', nm: '종가매매 close-slot', sub: '일봉 D4 · contextual bandit', tone: toneOf(closeVerdict),
      verdict: closeVerdict, vsrc: 'live', big: closeMetric, bsrc: 'live',
      foot: closeSlotFoot },
    { tab: 'rl', nm: '강화학습 · 인트라데이', sub: 'intraday · ts_imb RULE baseline', tone: 'danger',
      verdict: 'NO-GO', vsrc: 'fact', big: 'RESEARCH_ONLY', bsrc: 'fact',
      foot: 'D9 gate · locks 7 off', liveSub: rlLiveLine, liveSubLabel: rlLifecycleLabel, liveSubTone: rlLifecycleTone,
      guideTab: 'daily-rl-guide' },
    { tab: 'system-health', nm: '학습 · 시스템', sub: 'predictor · live-training', tone: toneOf(trainState),
      verdict: trainState, vsrc: 'live', big: trainMetric, bsrc: 'live',
      foot: runName ?? 'stom predictor' },
    { tab: 'daily-ohlcv', nm: '미해결 blocker', sub: 'D0–D9 게이트 롤업', tone: 'warn',
      verdict: `${blockers.length} open`, vsrc: 'fact', big: `${blockers.length} blocker`, bsrc: 'fact',
      foot: blockerSummary, scroll: 'mc-blockers' },
  ]);

  const lineCount = $derived(lines.length);

  function open(tab: string) {
    navigateToTab(tab);
  }

  // WP-S4(A) — 가이드 보기: 두 번째 클릭 타깃. 부모 .mc-line 버튼과 중첩되지 않는
  // 형제 버튼에서 호출하므로 stopPropagation으로 부모의 open(ln.tab)을 막는다.
  function openGuide(tab: string | undefined, event: MouseEvent): void {
    event.stopPropagation();
    if (tab) navigateToTab(tab);
  }

  function scrollToId(id: string) {
    if (typeof document === 'undefined') return;
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

<section class="mc" data-mission-control>
  <div class="text-eyebrow">Mission Control · 전 연구 라인 통합 계기판</div>
  <h1 class="mc-h1">모든 연구 라인을 한 계기판에서</h1>
  <p class="text-muted mc-lede">라인별 판정·핵심 지표·미해결 blocker를 한눈에 읽고, 카드를 눌러 상세로 들어갑니다. 실거래·수익 경로는 전부 잠금입니다.</p>

  <div class="mc-posture" data-mission-posture>
    <div class="pp"><span class="dot"></span>연구 전용 · 실거래 경로 전부 잠금</div>
    <div class="locks">
      {#each locks as l}<span class="lock">{l} ✕</span>{/each}
    </div>
  </div>

  <!-- 계기판 readout: 4 게이지 한눈 스캔 -->
  <div class="readout" role="group" aria-label="연구 라인 계기판">
    {#each gauges as g}
      <div class="gauge" data-t={g.tone}>
        <div class="gh"><span class="dot"></span><span class="gk">{g.k}</span><span class="tag {g.src}">{g.src === 'live' ? 'LIVE' : 'FACT'}</span></div>
        <div class="gv">{humanizeVerdict(g.v)}</div>
      </div>
    {/each}
  </div>

  <div class="mc-grid">
    <div class="mc-main">
      <div class="mc-sec">
        <h2>연구 라인</h2>
        <span>{lineCount} cards · 단일 그리드</span>
        <span class="legend"><i class="lg live"></i>LIVE 파생 <i class="lg fact"></i>FACT 가드레일</span>
      </div>

      <div class="mc-lines">
        {#each lines as ln}
          <div class="mc-line-wrap">
            <button type="button" class="mc-line" data-v={ln.tone} onclick={() => (ln.scroll ? scrollToId(ln.scroll) : open(ln.tab))}>
              <div class="top">
                <div class="ttl"><div class="nm">{ln.nm}</div><div class="sub">{ln.sub}</div></div>
                <span class="pill {ln.tone === 'idle' ? '' : ln.tone}"><span class="dot"></span>{humanizeVerdict(ln.verdict)}<span class="tag {ln.vsrc} inv">{ln.vsrc === 'live' ? 'LIVE' : 'FACT'}</span></span>
              </div>
              <div class="big">{ln.big}<span class="tag {ln.bsrc}">{ln.bsrc === 'live' ? 'LIVE' : 'FACT'}</span></div>
              {#if ln.liveSub}
                <div class="mc-live-sub" data-mc-rl-live-sub><span class="tag {ln.liveSubTone === 'accent' ? 'live' : 'fact'}">{ln.liveSubLabel ?? 'FACT'}</span><span>{ln.liveSub}</span></div>
              {/if}
              <div class="foot"><span class="bk">{ln.foot}</span><span class="go">열기 →</span></div>
            </button>
            {#if ln.guideTab}
              <button
                type="button"
                class="mc-line-guide-btn"
                data-mc-rl-guide-link
                onclick={(event) => openGuide(ln.guideTab, event)}
              >가이드 보기 →</button>
            {/if}
          </div>
        {/each}
      </div>
    </div>

    <div class="mc-rail">
      <div class="panel" id="mc-blockers">
        <h3>미해결 blocker <span class="rc">FACT</span></h3>
        {#each blockers as b}
          <div class="blk"><span class="g">{b.g}</span><span>{b.text}</span></div>
        {/each}
      </div>
      <div class="panel">
        <h3>다음 확인</h3>
        <div class="nx"><span class="n">1</span><span>D0–D9 게이트에서 PASS/WATCH/NOT_STARTED 우선 확인</span></div>
        <div class="nx"><span class="n">2</span><span>{closeSlotFoot} — close_slot_blockers/verdict 근거 확인</span></div>
        <div class="nx"><span class="n">3</span><span>artifact hash · stale/malformed → fail-closed 상태 점검</span></div>
      </div>
      <div class="panel">
        <h3>시스템 <span class="rc live">LIVE</span></h3>
        <div class="kv"><span>predictor</span><strong>{trainState}</strong></div>
        <div class="kv"><span>run</span><strong>{runName ?? '—'}</strong></div>
      </div>
    </div>
  </div>
</section>

<style>
  .mc { display: flex; flex-direction: column; gap: 4px; }
  .mc-h1 { font: 700 27px/1.15 var(--font-display); letter-spacing: -0.022em; color: var(--fg-strong); margin: 6px 0 4px; }
  .mc-lede { max-width: 74ch; }

  /* posture strip */
  .mc-posture { display: flex; align-items: center; gap: 16px; padding: 15px 18px; margin-top: 16px;
    border-radius: var(--r-lg); border: 1px solid var(--border); box-shadow: var(--shadow-md), var(--card-highlight); flex-wrap: wrap;
    background: linear-gradient(100deg, color-mix(in oklab, var(--accent) 13%, var(--surface)) 0%, var(--surface) 52%); }
  .mc-posture .pp { font: 700 14px/1.1 var(--font-display); display: flex; align-items: center; gap: 10px; }
  .mc-posture .pp .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--warn); box-shadow: 0 0 0 4px var(--warn-soft); }
  .mc-posture .locks { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
  .mc-posture .lock { font: 600 10px/1 var(--font-mono); padding: 5px 9px; border-radius: var(--r-pill); background: var(--danger-soft); color: var(--danger); }

  /* 계기판 readout — 4 게이지 인스트루먼트 클러스터 */
  .readout { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 14px;
    background: var(--card-grad); border: 1px solid var(--border); border-radius: var(--r-lg);
    box-shadow: var(--shadow-md), var(--card-highlight); overflow: hidden; }
  @media (max-width: 880px) { .readout { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 460px) { .readout { grid-template-columns: 1fr; } }
  .gauge { padding: 15px 17px 16px; border-left: 1px solid var(--border-faint); position: relative; min-width: 0; }
  .gauge:first-child { border-left: 0; }
  @media (max-width: 880px) { .gauge:nth-child(odd) { border-left: 0; } .gauge:nth-child(n+3) { border-top: 1px solid var(--border-faint); } }
  @media (max-width: 460px) { .gauge { border-left: 0; } .gauge:nth-child(n+2) { border-top: 1px solid var(--border-faint); } }
  .gauge::before { content: ''; position: absolute; inset: 0 auto auto 0; width: 3px; height: 100%; background: var(--dim); opacity: .55; }
  .gauge[data-t="warn"]::before { background: var(--warn); }
  .gauge[data-t="danger"]::before { background: var(--danger); }
  .gauge[data-t="success"]::before { background: var(--success); }
  .gauge[data-t="accent"]::before { background: var(--accent); }
  .gauge .gh { display: flex; align-items: center; gap: 7px; }
  .gauge .gh .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--dim); flex: none; }
  .gauge[data-t="warn"] .gh .dot { background: var(--warn); box-shadow: 0 0 0 3px var(--warn-soft); }
  .gauge[data-t="danger"] .gh .dot { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-soft); }
  .gauge[data-t="success"] .gh .dot { background: var(--success); box-shadow: 0 0 0 3px var(--success-soft); }
  .gauge[data-t="accent"] .gh .dot { background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .gauge .gk { font: 600 11px/1.2 var(--font-mono); color: var(--muted); letter-spacing: -0.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gauge .gv { font: 800 21px/1.1 var(--font-display); letter-spacing: -0.03em; color: var(--fg-strong); margin-top: 9px;
    overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

  /* src tags — LIVE(파생) vs FACT(가드레일 사실) 정직 라벨 */
  .tag { font: 700 8.5px/1 var(--font-mono); letter-spacing: 0.06em; padding: 3px 5px; border-radius: 5px; margin-left: auto; flex: none; }
  .tag.live { background: var(--accent-soft); color: var(--accent-strong); }
  .tag.fact { background: color-mix(in oklab, var(--muted) 16%, transparent); color: var(--muted); }
  .tag.inv { margin-left: 6px; opacity: .85; }

  .legend { display: inline-flex; align-items: center; gap: 6px; font: 500 10.5px/1 var(--font-mono); color: var(--dim); margin-left: auto; }
  .legend .lg { width: 8px; height: 8px; border-radius: 3px; display: inline-block; }
  .legend .lg.live { background: var(--accent); } .legend .lg.fact { background: var(--dim); }
  .legend .lg.fact { margin-left: 8px; }

  /* grid */
  .mc-grid { display: grid; grid-template-columns: 1.7fr 1fr; gap: 18px; margin-top: 18px; align-items: start; }
  @media (max-width: 1100px) { .mc-grid { grid-template-columns: 1fr; } }
  .mc-main { display: flex; flex-direction: column; gap: 18px; }
  .mc-sec { display: flex; align-items: baseline; gap: 10px; }
  .mc-sec h2 { font: 650 15px/1 var(--font-display); letter-spacing: -0.01em; color: var(--fg-strong); }
  .mc-sec > span { font: 500 12px/1 var(--font-mono); color: var(--muted); }

  .mc-lines { display: grid; grid-template-columns: repeat(3, 1fr); gap: 13px; }
  @media (max-width: 820px) { .mc-lines { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 560px) { .mc-lines { grid-template-columns: 1fr; } }

  /* WP-S4(A) — wrapper holds the primary .mc-line button plus an optional sibling
     "가이드 보기" button. Two independent button click targets must not nest. */
  .mc-line-wrap { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .mc-line-wrap .mc-line { flex: 1; }
  .mc-live-sub { display: flex; align-items: center; gap: 7px; margin-top: 10px; padding-top: 10px;
    border-top: 1px dashed var(--border-faint); font: 600 11.5px/1.3 var(--font-mono); color: var(--fg); }
  .mc-live-sub .tag.live { margin-left: 0; }
  .mc-line-guide-btn { align-self: flex-start; text-align: left; cursor: pointer; font: 650 11.5px/1 var(--font-mono);
    color: var(--accent-strong); background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-pill);
    padding: 7px 12px; transition: border-color var(--d-fast) var(--ease-out), transform var(--d-fast) var(--ease-out); }
  .mc-line-guide-btn:hover { border-color: var(--accent-strong); transform: translateY(-1px); }

  .mc-line { text-align: left; cursor: pointer; background: var(--card-grad); border: 1px solid var(--border); border-radius: var(--r-lg);
    padding: 16px 16px 13px; position: relative; overflow: hidden; box-shadow: var(--shadow-md), var(--card-highlight);
    transition: transform var(--d-fast) var(--ease-out), box-shadow var(--d-fast) var(--ease-out), border-color var(--d-fast) var(--ease-out); }
  .mc-line:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg), var(--card-highlight); border-color: var(--border-strong); }
  .mc-line::after { content: ''; position: absolute; inset: 0 0 auto 0; height: 3px; background: linear-gradient(90deg, var(--dim), transparent 72%); }
  .mc-line[data-v="warn"]::after { background: linear-gradient(90deg, var(--warn), transparent 72%); }
  .mc-line[data-v="danger"]::after { background: linear-gradient(90deg, var(--danger), transparent 72%); }
  .mc-line[data-v="success"]::after { background: linear-gradient(90deg, var(--success), transparent 72%); }
  .mc-line[data-v="accent"]::after { background: linear-gradient(90deg, var(--accent), var(--accent-strong) 55%, transparent); }
  .mc-line .top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 10px; }
  .mc-line .ttl { min-width: 120px; flex: 1 1 auto; }
  .mc-line .nm { font: 650 14px/1.25 var(--font-display); color: var(--fg-strong); word-break: keep-all; overflow-wrap: anywhere; }
  .mc-line .sub { font: 500 11px/1.3 var(--font-mono); color: var(--muted); margin-top: 3px; word-break: keep-all; overflow-wrap: anywhere; }
  .mc-line .pill { flex: none; max-width: 100%; overflow-wrap: anywhere; }
  .mc-line .pill .tag.inv { padding: 2px 4px; }
  .mc-line .big { display: flex; align-items: center; gap: 8px; font: 800 21px/1.05 var(--font-display); letter-spacing: -0.03em; color: var(--fg-strong); margin: 14px 0 2px; }
  .mc-line .big .tag { margin-left: 0; }
  .mc-line .foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 11px; font: 600 11px/1.3 var(--font-mono); }
  .mc-line .bk { color: var(--muted); min-width: 0; } .mc-line .go { color: var(--accent-strong); flex: none; }

  /* rail */
  .mc-rail { display: flex; flex-direction: column; gap: 16px; }
  .mc-rail .panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 16px 18px; box-shadow: var(--shadow-sm); }
  .mc-rail h3 { font: 650 13px/1 var(--font-display); color: var(--fg-strong); margin: 0 0 12px; display: flex; align-items: center; gap: 8px; }
  .mc-rail h3 .rc { font: 700 8.5px/1 var(--font-mono); letter-spacing: 0.06em; padding: 3px 5px; border-radius: 5px; margin-left: auto;
    background: color-mix(in oklab, var(--muted) 16%, transparent); color: var(--muted); }
  .mc-rail h3 .rc.live { background: var(--accent-soft); color: var(--accent-strong); }
  .mc-rail .blk { display: flex; gap: 11px; padding: 9px 0; border-bottom: 1px dashed var(--border-faint); font-size: 12.5px; color: var(--muted); }
  .mc-rail .blk:last-child { border-bottom: 0; } .mc-rail .blk .g { font: 700 10px/1.6 var(--font-mono); color: var(--danger); flex: none; }
  .mc-rail .nx { display: flex; gap: 9px; padding: 8px 0; font-size: 12.5px; color: var(--muted); border-bottom: 1px dashed var(--border-faint); }
  .mc-rail .nx:last-child { border-bottom: 0; } .mc-rail .nx .n { color: var(--accent-strong); font-weight: 700; flex: none; }
  .mc-rail .kv { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; padding: 5px 0; }
  .mc-rail .kv span { color: var(--muted); } .mc-rail .kv strong { color: var(--fg); font-family: var(--font-mono); font-weight: 600; word-break: break-all; text-align: right; }
</style>

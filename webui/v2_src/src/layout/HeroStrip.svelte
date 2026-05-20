<script lang="ts">
  import { trainingStatus, metricsLatest, lastUpdatedAt } from '$lib/stores';
  import { fmt } from '$lib/format';

  let status = $state<any>(null);
  trainingStatus.subscribe((v) => (status = v));

  let m = $state<any>({});
  metricsLatest.subscribe((v) => (m = v));

  let last = $state('-');
  lastUpdatedAt.subscribe((v) => (last = v));

  let latest = $derived(status?.latest_stage ?? {});
  let stages = $derived<any[]>(Array.isArray(status?.stages) ? status.stages : []);
  let tokenizer = $derived(stages.find((s) => s.train_stage === 'tokenizer'));
  let predictor = $derived(stages.find((s) => s.train_stage === 'predictor'));
  let stagePct = $derived(latest.stage_percent ?? 0);
  let overallPct = $derived(latest.overall_percent ?? 0);
  let sps = $derived(latest.samples_per_second ?? null);
  let etaSeconds = $derived(latest.eta_seconds ?? null);
  let etaCompact = $derived(fmt.durationCompact(etaSeconds));
  let etaFinish = $derived(fmt.finishKst(etaSeconds, latest.updated_at));
  let stageName = $derived(latest.train_stage ?? '-');
  let readinessLevel = $derived(status?.readiness?.level ?? 'waiting');
  let readinessLabel = $derived(
    readinessLevel === 'ready' ? 'Predictor 완료' :
    readinessLevel === 'training' ? '학습 진행 중' :
    'Predictor 대기'
  );

  function stageState(stage: any, isCurrent: boolean): 'active' | 'done' | 'pending' {
    if (!stage) return 'pending';
    const stat = stage.status;
    if (['ok', 'recovered', 'complete', 'completed', 'done', 'finished', 'success', 'succeeded'].includes(stat)) return 'done';
    if (isCurrent || stat === 'running' || stat === 'active') return 'active';
    return 'pending';
  }
</script>

<section class="hero">
  <div class="hero-left">
    <div class="hero-eyebrow">
      <span>실시간 학습 모니터 · /api/training/status</span>
      <span class="header-stat" style="padding:4px 10px;font-size:11px">
        <span class="header-stat-dot live"></span>live
      </span>
    </div>

    <h1 class="hero-title">
      {#if m.runName}
        <span class="text-mono" style="font-size:18px;font-weight:600;letter-spacing:0;color:var(--muted);display:block;margin-bottom:6px">
          {m.runName}
        </span>
      {/if}
      {stageName} 단계 <span class="accent">{fmt.pct(stagePct)} 진행</span>
    </h1>

    <p class="hero-sub">
      현재 stage <span class="text-mono" style="color:var(--fg);font-weight:600">{stageName}</span>,
      Epoch <span class="text-mono" style="color:var(--fg);font-weight:600">{m.epoch ?? '-'}/{m.epochs ?? '-'}</span>,
      처리 속도 <span class="text-mono" style="color:var(--accent-strong);font-weight:600">{fmt.num(sps, 1)} samples/s</span>.
      Predictor 단계는 Tokenizer 완료 시 자동 진입합니다.
    </p>

    <div class="stepper" style="margin-top:8px">
      <div class="step" data-state={stageState(tokenizer, latest.train_stage === 'tokenizer')}>
        <div class="row spread">
          <span class="step-num">STAGE 1</span>
          {#if stageState(tokenizer, latest.train_stage === 'tokenizer') === 'active'}
            <span class="pill accent"><span class="dot"></span>진행 중</span>
          {:else if stageState(tokenizer, false) === 'done'}
            <span class="pill success"><span class="dot"></span>완료</span>
          {:else}
            <span class="pill"><span class="dot"></span>대기</span>
          {/if}
        </div>
        <div class="step-title">Tokenizer · K-line 양자화</div>
        <div class="step-meta">
          step
          <span class="text-mono tnum" style="color:var(--fg-strong);font-weight:600">
            {fmt.int(tokenizer?.step)} / {fmt.int(tokenizer?.total_steps)}
          </span>
          · loss
          <span class="text-mono tnum" style="color:var(--accent-strong);font-weight:600">
            {m.loss != null ? m.loss.toFixed(4) : '—'}
          </span>
        </div>
        <div class="step-bar"><span style:width={`${tokenizer?.stage_percent ?? 0}%`}></span></div>
      </div>

      <div class="arrow" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </div>

      <div class="step" data-state={stageState(predictor, latest.train_stage === 'predictor')}>
        <div class="row spread">
          <span class="step-num">STAGE 2</span>
          {#if stageState(predictor, latest.train_stage === 'predictor') === 'active'}
            <span class="pill accent"><span class="dot"></span>진행 중</span>
          {:else if stageState(predictor, false) === 'done'}
            <span class="pill success"><span class="dot"></span>완료</span>
          {:else}
            <span class="pill"><span class="dot"></span>대기</span>
          {/if}
        </div>
        <div class="step-title">Predictor · 다음 step 예측</div>
        <div class="step-meta">
          step
          <span class="text-mono tnum" style="color:var(--muted)">
            {fmt.int(predictor?.step ?? 0)} / {fmt.int(predictor?.total_steps ?? 0)}
          </span>
          · loss <span class="text-mono" style="color:var(--muted)">—</span>
        </div>
        <div class="step-bar"><span style:width={`${predictor?.stage_percent ?? 0}%`}></span></div>
      </div>
    </div>
  </div>

  <div class="hero-right">
    <div class="card glow" style="padding:20px;gap:16px;align-items:center">
      <div class="row spread" style="width:100%">
        <span class="card-eyebrow">실행 요약</span>
        <span class="signal" data-level={readinessLevel === 'ready' ? 'ready' : readinessLevel === 'training' ? 'ready' : 'waiting'}>
          <span class="light"></span>
          <span>{readinessLabel}</span>
        </span>
      </div>

      <div class="hero-summary">
        <div>
          <div class="text-eyebrow">전체 진행</div>
          <strong class="text-mono tnum">{fmt.pct(overallPct, 1)}</strong>
          <span>단계 구간은 아래 원형 그래프에서 확인</span>
        </div>
        <div>
          <div class="text-eyebrow">현재 단계</div>
          <strong class="text-mono tnum">{fmt.pct(stagePct, 1)}</strong>
          <span>{stageName}</span>
        </div>
      </div>

      <div class="grid-2" style="width:100%">
        <div>
          <div class="text-eyebrow">완료 예상</div>
          <div class="text-mono tnum" style="font-size:22px;font-weight:600;color:var(--fg-strong);margin-top:4px">{etaCompact}</div>
          <div class="text-caption" style="margin-top:2px">{etaFinish}</div>
        </div>
        <div>
          <div class="text-eyebrow">처리 속도</div>
          <div class="text-mono tnum" style="font-size:22px;font-weight:600;color:var(--fg-strong);margin-top:4px">{fmt.num(sps, 1)}</div>
          <div class="text-caption" style="margin-top:2px">samples / second</div>
        </div>
      </div>

      <div style="width:100%;padding-top:8px;border-top:1px solid var(--border-faint);display:flex;align-items:center;justify-content:space-between;gap:8px">
        <span class="text-caption">Polling <span class="text-mono" style="color:var(--fg)">5초</span></span>
        <span class="text-caption">마지막 업데이트 <span class="text-mono" style="color:var(--fg)">{last}</span></span>
      </div>
    </div>
  </div>
</section>

<style>
  .hero-summary {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .hero-summary > div {
    padding: 14px;
    border-radius: var(--r-md);
    background: var(--surface-sunken);
    border: 1px solid var(--border-faint);
  }
  .hero-summary strong {
    display: block;
    margin-top: 5px;
    font-size: 24px;
    font-weight: 800;
    color: var(--fg-strong);
  }
  .hero-summary span {
    display: block;
    margin-top: 3px;
    color: var(--muted);
    font: 600 11px/1.3 var(--font-display);
  }
</style>

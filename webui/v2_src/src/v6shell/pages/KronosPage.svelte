<script lang="ts">
  import { onMount } from 'svelte';
  import PageDecisionRail from '../PageDecisionRail.svelte';
  import { classifyV6ModelStatus, getV6ModelStatus, type V6ModelStatus } from '../v6Api';
  let modelStatus = $state<V6ModelStatus | null>(null);
  let modelError = $state<string | null>(null);
  let loading = $state(true);
  const modelPresentation = $derived(classifyV6ModelStatus(modelStatus));
  const stateLabel = $derived(modelPresentation.state === 'LOADED' ? '로드됨' : modelPresentation.state === 'AVAILABLE_NOT_LOADED' ? '사용 가능 · 미로드' : '사용 불가');
  async function loadModelStatus(): Promise<void> {
    loading = true; modelError = null;
    const result = await getV6ModelStatus(); loading = false;
    if (result.ok && result.data) modelStatus = result.data;
    else modelError = result.error ?? 'Kronos 모델 상태를 확인하지 못했습니다.';
  }
  onMount(() => { void loadModelStatus(); });
</script>

<section class="page" aria-labelledby="kronos-title">
  <PageDecisionRail pageId="kronos" />
  <header><p class="eyebrow">INDEPENDENT RESEARCH LANE</p><h1 id="kronos-title">Kronos 모델</h1><p>시계열 예측 기반 모델을 점검하는 독립 연구 레인입니다. 일봉 강화학습 정책과 같은 모델로 표시하거나 성과를 합산하지 않습니다.</p></header>
  <section class="model-status" aria-labelledby="model-status-title" data-state={modelPresentation.state}>
    <div><p class="card-label">KRONOS FOUNDATION MODEL</p><h2 id="model-status-title">모델 로드 상태</h2></div>
    <strong>{loading ? '확인 중' : modelError ? '상태 확인 실패' : stateLabel}</strong>
    <p>{modelError ?? modelStatus?.message ?? '모델 상태 응답에 설명이 없습니다.'}</p>
    <p class="boundary"><b>Kronos 예측 모델 ≠ 강화학습 정책.</b> 미로드는 코드가 사라졌다는 뜻이 아닙니다. 메모리를 보호하기 위해 예측 작업을 실행할 때 명시적으로 로드합니다.</p>
  </section>
  <section class="notice"><h2>판정 경계</h2><p>Kronos 진단 결과는 이 레인 안에서만 해석합니다. RL 연구의 GO/NO-GO 또는 경제 모델 점수를 변경하지 않습니다.</p></section>
  <div class="links" aria-label="Kronos 연구 도구">
    <a class="lane-card" href="/?tab=forecast&amp;ui=v5"><span class="card-label">PREDICTION WORKBENCH</span><h2>예측 워크벤치</h2><p>입력, 예측, 검증 흐름을 확인합니다.</p><span class="destination">워크벤치 열기 →</span></a>
    <a class="lane-card" href="/?tab=stom&amp;ui=v5"><span class="card-label">PREDICTION DIAGNOSTICS</span><h2>예측 진단</h2><p>예측 연구의 진단 정보와 근거를 별도 화면에서 확인합니다.</p><span class="destination">진단 열기 →</span></a>
  </div>
</section>

<style>
  .page{width:100%;display:flex;flex-direction:column;gap:18px;color:var(--fg)}header,.notice,.model-status,.lane-card{border:1px solid var(--border);border-radius:14px;padding:clamp(18px,4vw,30px);background:var(--surface)}.eyebrow,.card-label{margin:0;color:var(--accent);font-size:.82rem;font-weight:800;letter-spacing:.1em}h1{margin:7px 0;color:var(--fg-strong);font-size:clamp(1.9rem,6vw,2.7rem)}h2{margin:0 0 10px;color:var(--fg-strong);font-size:1.2rem}header>p:last-child,.lane-card p{color:var(--muted);line-height:1.6;font-size:1.05rem}.model-status{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 18px;border-left:4px solid var(--accent)}.model-status strong{align-self:center;color:var(--accent-strong);font-size:1.05rem}.model-status>p{grid-column:1/-1;margin:0;color:var(--muted);line-height:1.55}.model-status .boundary{border-top:1px solid var(--border);padding-top:10px}.model-status[data-state='UNAVAILABLE']{border-left-color:var(--danger)}.notice{border-color:var(--warn);background:var(--warn-soft);color:var(--warn)}.notice p{margin-bottom:0;line-height:1.6;font-size:1.05rem}.links{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}.lane-card{display:block;min-width:0;color:inherit;text-decoration:none}.lane-card:hover{border-color:var(--accent);background:var(--accent-soft)}.lane-card:focus-visible{outline:2px solid var(--warn);outline-offset:3px}.destination{color:var(--accent-strong);font-weight:800;font-size:1.05rem}@media(max-width:560px){.model-status{grid-template-columns:1fr}.model-status>p{grid-column:auto}}
</style>

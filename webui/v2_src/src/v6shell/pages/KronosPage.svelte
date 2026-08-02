<script lang="ts">
  import { onMount } from 'svelte';
  import { classifyV6ModelStatus, getV6ModelStatus, type V6ModelStatus } from '../v6Api';

  let modelStatus = $state<V6ModelStatus | null>(null);
  let modelError = $state<string | null>(null);
  let loading = $state(true);
  const modelPresentation = $derived(classifyV6ModelStatus(modelStatus));

  async function loadModelStatus(): Promise<void> {
    loading = true;
    modelError = null;
    const result = await getV6ModelStatus();
    loading = false;
    if (result.ok && result.data) modelStatus = result.data;
    else modelError = result.error ?? 'Kronos 모델 상태를 확인하지 못했습니다.';
  }

  onMount(() => { void loadModelStatus(); });
</script>

<section class="page" aria-labelledby="kronos-title">
  <header><p class="eyebrow">INDEPENDENT RESEARCH LANE</p><h1 id="kronos-title">Kronos 예측</h1><p>Kronos 예측은 강화학습과 독립된 연구 레인입니다. 예측 레인의 판정은 RL 판정과 병합하지 않습니다.</p></header>
  <section class="model-status" aria-labelledby="model-status-title" data-state={modelPresentation.state}>
    <div><p class="card-label">KRONOS FOUNDATION MODEL</p><h2 id="model-status-title">예측 모델 상태</h2></div>
    {#if loading}<strong>확인 중</strong>{:else if modelError}<strong>상태 확인 실패</strong>{:else}<strong>{modelPresentation.label}</strong>{/if}
    <p>{modelError ?? modelStatus?.message ?? 'Kronos 모델 상태 응답이 없습니다.'}</p>
    <p class="boundary"><b>Kronos 예측 모델 ≠ 강화학습 policy.</b> 메모리 사용을 피하기 위해 V6 진입 시 자동으로 로드하지 않으며, 예측 워크벤치에서 명시적으로 불러옵니다.</p>
  </section>
  <section class="notice" aria-labelledby="kronos-boundary-title"><h2 id="kronos-boundary-title">판정 경계</h2><p>예측 결과, 진단, 기존 판정은 해당 레인 안에서만 해석합니다. RL 연구의 GO/NO-GO를 변경하거나 대신하지 않습니다.</p></section>
  <div class="links" aria-label="Kronos 예측 연구 레인">
    <a class="lane-card" href="/?tab=forecast&amp;ui=v5"><span class="card-label">PREDICTION WORKBENCH</span><h2>예측 워크벤치</h2><p>독립된 예측 연구의 입력, 결과, 검토 흐름을 확인합니다.</p><dl><dt>연구 레인</dt><dd>predictor 독립 레인</dd><dt>판정</dt><dd>판정 분리 유지</dd></dl><span class="destination">워크벤치 열기 →</span></a>
    <a class="lane-card" href="/?tab=stom&amp;ui=v5"><span class="card-label">PREDICTION DIAGNOSTICS</span><h2>예측 진단</h2><p>예측 연구의 진단 정보와 근거를 별도 레인에서 확인합니다.</p><dl><dt>근거</dt><dd>진단 레인 전용</dd><dt>RL 연계</dt><dd>병합하지 않음</dd></dl><span class="destination">진단 열기 →</span></a>
  </div>
</section>

<style>
  .page { width: 100%; color: var(--fg); } header, .notice, .model-status, .lane-card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 30px); background: var(--surface); } .eyebrow, .card-label { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.9rem, 6vw, 2.7rem); } h2 { margin: 0 0 10px; color: var(--fg-strong); font-size: 1.2rem; } header > p:last-child, .lane-card p { color: var(--muted); line-height: 1.6; font-size: 1.05rem; } .model-status { display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 18px;margin-top:18px;border-left:4px solid var(--accent) }.model-status strong { align-self:center;color:var(--accent-strong);font-size:1.05rem }.model-status>p { grid-column:1/-1;margin:0;color:var(--muted);line-height:1.55 }.model-status .boundary { border-top:1px solid var(--border);padding-top:10px }.model-status[data-state='UNAVAILABLE'] { border-left-color:var(--danger) }.notice { margin-top: 18px; border-color: var(--warn); background: var(--warn-soft); color: var(--warn); } .notice p { margin-bottom: 0; line-height: 1.6; font-size: 1.05rem; } .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; margin-top: 18px; } .lane-card { display: block; min-width: 0; color: inherit; text-decoration: none; } .lane-card:hover { border-color: var(--accent); background: var(--accent-soft); } .lane-card:focus-visible { outline: 2px solid var(--warn); outline-offset: 3px; } dl { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; margin: 16px 0; padding: 12px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); font-size: .95rem; } dt { color: var(--muted); } dd { margin: 0; color: var(--fg-strong);overflow-wrap:anywhere } .destination { color: var(--accent-strong); font-weight: 800; font-size: 1.05rem; } @media(max-width:560px){.model-status{grid-template-columns:1fr}.model-status>p{grid-column:auto}}
</style>

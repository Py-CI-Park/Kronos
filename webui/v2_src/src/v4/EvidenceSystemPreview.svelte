<script lang="ts">
  import A11yChartFrame from './components/A11yChartFrame.svelte';
  import EvidenceDisclosure from './components/EvidenceDisclosure.svelte';
  import EvidenceHeader from './components/EvidenceHeader.svelte';
  import FacetBar from './components/FacetBar.svelte';
  import LifecyclePill from './components/LifecyclePill.svelte';
  import MetricWithProvenance from './components/MetricWithProvenance.svelte';
  import PromotionLocksGrid from './components/PromotionLocksGrid.svelte';
  import StateBoundary from './components/StateBoundary.svelte';
  import {
    PROMOTION_LOCK_KEYS,
    adaptEvidenceIdentity,
    adaptMetricValue,
    adaptPromotionLocks,
    adaptRunEvidence,
  } from './evidence';
  import { EVIDENCE_UI_STATES, type EvidenceUiState } from './evidenceState';

  type V4Facet = {
    id: string;
    label: string;
    value?: string;
    active?: boolean;
    disabled?: boolean;
    reason?: string;
  };

  const sourceEndpoint = 'v4-wave2-contract-preview://missing-fixture';
  const intentionallyMissingFixture = {
    run_id: '000123',
    title: 'Wave-2 component contract preview',
  };

  const identity = adaptEvidenceIdentity(intentionallyMissingFixture, { source_endpoint: sourceEndpoint });
  const run = adaptRunEvidence(intentionallyMissingFixture, { source_endpoint: sourceEndpoint });
  const lockResult = adaptPromotionLocks(intentionallyMissingFixture);
  const notRecordedMetric = adaptMetricValue(null, {
    kind: 'research_metric',
    unit: 'NOT_RECORDED',
    source: sourceEndpoint,
    availability: 'NOT_RECORDED',
  });

  const facets: readonly V4Facet[] = [
    { id: 'identity', label: '증거 식별', value: identity.id, active: true, disabled: true, reason: '읽기 전용 미리보기' },
    { id: 'locks', label: '승격 잠금', value: `${PROMOTION_LOCK_KEYS.length}개 fail-closed`, disabled: true, reason: '입력 근거 없음' },
    { id: 'states', label: '상태 행렬', value: `${EVIDENCE_UI_STATES.length}개`, disabled: true, reason: '계약 표시 전용' },
    { id: 'metrics', label: '메트릭', value: 'NOT_RECORDED', disabled: true, reason: '연구 결과 아님' },
  ];

  const stateRows: ReadonlyArray<{
    state: EvidenceUiState;
    label: string;
    detail: string;
  }> = [
    { state: 'loading', label: '로딩', detail: '자료 확인 중' },
    { state: 'empty', label: '비어 있음', detail: '표시할 행 없음' },
    { state: 'error', label: '오류', detail: '계약 오류 표시' },
    { state: 'stale', label: '오래됨', detail: '재검증 필요' },
    { state: 'live', label: '라이브 상태', detail: '상태 토큰 예시일 뿐 실거래 아님' },
    { state: 'replay', label: '리플레이', detail: '재현 화면 상태' },
    { state: 'completed', label: '완료', detail: '컴포넌트 완료 상태' },
    { state: 'missing', label: '누락', detail: '근거 없음' },
    { state: 'no-go', label: '진행 불가', detail: '잠금 해제 근거 없음' },
  ];

  const chartColumns = ['항목', '값', '출처'];
  const chartRows: ReadonlyArray<ReadonlyArray<string | number | null>> = [
    ['run_id', identity.id, sourceEndpoint],
    ['default_cost_bps', null, 'MISSING'],
    ['research_metric', null, 'NOT_RECORDED'],
    ['promotion_locks', PROMOTION_LOCK_KEYS.length, 'fail-closed'],
  ];


</script>

<section class="evidence-preview" aria-labelledby="v4-evidence-preview-title" data-v4-evidence-system-preview>
  <div class="preview-intro">
    <span class="preview-eyebrow">Wave-2 component contract preview</span>
    <h2 id="v4-evidence-preview-title">증거 시스템 미리보기</h2>
    <p>
      이 영역은 V4 opt-in 셸 전용 읽기 전용 컴포넌트 계약 미리보기입니다. 연구 증거, 주문 가능성,
      수익성, 모델 빌드 승인 또는 운영 선언을 만들지 않습니다.
    </p>
  </div>

  <EvidenceHeader
    {identity}
    {run}
    eyebrow="Kronos V4"
    title="근거 없는 fixture는 fail-closed"
    description="입력 근거가 의도적으로 누락되어 여섯 승격 잠금은 모두 닫힌 상태로 표시되어야 합니다."
  />

  <FacetBar facets={facets} ariaLabel="V4 증거 미리보기 섹션" />

  <div class="preview-grid">
    <section class="preview-card" aria-labelledby="v4-locks-title">
      <h3 id="v4-locks-title">여섯 승격 잠금</h3>
      <p>소스가 선언하지 않은 잠금은 허용으로 해석하지 않습니다.</p>
      <PromotionLocksGrid result={lockResult} />
    </section>

    <section class="preview-card" aria-labelledby="v4-metric-title">
      <h3 id="v4-metric-title">기록되지 않은 메트릭</h3>
      <p>값이 없으면 연구 수치나 방향성을 만들지 않고 NOT_RECORDED로 남깁니다.</p>
      <MetricWithProvenance label="연구 메트릭" metric={notRecordedMetric} tone="warning" />
      <p class="metric-fallback">표시값: NOT_RECORDED</p>
    </section>
  </div>

  <EvidenceDisclosure summary="상태 행렬 9개" meta="loading · empty · error · stale · live · replay · completed · missing · no-go">
    <div class="state-matrix" role="list" aria-label="V4 evidence lifecycle states">
      {#each stateRows as row}
        <StateBoundary state={row.state} title={row.label} detail={row.detail}>
          <LifecyclePill state={row.state} detail={row.label} />
        </StateBoundary>
      {/each}
    </div>
  </EvidenceDisclosure>

  <EvidenceDisclosure summary="접근 가능한 차트 프레임" meta="시각 슬롯 + 표 대체">
    <A11yChartFrame name="증거 요약 차트 계약" summary="누락된 값은 NOT_RECORDED로 명시하며 선언되지 않은 추세는 만들지 않습니다." columns={chartColumns} rows={chartRows}>
      <div class="chart-placeholder" aria-label="차트 시각 슬롯 미리보기">
        <span>visual slot</span>
        <strong>{PROMOTION_LOCK_KEYS.length}</strong>
        <small>locks closed by missing source</small>
      </div>
    </A11yChartFrame>
  </EvidenceDisclosure>
</section>

<style>
  .evidence-preview {
    max-width: var(--content-max);
    width: calc(100% - 56px);
    margin: 16px auto 0;
    display: grid;
    gap: 16px;
  }

  .preview-intro,
  .preview-card {
    border: 1px solid var(--border-faint);
    border-radius: 22px;
    background: color-mix(in oklab, var(--surface) 90%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .preview-intro {
    padding: 18px 20px;
  }

  .preview-eyebrow {
    color: var(--accent-strong);
    font: 700 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin: 0;
  }

  h2 {
    margin-top: 6px;
    color: var(--fg-strong);
    font: 750 clamp(22px, 3vw, 30px)/1.05 var(--font-display);
    letter-spacing: -0.04em;
  }

  h3 {
    color: var(--fg-strong);
    font: 750 16px/1.2 var(--font-display);
  }

  p {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
  }

  .preview-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
    gap: 16px;
  }

  .preview-card {
    padding: 16px;
    display: grid;
    gap: 12px;
  }

  .metric-fallback {
    font-family: var(--font-mono);
  }

  .state-matrix {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .chart-placeholder {
    min-height: 96px;
    display: grid;
    place-items: center;
    gap: 4px;
    border-radius: 12px;
    color: var(--muted);
    background: color-mix(in oklab, var(--accent) 8%, var(--surface-sunken));
    text-align: center;
  }

  .chart-placeholder strong {
    color: var(--fg-strong);
    font: 800 28px/1 var(--font-display);
  }

  .chart-placeholder small {
    color: var(--muted);
    font: 600 11px/1.2 var(--font-mono);
    text-transform: uppercase;
  }

  @media (max-width: 900px) {
    .evidence-preview {
      width: calc(100% - 32px);
      margin-top: 16px;
    }

    .preview-grid,
    .state-matrix {
      grid-template-columns: 1fr;
    }
  }
</style>

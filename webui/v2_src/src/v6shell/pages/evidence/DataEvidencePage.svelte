<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import { loadResearchRunDetail, loadResearchRuns, loadResearchSummary, type ResearchPage, type ResearchRunDetail, type ResearchSummary } from '../../api/researchApi';
  import { loadTelemetryRuns, type TelemetryRuns } from '../../api/telemetryApi';
  import { runStatusTone } from '../../runStatusModel';

  let summary = $state<ResearchSummary | null>(null);
  let catalog = $state<ResearchPage | null>(null);
  let telemetry = $state<TelemetryRuns | null>(null);
  let authorityDetail = $state<ResearchRunDetail | null>(null);
  let allocationDetail = $state<ResearchRunDetail | null>(null);
  let authorityError = $state<string | null>(null);
  let allocationError = $state<string | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const sourceKnown = $derived(catalog?.items.filter((run) => run.source_file !== 'MISSING').length ?? 0);
  const datasetKnown = $derived(catalog?.items.filter((run) => run.dataset_id !== 'MISSING').length ?? 0);
  const evidenceProblems = $derived(catalog?.items.filter((run) => run.status.includes('CORRUPT') || run.status.includes('TOO_LARGE')).length ?? 0);
  const authorityRun = $derived(catalog?.items.find((run) => run.run_id === 'daily_market_authority/DAILY_MARKET_AUTHORITY_2026_08_10_002') ?? null);
  const allocationRun = $derived(catalog?.items.find((run) => run.run_id === 'daily_market_allocation/DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002') ?? null);
  const custodyReproduction = $derived(allocationRun?.status === 'REPRODUCTION_ONLY_VALIDATION_CONSUMED');
  const reproductionMismatch = $derived(allocationRun?.status === 'REPRODUCTION_MISMATCH_VALIDATION_CONSUMED');
  const modelCheckpoints = $derived(allocationDetail?.artifacts.filter((artifact) => artifact.name.endsWith('.kq')).length ?? 0);
  const authorityD0 = $derived(authorityDetail?.observed_outcome.series.find((row) => row.label === 'D0 PRICE BASIS') ?? null);
  const authorityD1 = $derived(authorityDetail?.observed_outcome.series.find((row) => row.label === 'D1 PIT UNIVERSE') ?? null);
  const won = (value: number): string => `${value >= 0 ? '+' : ''}${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value)}원`;
  const allocationPnlItems = $derived(allocationDetail?.observed_outcome.series.flatMap((row, index) => {
    const value = row.total_net_pnl_krw ?? row.net_pnl_krw;
    if (value === undefined) return [];
    return { label: row.label === 'CQL' ? `CQL seed-${index}` : row.label, value: Math.abs(value), displayValue: won(value), tone: value >= 0 ? 'positive' as const : 'danger' as const };
  }) ?? []);
  const allocationCostItems = $derived(allocationDetail?.observed_outcome.series.flatMap((row, index) => {
    if (row.total_cost_krw === undefined) return [];
    return { label: row.label === 'CQL' ? `CQL seed-${index}` : row.label, value: row.total_cost_krw, displayValue: won(row.total_cost_krw), tone: 'warning' as const };
  }) ?? []);
  const kpis = $derived([
    { label: '연구 디렉터리', value: String(summary?.catalog.total ?? 0), detail: '읽기 전용 카탈로그', tone: 'neutral' as const },
    { label: 'DIRECT METADATA', value: String(sourceKnown), detail: '직접 source file 확인', tone: 'positive' as const },
    { label: 'DATASET ID', value: String(datasetKnown), detail: '명시 identity 보유', tone: datasetKnown === 0 ? 'warning' as const : 'neutral' as const },
    { label: 'TELEMETRY', value: String(telemetry?.total ?? 0), detail: 'event file 보유 실행', tone: 'neutral' as const },
    { label: 'CORRUPT / LARGE', value: String(evidenceProblems), detail: '복구·분할 필요', tone: evidenceProblems > 0 ? 'danger' as const : 'neutral' as const },
    { label: 'LATEST RL', value: reproductionMismatch ? 'REPRO FAIL' : custodyReproduction ? 'REPRO ONLY' : allocationRun?.status === 'VALIDATION_CANDIDATE' ? 'CANDIDATE' : allocationRun?.status ?? 'MISSING', detail: reproductionMismatch ? '001과 002의 10모델·gate 지문 불일치 · 재현 실패' : custodyReproduction ? '001과 exact match · 이미 소비된 VALIDATION · 새 성능 증거 아님' : `${allocationRun?.status ?? 'MISSING'} · 4행동 TRAIN/VALIDATION 화면`, tone: reproductionMismatch ? 'danger' as const : custodyReproduction || allocationRun?.status === 'VALIDATION_CANDIDATE' ? 'warning' as const : 'neutral' as const },
  ]);
  const gates = $derived<readonly StateItem[]>([
    { label: 'LOCAL RESEARCH FILES', state: catalog ? 'PRESENT' : 'UNAVAILABLE', detail: '로컬 실행 파일을 관측했지만 외부 원천 권위와 동일하지 않습니다.', tone: catalog ? 'ok' : 'danger' },
    { label: 'D0 PRICE BASIS', state: authorityD0?.state ?? 'MISSING', detail: '직접 authority summary의 D0 판정입니다. 원천 artifact 결속 전에는 가격 의미를 확정하지 않습니다.', tone: authorityD0?.state === 'VERIFIED' ? 'ok' : 'danger' },
    { label: 'PIT / AVAILABLE-AT', state: authorityD1 ? `${authorityD1.state ?? 'MISSING'} ${authorityD1.covered_membership_pairs ?? 'MISSING'} / ${authorityD1.required_membership_pairs ?? 'MISSING'}` : 'MISSING', detail: authorityD1?.coverage_percent === undefined ? '직접 D1 coverage 증거를 읽지 못했습니다.' : `직접 authority summary coverage ${authorityD1.coverage_percent.toFixed(3)}%입니다.`, tone: authorityD1?.state === 'VERIFIED' ? 'ok' : 'danger' },
    { label: 'EXTERNAL KRX AUTHORITY', state: authorityRun?.status ?? 'MISSING', detail: '현재 KRX 목록만으로 과거 날짜별 투자 가능 종목군을 소급 증명하지 않습니다.', tone: authorityRun?.status === 'VERIFIED_RESEARCH_DATA_AUTHORITY' ? 'ok' : 'danger' },
    { label: 'MODEL FILES DISCOVERED', state: `${modelCheckpoints} / 10 FILES`, detail: '직접 디렉터리에서 발견한 .kq 수입니다. 이 숫자만으로 magic·hash·로드·경제성을 인증하지 않습니다.', tone: modelCheckpoints === 10 ? 'ok' : 'warning' },
    { label: 'PERFORMANCE EVIDENCE', state: reproductionMismatch ? 'REPRODUCTION FAILED' : custodyReproduction ? 'REPRODUCTION ONLY' : allocationRun?.status ?? 'MISSING', detail: reproductionMismatch ? '002가 hash-bound 001 결과와 일치하지 않아 재현 실패로 차단됐습니다.' : custodyReproduction ? '002는 001에서 이미 본 VALIDATION과 정확히 일치합니다. 성능 후보나 독립 OOS 증거가 아닙니다.' : 'VALIDATION_CANDIDATE도 수익성 확정이나 승격이 아닙니다.', tone: reproductionMismatch ? 'danger' : custodyReproduction || allocationRun?.status === 'VALIDATION_CANDIDATE' ? 'warning' : 'danger' },
    { label: 'HISTORICAL TEST', state: 'FEATURES CONSUMED / REWARDS NOT READ', detail: '후보 점수·상태 46일이 이미 파싱되어 독립 OOS 자격을 잃었습니다. 향후 경제 판정에는 사용하지 않습니다.', tone: 'danger' },
    { label: 'FRESH OOS SEALED', state: 'NOT RUN / NO READ', detail: '사전등록과 권위 gate가 닫히기 전에는 fresh OOS를 열지 않습니다.', tone: 'warning' },
  ]);
  const statusChartItems = $derived(Object.entries(summary?.catalog.by_status ?? {}).map(([status, count]) => ({
    label: status,
    value: count,
    tone: runStatusTone(status) === 'danger' ? 'danger' as const : runStatusTone(status) === 'warning' ? 'warning' as const : 'accent' as const,
  })));

  onMount(async () => {
    const [summaryResult, catalogResult, telemetryResult] = await Promise.all([
      loadResearchSummary(),
      loadResearchRuns({ search: '', lane: '', status: '', page: 1, pageSize: 200 }),
      loadTelemetryRuns(),
    ]);
    if (summaryResult.ok === false) error = summaryResult.message;
    else if (catalogResult.ok === false) error = catalogResult.message;
    else if (telemetryResult.ok === false) error = telemetryResult.message;
    else {
      summary = summaryResult.data;
      catalog = catalogResult.data;
      telemetry = telemetryResult.data;
      const registeredAuthority = catalogResult.data.items.find((run) => run.run_id === 'daily_market_authority/DAILY_MARKET_AUTHORITY_2026_08_10_002');
      const registered = catalogResult.data.items.find((run) => run.run_id === 'daily_market_allocation/DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002');
      if (registeredAuthority) {
        const detailResult = await loadResearchRunDetail(registeredAuthority.run_id);
        if (detailResult.ok === false) authorityError = detailResult.message;
        else authorityDetail = detailResult.data;
      }
      if (registered) {
        const detailResult = await loadResearchRunDetail(registered.run_id);
        if (detailResult.ok === false) allocationError = detailResult.message;
        else allocationDetail = detailResult.data;
      }
    }
    loading = false;
  });
</script>

<div class="evidence v6-page" data-evidence-page>
  <PageHeader eyebrow="DATA & EVIDENCE" title="데이터·증거" description="파일 존재, identity, 권위, OOS 개봉 상태를 서로 다른 gate로 봅니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'READ-ONLY'} />
  <KpiStrip items={kpis} />
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if authorityError}<p class="error" role="alert">권위 증거: {authorityError}</p>{/if}
  <ResearchPanel title="권위와 누수 방지 gate" description="현재 DB를 사용할 수 있다는 사실만으로 KRX 외부 권위가 증명되지는 않습니다."><StateMatrix items={gates} /></ResearchPanel>
  <ResearchPanel title="4행동 종가배분 RL 계보 재현" description="002는 이미 소비된 TRAIN/VALIDATION의 CQL 5씨드 결과를 재현합니다. 새 경제 성능 증거가 아니며 양수 중앙값과 한 개 실패 씨드를 함께 표시합니다.">
    {#if allocationError}<p class="error" role="alert">{allocationError}</p>{/if}
    {#if allocationDetail}
      <div class="allocation-head"><div><span>판정</span><strong>{allocationDetail.run.status}</strong></div><div><span>모델</span><strong>{modelCheckpoints} / 10</strong></div><div><span>TEST</span><strong>FEATURES CONSUMED</strong></div><div><span>PROMOTION</span><strong>BLOCKED</strong></div></div>
      <div class="allocation-charts"><AccessibleBarChart title="CQL 씨드별 비용 후 손익" ariaLabel="4행동 CQL 검증 씨드별 비용 후 원화 손익" summary="막대 길이는 절댓값, 표시는 부호가 있는 직접 관측 원화 손익입니다. seed-4 손실도 숨기지 않습니다." items={allocationPnlItems} valueHeader="비용 후 손익" /><AccessibleBarChart title="CQL 씨드별 연구 가정 비용" ariaLabel="4행동 CQL 검증 씨드별 연구 가정 매매 비용" summary="사전등록한 왕복 0.230% 연구 가정을 적용한 VALIDATION 비용이며 실제 키움 계좌 영수증이 아닙니다." items={allocationCostItems} valueHeader="가정 비용" /></div>
      <ul class="reasons" aria-label="승격 차단 이유">{#each allocationDetail.observed_outcome.reasons as reason}<li>{reason}</li>{/each}</ul>
    {:else if !loading}<p class="missing">등록된 4행동 RL 상세 증거를 찾지 못했습니다.</p>{/if}
  </ResearchPanel>
  <ResearchPanel title="판정 분포 시각화" description="API 카탈로그의 실제 판정 건수를 그대로 표시합니다."><AccessibleBarChart title="연구 판정 건수" ariaLabel="연구 카탈로그 상태별 실행 건수 막대그래프" summary="NO-GO·손상·대용량 증거도 숨기지 않으며, 건수는 성과 순위가 아닙니다." items={statusChartItems} valueHeader="실행 수" /></ResearchPanel>
  <ResearchPanel title="증거 파이프라인" description="각 단계가 다음 단계를 자동 승인하지 않습니다."><ol><li><b>1</b><span>로컬 DB·artifact 발견</span></li><li><b>2</b><span>source identity·hash·available-at 검증</span></li><li><b>3</b><span>PIT universe·비용·체결 계약 고정</span></li><li><b>4</b><span>사전등록 train/validation 실행</span></li><li><b>5</b><span>통제군·비용·강건성 gate</span></li><li><b>6</b><span>사람 승인 후에만 Fresh OOS</span></li></ol></ResearchPanel>
</div>

<style>
  .evidence{display:flex;flex-direction:column;gap:16px;min-width:0}.allocation-head{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:12px}.allocation-head>div{min-width:0;border:1px solid var(--border);border-radius:9px;padding:10px;background:var(--surface-sunken)}.allocation-head span{display:block;color:var(--dim);font:800 .56rem var(--font-mono)}.allocation-head strong{display:block;margin-top:4px;color:var(--warn);font:.72rem var(--font-mono);overflow-wrap:anywhere}.allocation-charts{display:grid;grid-template-columns:1fr 1fr;gap:12px}.reasons{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0;padding:0;list-style:none}.reasons li{border-left:3px solid var(--danger);padding:6px 8px;background:var(--surface-sunken);color:var(--fg);font:.62rem var(--font-mono)}ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0;padding:0;list-style:none}ol li{display:flex;align-items:center;gap:9px;border:1px solid var(--border);border-radius:8px;padding:9px;background:var(--surface-sunken)}ol li b{display:grid;place-items:center;flex:0 0 auto;width:24px;height:24px;border-radius:50%;background:var(--accent);color:var(--on-accent);font-size:.65rem}ol li span{color:var(--fg);font-size:.68rem}.error{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}.missing{margin:0;color:var(--muted)}
  @media(max-width:920px){.allocation-head{grid-template-columns:1fr 1fr}.allocation-charts{grid-template-columns:1fr}}@media(max-width:820px){ol{grid-template-columns:1fr 1fr}}@media(max-width:560px){.allocation-head,ol{grid-template-columns:1fr}}
</style>

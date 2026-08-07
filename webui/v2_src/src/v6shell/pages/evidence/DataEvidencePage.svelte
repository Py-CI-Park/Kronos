<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import { loadResearchRuns, loadResearchSummary, type ResearchPage, type ResearchSummary } from '../../api/researchApi';
  import { loadTelemetryRuns, type TelemetryRuns } from '../../api/telemetryApi';

  let summary = $state<ResearchSummary | null>(null);
  let catalog = $state<ResearchPage | null>(null);
  let telemetry = $state<TelemetryRuns | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const sourceKnown = $derived(catalog?.items.filter((run) => run.source_file !== 'MISSING').length ?? 0);
  const datasetKnown = $derived(catalog?.items.filter((run) => run.dataset_id !== 'MISSING').length ?? 0);
  const evidenceProblems = $derived(catalog?.items.filter((run) => run.status.includes('CORRUPT') || run.status.includes('TOO_LARGE')).length ?? 0);
  const kpis = $derived([
    { label: '연구 디렉터리', value: String(summary?.catalog.total ?? 0), detail: '읽기 전용 카탈로그', tone: 'neutral' as const },
    { label: 'DIRECT METADATA', value: String(sourceKnown), detail: '직접 source file 확인', tone: 'positive' as const },
    { label: 'DATASET ID', value: String(datasetKnown), detail: '명시 identity 보유', tone: datasetKnown === 0 ? 'warning' as const : 'neutral' as const },
    { label: 'TELEMETRY', value: String(telemetry?.total ?? 0), detail: 'event file 보유 실행', tone: 'neutral' as const },
    { label: 'CORRUPT / LARGE', value: String(evidenceProblems), detail: '복구·분할 필요', tone: evidenceProblems > 0 ? 'danger' as const : 'neutral' as const },
  ]);
  const gates = $derived<readonly StateItem[]>([
    { label: 'LOCAL RESEARCH FILES', state: catalog ? 'PRESENT' : 'UNAVAILABLE', detail: '로컬 실행 파일을 관측했지만 외부 원천 권위와 동일하지 않습니다.', tone: catalog ? 'ok' : 'danger' },
    { label: 'PIT / AVAILABLE-AT', state: 'LOCAL AUDIT ONLY', detail: '일부 로컬 앵커 감사만 존재하며 전체 시점별 universe custody 증명은 아닙니다.', tone: 'warning' },
    { label: 'EXTERNAL KRX AUTHORITY', state: 'NO-GO', detail: '외부 KRX 권위·수정주가 의미·원천 custody가 닫히지 않았습니다.', tone: 'danger' },
    { label: 'FRESH OOS SEALED', state: 'NOT RUN / NO READ', detail: '사전등록과 권위 gate가 닫히기 전에는 fresh OOS를 열지 않습니다.', tone: 'warning' },
  ]);
  const statusChartItems = $derived(Object.entries(summary?.catalog.by_status ?? {}).map(([status, count]) => ({
    label: status,
    value: count,
    tone: /NO[_-]?GO|CORRUPT|TOO_LARGE/u.test(status) ? 'danger' as const : 'accent' as const,
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
    }
    loading = false;
  });
</script>

<div class="evidence v6-page" data-evidence-page>
  <PageHeader eyebrow="DATA & EVIDENCE" title="데이터·증거" description="파일 존재, identity, 권위, OOS 개봉 상태를 서로 다른 gate로 봅니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'READ-ONLY'} />
  <KpiStrip items={kpis} />
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <ResearchPanel title="권위와 누수 방지 gate" description="현재 DB를 사용할 수 있다는 사실만으로 KRX 외부 권위가 증명되지는 않습니다."><StateMatrix items={gates} /></ResearchPanel>
  <ResearchPanel title="판정 분포 시각화" description="API 카탈로그의 실제 판정 건수를 그대로 표시합니다."><AccessibleBarChart title="연구 판정 건수" ariaLabel="연구 카탈로그 상태별 실행 건수 막대그래프" summary="NO-GO·손상·대용량 증거도 숨기지 않으며, 건수는 성과 순위가 아닙니다." items={statusChartItems} valueHeader="실행 수" /></ResearchPanel>
  <ResearchPanel title="증거 파이프라인" description="각 단계가 다음 단계를 자동 승인하지 않습니다."><ol><li><b>1</b><span>로컬 DB·artifact 발견</span></li><li><b>2</b><span>source identity·hash·available-at 검증</span></li><li><b>3</b><span>PIT universe·비용·체결 계약 고정</span></li><li><b>4</b><span>사전등록 train/validation 실행</span></li><li><b>5</b><span>통제군·비용·강건성 gate</span></li><li><b>6</b><span>사람 승인 후에만 Fresh OOS</span></li></ol></ResearchPanel>
</div>

<style>
  .evidence{display:flex;flex-direction:column;gap:16px;min-width:0}ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0;padding:0;list-style:none}li{display:flex;align-items:center;gap:9px;border:1px solid var(--border);border-radius:8px;padding:9px;background:var(--surface-sunken)}li b{display:grid;place-items:center;flex:0 0 auto;width:24px;height:24px;border-radius:50%;background:var(--accent);color:var(--on-accent);font-size:.65rem}li span{color:var(--fg);font-size:.68rem}.error{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}
  @media(max-width:820px){ol{grid-template-columns:1fr 1fr}}@media(max-width:560px){ol{grid-template-columns:1fr}}
</style>

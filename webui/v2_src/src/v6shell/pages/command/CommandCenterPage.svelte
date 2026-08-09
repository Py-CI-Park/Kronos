<script lang="ts">
  import { onMount } from 'svelte';
  import { loadGovernanceSummary, type GovernanceSummary } from '../../api/governanceApi';
  import { loadResearchSummary, type ResearchSummary } from '../../api/researchApi';
  import { loadTelemetryRuns, type TelemetryRuns } from '../../api/telemetryApi';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import { V6_PAGES } from '../../registry';
  import { PROGRAM_EXECUTION } from '../../scorecard/programExecution';
  import { PROGRAM_LANES } from '../../scorecard/programScorecard';

  interface Props { readonly onNavigate: (id: string) => void }
  let { onNavigate }: Props = $props();
  let summary = $state<ResearchSummary | null>(null);
  let telemetry = $state<TelemetryRuns | null>(null);
  let governance = $state<GovernanceSummary | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const noGoCount = $derived(Object.entries(summary?.catalog.by_status ?? {})
    .filter(([status]) => status.includes('NO_GO') || status.includes('NO-GO'))
    .reduce((total, [, count]) => total + count, 0));
  const kpis = $derived([
    { label: '제품 구현·UX', value: `${PROGRAM_EXECUTION.implementationScore}/100`, detail: '통합 페이지·API·QA 점수', tone: 'positive' as const },
    { label: '연구 프로그램', value: `${PROGRAM_EXECUTION.overallScore}/100`, detail: 'RL·거버넌스·live 포함', tone: 'warning' as const },
    { label: '경제 모델', value: `${PROGRAM_EXECUTION.economicModelScore}/100`, detail: '체크포인트 20개 · 비용 후 GO 없음', tone: 'danger' as const },
    { label: '실거래 준비', value: `${PROGRAM_EXECUTION.liveReadinessScore}/100`, detail: 'Fresh OOS·paper·broker 차단', tone: 'danger' as const },
  ]);
  const states = $derived<readonly StateItem[]>([
    { label: 'RESEARCH CATALOG', state: summary ? `${summary.catalog.total} RUNS` : 'UNAVAILABLE', detail: '로컬 run과 공식 판정을 같은 카탈로그에서 조회합니다.', tone: summary ? 'ok' : 'danger' },
    { label: 'TELEMETRY', state: telemetry ? `${telemetry.total} RUNS` : 'UNAVAILABLE', detail: '학습 로그가 있는 실행의 reward·equity·loss를 시각화합니다.', tone: telemetry ? 'ok' : 'danger' },
    { label: 'OFFICIAL VERDICT', state: noGoCount > 0 ? `${noGoCount} NO-GO` : 'NO GO FOUND', detail: 'NO-GO는 추가 학습 금지가 아니라 운영 승격 차단 판정입니다.', tone: noGoCount > 0 ? 'warning' : 'neutral' },
    { label: 'FRESH OOS', state: 'SEALED', detail: '외부 권위와 사람 승인 전에는 열거나 읽지 않습니다.', tone: 'danger' },
  ]);
  const programChartItems = PROGRAM_LANES.map((lane) => ({
    label: lane.labelKo,
    value: lane.score,
    displayValue: `${lane.score}/100`,
    tone: lane.state === 'BLOCKED' ? 'danger' as const : lane.state === 'PARTIAL' ? 'warning' as const : 'positive' as const,
  }));
  const phase = (id: string): string => ({ command: 'P0', research: 'P0', live: 'P1', evaluation: 'P1', evidence: 'P2', models: 'P2', governance: 'P2', settings: 'P2' })[id] ?? 'P2';
  const nextAction = (id: string): string => ({
    command: '최종 회귀·릴리스 증거 유지', research: '새 가설 사전등록·PIT 권위 확보', live: '다음 실행에 seed별 telemetry 연결', evaluation: '동일 TEST 재튜닝 금지·새 검증 구간 설계',
    evidence: '가격·universe custody 확보', models: '20개 체크포인트와 경제성 NO-GO 분리 검토', governance: 'Fresh OOS 사람 승인', settings: '접근성 사용자 검수',
  })[id] ?? '근거 유지';

  async function load(): Promise<void> {
    loading = true; error = null;
    const [summaryResult, telemetryResult, governanceResult] = await Promise.all([
      loadResearchSummary(), loadTelemetryRuns(), loadGovernanceSummary(),
    ]);
    const failure = [summaryResult, telemetryResult, governanceResult].find((result) => result.ok === false);
    if (failure?.ok === false) error = failure.message;
    else if (summaryResult.ok && telemetryResult.ok && governanceResult.ok) {
      summary = summaryResult.data; telemetry = telemetryResult.data; governance = governanceResult.data;
    }
    loading = false;
  }
  onMount(() => { void load(); });
</script>

<div class="command v6-page" data-command-center>
  <PageHeader eyebrow="RESEARCH COMMAND CENTER" title="통합 현황" description="연구 실행, 학습 성과, 실패 원인, 증거와 다음 행동을 한 화면에서 봅니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'READ-ONLY'} />
  <KpiStrip items={kpis} />
  <ResearchPanel title="프로그램 성숙도 지도" description="제품 UX와 경제 모델·실거래 준비도를 분리한 공식 5개 영역 점수입니다.">
    <AccessibleBarChart title="영역별 근거 점수" ariaLabel="플랫폼 UX, 강화학습 증거, 엔지니어링, 거버넌스, 실거래 준비도 점수 비교" summary="가중 종합은 70점입니다. 플랫폼 구현이 높아도 경제성·Fresh OOS·실거래 gate를 대신하지 않습니다." items={programChartItems} valueHeader="점수" />
  </ResearchPanel>
  {#if error}<p class="error" role="alert">{error}<button type="button" onclick={() => void load()}>다시 불러오기</button></p>{/if}
  <ResearchPanel title="현재 연구 판정" description="제품 완성도와 수익 모델 성공 여부를 섞지 않습니다."><StateMatrix items={states} /></ResearchPanel>
  <div class="grid">
    <ResearchPanel title="지금 할 수 있는 것" description="모든 기능은 로컬 연구·증거 검토 범위입니다.">
      <ul><li>과거·현재 RL run 98개를 검색하고 상세 artifact를 확인</li><li>학습 reward·equity·drawdown·loss·action을 그래프로 추적</li><li>같은 데이터 lane 안에서만 알고리즘·seed·통제군 비교</li><li>종가 결정 → 다음 거래일 시가 체결 흐름과 0.230% 비용 검토</li><li>모델 파일 존재·로드·승격과 사전등록·결과 hash를 분리 감사</li></ul>
    </ResearchPanel>
    <ResearchPanel title="성공에 필요한 다음 gate" description="학습 반복만으로 데이터 권위와 경제성이 자동 해결되지는 않습니다.">
      <ol><li><b>1</b><span>날짜별 PIT universe·available-at·공식 수정주가 확정</span></li><li><b>2</b><span>23bp 비용·체결 계약을 고정하고 train/validation 재실행</span></li><li><b>3</b><span>DQN·CQL·rule·random·shuffle을 동일 조건으로 비교</span></li><li><b>4</b><span>사전등록 gate 통과 뒤 사람 승인으로 Fresh OOS 1회 개봉</span></li></ol>
    </ResearchPanel>
  </div>
  <ResearchPanel title="전체 페이지 진행표" description={`P0→P2 구현 완료 · 거버넌스 ${governance?.preregistrations.length ?? 0}건 사전등록`}>
    <div class="table-wrap"><table><thead><tr><th>우선순위</th><th>페이지</th><th>목적</th><th>구현</th><th>다음 연구 행동</th><th></th></tr></thead><tbody>{#each V6_PAGES as item}<tr><td><code>{phase(item.id)}</code></td><td><strong>{item.labelKo}</strong></td><td>{item.description}</td><td><span class="done">100% BUILT</span></td><td>{nextAction(item.id)}</td><td><button type="button" onclick={() => onNavigate(item.id)}>열기</button></td></tr>{/each}</tbody></table></div>
  </ResearchPanel>
</div>

<style>
  .command{display:flex;flex-direction:column;gap:16px;min-width:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}ul,ol{display:grid;gap:8px;margin:0;padding:0;list-style:none}li{border:1px solid var(--border);border-radius:8px;padding:10px;background:var(--surface-sunken);color:var(--fg);font-size:.72rem;line-height:1.5}ol li{display:flex;align-items:center;gap:9px}li b{display:grid;place-items:center;flex:0 0 auto;width:24px;height:24px;border-radius:50%;background:var(--accent);color:var(--on-accent)}.table-wrap{max-width:100%;overflow:auto}table{width:100%;min-width:820px;border-collapse:collapse}th,td{border-bottom:1px solid var(--border);padding:9px;text-align:left;font-size:.68rem;vertical-align:top}th{color:var(--muted);font:.6rem var(--font-mono);letter-spacing:.05em}td{color:var(--fg)}td strong{color:var(--fg-strong)}code,.done{color:var(--success);font:.62rem var(--font-mono)}button{border:1px solid var(--accent);border-radius:7px;padding:7px 9px;background:transparent;color:var(--accent-strong);font:700 .66rem inherit;cursor:pointer}button:focus-visible{outline:2px solid var(--warn);outline-offset:2px}.error{display:flex;justify-content:space-between;gap:10px;border:1px solid var(--danger);border-radius:9px;padding:12px;color:var(--danger)}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:520px){.error{align-items:start;flex-direction:column}}
</style>

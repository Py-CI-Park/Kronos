<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import { loadResearchRunDetail, loadResearchRuns, type ResearchRun, type ResearchRunDetail } from '../../api/researchApi';
  import { getV6ModelStatus, type V6ModelStatus } from '../../v6Api';

  let runs = $state<readonly ResearchRun[]>([]);
  let selected = $state('');
  let runSearch = $state('');
  let detail = $state<ResearchRunDetail | null>(null);
  let kronos = $state<V6ModelStatus | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  function formatBytes(value: number): string {
    if (value >= 1_048_576) return `${(value / 1_048_576).toFixed(2)} MB`;
    if (value >= 1_024) return `${(value / 1_024).toFixed(1)} KB`;
    return `${value} B`;
  }

  const modelArtifacts = $derived(detail?.artifacts.filter((artifact) => /\.(kq|zip|pt|pth|ckpt|onnx|pkl)$/iu.test(artifact.name)) ?? []);
  const artifactChartItems = $derived([...(detail?.artifacts ?? [])]
    .sort((left, right) => right.size_bytes - left.size_bytes)
    .slice(0, 8)
    .map((artifact) => ({
      label: artifact.name,
      value: artifact.size_bytes,
      displayValue: formatBytes(artifact.size_bytes),
      tone: /\.(kq|zip|pt|pth|ckpt|onnx|pkl)$/iu.test(artifact.name) ? 'positive' as const : 'accent' as const,
    })));
  const visibleRuns = $derived.by(() => {
    const query = runSearch.trim().toLocaleLowerCase('ko-KR');
    const filtered = runs.filter((run) => !query || run.run_id.toLocaleLowerCase('ko-KR').includes(query) || run.algorithm.toLocaleLowerCase('ko-KR').includes(query));
    const current = runs.find((run) => run.run_id === selected);
    return [current, ...filtered].filter((run, index, rows): run is ResearchRun => run !== undefined && rows.findIndex((item) => item?.run_id === run.run_id) === index).slice(0, 50);
  });
  const kpis = $derived([
    { label: 'FILE PRESENT', value: String(modelArtifacts.length), detail: 'bounded models 하위 체크포인트', tone: modelArtifacts.length ? 'positive' as const : 'warning' as const },
    { label: 'LOADED', value: kronos?.loaded === true ? 'YES' : 'NO', detail: 'Kronos Core 프로세스 상태', tone: kronos?.loaded === true ? 'positive' as const : 'neutral' as const },
    { label: 'PROMOTED', value: 'NO', detail: '자동 승격 금지', tone: 'danger' as const },
    { label: 'RUN VERDICT', value: detail?.run.status ?? 'MISSING', detail: detail?.run.algorithm ?? 'algorithm 없음', tone: detail?.run.status.includes('NO') ? 'danger' as const : 'neutral' as const },
  ]);
  const states = $derived<readonly StateItem[]>([
    { label: 'RUN MODEL FILE', state: modelArtifacts.length ? 'FILE PRESENT' : 'MISSING', detail: '파일 존재는 로드 성공·성능·안전성을 증명하지 않습니다.', tone: modelArtifacts.length ? 'ok' : 'warning' },
    { label: 'KRONOS CORE', state: kronos?.available === true ? (kronos.loaded === true ? 'LOADED' : 'AVAILABLE / NOT LOADED') : 'UNAVAILABLE', detail: kronos?.message ?? '모델 상태 API 메시지가 없습니다.', tone: kronos?.available === true ? 'ok' : 'warning' },
    { label: 'ECONOMIC GATE', state: 'NO-GO', detail: '현재 모델 파일과 텔레메트리는 경제적 성능 승격 gate를 통과하지 못했습니다.', tone: 'danger' },
    { label: 'PROMOTION', state: 'HUMAN APPROVAL REQUIRED', detail: 'OOS·통제군·비용·강건성 통과 전 자동 배포나 broker 연결을 하지 않습니다.', tone: 'warning' },
  ]);

  async function loadSelected(): Promise<void> {
    if (!selected) return;
    loading = true;
    const result = await loadResearchRunDetail(selected);
    if (result.ok === false) error = result.message;
    else {
      detail = result.data;
      error = null;
    }
    loading = false;
  }

  onMount(async () => {
    const [runsResult, modelResult] = await Promise.all([
      loadResearchRuns({ search: '', lane: '', status: '', page: 1, pageSize: 200 }),
      getV6ModelStatus(),
    ]);
    if (runsResult.ok === false) {
      error = runsResult.message;
      loading = false;
      return;
    }
    runs = runsResult.data.items;
    kronos = modelResult.ok ? modelResult.data ?? null : null;
    selected = runs.find((run) => run.run_id === 'stom_orderbook_dqn_smoke')?.run_id ?? runs[0]?.run_id ?? '';
    await loadSelected();
  });
</script>

<div class="models v6-page" data-models-page>
  <PageHeader eyebrow="MODELS & ARTIFACTS" title="모델·산출물" description="파일 존재, 런타임 로드, 경제 판정, 운영 승격을 한 단어로 합치지 않습니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'RESEARCH ONLY'} />
  <KpiStrip items={kpis} />
  <ResearchPanel title="모델 상태 계약" description="Kronos Core와 trading policy artifact는 서로 다른 모델 계열입니다."><StateMatrix items={states} /></ResearchPanel>
  <ResearchPanel title="실행 산출물 선택" description="모델 파일이 없어도 실패 실행과 증거 파일은 목록에 남깁니다."><div class="picker"><label>실행 검색<input bind:value={runSearch} placeholder="run id 또는 알고리즘" /></label><label>연구 실행<select bind:value={selected} onchange={() => void loadSelected()}>{#each visibleRuns as run}<option value={run.run_id}>{run.status} · {run.name}</option>{/each}</select></label><button type="button" onclick={() => void loadSelected()} disabled={loading}>다시 확인</button></div></ResearchPanel>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if detail}<ResearchPanel title="산출물 크기 지도" description="선택 run의 큰 파일 8개를 metadata 바이트 기준으로 비교합니다."><AccessibleBarChart title="직접 산출물 크기" ariaLabel="선택한 연구 실행의 산출물 파일 크기 막대그래프" summary="파일 크기와 모델 확장자는 성능·로드 성공·운영 승격을 증명하지 않습니다." items={artifactChartItems} valueHeader="파일 크기" /></ResearchPanel>{/if}
  {#if detail}<ResearchPanel title="직접 산출물" description="내용을 자동 실행하거나 역직렬화하지 않는 metadata 목록입니다."><div class="artifacts">{#each detail.artifacts as artifact}<article class:model={modelArtifacts.some((model) => model.name === artifact.name)}><div><strong>{artifact.name}</strong><code>{artifact.relative_path}</code></div><span>{new Intl.NumberFormat('ko-KR').format(artifact.size_bytes)} bytes</span><small>{artifact.modified_at}</small></article>{:else}<p>직접 산출물이 없습니다.</p>{/each}</div></ResearchPanel>{/if}
</div>

<style>
  .models{display:flex;flex-direction:column;gap:16px;min-width:0}.picker{display:grid;grid-template-columns:minmax(180px,.6fr) minmax(260px,1fr) auto;gap:12px;align-items:end}.picker label{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:.68rem;font-weight:800}input,select,button{min-width:0;height:40px;border:1px solid var(--border-strong);border-radius:8px;padding:0 10px;background:var(--surface-sunken);color:var(--fg);font:inherit}button{background:var(--accent);color:var(--on-accent);font-weight:900;cursor:pointer}.artifacts{display:grid;gap:8px}.artifacts article{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;border:1px solid var(--border);border-radius:8px;padding:10px;background:var(--surface-sunken)}.artifacts article.model{border-left:4px solid var(--accent)}.artifacts div{min-width:0}.artifacts strong,.artifacts code{display:block;overflow-wrap:anywhere}.artifacts code,.artifacts small{color:var(--muted);font-size:.62rem}.artifacts span{color:var(--fg);font:.64rem var(--font-mono)}.error{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}
  @media(max-width:700px){.picker{grid-template-columns:1fr}.artifacts article{grid-template-columns:1fr}.picker button{width:100%}}
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import { loadResearchRuns, type ResearchPage } from '../../api/researchApi';
  import { resultEvidenceHealth } from './researchResultModel';

  interface Props {
    readonly onSelect: (runId: string) => void;
  }

  let { onSelect }: Props = $props();
  let page = $state<ResearchPage | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let search = $state('');
  let lane = $state('');
  let status = $state('');
  let pageNumber = $state(1);
  const pageSize = 24;
  let requestGeneration = 0;

  const visibleNoGo = $derived(page?.items.filter((row) => row.status.includes('NO_GO') || row.status.includes('NO-GO')).length ?? 0);
  const visibleBlocked = $derived(page?.items.filter((row) => row.status.includes('BLOCK')).length ?? 0);
  const kpis = $derived([
    { label: '전체 기록', value: String(page?.total ?? 0), detail: '현재 필터와 일치하는 run', tone: 'neutral' as const },
    { label: '현재 페이지', value: `${page?.page ?? 1}/${Math.max(1, Math.ceil((page?.total ?? 0) / pageSize))}`, detail: `페이지당 ${pageSize}건 · 전체 ${page?.total ?? 0}건`, tone: 'neutral' as const },
    { label: 'NO-GO', value: String(visibleNoGo), detail: '실패 결과도 같은 비중으로 보존', tone: 'danger' as const },
    { label: 'BLOCKED', value: String(visibleBlocked), detail: '외부 권위·데이터 차단', tone: 'warning' as const },
  ]);
  const statusChartItems = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const row of page?.items ?? []) counts.set(row.status, (counts.get(row.status) ?? 0) + 1);
    return [...counts.entries()].map(([label, value]) => ({
      label,
      value,
      tone: /NO[_-]?GO|BLOCK|CORRUPT/u.test(label) ? 'danger' as const : 'accent' as const,
    }));
  });
  const laneChartItems = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const row of page?.items ?? []) counts.set(row.lane, (counts.get(row.lane) ?? 0) + 1);
    return [...counts.entries()].map(([label, value]) => ({ label, value, tone: 'accent' as const }));
  });
  const totalPages = $derived(Math.max(1, Math.ceil((page?.total ?? 0) / pageSize)));

  async function refresh(): Promise<void> {
    const currentRequest = ++requestGeneration;
    loading = true;
    error = null;
    const result = await loadResearchRuns({ search: search.trim(), lane, status, page: pageNumber, pageSize });
    if (currentRequest !== requestGeneration) return;
    if (result.ok === false) error = result.message;
    else page = result.data;
    loading = false;
  }

  function applyFilters(): void {
    pageNumber = 1;
    void refresh();
  }

  function changePage(nextPage: number): void {
    pageNumber = Math.max(1, Math.min(totalPages, nextPage));
    void refresh();
  }

  onMount(() => void refresh());
</script>

<div class="library v6-page" data-research-library>
  <PageHeader eyebrow="RESEARCH LIBRARY" title="지금까지의 모든 연구" description="실패와 NO-GO도 숨기지 않습니다. run 하나를 선택하면 결과·증거·산출물의 영구 상세 화면으로 이동합니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'READ-ONLY'} />
  <KpiStrip items={kpis} />
  <div class="catalog-charts">
    <ResearchPanel title="현재 페이지 판정 분포" description="현재 페이지에 표시된 run의 실제 판정 건수입니다."><AccessibleBarChart title="표시 run 상태" ariaLabel="현재 연구 라이브러리 결과의 상태별 실행 건수" summary="필터 결과의 구성만 보여주며 알고리즘 우열이나 경제적 성능을 의미하지 않습니다." items={statusChartItems} valueHeader="실행 수" /></ResearchPanel>
    <ResearchPanel title="현재 페이지 연구 lane" description="서로 다른 연구 문제를 한 성능 순위로 섞지 않기 위한 분포입니다."><AccessibleBarChart title="표시 run lane" ariaLabel="현재 연구 라이브러리 결과의 lane별 실행 건수" summary="현재 페이지의 연구 종류별 기록 수입니다." items={laneChartItems} valueHeader="실행 수" /></ResearchPanel>
  </div>
  <ResearchPanel title="실험·실행 찾기" description="lane, 판정, 알고리즘 또는 run id로 검색합니다.">
    <form onsubmit={(event) => { event.preventDefault(); applyFilters(); }}>
      <label>검색<input bind:value={search} placeholder="run id 또는 알고리즘" /></label>
      <label>연구 레인<select bind:value={lane}><option value="">전체</option><option value="daily_close">일봉 종가</option><option value="orderbook">호가 RL</option><option value="intraday">인트라데이</option><option value="portfolio">포트폴리오</option><option value="discovery">발견 연구</option><option value="other">기타</option></select></label>
      <label>상태<input bind:value={status} placeholder="NO_GO, BLOCKED…" /></label>
      <button type="submit" disabled={loading}>필터 적용</button>
    </form>
  </ResearchPanel>

  <ResearchPanel title="Research Runs" description="표시값은 선택된 evidence 파일에서 직접 관측된 metadata입니다.">
    {#if loading}<p class="state">연구 실행 목록을 불러오는 중입니다.</p>
    {:else if error}<p class="state error">{error}</p>
    {:else if !page?.items.length}<p class="state">조건에 맞는 연구 기록이 없습니다.</p>
    {:else}
      <div class="rows" role="list" aria-label="연구 실행 목록">
        {#each page.items as row}
          {@const health = resultEvidenceHealth(row)}
          <article role="listitem">
            <div class="identity"><span>{row.lane}</span><strong>{row.name}</strong><code>{row.run_id}</code></div>
            <dl><div><dt>판정</dt><dd data-status={row.status}>{row.status}</dd></div><div><dt>알고리즘</dt><dd>{row.algorithm}</dd></div><div><dt>데이터셋</dt><dd>{row.dataset_id}</dd></div><div><dt>증거</dt><dd>{row.source_file}</dd></div><div class="health"><dt>결과 근거</dt><dd><span><i style={`width:${health.percent}%`}></i></span>{health.observed}/{health.total}<small>{health.missing.length ? `없음: ${health.missing.join('·')}` : '핵심 metadata 관측'}</small></dd></div></dl>
            <button type="button" onclick={() => onSelect(row.run_id)}>상세 보기</button>
          </article>
        {/each}
      </div>
      <nav class="pagination" aria-label="연구 실행 페이지">
        <button type="button" onclick={() => changePage(pageNumber - 1)} disabled={loading || pageNumber <= 1}>← 이전</button>
        <span><b>{pageNumber}</b> / {totalPages} 페이지 · 총 {page?.total ?? 0}건</span>
        <button type="button" onclick={() => changePage(pageNumber + 1)} disabled={loading || pageNumber >= totalPages}>다음 →</button>
      </nav>
    {/if}
  </ResearchPanel>
</div>

<style>
  .library{display:flex;flex-direction:column;gap:16px;min-width:0}.catalog-charts{display:grid;grid-template-columns:1fr 1fr;gap:16px;min-width:0}form{display:grid;grid-template-columns:minmax(180px,1.4fr) repeat(2,minmax(150px,1fr)) auto;gap:10px;align-items:end}label{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:.68rem;font-weight:700}input,select,form button{min-width:0;height:38px;border:1px solid var(--border-strong);border-radius:8px;padding:0 10px;background:var(--surface-sunken);color:var(--fg);font:inherit}form button{cursor:pointer;background:var(--accent);color:var(--on-accent);font-weight:800}.rows{display:flex;flex-direction:column;gap:9px}.rows article{min-width:0;display:grid;grid-template-columns:minmax(190px,1.2fr) minmax(420px,2fr) auto;gap:14px;align-items:center;border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--surface-sunken)}.identity{min-width:0;display:flex;flex-direction:column;gap:3px}.identity span{color:var(--accent);font:800 .58rem var(--font-mono);text-transform:uppercase}.identity strong{color:var(--fg-strong);overflow-wrap:anywhere}.identity code{color:var(--muted);font-size:.62rem;overflow-wrap:anywhere}dl{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin:0}dl div{min-width:0}dt{color:var(--dim);font:700 .56rem var(--font-mono)}dd{margin:3px 0 0;color:var(--fg);font-size:.67rem;overflow-wrap:anywhere}dd[data-status*=NO_GO],dd[data-status*=NO-GO]{color:var(--danger);font-weight:900}dd[data-status*=BLOCK]{color:var(--warn);font-weight:900}.health dd>span{display:block;width:100%;height:4px;margin:3px 0 4px;border-radius:999px;background:var(--surface-raised);overflow:hidden}.health dd>span i{display:block;height:100%;background:var(--accent)}.health small{display:block;margin-top:3px;color:var(--dim);font-size:.55rem}.rows article>button,.pagination button{border:1px solid var(--accent);border-radius:8px;padding:8px 10px;background:transparent;color:var(--accent-strong);font-weight:800;cursor:pointer}.pagination{display:flex;align-items:center;justify-content:center;gap:12px;margin-top:14px}.pagination span{color:var(--muted);font-size:.68rem}.pagination b{color:var(--fg-strong)}.pagination button:disabled{cursor:not-allowed;opacity:.4}.state{margin:0;color:var(--muted)}.state.error{color:var(--danger)}
  @media(max-width:1050px){.catalog-charts{grid-template-columns:1fr}form{grid-template-columns:1fr 1fr}.rows article{grid-template-columns:1fr auto}.rows dl{grid-column:1/-1;grid-row:2}}
  @media(max-width:620px){form{grid-template-columns:1fr}.rows article{grid-template-columns:1fr}.rows dl{grid-column:auto;grid-row:auto;grid-template-columns:1fr 1fr}.rows article>button{width:100%}.pagination{flex-wrap:wrap}}
</style>

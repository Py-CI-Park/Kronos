<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import { loadResearchRunDetail, type ResearchRunDetail } from '../../api/researchApi';

  interface Props {
    readonly runId: string;
    readonly onBack: () => void;
  }

  let { runId, onBack }: Props = $props();
  let detail = $state<ResearchRunDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const kpis = $derived([
    { label: '판정', value: detail?.run.status ?? 'MISSING', detail: '관측된 상태 원문', tone: detail?.run.status.includes('NO') ? 'danger' as const : 'neutral' as const },
    { label: '알고리즘', value: detail?.run.algorithm ?? 'MISSING', detail: 'summary metadata', tone: 'neutral' as const },
    { label: '산출물', value: String(detail?.artifacts.length ?? 0), detail: '직접 디렉터리 파일', tone: 'neutral' as const },
    { label: '증거 범위', value: 'DIRECT', detail: '하위 파일 내용은 자동 해석하지 않음', tone: 'warning' as const },
  ]);

  async function load(): Promise<void> {
    loading = true;
    const result = await loadResearchRunDetail(runId);
    if (result.ok === false) error = result.message;
    else detail = result.data;
    loading = false;
  }

  onMount(() => void load());
</script>

<div class="detail" data-run-detail>
  <button class="back" type="button" onclick={onBack}>← 연구 라이브러리</button>
  <PageHeader eyebrow="RUN DETAIL" title={detail?.run.name ?? runId} description="한 실행의 identity와 직접 관측된 artifact metadata를 한 URL에서 확인합니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : detail?.run.status} />
  <KpiStrip items={kpis} />
  {#if error}<p class="error">{error}</p>{/if}
  {#if detail}
    <div class="grid">
      <ResearchPanel title="Observed Metadata" description="추정값을 만들지 않고 evidence 파일에서 확인된 값만 표시합니다.">
        <dl><div><dt>Run ID</dt><dd><code>{detail.run.run_id}</code></dd></div><div><dt>Lane</dt><dd>{detail.run.lane}</dd></div><div><dt>Dataset</dt><dd>{detail.run.dataset_id}</dd></div><div><dt>Source</dt><dd>{detail.run.source_file}</dd></div><div><dt>Updated</dt><dd>{detail.run.updated_at}</dd></div><div><dt>Scope</dt><dd><code>DIRECT_DIRECTORY_METADATA_ONLY</code></dd></div></dl>
      </ResearchPanel>
      <ResearchPanel title="Artifacts" description="파일을 열거나 모델을 로드하지 않는 bounded metadata 목록입니다.">
        <div class="artifacts">
          {#each detail.artifacts as artifact}
            <article><strong>{artifact.name}</strong><code>{artifact.relative_path}</code><span>{new Intl.NumberFormat('ko-KR').format(artifact.size_bytes)} bytes</span><small>{artifact.modified_at}</small></article>
          {/each}
        </div>
      </ResearchPanel>
    </div>
  {/if}
</div>

<style>
  .detail{display:flex;flex-direction:column;gap:16px;min-width:0}.back{align-self:flex-start;border:0;background:transparent;color:var(--accent-strong);font-weight:800;cursor:pointer}.grid{display:grid;grid-template-columns:minmax(280px,.85fr) minmax(0,1.4fr);gap:16px;min-width:0}dl{display:grid;gap:10px;margin:0}dl div{min-width:0;border-bottom:1px solid var(--border);padding-bottom:8px}dt{color:var(--dim);font:700 .58rem var(--font-mono)}dd{margin:4px 0 0;color:var(--fg);font-size:.74rem;overflow-wrap:anywhere}code{font-family:var(--font-mono);overflow-wrap:anywhere}.artifacts{display:grid;gap:8px}.artifacts article{min-width:0;display:grid;grid-template-columns:minmax(150px,1fr) minmax(220px,1.5fr) auto;gap:6px 12px;border:1px solid var(--border);border-radius:9px;padding:10px;background:var(--surface-sunken)}.artifacts strong,.artifacts code{min-width:0;overflow-wrap:anywhere}.artifacts code{color:var(--muted);font-size:.65rem}.artifacts span{color:var(--fg);font:.65rem var(--font-mono)}.artifacts small{grid-column:1/-1;color:var(--dim)}.error{border:1px solid var(--danger);padding:12px;color:var(--danger)}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}
  @media(max-width:620px){.artifacts article{grid-template-columns:1fr}.artifacts small{grid-column:auto}}
</style>

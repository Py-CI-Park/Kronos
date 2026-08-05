<script lang="ts">
  import { onMount } from 'svelte';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import KpiStrip from '../../components/shell/KpiStrip.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import { getV6ProjectReports, v6ProjectReportHtmlUrl, type V6ProjectReports } from '../../v6Api';
  import { loadGovernanceSummary, type GovernanceSummary } from '../../api/governanceApi';

  let reports = $state<V6ProjectReports | null>(null);
  let registry = $state<GovernanceSummary | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const projects = $derived(reports?.projects ?? []);
  const preregs = $derived(registry?.preregistrations ?? []);
  const frozenCount = $derived(preregs.filter((item) => item.status === 'FROZEN').length);
  const kpis = $derived([
    { label: 'PROJECT REPORT', value: String(projects.length), detail: 'SHA-256 고정 보고서', tone: 'neutral' as const },
    { label: 'PREREGISTRATION', value: String(preregs.length), detail: `FROZEN ${frozenCount}`, tone: 'positive' as const },
    { label: 'RESULT DOC', value: String(registry?.result_docs?.length ?? 0), detail: '원문 hash 보유 문서', tone: 'neutral' as const },
    { label: 'FRESH OOS', value: 'SEALED', detail: 'NOT RUN / NO READ', tone: 'warning' as const },
  ]);
  const gates = $derived<readonly StateItem[]>([
    { label: 'PREREGISTRATION', state: frozenCount > 0 ? `${frozenCount} FROZEN` : 'MISSING', detail: '가설·split·비용·중단 기준을 실행 전에 동결합니다.', tone: frozenCount > 0 ? 'ok' : 'danger' },
    { label: 'VERDICT DISCLOSURE', state: 'NO-GO VISIBLE', detail: '실패·0거래·통제군 열위를 보고서와 화면에 그대로 남깁니다.', tone: 'ok' },
    { label: 'FRESH OOS', state: 'SEALED', detail: '설계·권위 gate와 승인 없이 fresh OOS를 열지 않습니다.', tone: 'warning' },
    { label: 'HUMAN APPROVAL', state: 'REQUIRED', detail: 'paper·broker·live 승격은 명시적 사람 승인 없이는 BLOCKED입니다.', tone: 'danger' },
  ]);

  function shortHash(value: string | undefined): string {
    return value ? `${value.slice(0, 12)}…` : 'MISSING';
  }

  onMount(async () => {
    const [reportsResult, registryResult] = await Promise.all([getV6ProjectReports(), loadGovernanceSummary()]);
    if (!reportsResult.ok) error = reportsResult.error ?? '프로젝트 보고서를 읽지 못했습니다.';
    else if (registryResult.ok === false) error = registryResult.message;
    else {
      reports = reportsResult.data ?? null;
      registry = registryResult.data;
    }
    loading = false;
  });
</script>

<div class="governance" data-governance-page>
  <PageHeader eyebrow="REPORTS & GOVERNANCE" title="보고서·거버넌스" description="사전등록 → 실행 → 판정 → 보고서 SHA-256 → 사람 승인의 계보를 확인합니다." status={loading ? 'LOADING' : error ? 'UNAVAILABLE' : 'FAIL-CLOSED'} />
  <KpiStrip items={kpis} />
  <ResearchPanel title="승격 gate" description="NO-GO는 연구 중단이 아니라 운영 승격 차단 판정입니다."><StateMatrix items={gates} /></ResearchPanel>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <div class="grid">
    <ResearchPanel title="프로젝트 보고서" description="report hash와 포함된 verdict를 함께 표시합니다."><div class="list">{#each projects as project}<article><div><strong>{project.title ?? project.project_id ?? 'UNTITLED'}</strong><code>{project.project_id ?? 'MISSING'}</code></div><span>{(project.verdicts ?? ['MISSING']).join(' · ')}</span><small>SHA {shortHash(project.report_sha256)} · cycle {project.cycle_count ?? 0} · run {project.run_count ?? 0}</small>{#if project.project_id}<a href={v6ProjectReportHtmlUrl(project.project_id)} target="_blank" rel="noreferrer">보고서 보기</a>{/if}</article>{:else}<p>프로젝트 보고서가 없습니다.</p>{/each}</div></ResearchPanel>
    <ResearchPanel title="사전등록 ledger" description="FROZEN과 DRAFT를 같은 의미로 표시하지 않으며 run linkage는 상세 화면으로 지연합니다."><div class="list compact">{#each preregs.slice(0, 16) as prereg}<article><div><strong>{prereg.prereg_id}</strong><code>{prereg.doc}</code></div><span>{prereg.status}</span><small>SHA {shortHash(prereg.sha256)} · {prereg.family} · {prereg.linkage_state}</small></article>{:else}<p>사전등록 기록이 없습니다.</p>{/each}</div></ResearchPanel>
  </div>
  <ResearchPanel title="결과 문서 custody" description="문서 경로·크기·hash를 보존하고 내용이 없으면 발명하지 않습니다."><div class="docs">{#each registry?.result_docs ?? [] as doc}<article><code>{doc.doc ?? 'MISSING'}</code><span>{new Intl.NumberFormat('ko-KR').format(doc.size_bytes ?? 0)} bytes</span><small>SHA-256 {shortHash(doc.sha256)}</small></article>{:else}<p>결과 문서 ledger가 없습니다.</p>{/each}</div></ResearchPanel>
</div>

<style>
  .governance{display:flex;flex-direction:column;gap:16px;min-width:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.list{display:grid;gap:8px}.list article{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;border:1px solid var(--border);border-radius:8px;padding:10px;background:var(--surface-sunken)}.list div{min-width:0}.list strong,.list code{display:block;overflow-wrap:anywhere}.list code,.list small{color:var(--muted);font-size:.61rem}.list span{color:var(--fg);font:.65rem var(--font-mono)}.list small{grid-column:1/-1}.list a{grid-column:1/-1;color:var(--accent-strong);font-size:.68rem;font-weight:800}.docs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}.docs article{display:flex;flex-direction:column;gap:5px;min-width:0;border:1px solid var(--border);border-radius:8px;padding:10px;background:var(--surface-sunken)}.docs code{color:var(--fg-strong);overflow-wrap:anywhere}.docs span,.docs small{color:var(--muted);font-size:.62rem}.error{border:1px solid var(--danger);border-radius:8px;padding:12px;color:var(--danger)}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:560px){.list article{grid-template-columns:1fr}.list small,.list a{grid-column:auto}}
</style>

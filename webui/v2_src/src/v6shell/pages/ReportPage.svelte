<script lang="ts">
  import { onMount } from 'svelte';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  import {
    getV6ProjectReports,
    getV6Reports,
    getV6ResearchDoc,
    getV6ResearchRegistry,
    getV6RunDetail,
    getV6Runs,
    getV6Status,
    v6ProjectReportHtmlUrl,
    v6ReportHtmlUrl,
    type V6ProjectReportEntry,
    type V6ProjectReports,
    type V6ReportEntry,
    type V6Reports,
    type V6ResearchRegistry,
    type V6RunDetail,
    type V6Runs,
    type V6Status,
  } from '../v6Api';

  let status = $state<V6Status | null>(null);
  let runs = $state<V6Runs | null>(null);
  let detail = $state<V6RunDetail | null>(null);
  let reports = $state<V6Reports | null>(null);
  let projectReports = $state<V6ProjectReports | null>(null);
  let registry = $state<V6ResearchRegistry | null>(null);
  let selectedReport = $state<V6ReportEntry | null>(null);
  let selectedProject = $state<V6ProjectReportEntry | null>(null);
  let viewerReport = $state<V6ReportEntry | null>(null);
  let docName = $state<string | null>(null);
  let docHtml = $state('');
  let docLoading = $state(false);
  let loading = $state(true);
  let detailLoading = $state(false);
  let copyMessage = $state<string | null>(null);
  let projectError = $state<string | null>(null);
  let reportError = $state<string | null>(null);
  let registryError = $state<string | null>(null);
  let detailError = $state<string | null>(null);
  let coreError = $state<string | null>(null);

  const text = (value: unknown) => value === undefined || value === null || value === '' ? 'MISSING' : String(value);
  const short = (value: unknown) => text(value).slice(0, 12);
  const kb = (value: number | undefined) => typeof value === 'number' ? `${(value / 1024).toFixed(0)} KB` : 'MISSING';
  const badgeClass = (value: string | undefined) => value === 'NO_GO' ? 'danger' : value === 'INCONCLUSIVE' ? 'warn' : value?.startsWith('GO_CANDIDATE') ? 'warn' : 'muted';
  const reportUrl = (report: V6ReportEntry, download = false) => v6ReportHtmlUrl(report.dataset_run_id ?? '', report.train_run_id ?? '', download);
  const projectUrl = (project: V6ProjectReportEntry, download = false) => v6ProjectReportHtmlUrl(project.project_id ?? '', download);
  const projectUsable = (project: V6ProjectReportEntry) => project.integrity === 'CHAIN_OK';
  const selectedDataset = () => runs?.datasets?.find((dataset) => dataset.run_id === selectedReport?.dataset_run_id);
  const selectedRun = () => selectedReport ? runs?.runs?.find((run) => run.run_id === selectedReport.train_run_id && run.dataset_run_id === selectedReport.dataset_run_id) : undefined;
  const selectedVerdict = () => detail?.manifest?.verdict_candidate ?? selectedRun()?.verdict_candidate;

  async function copy(value: unknown) {
    try {
      await navigator.clipboard.writeText(text(value));
      copyMessage = 'SHA를 클립보드에 복사했습니다.';
    } catch {
      copyMessage = '클립보드를 사용할 수 없습니다. SHA를 직접 복사하세요.';
    }
  }

  async function openDoc(name: string | undefined) {
    if (!name) return;
    docName = name;
    docHtml = '';
    docLoading = true;
    const response = await getV6ResearchDoc(name);
    docLoading = false;
    if (response.ok && response.data?.content !== undefined) {
      const raw = response.data.format === 'json' ? `\`\`\`json\n${response.data.content}\n\`\`\`` : response.data.content;
      docHtml = DOMPurify.sanitize(await marked.parse(raw));
    } else {
      docHtml = '<p>문서를 불러오지 못했습니다.</p>';
    }
  }

  async function selectReport(report: V6ReportEntry, openViewer = false) {
    selectedReport = report;
    if (openViewer) {
      selectedProject = null;
      viewerReport = report;
    }
    detail = null;
    detailError = null;
    if (!report.dataset_run_id || !report.train_run_id) {
      detailError = 'UNAVAILABLE: 실행 식별자가 없어 provenance를 불러올 수 없습니다.';
      return;
    }
    detailLoading = true;
    const response = await getV6RunDetail(report.dataset_run_id, report.train_run_id);
    detailLoading = false;
    if (response.ok && response.data) detail = response.data;
    else detailError = `UNAVAILABLE: ${response.error ?? '실행 상세를 불러올 수 없습니다.'}`;
  }

  async function loadProjects() {
    projectError = null;
    const response = await getV6ProjectReports();
    if (response.ok && response.data) projectReports = response.data;
    else projectError = `UNAVAILABLE: ${response.error ?? '프로젝트 보고서 카탈로그를 불러올 수 없습니다.'}`;
  }

  async function loadReports() {
    reportError = null;
    const response = await getV6Reports();
    if (response.ok && response.data) reports = response.data;
    else reportError = `UNAVAILABLE: ${response.error ?? '실행 보고서 카탈로그를 불러올 수 없습니다.'}`;
  }

  async function loadRegistry() {
    registryError = null;
    const response = await getV6ResearchRegistry();
    if (response.ok && response.data) registry = response.data;
    else registryError = `UNAVAILABLE: ${response.error ?? '연구 레지스트리를 불러올 수 없습니다.'}`;
  }

  async function load() {
    loading = true;
    coreError = null;
    const [statusResponse, runsResponse] = await Promise.all([getV6Status(), getV6Runs()]);
    await Promise.all([loadProjects(), loadReports(), loadRegistry()]);
    if (statusResponse.ok && statusResponse.data) status = statusResponse.data;
    if (runsResponse.ok && runsResponse.data) {
      runs = runsResponse.data;
      const newest = runsResponse.data.runs?.[0];
      if (newest?.dataset_run_id && newest.run_id) {
        await selectReport({ dataset_run_id: newest.dataset_run_id, train_run_id: newest.run_id });
      }
    } else {
      coreError = `UNAVAILABLE: ${runsResponse.error ?? statusResponse.error ?? '기본 연구 데이터를 불러올 수 없습니다.'}`;
    }
    loading = false;
  }

  onMount(load);
</script>

<section class="page">
  <header>
    <p class="eyebrow">RESEARCH PROVENANCE</p>
    <h1>보고서</h1>
    <p>판정과 근거의 연결만 기록합니다. 이 화면은 투자 권유나 수익 주장이 아닙니다.</p>
  </header>

  {#if loading}
    <section class="panel" aria-live="polite">판정과 증거 체인을 확인하고 있습니다.</section>
  {:else}
    {#if coreError}<section class="panel error" role="alert">{coreError}<button onclick={load}>다시 시도</button></section>{/if}

    <section class="card projects" aria-labelledby="project-research-title">
      <h2 id="project-research-title">프로젝트 연구 <span class="chip">{projectReports?.projects?.length ?? 'UNAVAILABLE'}건</span></h2>
      <p class="note">여러 cycle의 가설 변화, 판정, 테스트 상태와 비교 상태를 HTML을 열지 않고 확인합니다. CHAIN_OK 프로젝트만 열람할 수 있습니다.</p>
      {#if projectError}
        <section class="unavailable" role="alert">{projectError}<button onclick={loadProjects}>다시 시도</button></section>
      {:else if projectReports?.projects?.length}
        <div class="project-grid">
          {#each projectReports.projects as project}
            <article class:blocked={!projectUsable(project)} class="project-card">
              <div class="project-head">
                <div><p class="eyebrow">{text(project.project_id)}</p><h3>{text(project.title)}</h3></div>
                <span class="status {projectUsable(project) ? 'ok' : 'blocked'}">{projectUsable(project) ? 'CHAIN_OK' : 'BLOCKED'}</span>
              </div>
              <div class="summary-grid">
                <p><strong>{text(project.cycle_count)}</strong><span>cycles</span></p>
                <p><strong>{text(project.run_count)}</strong><span>runs</span></p>
                <p><strong>{kb(project.size_bytes)}</strong><span>report size</span></p>
              </div>
              <div class="tokens" aria-label="Project verdict and test states">
                {#each (project.verdicts ?? []) as item}<span class="badge {badgeClass(item)}">{text(item)}</span>{/each}
                {#each (project.test_states ?? []) as item}<span class="test-token">{text(item)}</span>{/each}
              </div>
              <ol class="timeline" aria-label="Ordered project cycles">
                {#each [...(project.cycles ?? [])].sort((left, right) => (left.order ?? 0) - (right.order ?? 0)) as cycle}
                  <li>
                    <div class="cycle-head"><strong>{text(cycle.order)}. {text(cycle.cycle_id)}</strong><span>{text(cycle.title)}</span></div>
                    <p>{text(cycle.hypothesis_delta)}</p>
                    <code title={text(cycle.prereg_sha256)}>prereg {short(cycle.prereg_sha256)}…</code>
                    <div class="cycle-runs">
                      {#each (cycle.runs ?? []) as run}
                        <span class="comparison" title={`${text(run.dataset_run_id)} / ${text(run.train_run_id)}`}>
                          <b class={badgeClass(run.verdict)}>{text(run.verdict)}</b> · {text(run.test_state)} · {text(run.comparison_state)}
                        </span>
                      {:else}<span class="comparison muted">실행 없음</span>{/each}
                    </div>
                  </li>
                {/each}
              </ol>
              <p class="integrity-reasons">Integrity: {project.integrity_reasons?.length ? project.integrity_reasons.join(' · ') : text(project.integrity)}</p>
              {#if !projectUsable(project)}
                <p class="mismatch-note">BLOCKED: {project.integrity_reasons?.length ? project.integrity_reasons.join(' · ') : text(project.integrity)}</p>
              {:else}
                <div class="actions">
                  <button onclick={() => { selectedProject = project; selectedReport = null; viewerReport = null; }}>프로젝트 보기</button>
                  <a href={projectUrl(project)} target="_blank" rel="noopener">새 창</a>
                  <a href={projectUrl(project, true)}>다운로드</a>
                </div>
              {/if}
            </article>
          {/each}
        </div>
        {#if selectedProject && projectUsable(selectedProject)}
          <div class="viewer-head"><h3>{text(selectedProject.project_id)} / {text(selectedProject.title)}</h3><button onclick={() => { selectedProject = null; }}>닫기</button></div>
          <iframe class="viewer" sandbox="" src={projectUrl(selectedProject)} title="프로젝트 연구 보고서 뷰어"></iframe>
        {/if}
      {:else}
        <p>생성된 프로젝트 보고서가 없습니다.</p>
      {/if}
    </section>

    <section class="verdict" class:danger={text(selectedVerdict()?.value) === 'NO_GO'} aria-live="polite">
      <p class="eyebrow">선택된 실행의 판정</p><h2>{text(selectedVerdict()?.value)}</h2>
      {#each (selectedVerdict()?.reasons ?? []) as reason}<p>{text(reason)}</p>{:else}<p>판정 사유가 기록되지 않았습니다.</p>{/each}
    </section>

    <section class="card catalog" aria-labelledby="report-catalog-title">
      <h2 id="report-catalog-title">연구 보고서 카탈로그 <span class="chip">{reports?.reports?.length ?? 'UNAVAILABLE'}건</span></h2>
      <p class="note">실행별 self-contained HTML 보고서입니다. 판정 토큰은 원문 그대로이며 SHA 불일치 보고서는 열람이 차단됩니다.</p>
      {#if reportError}
        <section class="unavailable" role="alert">{reportError}<button onclick={loadReports}>다시 시도</button></section>
      {:else if reports?.reports?.length}
        <div class="report-grid">
          {#each reports.reports as report}
            <article class:selected={selectedReport?.dataset_run_id === report.dataset_run_id && selectedReport?.train_run_id === report.train_run_id} class:mismatch={report.integrity !== 'OK'} class="report-card">
              <span class="badge {badgeClass(report.verdict)}">{text(report.verdict)}</span><h3>{text(report.dataset_run_id)}</h3><p class="run">{text(report.train_run_id)}</p>
              <dl><dt>생성</dt><dd>{text(report.generated_utc)}</dd><dt>test OOS</dt><dd>{text(report.test_state)}</dd><dt>지수 절</dt><dd>{text(report.index_overlay_state)}</dd><dt>SHA</dt><dd><code title={text(report.report_sha256)}>{short(report.report_sha256)}…</code><button class="mini" onclick={() => copy(report.report_sha256)}>복사</button></dd><dt>크기·무결성</dt><dd>{kb(report.size_bytes)} · {text(report.integrity)}</dd></dl>
              {#if report.integrity === 'OK'}<div class="actions"><button onclick={() => selectReport(report, true)}>보고서 보기</button><button onclick={() => selectReport(report)}>provenance 선택</button><a href={reportUrl(report)} target="_blank" rel="noopener">새 창</a><a href={reportUrl(report, true)}>다운로드</a></div>{:else}<p class="mismatch-note">SHA_MISMATCH · 열람 차단됨(재생성 필요)</p>{/if}
            </article>
          {/each}
        </div>
        {#if viewerReport}
          <div class="viewer-head"><h3>{text(viewerReport.dataset_run_id)} / {text(viewerReport.train_run_id)}</h3><button onclick={() => { viewerReport = null; }}>닫기</button></div>
          <iframe class="viewer" sandbox="" src={reportUrl(viewerReport)} title="연구 실행 보고서 뷰어"></iframe>
        {/if}
      {:else}<p>생성된 보고서가 없습니다. 실행 종료 후 보고서를 생성합니다.</p>{/if}
    </section>

    <section class="card registry" aria-labelledby="registry-title">
      <h2 id="registry-title">연구 레지스트리 <span class="chip">{registry?.preregistrations?.length ?? 'UNAVAILABLE'} 사전등록</span></h2>
      <p class="note">사전등록 → 실행 → 판정 → 보고서 생명주기를 한 곳에서 관리합니다. 판정 토큰은 원문 그대로입니다.</p>
      {#if registryError}
        <section class="unavailable" role="alert">{registryError}<button onclick={loadRegistry}>다시 시도</button></section>
      {:else if registry?.preregistrations?.length}
        <div class="prereg-grid">{#each registry.preregistrations as prereg}<article class="prereg-card"><div class="prereg-head"><span class="status {prereg.status === 'FROZEN' ? 'ok' : 'warn'}">{text(prereg.status)}</span>{#each (prereg.verdicts ?? []) as item}<span class="badge {badgeClass(item)}">{text(item)}</span>{/each}</div><h3>{text(prereg.prereg_id)}</h3><p class="fam">{text(prereg.family)} · 실행 {prereg.run_count ?? 0}건 · 동결 {text(prereg.frozen_utc)}</p>{#if prereg.supersedes}<p class="sup">대체: {text(prereg.supersedes)}</p>{/if}<div class="prereg-runs">{#each (prereg.runs ?? []) as run}<span class="run-chip {badgeClass(run.verdict)}" title={`${text(run.dataset_run_id)} / ${text(run.train_run_id)} · test ${text(run.test_state)}`}>{text(run.verdict)}{#if run.has_report} ▪ 보고서{/if}</span>{:else}<span class="run-chip muted">실행 없음</span>{/each}</div><div class="actions"><button onclick={() => openDoc(prereg.doc)}>사전등록 문서</button><button class="mini" onclick={() => copy(prereg.sha256)}>SHA 복사</button></div></article>{/each}</div>
      {:else}<p>사전등록 문서가 없습니다.</p>{/if}
      {#if registry?.result_docs?.length}<h3 class="docs-title">결과·계획 문서 <span class="chip">{registry.result_docs.length}건</span></h3><div class="doc-links">{#each registry.result_docs as document}<button class="doc-link" onclick={() => openDoc(document.doc)}>{text(document.doc)}</button>{/each}</div>{/if}
      {#if docName}<div class="viewer-head"><h3>{text(docName)}</h3><button onclick={() => { docName = null; docHtml = ''; }}>닫기</button></div>{#if docLoading}<p class="note" aria-live="polite">문서를 불러오는 중…</p>{:else}<article class="doc-body">{@html docHtml}</article>{/if}{/if}
    </section>

    {#if detailError}<section class="panel unavailable" role="alert">{detailError}{#if selectedReport}<button onclick={() => selectReport(selectedReport)}>다시 시도</button>{/if}</section>{/if}
    {#if detailLoading}<p class="note" aria-live="polite">선택된 실행의 provenance를 불러오는 중…</p>{/if}
    {#if selectedReport}
      <section class="chains" aria-label="Selected run SHA chain">
        <section class="chain"><h2>Universe manifest</h2><code title={text(status?.journey.data.universe_manifest)}>{short(status?.journey.data.universe_manifest)}</code><button onclick={() => copy(status?.journey.data.universe_manifest)}>복사</button><p>{text(status?.journey.data.universe_size)} rows</p></section>
        <section class="chain"><h2>Preregistration</h2><code title={text(detail?.manifest?.prereg?.sha256)}>{short(detail?.manifest?.prereg?.sha256)}</code><button onclick={() => copy(detail?.manifest?.prereg?.sha256)}>복사</button></section>
        <section class="chain"><h2>Dataset run</h2><code title={text(selectedDataset()?.sha256)}>{short(selectedDataset()?.sha256)}</code><button onclick={() => copy(selectedDataset()?.sha256)}>복사</button><p>{text(selectedDataset()?.run_id)}</p></section>
        <section class="chain"><h2>Training manifest</h2><code title={text(detail?.manifest_sha256)}>{short(detail?.manifest_sha256)}</code><button onclick={() => copy(detail?.manifest_sha256)}>복사</button><p>{text(selectedReport.train_run_id)}</p></section>
      </section>
    {:else}<section class="panel empty"><h2>증거 체인이 비어 있습니다</h2><p>학습 실행이 없으므로 데이터셋·학습 manifest·판정을 연결할 수 없습니다.</p></section>{/if}

    {#if copyMessage}<p class="copy-message" aria-live="polite">{copyMessage}</p>{/if}
    <section class="card rules"><h2>보고 규칙</h2><p>GO/NO-GO/INCONCLUSIVE/NOT_RUN은 그대로 기록되며 완화되지 않습니다.</p></section>
    <section class="card"><h2>관련 문서</h2><div class="docs"><code>requirements.txt</code><code>docs/kronos_v6_prereg_h1_2026-07-19.json</code><code>docs/kronos_v6_universe_manifest_2026-07-19.json</code><code>docs/kronos_v6_goal_review_and_plan_2026-07-19.md</code></div></section>
  {/if}
</section>

<style>
  .page { width: 100%; color: var(--fg); }
  header, .panel, .card, .verdict { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); }
  .eyebrow { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.8rem, 6vw, 2.6rem); }
  h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.15rem; }
  h3 { overflow-wrap: anywhere; }
  .verdict, .card, .panel, .chains { margin-top: 16px; }
  .verdict h2 { color: var(--info); font-size: clamp(2rem, 8vw, 3.5rem); }
  .verdict.danger, .report-card.mismatch, .project-card.blocked { border-color: var(--danger); background: var(--danger-soft); }
  .verdict.danger h2, .error, .mismatch-note { color: var(--danger); }
  .note, .run, .fam { color: var(--muted); font-size: .9rem; }
  .chip, .status, .badge, .test-token { display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: .76rem; font-weight: 800; }
  .chip { border: 1px solid var(--accent); margin-left: 8px; color: var(--accent-strong); }
  .status { border: 1px solid currentColor; }.status.ok { color: var(--success); }.status.warn { color: var(--warn); }.status.blocked { color: var(--danger); }
  .badge.danger { background: var(--danger); color: #fff; }.badge.warn { background: var(--warn); color: #1c1917; }.badge.muted { background: var(--surface-hover, #64748b); color: var(--fg-strong); }
  .test-token { border: 1px solid var(--border-strong); color: var(--fg); }
  button, .actions a { border: 1px solid var(--accent); border-radius: 6px; padding: 6px 10px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; text-decoration: none; }
  .unavailable { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; border: 1px solid var(--danger); border-radius: 10px; padding: 12px; color: var(--danger); background: var(--danger-soft); }
  .project-grid, .report-grid, .prereg-grid, .chains { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 14px; margin-top: 12px; }
  .project-card, .report-card, .prereg-card, .chain { min-width: 0; border: 1px solid var(--border-strong); border-radius: 10px; padding: 16px; background: var(--surface-raised); }
  .project-head, .viewer-head { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: 10px; }
  .project-head h3, .report-card h3, .prereg-card h3 { margin: 6px 0 2px; color: var(--fg-strong); font-size: 1rem; }
  .summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }.summary-grid p { margin: 0; min-width: 0; }.summary-grid strong, .summary-grid span { display: block; overflow-wrap: anywhere; }.summary-grid span { color: var(--muted); font-size: .75rem; }
  .tokens, .actions, .prereg-head, .prereg-runs, .doc-links { display: flex; flex-wrap: wrap; gap: 8px; }.actions { margin-top: 12px; }
  .timeline { margin: 14px 0 0; padding-left: 22px; }.timeline li { padding: 0 0 14px 8px; }.cycle-head { display: flex; flex-wrap: wrap; gap: 6px; }.timeline p { margin: 5px 0; overflow-wrap: anywhere; }.cycle-runs { display: grid; gap: 5px; margin-top: 8px; }.comparison { min-width: 0; padding: 5px; border: 1px solid var(--border); border-radius: 5px; overflow-wrap: anywhere; font-size: .78rem; }.comparison b.danger { color: var(--danger); }.comparison b.warn { color: var(--warn); }.comparison b.muted { color: var(--muted); }
  code { overflow-wrap: anywhere; color: var(--accent-strong); font-size: .85rem; }.mini { margin-left: 6px; padding: 1px 7px; font-size: .74rem; }
  .report-card.selected { outline: 2px solid var(--accent); }.report-card dl { display: grid; grid-template-columns: minmax(70px, auto) minmax(0, 1fr); gap: 5px 12px; margin: 10px 0 0; font-size: .84rem; }.report-card dt { color: var(--muted); }.report-card dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
  .viewer-head { margin-top: 16px; }.viewer-head h3 { margin: 0; color: var(--fg-strong); }.viewer { width: 100%; height: min(1400px, 85vh); margin-top: 8px; border: 1px solid var(--border-strong); border-radius: 10px; background: #fff; }
  .sup { color: var(--warn); font-size: .78rem; }.run-chip { border: 1px solid currentColor; border-radius: 6px; padding: 2px 7px; font-size: .72rem; font-weight: 700; }.run-chip.danger { color: var(--danger); }.run-chip.warn { color: var(--warn); }.run-chip.muted { color: var(--muted); }
  .docs { display: flex; flex-wrap: wrap; gap: 8px; }.docs code { border: 1px solid var(--border-strong); border-radius: 999px; padding: 5px 8px; background: var(--surface-sunken); }.docs-title { margin: 18px 0 8px; font-size: 1rem; }.doc-link { border: 1px solid var(--border-strong); border-radius: 999px; background: var(--surface-sunken); }
  .doc-body { display: block; margin-top: 12px; max-height: 80vh; overflow: auto; border: 1px solid var(--border-strong); border-radius: 10px; padding: clamp(16px, 3vw, 28px); background: var(--surface-sunken); line-height: 1.6; }.doc-body :global(table) { width: 100%; border-collapse: collapse; }.doc-body :global(th), .doc-body :global(td) { border: 1px solid var(--border); padding: 6px 9px; text-align: left; }.doc-body :global(pre) { overflow: auto; }.rules, .empty { border-color: var(--warn); background: var(--warn-soft); color: var(--warn); }.copy-message { color: var(--accent-strong); }
  @media (max-width: 420px) { .project-card, .report-card, .prereg-card, .chain { padding: 12px; }.summary-grid { grid-template-columns: 1fr; }.viewer { height: 70vh; }.actions > * { flex: 1 1 100%; text-align: center; } }
</style>

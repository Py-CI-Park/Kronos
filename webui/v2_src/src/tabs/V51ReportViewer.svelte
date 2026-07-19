<script lang="ts">
  import { onMount } from 'svelte';
  import {
    V51ApiError,
    v51Api,
    type V51ReportListRoot,
    type V51ReportReadRoot,
    type V51ReportSummary,
  } from '$lib/v51Api';

  interface LoadState {
    loading: boolean;
    error: string | null;
  }

  const ESCAPED_PRE_SAFE_HTML = /^<article data-kronos-report-html="escaped-pre"><pre>[^<]*<\/pre><\/article>$/u;

  let reportCatalog = $state<V51ReportListRoot | null>(null);
  let selectedReportId = $state<string | null>(null);
  let selectedReportRead = $state<V51ReportReadRoot | null>(null);
  let listState = $state<LoadState>({ loading: false, error: null });
  let readState = $state<LoadState>({ loading: false, error: null });
  let catalogRequestToken = 0;
  let reportReadToken = 0;

  let reports = $derived(reportCatalog?.reports ?? []);
  let selectedSummary = $derived.by((): V51ReportSummary | null => {
    return reports.find((report) => report.report_id === selectedReportId) ?? selectedReportRead?.report ?? null;
  });
  let renderableReportContent = $derived.by(() => {
    const content = selectedReportRead?.content;
    if (!content) return { mode: 'empty', safeHtml: '', text: '' };
    if (isEscapedPreSafeHtml(content.safe_html)) {
      return { mode: 'safe_html_escaped_pre', safeHtml: content.safe_html, text: '' };
    }
    return { mode: 'text_fallback', safeHtml: '', text: content.raw_text };
  });

  function isEscapedPreSafeHtml(value: string | null | undefined): value is string {
    return typeof value === 'string' && ESCAPED_PRE_SAFE_HTML.test(value);
  }

  function describeReportError(scope: 'REPORTS' | 'REPORT_READ', error: unknown): string {
    if (error instanceof V51ApiError) {
      const status = error.status === null ? 'no-http-status' : `HTTP ${error.status}`;
      return `${scope} ${error.code} · ${status} · ${error.message}`;
    }
    return `${scope} ERROR · ${error instanceof Error ? error.message : String(error)}`;
  }

  function formatBytes(bytes: number): string {
    return `${bytes.toLocaleString('ko-KR')} bytes`;
  }

  function shortHash(value: string | null | undefined): string {
    if (!value) return 'NOT_AVAILABLE';
    return value.length > 24 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value;
  }

  function mediaLabel(report: V51ReportSummary): string {
    return report.media_type === 'text/html; charset=utf-8'
      ? 'HTML · charset=utf-8'
      : 'Wiki/Markdown · charset=utf-8';
  }

  async function loadReportCatalog(): Promise<void> {
    const requestToken = ++catalogRequestToken;
    listState = { loading: true, error: null };
    try {
      const payload = await v51Api.listReports();
      if (requestToken !== catalogRequestToken) return;
      reportCatalog = payload;
      listState = { loading: false, error: null };
      const currentStillExists = selectedReportId !== null && payload.reports.some((report) => report.report_id === selectedReportId);
      const nextReportId = currentStillExists ? selectedReportId : payload.reports[0]?.report_id ?? null;
      if (nextReportId) {
        void selectReport(nextReportId);
      } else {
        selectedReportId = null;
        selectedReportRead = null;
        readState = { loading: false, error: null };
      }
    } catch (error) {
      if (requestToken !== catalogRequestToken) return;
      reportCatalog = null;
      selectedReportId = null;
      selectedReportRead = null;
      listState = { loading: false, error: describeReportError('REPORTS', error) };
      readState = { loading: false, error: null };
    }
  }

  async function selectReport(reportId: string): Promise<void> {
    selectedReportId = reportId;
    selectedReportRead = null;
    const requestToken = ++reportReadToken;
    readState = { loading: true, error: null };
    try {
      const payload = await v51Api.readReport(reportId);
      if (requestToken !== reportReadToken || selectedReportId !== reportId) return;
      selectedReportRead = payload;
      readState = { loading: false, error: null };
    } catch (error) {
      if (requestToken !== reportReadToken || selectedReportId !== reportId) return;
      selectedReportRead = null;
      readState = { loading: false, error: describeReportError('REPORT_READ', error) };
    }
  }

  onMount(() => {
    void loadReportCatalog();
  });
</script>

<section class="panel v51-report-viewer" data-v51-report-viewer data-v51-selected-report={selectedReportId ?? 'NOT_SELECTED'}>
  <div class="panel-head v51-report-head">
    <div>
      <div class="text-eyebrow">V5.1 Report catalog/list/read viewer</div>
      <h2 class="text-h3">Wiki/HTML 리포트 뷰어</h2>
      <p class="text-muted" style="margin-top:6px">
        GET-only V5.1 client로 catalog/list/read를 조회합니다. UTF-8 Korean text is rendered from server safe_html=escaped-pre or text fallback only.
      </p>
    </div>
    <div class="row" style="gap:8px;flex-wrap:wrap;justify-content:flex-end">
      <span class="pill"><span class="dot"></span>GET-only · read-only</span>
      <span class="pill warn"><span class="dot"></span>NO writes · NO downloads</span>
    </div>
  </div>

  {#if reportCatalog && reportCatalog.status !== 'READY'}
    <div class="notice warn" data-v51-report-catalog-blocked>BLOCKED · {reportCatalog.status_reason}</div>
  {/if}

  <div class="v51-report-shell">
    <aside class="v51-report-list" data-v51-report-list>
      <div class="v51-report-list-head">
        <div>
          <div class="text-eyebrow">catalog/list</div>
          <strong>{reports.length.toLocaleString('ko-KR')} reports</strong>
        </div>
        <button type="button" class="btn ghost sm" onclick={() => void loadReportCatalog()} disabled={listState.loading}>
          {listState.loading ? '조회 중…' : '목록 갱신'}
        </button>
      </div>

      {#if listState.error}
        <div class="notice danger" data-v51-report-list-error>ERROR · {listState.error}</div>
      {:else if listState.loading && reports.length === 0}
        <div class="notice" data-v51-report-list-loading>V5.1 REPORTS 조회 중…</div>
      {:else}
        <div class="v51-report-items">
          {#each reports as report (report.report_id)}
            <button
              type="button"
              class="v51-report-item"
              data-active={selectedReportId === report.report_id ? 'true' : 'false'}
              data-v51-report-id={report.report_id}
              onclick={() => void selectReport(report.report_id)}
            >
              <span class="v51-report-title">{report.title}</span>
              <span class="v51-report-subline">{mediaLabel(report)} · {formatBytes(report.byte_length)}</span>
              <span class="v51-report-subline mono">content_hash={shortHash(report.sha256)}</span>
              <span class="v51-report-subline">updated_at={report.updated_at}</span>
            </button>
          {:else}
            <div class="notice" data-v51-report-empty>NOT_RUN · report catalog has no entries.</div>
          {/each}
        </div>
      {/if}
    </aside>

    <main class="v51-report-read" data-v51-report-read>
      {#if readState.loading}
        <div class="notice" data-v51-report-read-loading>REPORT_READ 조회 중…</div>
      {:else if readState.error}
        <div class="notice danger" data-v51-report-read-error>ERROR · {readState.error}</div>
      {:else if !selectedReportRead}
        <div class="notice" data-v51-report-read-empty>NOT_SELECTED · left catalog에서 리포트를 선택하세요.</div>
      {:else}
        {#if selectedReportRead.status !== 'READY'}
          <div class="notice warn" data-v51-report-read-blocked>BLOCKED · {selectedReportRead.status_reason}</div>
        {/if}
        <div class="v51-report-meta" data-v51-report-meta>
          <div><span>report_id</span><b>{selectedReportRead.report.report_id}</b></div>
          <div><span>content_hash</span><b class="mono">sha256={selectedReportRead.report.sha256}</b></div>
          <div><span>source</span><b>{selectedReportRead.report.source_protocol} · {selectedReportRead.report.root_id}</b></div>
          <div><span>catalog_source</span><b>{selectedReportRead.source.catalog_artifact_id} · sha256={shortHash(selectedReportRead.source.catalog_sha256)}</b></div>
          <div><span>date</span><b>updated_at={selectedReportRead.report.updated_at} · generated_at={selectedReportRead.source.generated_at}</b></div>
          <div><span>path/media</span><b>{selectedReportRead.report.relative_path} · {mediaLabel(selectedReportRead.report)}</b></div>
          <div><span>render_contract</span><b>safe_html=escaped-pre · raw_text fallback only</b></div>
          <div><span>claims</span><b>official_close={String(selectedReportRead.report.official_close)} · read_only={String(selectedReportRead.protocol.read_only)}</b></div>
        </div>
        <article
          class="v51-report-body"
          data-v51-report-content
          data-v51-render-mode={renderableReportContent.mode}
          aria-label={selectedSummary?.title ?? 'V5.1 report content'}
        >
          {#if renderableReportContent.mode === 'safe_html_escaped_pre'}
            <div class="v51-report-safe-html" data-safe-html-source="server-escaped-pre">
              {@html renderableReportContent.safeHtml}
            </div>
          {:else}
            <pre class="v51-report-text">{renderableReportContent.text}</pre>
          {/if}
        </article>
      {/if}
    </main>
  </div>
</section>

<style>
  .v51-report-viewer { display:grid; gap:16px; }
  .v51-report-head { align-items:flex-start; }
  .v51-report-shell {
    display:grid;
    grid-template-columns:minmax(240px, 320px) minmax(0, 1fr);
    gap:14px;
    align-items:start;
    min-width:0;
  }
  .v51-report-list,
  .v51-report-read {
    border:1px solid var(--border-faint);
    border-radius:16px;
    background:var(--surface-sunken);
    min-width:0;
  }
  .v51-report-list { padding:12px; display:grid; gap:12px; }
  .v51-report-list-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
  .v51-report-items { display:grid; gap:8px; max-height:520px; overflow:auto; padding-right:2px; }
  .v51-report-item {
    display:grid;
    gap:4px;
    width:100%;
    border:1px solid var(--border-faint);
    border-radius:12px;
    padding:10px;
    background:var(--surface);
    color:var(--fg);
    text-align:left;
    cursor:pointer;
  }
  .v51-report-item[data-active="true"] { border-color:var(--accent); background:var(--accent-soft); }
  .v51-report-title { font-weight:700; overflow-wrap:anywhere; }
  .v51-report-subline { color:var(--muted); font-size:11px; overflow-wrap:anywhere; }
  .v51-report-read { padding:14px; display:grid; gap:12px; }
  .v51-report-meta { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:8px; }
  .v51-report-meta > div { border:1px solid var(--border-faint); border-radius:12px; padding:10px; background:var(--surface); min-width:0; }
  .v51-report-meta span { display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:0.04em; }
  .v51-report-meta b { display:block; margin-top:4px; font-size:12px; overflow-wrap:anywhere; }
  .v51-report-body {
    border:1px solid var(--border-faint);
    border-radius:16px;
    background:var(--surface);
    padding:16px;
    min-width:0;
    overflow:auto;
  }
  .v51-report-body :global(article[data-kronos-report-html="escaped-pre"] pre),
  .v51-report-text {
    margin:0;
    white-space:pre-wrap;
    word-break:break-word;
    overflow-wrap:anywhere;
    font-family:var(--font-mono);
    font-size:12.5px;
    line-height:1.65;
    color:var(--fg);
  }
  .mono { font-family:var(--font-mono); }
  @media (max-width: 900px) {
    .v51-report-shell { grid-template-columns:1fr; }
    .v51-report-items { max-height:320px; }
  }
</style>

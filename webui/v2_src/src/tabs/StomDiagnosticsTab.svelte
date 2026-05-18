<script lang="ts">
  import { onMount } from 'svelte';
  import { fmt } from '$lib/format';
  import { ICONS } from '$lib/icons';

  // ── Summary 데이터 ───────────────────────────────────────────
  interface StomSummary {
    compatible_stock_table_count?: number;
    db_size_bytes?: number;
    eligible_group_count?: number;
    estimated_samples?: number;
    table_count?: number;
    total_rows_stock_groups?: number;
    excluded_tables?: string[];
    warnings?: string[];
    inspect_available?: boolean;
    scale_available?: boolean;
  }
  interface FileItem {
    name: string;
    path: string;
    directory?: string;
    modified_at?: number;
    size_bytes?: number;
    artifact_type?: string;
  }

  let summary = $state<StomSummary | null>(null);
  let predFiles = $state<FileItem[]>([]);
  let backtestFiles = $state<FileItem[]>([]);
  let filterFiles = $state<FileItem[]>([]);
  let loadingSummary = $state(false);
  let summaryError = $state<string | null>(null);

  // 활성 패널
  let view = $state<'prediction' | 'backtest' | 'filter'>('prediction');

  // 선택한 파일 + 진단 결과
  let selectedFile = $state<FileItem | null>(null);
  let diagnostics = $state<any>(null);
  let loadingDiag = $state(false);
  let diagError = $state<string | null>(null);

  async function loadSummary() {
    loadingSummary = true;
    summaryError = null;
    try {
      const r = await fetch('/api/stom/summary');
      if (!r.ok) {
        summaryError = `HTTP ${r.status}`;
        return;
      }
      summary = await r.json();
    } catch (e: any) {
      summaryError = e?.message ?? 'STOM 요약 조회 실패';
    } finally {
      loadingSummary = false;
    }
  }

  async function loadList(url: string): Promise<FileItem[]> {
    try {
      const r = await fetch(url);
      if (!r.ok) return [];
      const d = await r.json();
      return Array.isArray(d.files) ? d.files : Array.isArray(d) ? d : [];
    } catch {
      return [];
    }
  }

  async function loadAllLists() {
    [predFiles, backtestFiles, filterFiles] = await Promise.all([
      loadList('/api/stom/prediction-files'),
      loadList('/api/stom/qlib-backtests'),
      loadList('/api/stom/filter-reports'),
    ]);
  }

  async function selectFile(f: FileItem) {
    selectedFile = f;
    diagnostics = null;
    diagError = null;
    if (view !== 'prediction') return;
    loadingDiag = true;
    try {
      const r = await fetch(`/api/stom/diagnostics?file=${encodeURIComponent(f.path)}`);
      if (!r.ok) {
        diagError = `HTTP ${r.status}`;
        return;
      }
      diagnostics = await r.json();
    } catch (e: any) {
      diagError = e?.message ?? '진단 조회 실패';
    } finally {
      loadingDiag = false;
    }
  }

  onMount(() => {
    loadSummary();
    loadAllLists();
  });

  function gib(b: number | undefined | null): string {
    if (b == null) return '—';
    if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(2) + ' GiB';
    if (b >= 1024 ** 2) return (b / 1024 ** 2).toFixed(1) + ' MiB';
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KiB';
    return b + ' B';
  }

  let activeFiles = $derived(view === 'prediction' ? predFiles : view === 'backtest' ? backtestFiles : filterFiles);
  let viewLabel = $derived(view === 'prediction' ? '예측 결과' : view === 'backtest' ? '백테스트' : '필터 리포트');
</script>

<section class="page-hero">
  <div class="row" style="gap:10px;flex-wrap:wrap">
    <span class="text-eyebrow">P4 · 본격</span>
    <span class="pill"><span class="dot" style="background:var(--info)"></span>9개 endpoint · read-only</span>
    <span class="pill"><span class="dot" style="background:{summary?.inspect_available ? 'var(--success)' : 'var(--warn)'}"></span>
      inspect {summary?.inspect_available ? 'OK' : '제한'}</span>
  </div>
  <h1 class="text-h2" style="margin-top:8px">예측 진단</h1>
  <p class="text-muted" style="margin-top:6px">
    STOM (Securities Time-series Open Market) 데이터셋 요약과 예측·백테스트·필터 산출물을 통합 조회합니다.
    모든 데이터는 read-only 이며 사용자는 산출물을 수정할 수 없습니다.
  </p>
</section>

<!-- ===== DB summary KPIs ===== -->
{#if loadingSummary && !summary}
  <div class="card"><div class="text-muted">STOM 데이터셋 요약 조회 중...</div></div>
{:else if summaryError}
  <div class="card" style="border-color:var(--danger-soft)">
    <div class="text-caption" style="color:var(--danger)">⚠ {summaryError}</div>
    <button class="btn" onclick={loadSummary} style="margin-top:8px">다시 시도</button>
  </div>
{:else if summary}
  <section class="grid-4-summary">
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">DB 크기</span>
        <span class="pill"><span class="dot" style="background:var(--info)"></span>SQLite</span>
      </div>
      <div class="metric-value tnum">{gib(summary.db_size_bytes)}</div>
      <div class="metric-foot">테이블 {fmt.int(summary.table_count)} · 호환 {fmt.int(summary.compatible_stock_table_count)}</div>
    </div>
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">총 row 수</span>
        <span class="pill accent"><span class="dot"></span>stock_groups</span>
      </div>
      <div class="metric-value tnum">{fmt.int(summary.total_rows_stock_groups)}</div>
      <div class="metric-foot">stock_groups 테이블 누적</div>
    </div>
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">학습 가능 그룹</span>
        <span class="pill success"><span class="dot"></span>eligible</span>
      </div>
      <div class="metric-value tnum">{fmt.int(summary.eligible_group_count)}</div>
      <div class="metric-foot">길이·결측 검증 통과</div>
    </div>
    <div class="metric">
      <div class="metric-head">
        <span class="metric-label">예상 샘플 수</span>
        <span class="pill"><span class="dot"></span>estimated</span>
      </div>
      <div class="metric-value tnum">{fmt.int(summary.estimated_samples)}</div>
      <div class="metric-foot">학습/검증 분할 가능</div>
    </div>
  </section>

  {#if summary.warnings && summary.warnings.length > 0}
    <div class="card compact flat" style="background:var(--warn-soft);border-color:transparent;padding:12px 16px">
      <div class="row" style="gap:8px;margin-bottom:6px">
        <span class="pill warn"><span class="dot"></span>경고 {summary.warnings.length}</span>
      </div>
      {#each summary.warnings as w}
        <div class="text-caption" style="line-height:1.6">⚠ {w}</div>
      {/each}
    </div>
  {/if}
{/if}

<!-- ===== File browser ===== -->
<section class="row" style="gap:10px;flex-wrap:wrap">
  <div class="tabs">
    <button data-active={view === 'prediction' ? 'true' : 'false'} onclick={() => (view = 'prediction')}>
      예측 결과 ({predFiles.length})
    </button>
    <button data-active={view === 'backtest' ? 'true' : 'false'} onclick={() => (view = 'backtest')}>
      백테스트 ({backtestFiles.length})
    </button>
    <button data-active={view === 'filter' ? 'true' : 'false'} onclick={() => (view = 'filter')}>
      필터 리포트 ({filterFiles.length})
    </button>
  </div>
  <button class="btn ghost sm" onclick={loadAllLists} style="margin-left:auto">
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">{@html ICONS.refresh}</svg>
    목록 새로고침
  </button>
</section>

<section class="grid-list-detail">
  <!-- File list -->
  <div class="card" style="padding:0;overflow:hidden">
    <div class="row spread" style="padding:14px 18px 8px">
      <div>
        <div class="card-eyebrow">{viewLabel.toUpperCase()} ({activeFiles.length})</div>
        <div class="card-title">파일 목록</div>
      </div>
      <span class="text-caption">최신순</span>
    </div>
    <div class="file-list">
      {#if activeFiles.length === 0}
        <div class="text-caption" style="padding:32px 20px;text-align:center;color:var(--dim)">
          파일이 없습니다
        </div>
      {:else}
        {#each [...activeFiles].sort((a, b) => (b.modified_at ?? 0) - (a.modified_at ?? 0)) as f}
          <button
            type="button"
            class="file-row-btn"
            data-active={selectedFile?.path === f.path ? 'true' : 'false'}
            onclick={() => selectFile(f)}
          >
            <span class="file-icon">
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">{@html ICONS.file}</svg>
            </span>
            <div style="min-width:0;flex:1">
              <div class="text-mono" style="font-weight:600;color:var(--fg-strong);font-size:12px;line-height:1.3;word-break:break-all">{f.name}</div>
              <div class="text-caption" style="font-size:10px;margin-top:2px">
                {gib(f.size_bytes)} · {f.modified_at ? fmt.relative(f.modified_at * 1000) : '—'}
              </div>
            </div>
            {#if f.artifact_type}
              <span class="pill" style="padding:2px 6px;font-size:10px">{f.artifact_type}</span>
            {/if}
          </button>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Detail panel -->
  <div class="card">
    {#if !selectedFile}
      <div class="card-eyebrow">DETAIL</div>
      <div class="text-muted" style="padding:24px 0;text-align:center">
        좌측에서 파일을 선택하면 상세 정보가 표시됩니다.
      </div>
    {:else}
      <div class="card-header">
        <div style="min-width:0;flex:1">
          <div class="card-eyebrow">{viewLabel.toUpperCase()} · DETAIL</div>
          <div class="text-mono" style="font-weight:700;color:var(--fg-strong);font-size:13px;word-break:break-all">{selectedFile.name}</div>
        </div>
        <span class="pill"><span class="dot"></span>{gib(selectedFile.size_bytes)}</span>
      </div>

      <table class="kv-table">
        <tbody>
          <tr><td>전체 경로</td><td class="text-mono" style="word-break:break-all;font-size:11px">{selectedFile.path}</td></tr>
          <tr><td>수정 시각</td><td class="text-mono">{selectedFile.modified_at ? fmt.kst(selectedFile.modified_at * 1000) : '—'}</td></tr>
          <tr><td>파일 크기</td><td class="text-mono tnum">{gib(selectedFile.size_bytes)}</td></tr>
          {#if selectedFile.artifact_type}
            <tr><td>아티팩트 타입</td><td class="text-mono">{selectedFile.artifact_type}</td></tr>
          {/if}
        </tbody>
      </table>

      {#if view === 'prediction'}
        <div style="margin-top:12px">
          {#if loadingDiag}
            <div class="text-caption">진단 데이터 조회 중...</div>
          {:else if diagError}
            <div class="text-caption" style="color:var(--danger)">⚠ {diagError}</div>
          {:else if diagnostics}
            <div class="card-eyebrow" style="margin-bottom:8px">DIAGNOSTICS · /api/stom/diagnostics</div>
            {#if diagnostics.overall}
              <table class="kv-table">
                <tbody>
                  {#each Object.entries(diagnostics.overall) as [k, v]}
                    <tr>
                      <td>{k}</td>
                      <td class="text-mono tnum">
                        {typeof v === 'number' ? (Math.abs(v as number) < 0.001 ? (v as number).toExponential(2) : (v as number).toFixed(4)) : String(v)}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {:else}
              <pre class="diag-json">{JSON.stringify(diagnostics, null, 2).slice(0, 800)}{JSON.stringify(diagnostics).length > 800 ? '\n...' : ''}</pre>
            {/if}
          {:else}
            <div class="text-caption">진단 결과 없음</div>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .page-hero { padding: 8px 0; }
  .grid-4-summary {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
  @media (max-width: 1200px) { .grid-4-summary { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 560px) { .grid-4-summary { grid-template-columns: 1fr; } }

  .grid-list-detail {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.6fr);
    gap: 16px;
  }
  @media (max-width: 1100px) {
    .grid-list-detail { grid-template-columns: 1fr; }
  }
  .file-list {
    max-height: 540px;
    overflow-y: auto;
    padding: 6px 8px 12px;
  }
  .file-row-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--r-sm);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: background var(--d-fast), border-color var(--d-fast);
  }
  .file-row-btn:hover {
    background: var(--surface-sunken);
  }
  .file-row-btn[data-active="true"] {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .file-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--r-sm);
    background: var(--accent-soft);
    color: var(--accent-strong);
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }

  .kv-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 8px;
  }
  .kv-table tbody tr {
    border-bottom: 1px solid var(--border-faint);
  }
  .kv-table tbody tr:last-child {
    border-bottom: none;
  }
  .kv-table td {
    padding: 8px 0;
    vertical-align: top;
  }
  .kv-table td:first-child {
    color: var(--muted);
    width: 35%;
    padding-right: 12px;
  }
  .kv-table td:last-child {
    color: var(--fg-strong);
    text-align: right;
    font-weight: 600;
  }
  .diag-json {
    background: var(--surface-sunken);
    border-radius: var(--r-sm);
    padding: 10px;
    font: 500 11px/1.5 var(--font-mono);
    color: var(--muted);
    max-height: 280px;
    overflow: auto;
    white-space: pre;
  }
</style>

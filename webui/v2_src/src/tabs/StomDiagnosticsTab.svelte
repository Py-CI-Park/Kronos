<script lang="ts">
  import { onMount } from 'svelte';
  import { fmt } from '$lib/format';
  import { ICONS } from '$lib/icons';
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';

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
  let predictionDetail = $state<any>(null);
  let backtestReport = $state<any>(null);
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
    const latest = preferredPredictionFile();
    if (!selectedFile && latest && view === 'prediction') {
      await selectFile(latest);
    }
  }

  function fileQuery(f: FileItem): string {
    return f.name || f.path;
  }

  async function selectFile(f: FileItem) {
    selectedFile = f;
    diagnostics = null;
    predictionDetail = null;
    backtestReport = null;
    diagError = null;
    if (view !== 'prediction') return;
    loadingDiag = true;
    try {
      const query = encodeURIComponent(fileQuery(f));
      const [diagRes, predictionRes, reportRes] = await Promise.all([
        fetch(`/api/stom/diagnostics?file=${query}&max_symbols=30`),
        fetch(`/api/stom/prediction?file=${query}`),
        fetch(`/api/stom/backtest-report?file=${query}&top_k=5`),
      ]);
      if (!diagRes.ok) throw new Error(`진단 HTTP ${diagRes.status}`);
      if (!predictionRes.ok) throw new Error(`예측 상세 HTTP ${predictionRes.status}`);
      diagnostics = await diagRes.json();
      predictionDetail = await predictionRes.json();
      backtestReport = reportRes.ok ? await reportRes.json() : null;
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
  let sortedActiveFiles = $derived(sortFilesForDisplay(activeFiles, view));

  function predictionPriority(name: string): number {
    if (name.includes('_kronos.csv')) return 0;
    if (name.includes('_persistence.csv')) return 1;
    if (name.includes('_random.csv')) return 2;
    return 3;
  }

  function sortFilesForDisplay(files: FileItem[], currentView: 'prediction' | 'backtest' | 'filter'): FileItem[] {
    return [...files].sort((a, b) => {
      const modified = (b.modified_at ?? 0) - (a.modified_at ?? 0);
      if (Math.abs(modified) > 120) return modified;
      if (currentView === 'prediction') {
        const priority = predictionPriority(a.name) - predictionPriority(b.name);
        if (priority !== 0) return priority;
      }
      return a.name.localeCompare(b.name);
    });
  }

  function preferredPredictionFile(): FileItem | undefined {
    const sorted = sortFilesForDisplay(predFiles, 'prediction');
    return sorted.find((file) => file.name.includes('_kronos.csv')) ?? sorted[0];
  }

  function switchView(next: 'prediction' | 'backtest' | 'filter') {
    view = next;
    selectedFile = null;
    diagnostics = null;
    predictionDetail = null;
    backtestReport = null;
    diagError = null;
    if (next === 'prediction') {
      const latest = preferredPredictionFile();
      if (latest) void selectFile(latest);
    }
  }

  function pct(value: unknown, digits = 1): string {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return `${n.toFixed(digits)}%`;
  }

  function num(value: unknown, digits = 3): string {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    if (Math.abs(n) >= 1000) return fmt.int(n);
    return n.toFixed(digits);
  }

  function verdict(overall: any): { label: string; tone: 'success' | 'warn' | 'danger'; message: string } {
    const direction = Number(overall?.direction_accuracy ?? 0);
    const avgReturn = Number(overall?.avg_actual_return ?? 0);
    if (direction >= 0.45 && avgReturn >= 0) {
      return { label: '탐색 가치 있음', tone: 'success', message: '방향 적중률이 0.40 기준선을 넘고 평균 실제 수익률도 양수입니다. 단, 비용 반영 수익은 별도 확인이 필요합니다.' };
    }
    if (direction >= 0.4) {
      return { label: '조건식 보완 필요', tone: 'warn', message: '방향성은 기준선을 넘지만 수익/비용 관점에서 필터와 리스크 조건을 추가해야 합니다.' };
    }
    return { label: '실전 사용 보류', tone: 'danger', message: '방향 적중률이 낮아 현재 결과만으로 자동매매 신호로 쓰기 어렵습니다.' };
  }

  const resultVerdict = $derived(verdict(diagnostics?.overall));

  const actualPredictionOption = $derived.by(() => {
    const visual = predictionDetail?.visual;
    const rows = visual?.window_series ?? [];
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 52, right: 24, top: 34, bottom: 42 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: 'inherit' } },
      xAxis: { type: 'category', data: rows.map((r: any) => String(r.timestamp).slice(11, 19)), axisLabel: { color: '#64748b' } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.22)' } } },
      series: [
        { name: '실제 종가', type: 'line', smooth: 0.25, symbol: 'none', data: rows.map((r: any) => r.actual_close), lineStyle: { color: '#0f172a', width: 2.2 } },
        { name: 'Kronos 예측', type: 'line', smooth: 0.25, symbol: 'none', data: rows.map((r: any) => r.pred_close), lineStyle: { color: '#ef4444', width: 2, type: 'dashed' } },
      ],
    };
  });

  const returnScatterOption = $derived.by(() => {
    const rows = predictionDetail?.visual?.return_scatter ?? [];
    if (!rows.length) return {};
    return {
      backgroundColor: 'transparent',
      grid: { left: 54, right: 24, top: 26, bottom: 46 },
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => {
          const r = rows[p.dataIndex];
          return `${r.symbol}<br/>예측 ${num(r.pred_return_window, 3)}%<br/>실제 ${num(r.actual_return_window, 3)}%<br/>${r.direction_hit_window ? '방향 적중' : '방향 실패'}`;
        },
      },
      xAxis: { type: 'value', name: '예측 등락률 %', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.2)' } } },
      yAxis: { type: 'value', name: '실제 등락률 %', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.2)' } } },
      series: [
        {
          name: 'window',
          type: 'scatter',
          symbolSize: 7,
          data: rows.map((r: any) => [r.pred_return_window, r.actual_return_window]),
          itemStyle: { color: (p: any) => rows[p.dataIndex]?.direction_hit_window ? '#22c55e' : '#ef4444', opacity: 0.72 },
        },
      ],
    };
  });
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
    <button data-active={view === 'prediction' ? 'true' : 'false'} onclick={() => switchView('prediction')}>
      예측 결과 ({predFiles.length})
    </button>
    <button data-active={view === 'backtest' ? 'true' : 'false'} onclick={() => switchView('backtest')}>
      백테스트 ({backtestFiles.length})
    </button>
    <button data-active={view === 'filter' ? 'true' : 'false'} onclick={() => switchView('filter')}>
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
        {#each sortedActiveFiles as f}
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
            <div class="card-eyebrow" style="margin-bottom:8px">EVALUATION SUMMARY · 사용자가 바로 읽는 성과 요약</div>
            {#if diagnostics.overall}
              <div class="verdict-card {resultVerdict.tone}">
                <div>
                  <div class="text-eyebrow">MODEL VERDICT</div>
                  <h3>{resultVerdict.label}</h3>
                  <p>{resultVerdict.message}</p>
                </div>
                <span class="pill {resultVerdict.tone}">
                  방향 적중 {pct(Number(diagnostics.overall.direction_accuracy ?? 0) * 100)}
                </span>
              </div>

              <div class="eval-kpi-grid">
                <div class="eval-kpi">
                  <span>방향 적중률</span>
                  <strong>{pct(Number(diagnostics.overall.direction_accuracy ?? 0) * 100)}</strong>
                  <small>0.40 기준선 대비 {Number(diagnostics.overall.direction_accuracy ?? 0) >= 0.4 ? '상회' : '미달'}</small>
                </div>
                <div class="eval-kpi">
                  <span>MAPE</span>
                  <strong>{pct(diagnostics.overall.mape)}</strong>
                  <small>가격 경로 평균 오차율</small>
                </div>
                <div class="eval-kpi">
                  <span>평가 범위</span>
                  <strong>{fmt.int(diagnostics.overall.windows)} windows</strong>
                  <small>{fmt.int(diagnostics.overall.symbols)}종목 · {fmt.int(diagnostics.overall.sessions)}거래일</small>
                </div>
                <div class="eval-kpi">
                  <span>평균 실제 등락률</span>
                  <strong>{pct(diagnostics.overall.avg_actual_return, 3)}</strong>
                  <small>예측 window 최종 시점 기준</small>
                </div>
              </div>

              {#if backtestReport?.filters}
                <div class="card-eyebrow" style="margin:16px 0 8px">조건식/Top-K 필터별 성과</div>
                <div class="filter-grid">
                  {#each backtestReport.filters.slice(0, 6) as row}
                    <div class="filter-card">
                      <span>{row.label}</span>
                      <strong>{pct(row.hit_rate * 100)}</strong>
                      <small>count {fmt.int(row.count)} · 실제 {pct(row.avg_actual_return, 3)}</small>
                    </div>
                  {/each}
                </div>
              {/if}

              {#if predictionDetail?.visual?.window_series?.length}
                <div class="chart-section">
                  <div class="chart-title">
                    <div>
                      <div class="card-eyebrow">ACTUAL VS PREDICTION</div>
                      <h3>선택 window 실제 종가와 Kronos 예측 종가</h3>
                    </div>
                    {#if predictionDetail.visual.selected_window}
                      <span class="pill accent">
                        {predictionDetail.visual.selected_window.symbol} · window {predictionDetail.visual.selected_window.window_id}
                      </span>
                    {/if}
                  </div>
                  <EChartsRenderer option={actualPredictionOption} height="320px" />
                </div>

                <div class="chart-section">
                  <div class="chart-title">
                    <div>
                      <div class="card-eyebrow">RETURN SCATTER</div>
                      <h3>전체 window 예측 등락률 vs 실제 등락률</h3>
                    </div>
                    <span class="text-caption">초록=방향 적중 · 빨강=방향 실패</span>
                  </div>
                  <EChartsRenderer option={returnScatterOption} height="320px" />
                </div>
              {/if}

              {#if predictionDetail?.recommendations?.length}
                <div class="card-eyebrow" style="margin:16px 0 8px">Kronos 점수 상위 후보</div>
                <div class="table-scroll">
                  <table class="result-table">
                    <thead>
                      <tr>
                        <th>순위</th>
                        <th>종목</th>
                        <th>일자</th>
                        <th>점수</th>
                        <th>신호</th>
                        <th>예측 등락률</th>
                        <th>실제 등락률</th>
                        <th>방향</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each predictionDetail.recommendations.slice(0, 10) as row, idx}
                        <tr>
                          <td>{idx + 1}</td>
                          <td class="text-mono">{row.symbol}</td>
                          <td class="text-mono">{row.session}</td>
                          <td class="tnum">{num(row.kronos_score, 1)}</td>
                          <td><span class="pill {row.signal === 'BUY_CANDIDATE' ? 'success' : row.signal === 'WATCH' ? 'warn' : 'danger'}">{row.signal}</span></td>
                          <td class="tnum">{pct(row.pred_return_window, 3)}</td>
                          <td class="tnum">{pct(row.actual_return_window, 3)}</td>
                          <td>{row.direction_hit_window ? '적중' : '실패'}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {/if}

              {#if diagnostics.best_symbols?.length}
                <div class="card-eyebrow" style="margin:16px 0 8px">종목별 해석</div>
                <div class="symbol-columns">
                  <div>
                    <h4>상위 종목</h4>
                    {#each diagnostics.best_symbols.slice(0, 6) as row}
                      <div class="symbol-row">
                        <strong class="text-mono">{row.symbol}</strong>
                        <span>방향 {pct(row.direction_accuracy * 100, 1)} · MAPE {pct(row.mape, 2)}</span>
                      </div>
                    {/each}
                  </div>
                  <div>
                    <h4>주의 종목</h4>
                    {#each diagnostics.worst_symbols.slice(0, 6) as row}
                      <div class="symbol-row">
                        <strong class="text-mono">{row.symbol}</strong>
                        <span>방향 {pct(row.direction_accuracy * 100, 1)} · MAPE {pct(row.mape, 2)}</span>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
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

  .verdict-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    align-items: start;
    padding: 16px;
    border-radius: var(--r-md);
    border: 1px solid var(--border-faint);
    margin-bottom: 14px;
  }
  .verdict-card h3 {
    margin: 4px 0 6px;
    font: 800 20px/1.2 var(--font-display);
    color: var(--fg-strong);
  }
  .verdict-card p {
    margin: 0;
    color: var(--muted);
    line-height: 1.55;
  }
  .verdict-card.success { background: var(--success-soft); border-color: color-mix(in oklch, var(--success) 28%, transparent); }
  .verdict-card.warn { background: var(--warn-soft); border-color: color-mix(in oklch, var(--warn) 28%, transparent); }
  .verdict-card.danger { background: var(--danger-soft); border-color: color-mix(in oklch, var(--danger) 28%, transparent); }

  .eval-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  .eval-kpi,
  .filter-card {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-sm);
    padding: 12px;
    background: var(--surface-sunken);
  }
  .eval-kpi span,
  .filter-card span {
    display: block;
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
  }
  .eval-kpi strong,
  .filter-card strong {
    display: block;
    margin-top: 4px;
    color: var(--fg-strong);
    font: 800 22px/1 var(--font-mono);
  }
  .eval-kpi small,
  .filter-card small {
    display: block;
    margin-top: 6px;
    color: var(--dim);
    line-height: 1.4;
  }

  .filter-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .chart-section {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--border-faint);
  }
  .chart-title {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }
  .chart-title h3 {
    margin: 3px 0 0;
    color: var(--fg-strong);
    font: 750 16px/1.25 var(--font-display);
  }

  .table-scroll {
    overflow-x: auto;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-sm);
  }
  .result-table {
    width: 100%;
    border-collapse: collapse;
    min-width: 760px;
    font-size: 12px;
  }
  .result-table th,
  .result-table td {
    padding: 9px 10px;
    border-bottom: 1px solid var(--border-faint);
    text-align: left;
  }
  .result-table th {
    color: var(--muted);
    background: var(--surface-sunken);
    font-weight: 800;
  }
  .result-table tr:last-child td {
    border-bottom: none;
  }

  .symbol-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .symbol-columns h4 {
    margin: 0 0 8px;
    color: var(--fg-strong);
  }
  .symbol-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-faint);
    color: var(--muted);
    font-size: 12px;
  }

  @media (max-width: 900px) {
    .eval-kpi-grid,
    .filter-grid,
    .symbol-columns {
      grid-template-columns: 1fr;
    }
    .verdict-card,
    .chart-title {
      display: block;
    }
  }
</style>

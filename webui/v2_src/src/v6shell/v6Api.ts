export interface V6ApiResult<T> {
  readonly ok: boolean;
  readonly data?: T;
  readonly error?: string;
}

export interface V6ModelStatus {
  readonly available?: boolean;
  readonly loaded?: boolean;
  readonly message?: string;
}

export type V6ModelStatusPresentation =
  | { readonly state: 'LOADED'; readonly label: '로드됨' }
  | { readonly state: 'AVAILABLE_NOT_LOADED'; readonly label: '사용 가능 · 아직 미로드' }
  | { readonly state: 'UNAVAILABLE'; readonly label: '사용 불가' };

export function classifyV6ModelStatus(status: V6ModelStatus | null | undefined): V6ModelStatusPresentation {
  if (status?.available === true && status.loaded === true) {
    return { state: 'LOADED', label: '로드됨' };
  }
  if (status?.available === true) {
    return { state: 'AVAILABLE_NOT_LOADED', label: '사용 가능 · 아직 미로드' };
  }
  return { state: 'UNAVAILABLE', label: '사용 불가' };
}

export interface V6JourneyStep {
  readonly state?: string;
}

export interface V6Status {
  readonly schema_version?: string;
  readonly status?: string;
  readonly journey: {
    readonly data: V6JourneyStep & {
      readonly universe_manifest?: string;
      readonly universe_size?: number;
      readonly index_overlay?: string;
      readonly index_blocker_reason?: string;
    };
    readonly experiment: V6JourneyStep;
    readonly training: V6JourneyStep;
    readonly evaluation: V6JourneyStep;
    readonly report: V6JourneyStep;
  };
  readonly locks: Record<string, boolean>;
}

export interface V6UniverseRow {
  readonly table?: string;
  readonly code?: string;
  readonly rows?: number;
  readonly first_date?: string;
  readonly last_date?: string;
}

export interface V6Universe {
  readonly status?: string;
  readonly manifest?: string;
  readonly sha256?: string;
  readonly universe: readonly V6UniverseRow[];
  readonly total?: number;
  readonly filters?: unknown;
  readonly instrument_type?: string;
  readonly price_basis?: string;
}

export interface V6DataReadiness {
  readonly daily_db: {
    readonly present?: boolean;
    readonly state?: string;
    readonly size_bytes?: number;
    readonly mtime?: string;
    readonly mtime_epoch?: number;
    readonly table_count?: number;
  };
  readonly fivemin_db: {
    readonly present?: boolean;
    readonly state?: string;
    readonly size_bytes?: number;
  };
  readonly audit: {
    readonly state?: string;
    readonly population?: unknown;
    readonly filters?: unknown;
    readonly disclaimers?: {
      readonly instrument_type?: unknown;
      readonly flow_columns_disclaimer?: unknown;
      readonly liquidity_proxy_disclaimer?: unknown;
    };
  };
  readonly index: {
    readonly state?: string;
    readonly reason?: string;
    readonly markets?: Record<string, {
      readonly index_code?: string;
      readonly index_name?: string;
      readonly actual_start_date?: string;
      readonly actual_end_date?: string;
      readonly row_count?: number;
      readonly normalized_sha256?: string;
    }>;
  };
  readonly price_basis: {
    readonly status?: string;
    readonly decision_grade_returns?: boolean;
    readonly caveat?: unknown;
  };
}
export interface V6Experiment {
  readonly prereg?: {
    readonly state?: string;
    readonly path?: string;
    readonly sha256?: string;
    readonly frozen_utc?: string;
    readonly hypothesis?: unknown;
  };
  readonly planned?: {
    readonly strategy?: string;
    readonly horizons?: { readonly primary?: unknown; readonly validation?: unknown };
    readonly execution?: { readonly price_basis?: unknown; readonly official_close?: boolean };
    readonly capital?: {
      readonly initial_krw?: number;
      readonly slots?: number;
      readonly slot_budget_krw?: number;
      readonly reserve_krw?: number;
    };
    readonly costs?: { readonly primary?: unknown; readonly zero_control?: unknown; readonly stress?: unknown };
    readonly universe?: { readonly manifest?: unknown; readonly size?: unknown };
    readonly dataset_contract?: unknown;
    readonly seeds?: unknown;
    readonly constraints?: Record<string, unknown>;
  };
  readonly locks?: Record<string, boolean>;
}

export interface V6DatasetRun {
  readonly run_id?: string;
  readonly path?: string;
  readonly generated_utc?: string;
  readonly split_row_counts?: unknown;
  readonly sha256?: string;
}

export interface V6TrainingRun {
  readonly run_id?: string;
  readonly path?: string;
  readonly state?: string;
  readonly seeds?: unknown;
  readonly generated_utc?: string;
  readonly dataset_run_id?: string;
  readonly verdict_candidate?: { readonly value?: string; readonly reasons?: readonly unknown[] };
}
export interface V6Runs {
  readonly datasets?: readonly V6DatasetRun[];
  readonly runs?: readonly V6TrainingRun[];
  readonly training_state?: string;
}
export interface V6RunSeed {
  readonly episodes_ran?: number;
  readonly best_episode?: number;
  readonly val_nav_curve?: readonly number[];
  readonly final_val_metrics?: {
    readonly nav?: number;
    readonly total_net_return_pct?: number;
    readonly max_drawdown?: number;
    readonly trade_count?: number;
    readonly cost_scenario_navs?: Record<string, number>;
  };
}

export interface V6RunDetail {
  readonly status?: string;
  readonly state?: string;
  readonly execution_status?: string;
  readonly dataset_run_id?: string;
  readonly train_run_id?: string;
  readonly manifest?: {
    readonly per_seed?: Record<string, V6RunSeed>;
    readonly baselines?: Record<string, { readonly nav?: number }>;
    readonly shuffled_label_control?: Record<string, V6RunSeed>;
    readonly verdict_candidate?: { readonly value?: string; readonly reasons?: readonly unknown[] };
    readonly test?: { readonly state?: string };
    readonly seeds?: unknown;
    readonly trainer_version?: string;
    readonly model_family?: string;
    readonly algorithm?: string;
    readonly prereg?: { readonly id?: string; readonly sha256?: string };
    readonly generated_utc?: string;
    readonly primary_cost_rate?: number;
    readonly hyperparams?: {
      readonly algorithm?: string;
      readonly model_family?: string;
      readonly primary_cost_rate?: number;
    };
    readonly false_research_locks?: unknown;
    readonly training_state?: string;
  };
  readonly manifest_sha256?: string;
  readonly events_tail?: readonly { readonly episode?: unknown; readonly val_nav?: unknown }[];
  readonly reason?: string;
}


export interface V6InsightSeriesRow {
  readonly date: number;
  readonly close?: number | null;
  readonly volume?: number | null;
  readonly foreign_ratio?: number | null;
  readonly inst_netbuy?: number | null;
}

export interface V6InsightSymbol {
  readonly status?: string;
  readonly code?: string;
  readonly total_rows?: number;
  readonly sampled?: boolean;
  readonly series?: readonly V6InsightSeriesRow[];
  readonly price_basis_caveat?: string;
  readonly flow_caveat?: string;
  readonly reason?: string;
}

export interface V6InsightFlowRow {
  readonly table?: string;
  readonly code?: string;
  readonly inst_netbuy_sum?: number;
  readonly foreign_ratio_delta?: number;
  readonly last_close?: number;
  readonly last_date?: number;
}

export interface V6InsightFlow {
  readonly status?: string;
  readonly window?: number;
  readonly top_inst_buy?: readonly V6InsightFlowRow[];
  readonly top_inst_sell?: readonly V6InsightFlowRow[];
  readonly top_foreign_gain?: readonly V6InsightFlowRow[];
  readonly top_foreign_loss?: readonly V6InsightFlowRow[];
  readonly not_a_recommendation?: boolean;
  readonly note?: string;
  readonly price_basis_caveat?: string;
  readonly flow_caveat?: string;
  readonly reason?: string;
}

export function observedV6TrainingState(
  detail: V6RunDetail | null | undefined,
  run: V6TrainingRun | null | undefined,
  aggregate: string | undefined,
): string | undefined {
  return detail?.state ?? detail?.manifest?.training_state ?? run?.state ?? aggregate;
}

export function insightQuickPickCodes(flow: V6InsightFlow | null | undefined, limit = 8): readonly string[] {
  const codes: string[] = [];
  const seen = new Set<string>();
  const groups = [
    flow?.top_inst_buy ?? [],
    flow?.top_foreign_gain ?? [],
    flow?.top_inst_sell ?? [],
    flow?.top_foreign_loss ?? [],
  ] as const;
  for (const rows of groups) {
    for (const row of rows) {
      const code = row.code;
      if (typeof code !== 'string' || !/^\d{6}$/.test(code) || seen.has(code)) continue;
      seen.add(code);
      codes.push(code);
      if (codes.length === limit) return codes;
    }
  }
  return codes;
}

export interface V6InsightRegime {
  readonly index_regime?: {
    readonly state?: string;
    readonly reason?: string;
    readonly markets?: Record<string, V6IndexRegimeMarket>;
    readonly caveat?: string;
  };
  readonly breadth_proxy?: {
    readonly as_of_date?: number;
    readonly tables_evaluated?: number;
    readonly pct_above_20s_mean?: number;
    readonly disclaimer?: string;
  };
}

async function getV6<T>(path: string): Promise<V6ApiResult<T>> {
  try {
    const response = await fetch(path, { headers: { Accept: 'application/json' } });
    if (!response.ok) return { ok: false, error: `요청 실패 (${response.status})` };
    return { ok: true, data: await response.json() as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : '네트워크 요청에 실패했습니다.' };
  }
}

export interface V6IndexSeriesRow {
  readonly date: string;
  readonly close: number;
}

export interface V6IndexSeries {
  readonly schema_version?: string;
  readonly status?: string;
  readonly market?: string;
  readonly index_code?: string;
  readonly index_name?: string;
  readonly actual_start_date?: string;
  readonly actual_end_date?: string;
  readonly row_count?: number;
  readonly series?: readonly V6IndexSeriesRow[];
  readonly provider_package?: { readonly name?: string; readonly version?: string; readonly required_version?: string };
  readonly normalization_method?: string;
  readonly point_in_time?: { readonly constituents?: string; readonly limitation?: string; readonly index_levels_only?: boolean };
  readonly false_locks?: Record<string, boolean>;
  readonly claims?: Record<string, boolean>;
  readonly hashes?: { readonly raw_sha256?: string; readonly normalized_sha256?: string; readonly artifact_sha256?: string };
  readonly reason?: string;
}

export interface V6IndexRegimeMarket {
  readonly last_date?: string;
  readonly last_close?: number;
  readonly pct_vs_20d_mean?: number | null;
  readonly window_days?: number;
}


export interface V6ReportRevisionResult {
  readonly verdict?: string;
  readonly fresh_oos_state?: string;
  readonly training_state?: string;
  readonly reused_validation_state?: string;
  readonly failures?: readonly string[];
  readonly integrity?: string;
  readonly integrity_reasons?: readonly string[];
}

export interface V6ReportRevision {
  readonly revision_id?: string;
  readonly revision_ordinal?: number;
  readonly revision_event_sha256?: string;
  readonly parent_sha256?: string | null;
  readonly materialization_sha256?: string;
  readonly report_sha256?: string;
  readonly report_url?: string;
  readonly size_bytes?: number;
  readonly builder_version?: string;
  readonly result?: V6ReportRevisionResult;
  readonly failures?: readonly string[];
  readonly integrity?: string;
}

export interface V6ReportEntry {
  readonly dataset_run_id?: string;
  readonly train_run_id?: string;
  readonly schema?: string;
  readonly family?: string;
  readonly report_family?: string;
  readonly compatibility_state?: string;
  readonly availability?: string;
  readonly integrity?: string;
  readonly chain_integrity?: string;
  readonly integrity_reasons?: readonly string[];
  readonly chain_reasons?: readonly string[];
  readonly revisions?: readonly V6ReportRevision[];
  /** Compatibility alias for early catalog responses; revisions is authoritative. */
  readonly reports?: readonly V6ReportRevision[];
}

export interface V6Reports {
  readonly schema_version?: string;
  readonly schema?: string;
  readonly family?: string;
  readonly status?: string;
  readonly catalog_sha256?: string;
  readonly reports?: readonly V6ReportEntry[];
}

export interface V6RegistryRun {
  readonly dataset_run_id?: string;
  readonly train_run_id?: string;
  readonly trainer_version?: string;
  readonly verdict?: string;
  readonly test_state?: string;
  readonly generated_utc?: string;
  readonly has_report?: boolean;
}
export interface V6ProjectReportRun {
  readonly run_ref?: string;
  readonly dataset_run_id?: string;
  readonly train_run_id?: string;
  readonly verdict?: string;
  readonly test_state?: string;
  readonly comparison_state?: string;
}

export interface V6ProjectReportCycle {
  readonly cycle_id?: string;
  readonly order?: number;
  readonly title?: string;
  readonly hypothesis_delta?: string;
  readonly prereg_sha256?: string;
  readonly runs?: readonly V6ProjectReportRun[];
}

export interface V6ProjectReportEntry {
  readonly project_id?: string;
  readonly title?: string;
  readonly generated_utc?: string;
  readonly builder_version?: string;
  readonly report_sha256?: string;
  readonly size_bytes?: number;
  readonly cycle_count?: number;
  readonly run_count?: number;
  readonly verdicts?: readonly string[];
  readonly test_states?: readonly string[];
  readonly cycles?: readonly V6ProjectReportCycle[];
  readonly integrity?: string;
  readonly integrity_reasons?: readonly string[];
}

export interface V6ProjectReports {
  readonly schema_version?: string;
  readonly status?: string;
  readonly projects?: readonly V6ProjectReportEntry[];
}

export function v6ProjectReportHtmlUrl(projectId: string, download = false): string {
  return `/api/v6/project-report-html?project=${encodeURIComponent(projectId)}${download ? '&download=1' : ''}`;
}


export interface V6PreregEntry {
  readonly prereg_id?: string;
  readonly doc?: string;
  readonly status?: string;
  readonly frozen_utc?: string;
  readonly supersedes?: string | null;
  readonly family?: string | null;
  readonly sha256?: string;
  readonly runs?: readonly V6RegistryRun[];
  readonly run_count?: number;
  readonly verdicts?: readonly string[];
}

export interface V6ResultDoc {
  readonly doc?: string;
  readonly size_bytes?: number;
  readonly sha256?: string;
}

export interface V6ResearchRegistry {
  readonly schema_version?: string;
  readonly status?: string;
  readonly preregistrations?: readonly V6PreregEntry[];
  readonly result_docs?: readonly V6ResultDoc[];
}

export type V6NextDraftPresentation =
  | { readonly kind: 'draft'; readonly entry: V6PreregEntry }
  | { readonly kind: 'empty'; readonly frozenCount: number; readonly latestFrozenId: string | null };

export function newestDraftPreregistration(registry: V6ResearchRegistry | null | undefined): V6PreregEntry | null {
  return [...(registry?.preregistrations ?? [])]
    .filter((entry) => entry.status === 'DRAFT_NOT_FROZEN')
    .sort((left, right) => String(right.prereg_id ?? '').localeCompare(String(left.prereg_id ?? '')))[0] ?? null;
}

export function nextDraftPresentation(registry: V6ResearchRegistry | null | undefined): V6NextDraftPresentation {
  const draft = newestDraftPreregistration(registry);
  if (draft !== null) return { kind: 'draft', entry: draft };
  const frozen = [...(registry?.preregistrations ?? [])]
    .filter((entry) => entry.status === 'FROZEN')
    .sort((left, right) => String(right.frozen_utc ?? '').localeCompare(String(left.frozen_utc ?? '')));
  return {
    kind: 'empty',
    frozenCount: frozen.length,
    latestFrozenId: frozen[0]?.prereg_id ?? null,
  };
}

export interface V6ResearchDoc {
  readonly status?: string;
  readonly doc?: string;
  readonly format?: string;
  readonly sha256?: string;
  readonly content?: string;
  readonly reason?: string;
}

export function v6ReportHtmlUrl(dataset: string, train: string): string;
export function v6ReportHtmlUrl(dataset: string, train: string, download: boolean): string;
export function v6ReportHtmlUrl(dataset: string, train: string, reportSha256?: string, download?: boolean): string;
export function v6ReportHtmlUrl(
  dataset: string,
  train: string,
  reportSha256OrDownload?: string | boolean,
  download = false,
): string {
  const reportSha256 = typeof reportSha256OrDownload === 'string' ? reportSha256OrDownload : undefined;
  const shouldDownload = typeof reportSha256OrDownload === 'boolean' ? reportSha256OrDownload : download;
  return `/api/v6/report-html?dataset=${encodeURIComponent(dataset)}&train=${encodeURIComponent(train)}${reportSha256 === undefined ? '' : `&report_sha256=${encodeURIComponent(reportSha256)}`}${shouldDownload ? '&download=1' : ''}`;
}

export function v6ExactReportHtmlUrl(
  dataset: string | undefined,
  train: string | undefined,
  reportSha256: string | undefined,
  download = false,
): string | null {
  if (!dataset || !train || !reportSha256) return null;
  return v6ReportHtmlUrl(dataset, train, reportSha256, download);
}

export const initialReportSelection = (): null => null;

export const getV6Status = (): Promise<V6ApiResult<V6Status>> => getV6('/api/v6/status');
export const getV6ModelStatus = (): Promise<V6ApiResult<V6ModelStatus>> => getV6('/api/model-status');
export const getV6Universe = (limit: number): Promise<V6ApiResult<V6Universe>> =>
  getV6(`/api/v6/universe?limit=${encodeURIComponent(String(limit))}`);
export const getV6DataReadiness = (): Promise<V6ApiResult<V6DataReadiness>> => getV6('/api/v6/data-readiness');
export const getV6Experiment = (): Promise<V6ApiResult<V6Experiment>> => getV6('/api/v6/experiment');
let v6RunsInFlight: Promise<V6ApiResult<V6Runs>> | null = null;
export function getV6Runs(): Promise<V6ApiResult<V6Runs>> {
  if (v6RunsInFlight) return v6RunsInFlight;
  const request = getV6<V6Runs>('/api/v6/runs');
  v6RunsInFlight = request;
  const clear = (): void => { if (v6RunsInFlight === request) v6RunsInFlight = null; };
  void request.then(clear, clear);
  return request;
}
export const getV6RunDetail = (dataset: string, train: string): Promise<V6ApiResult<V6RunDetail>> =>
  getV6(`/api/v6/run-detail?dataset=${encodeURIComponent(dataset)}&train=${encodeURIComponent(train)}`);
export const getV6InsightSymbol = (code: string, maxPoints?: number): Promise<V6ApiResult<V6InsightSymbol>> =>
  getV6(`/api/v6/insight/symbol?code=${encodeURIComponent(code)}${maxPoints === undefined ? '' : `&max_points=${encodeURIComponent(String(maxPoints))}`}`);
export const getV6InsightFlow = (window?: number, limit?: number): Promise<V6ApiResult<V6InsightFlow>> =>
  getV6(`/api/v6/insight/flow${window === undefined && limit === undefined ? '' : `?${[window === undefined ? '' : `window=${encodeURIComponent(String(window))}`, limit === undefined ? '' : `limit=${encodeURIComponent(String(limit))}`].filter(Boolean).join('&')}`}`);
export const getV6InsightRegime = (): Promise<V6ApiResult<V6InsightRegime>> => getV6('/api/v6/insight/regime');
export const getV6IndexSeries = (market: 'KOSPI' | 'KOSDAQ'): Promise<V6ApiResult<V6IndexSeries>> =>
  getV6(`/api/v6/index-series?market=${encodeURIComponent(market)}`);
export const getV6Reports = (dataset?: string, train?: string): Promise<V6ApiResult<V6Reports>> =>
  getV6(dataset === undefined || train === undefined
    ? '/api/v6/reports'
    : `/api/v6/reports?dataset=${encodeURIComponent(dataset)}&train=${encodeURIComponent(train)}`);
export const getV6ProjectReports = (): Promise<V6ApiResult<V6ProjectReports>> => getV6('/api/v6/project-reports');
export const getV6ResearchRegistry = (): Promise<V6ApiResult<V6ResearchRegistry>> => getV6('/api/v6/research-registry');
export const getV6ResearchDoc = (doc: string): Promise<V6ApiResult<V6ResearchDoc>> =>
  getV6(`/api/v6/research-doc?doc=${encodeURIComponent(doc)}`);

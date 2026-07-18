export type V51ResearchRouteId = 'SOURCE_COVERAGE' | 'CAUSAL_PANEL' | 'ACCOUNTING' | 'EVALUATOR' | 'BENCHMARK_OVERLAY';
export type V51ReportRouteId = 'REPORTS' | 'REPORT_READ';
export type V51RouteId = V51ResearchRouteId | V51ReportRouteId;
export type V51Status = 'READY' | 'BLOCKED';
export type V51StatusReason =
  | 'READY'
  | 'BLOCKED_SOURCE_CONTRACT'
  | 'BLOCKED_ARTIFACT_UNAVAILABLE'
  | 'BLOCKED_SCHEMA_INVALID'
  | 'BLOCKED_INDEX_SERIES_SOURCE'
  | 'BLOCKED_PYKRX_ARTIFACT_MISSING'
  | 'BLOCKED_REPORT_NOT_FOUND';
export type V51ExactCostPercent = '0.00%' | '0.23%' | '0.46%';
export type V51DisplayPercent = `${number}%`;

export const V51_MAX_RESPONSE_BYTES = 1_000_000;

export const v51RouteDescriptors = {
  SOURCE_COVERAGE: {
    method: 'GET',
    path: '/api/daily-close-v51/source-coverage',
    root: 'sourceCoverageRoot',
    pathBindings: [] as const,
    query: ['run_id', 'artifact_id', 'revision'] as const,
  },
  CAUSAL_PANEL: {
    method: 'GET',
    path: '/api/daily-close-v51/causal-panel',
    root: 'causalPanelRoot',
    pathBindings: [] as const,
    query: ['run_id', 'artifact_id', 'revision'] as const,
  },
  ACCOUNTING: {
    method: 'GET',
    path: '/api/daily-close-v51/accounting',
    root: 'accountingRoot',
    pathBindings: [] as const,
    query: ['run_id', 'artifact_id', 'revision'] as const,
  },
  EVALUATOR: {
    method: 'GET',
    path: '/api/daily-close-v51/evaluator',
    root: 'evaluatorRoot',
    pathBindings: [] as const,
    query: ['run_id', 'artifact_id', 'revision'] as const,
  },
  BENCHMARK_OVERLAY: {
    method: 'GET',
    path: '/api/daily-close-v51/benchmark-overlay',
    root: 'benchmarkOverlayRoot',
    pathBindings: [] as const,
    query: ['run_id', 'artifact_id', 'revision'] as const,
  },
  REPORTS: {
    method: 'GET',
    path: '/api/daily-close-v51/reports',
    root: 'reportListRoot',
    pathBindings: [] as const,
    query: [] as const,
  },
  REPORT_READ: {
    method: 'GET',
    path: '/api/daily-close-v51/reports/{report_id}',
    root: 'reportReadRoot',
    pathBindings: ['report_id'] as const,
    query: [] as const,
  },
} as const satisfies Record<V51RouteId, {
  readonly method: 'GET';
  readonly path: string;
  readonly root: string;
  readonly pathBindings: readonly string[];
  readonly query: readonly string[];
}>;

export type V51RouteDescriptor = typeof v51RouteDescriptors[V51RouteId];

export interface V51FalseResearchLocks {
  readonly promotion_allowed: false;
  readonly model_build_allowed: false;
  readonly paper_forward_allowed: false;
  readonly live_broker_order_allowed: false;
  readonly profitability_claim_allowed: false;
  readonly go_summary_allowed: false;
}

export interface V51NoClaimFlags {
  readonly official_close_claim: false;
  readonly paper_forward_claim: false;
  readonly live_trading_claim: false;
  readonly broker_integration_claim: false;
  readonly profitability_claim: false;
  readonly go_readiness_claim: false;
}

export interface V51AccountingContract {
  readonly initial_capital_krw: 60000000;
  readonly slot_count: 10;
  readonly slot_budget_krw: 5000000;
  readonly max_invested_krw: 50000000;
  readonly reserve_cash_krw: 10000000;
  readonly reserve_cash_display_percent: '16.6667%';
  readonly max_target_investment_display_percent: '83.3333%';
  readonly shorting_allowed: false;
  readonly leverage_allowed: false;
  readonly duplicate_symbol_slots_allowed: false;
}

export interface V51CostEntry {
  readonly internal_id: 'base_23bp' | 'cost_00bp' | 'stress_46bp';
  readonly round_trip_cost_bp: 0 | 23 | 46;
  readonly display_percent: V51ExactCostPercent;
}

export interface V51CostSchedule {
  readonly primary: V51CostEntry & { readonly internal_id: 'base_23bp'; readonly round_trip_cost_bp: 23; readonly display_percent: '0.23%' };
  readonly zero_cost_control: V51CostEntry & { readonly internal_id: 'cost_00bp'; readonly round_trip_cost_bp: 0; readonly display_percent: '0.00%' };
  readonly stress_control: V51CostEntry & { readonly internal_id: 'stress_46bp'; readonly round_trip_cost_bp: 46; readonly display_percent: '0.46%' };
}

export interface V51HorizonContract {
  readonly primary_horizon: 'H1';
  readonly validation_horizons: readonly ['H3', 'H5'];
  readonly label_columns: readonly ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'];
}

export interface V51SourcePolicy {
  readonly daily_1520_source_schema: 'kronos_daily_1520_source.v1';
  readonly causal_panel_schema: 'kronos_daily_v51_causal_panel.v1';
  readonly causal_cutoff_kst: '15:20:00';
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
  readonly nearest_fallback_allowed: false;
  readonly full_day_daily_ohlcv_allowed: false;
  readonly price_volume_amount_approximation_allowed: false;
  readonly pykrx_offline_only: true;
  readonly naver_fallback_allowed: false;
  readonly network_required: false;
}

export interface V51OverlayPolicy {
  readonly allowed_index_provider: 'PYKRX';
  readonly offline_artifact_required: true;
  readonly naver_fallback_allowed: false;
  readonly forbidden_provider: 'NAVER';
  readonly missing_index_state: 'BLOCKED_INDEX_SERIES_SOURCE';
}

export interface V51Protocol<RouteId extends V51RouteId = V51RouteId> {
  readonly schema_version: 'kronos_v51_research_api.v1';
  readonly api_version: 'v5.1';
  readonly method: 'GET';
  readonly read_only: true;
  readonly route_id: RouteId;
  readonly route_path: typeof v51RouteDescriptors[RouteId]['path'];
  readonly causal_cutoff_kst: '15:20:00';
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
  readonly accounting: V51AccountingContract;
  readonly cost_schedule: V51CostSchedule;
  readonly horizon: V51HorizonContract;
  readonly source_policy: V51SourcePolicy;
  readonly overlay_policy: V51OverlayPolicy;
}

export interface V51SourceIdentity {
  readonly source_protocol: 'kronos_daily_1520_source.v1';
  readonly source_artifact_id: string;
  readonly source_sha256: string;
  readonly source_db_sha256: string;
  readonly generated_at: string;
  readonly causal_cutoff_kst: '15:20:00';
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
}

export interface V51StableArtifactIds {
  readonly source_coverage: string;
  readonly causal_panel: string;
  readonly accounting: string;
  readonly evaluator: string;
  readonly benchmark_overlay: string;
}

export interface V51RunIdentity {
  readonly run_id: string;
  readonly run_revision: number;
  readonly run_artifact_id: string;
  readonly source_sha256: string;
  readonly protocol_sha256: string;
  readonly stable_artifact_ids: V51StableArtifactIds;
}

export interface V51ArtifactIdentity {
  readonly artifact_id: string;
  readonly artifact_kind: 'source_coverage' | 'causal_panel' | 'accounting' | 'evaluator' | 'benchmark_overlay' | 'report_catalog' | 'report_content';
  readonly media_type: 'application/json; charset=utf-8';
  readonly byte_length: number;
  readonly sha256: string;
  readonly stable_id: true;
}

export type V51ResearchRoot<RouteId extends V51ResearchRouteId, PayloadName extends string, Payload> = {
  readonly route_id: RouteId;
  readonly status: V51Status;
  readonly status_reason: V51StatusReason;
  readonly protocol: V51Protocol<RouteId>;
  readonly source: V51SourceIdentity;
  readonly run: V51RunIdentity;
  readonly artifact: V51ArtifactIdentity;
  readonly locks: V51FalseResearchLocks;
  readonly claims: V51NoClaimFlags;
} & { readonly [Key in PayloadName]: Payload };

export interface V51SourceCoverage {
  readonly coverage_status: V51Status;
  readonly exact_1520_row_count: number;
  readonly symbol_count: number;
  readonly session_count: number;
  readonly first_valid_date: string | null;
  readonly last_valid_date: string | null;
  readonly sample_symbol: string;
  readonly sample_timestamp_yyyymmddhhmm: string;
  readonly volume_to_1520_status: 'NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY';
  readonly amount_to_1520_status: 'NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME';
  readonly missing_policy: 'MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK';
}

export interface V51PanelPreviewRow {
  readonly symbol: string;
  readonly session_date: string;
  readonly timestamp_kst: string;
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
  readonly entry_status: V51Status;
  readonly h1_status: V51Status;
  readonly h3_status: V51Status;
  readonly h5_status: V51Status;
}

export interface V51CausalPanelSummary {
  readonly panel_schema: 'kronos_daily_v51_causal_panel.v1';
  readonly row_count: number;
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
  readonly primary_horizon: 'H1';
  readonly validation_horizons: readonly ['H3', 'H5'];
  readonly label_columns: readonly ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'];
  readonly rows_preview: readonly V51PanelPreviewRow[];
}

export interface V51AccountingSummary {
  readonly accounting_status: V51Status;
  readonly contract: V51AccountingContract;
  readonly cost_schedule: V51CostSchedule;
  readonly economic_nav_krw: number;
  readonly cash_reserve_krw: number;
  readonly slots_used: number;
  readonly max_slots: 10;
  readonly internal_cost_id: 'base_23bp';
  readonly display_cost_percent: '0.23%';
}

export interface V51SplitStatuses {
  readonly train: V51Status;
  readonly validation: V51Status;
  readonly test: V51Status;
}

export interface V51EvaluationMetric {
  readonly metric_id: 'cumulative_return' | 'max_drawdown' | 'turnover' | 'trade_count';
  readonly split: 'train' | 'validation' | 'test';
  readonly horizon: 'H1' | 'H3' | 'H5';
  readonly internal_cost_id: 'base_23bp' | 'cost_00bp' | 'stress_46bp';
  readonly display_cost_percent: V51ExactCostPercent;
  readonly value: number;
  readonly display_percent: V51DisplayPercent;
}

export interface V51EvaluatorSummary {
  readonly evaluation_status: V51Status;
  readonly primary_horizon: 'H1';
  readonly validation_horizons: readonly ['H3', 'H5'];
  readonly cost_schedule: V51CostSchedule;
  readonly split_statuses: V51SplitStatuses;
  readonly metrics: readonly V51EvaluationMetric[];
}

export interface V51OverlaySeries {
  readonly series_id: 'KOSPI' | 'KOSDAQ' | 'RL_PORTFOLIO';
  readonly status: V51Status;
  readonly source_state: 'READY' | 'BLOCKED_INDEX_SERIES_SOURCE' | 'BLOCKED_PYKRX_ARTIFACT_MISSING';
  readonly provider: 'PYKRX' | null;
  readonly naver_used: false;
  readonly index_100: number | null;
  readonly cumulative_return_display_percent: V51DisplayPercent | null;
}

export interface V51BenchmarkOverlay {
  readonly overlay_status: V51Status;
  readonly provider_policy: V51OverlayPolicy;
  readonly common_start_index: 100;
  readonly series: readonly V51OverlaySeries[];
}

export interface V51ReportSource {
  readonly source_protocol: 'kronos_v51_report_catalog.v1';
  readonly catalog_artifact_id: string;
  readonly catalog_sha256: string;
  readonly generated_at: string;
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
}

export interface V51ReportSummary {
  readonly report_id: string;
  readonly title: string;
  readonly relative_path: string;
  readonly root_id: string;
  readonly media_type: 'text/markdown; charset=utf-8' | 'text/html; charset=utf-8';
  readonly byte_length: number;
  readonly sha256: string;
  readonly updated_at: string;
  readonly source_protocol: 'kronos_v51_report_catalog.v1';
  readonly price_basis: '15:20_bar_close_proxy';
  readonly official_close: false;
}

export interface V51ReportContent {
  readonly raw_text: string;
  readonly safe_html: string;
}

export type V51SourceCoverageRoot = V51ResearchRoot<'SOURCE_COVERAGE', 'source_coverage', V51SourceCoverage>;
export type V51CausalPanelRoot = V51ResearchRoot<'CAUSAL_PANEL', 'causal_panel', V51CausalPanelSummary>;
export type V51AccountingRoot = V51ResearchRoot<'ACCOUNTING', 'accounting', V51AccountingSummary>;
export type V51EvaluatorRoot = V51ResearchRoot<'EVALUATOR', 'evaluator', V51EvaluatorSummary>;
export type V51BenchmarkOverlayRoot = V51ResearchRoot<'BENCHMARK_OVERLAY', 'benchmark_overlay', V51BenchmarkOverlay>;

export interface V51ReportListRoot {
  readonly route_id: 'REPORTS';
  readonly status: V51Status;
  readonly status_reason: V51StatusReason;
  readonly protocol: V51Protocol<'REPORTS'>;
  readonly source: V51ReportSource;
  readonly locks: V51FalseResearchLocks;
  readonly claims: V51NoClaimFlags;
  readonly reports: readonly V51ReportSummary[];
}

export interface V51ReportReadRoot {
  readonly route_id: 'REPORT_READ';
  readonly status: V51Status;
  readonly status_reason: V51StatusReason;
  readonly protocol: V51Protocol<'REPORT_READ'>;
  readonly source: V51ReportSource;
  readonly locks: V51FalseResearchLocks;
  readonly claims: V51NoClaimFlags;
  readonly report: V51ReportSummary;
  readonly content: V51ReportContent;
}

export interface V51RouteRootMap {
  readonly SOURCE_COVERAGE: V51SourceCoverageRoot;
  readonly CAUSAL_PANEL: V51CausalPanelRoot;
  readonly ACCOUNTING: V51AccountingRoot;
  readonly EVALUATOR: V51EvaluatorRoot;
  readonly BENCHMARK_OVERLAY: V51BenchmarkOverlayRoot;
  readonly REPORTS: V51ReportListRoot;
  readonly REPORT_READ: V51ReportReadRoot;
}

export type V51RouteRoot = V51RouteRootMap[V51RouteId];

export interface V51ResearchQuery {
  readonly runId?: string;
  readonly artifactId?: string;
  readonly revision?: number;
}

export interface V51FetchOptions {
  readonly maxBytes?: number;
}

export class V51ApiError extends Error {
  readonly name = 'V51ApiError' as const;
  readonly routeId: V51RouteId;
  readonly code: 'HTTP_STATUS' | 'RESPONSE_TOO_LARGE' | 'INVALID_JSON' | 'SCHEMA_INVALID' | 'INVALID_REQUEST';
  readonly status: number | null;

  constructor(
    routeId: V51RouteId,
    code: V51ApiError['code'],
    message: string,
    status: number | null = null,
  ) {
    super(message);
    this.routeId = routeId;
    this.code = code;
    this.status = status;
    Object.freeze(this);
  }
}

const falseLockKeys = [
  'promotion_allowed',
  'model_build_allowed',
  'paper_forward_allowed',
  'live_broker_order_allowed',
  'profitability_claim_allowed',
  'go_summary_allowed',
] as const;

const noClaimKeys = [
  'official_close_claim',
  'paper_forward_claim',
  'live_trading_claim',
  'broker_integration_claim',
  'profitability_claim',
  'go_readiness_claim',
] as const;

const protocolKeys = [
  'schema_version',
  'api_version',
  'method',
  'read_only',
  'route_id',
  'route_path',
  'causal_cutoff_kst',
  'price_basis',
  'official_close',
  'accounting',
  'cost_schedule',
  'horizon',
  'source_policy',
  'overlay_policy',
] as const;

const researchTopKeys = {
  SOURCE_COVERAGE: ['route_id', 'status', 'status_reason', 'protocol', 'source', 'run', 'artifact', 'locks', 'claims', 'source_coverage'],
  CAUSAL_PANEL: ['route_id', 'status', 'status_reason', 'protocol', 'source', 'run', 'artifact', 'locks', 'claims', 'causal_panel'],
  ACCOUNTING: ['route_id', 'status', 'status_reason', 'protocol', 'source', 'run', 'artifact', 'locks', 'claims', 'accounting'],
  EVALUATOR: ['route_id', 'status', 'status_reason', 'protocol', 'source', 'run', 'artifact', 'locks', 'claims', 'evaluator'],
  BENCHMARK_OVERLAY: ['route_id', 'status', 'status_reason', 'protocol', 'source', 'run', 'artifact', 'locks', 'claims', 'benchmark_overlay'],
} as const satisfies Record<V51ResearchRouteId, readonly string[]>;

const artifactKindByRoute = {
  SOURCE_COVERAGE: 'source_coverage',
  CAUSAL_PANEL: 'causal_panel',
  ACCOUNTING: 'accounting',
  EVALUATOR: 'evaluator',
  BENCHMARK_OVERLAY: 'benchmark_overlay',
} as const satisfies Record<V51ResearchRouteId, V51ArtifactIdentity['artifact_kind']>;

const reportListTopKeys = ['route_id', 'status', 'status_reason', 'protocol', 'source', 'locks', 'claims', 'reports'] as const;
const reportReadTopKeys = ['route_id', 'status', 'status_reason', 'protocol', 'source', 'locks', 'claims', 'report', 'content'] as const;
const sha256Pattern = /^[0-9a-f]{64}$/u;
const artifactIdPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const runIdPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const reportPathPattern = /^(?![a-z]:)(?!\/)(?!.*[\\])(?!.*(?:^|\/)\.\.(?:\/|$))[a-z0-9._/-]+\.(?:md|html)$/u;
const safeReportHtmlPattern = /^<article data-kronos-report-html="escaped-pre"><pre>[^<]*<\/pre><\/article>$/u;
const unsafeReportHtmlPattern = /javascript\s*:/iu;
const rfc3339UtcPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const timestamp1520Pattern = /^\d{4}-\d{2}-\d{2}T15:20:00\+09:00$/u;
const compactTimestamp1520Pattern = /^\d{8}1520$/u;
const symbolPattern = /^[0-9]{6}$/u;
const displayPercentPattern = /^-?(?:0|[1-9]\d*)(?:\.\d{2,6})?%$/u;
const contentLengthPattern = /^(?:0|[1-9]\d*)$/u;
const exactCostPercentByInternalId = {
  base_23bp: '0.23%',
  cost_00bp: '0.00%',
  stress_46bp: '0.46%',
} as const;
const benchmarkSeriesOrder = ['KOSPI', 'KOSDAQ', 'RL_PORTFOLIO'] as const;
const responseTextEncoder = new TextEncoder();

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const observed = Object.keys(value);
  return observed.length === keys.length && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function isSafeInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isPositiveInt(value: unknown): value is number {
  return isSafeInt(value) && value >= 1;
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= Number.MAX_SAFE_INTEGER;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isStatus(value: unknown): value is V51Status {
  return value === 'READY' || value === 'BLOCKED';
}

function isStatusReason(value: unknown): value is V51StatusReason {
  return value === 'READY'
    || value === 'BLOCKED_SOURCE_CONTRACT'
    || value === 'BLOCKED_ARTIFACT_UNAVAILABLE'
    || value === 'BLOCKED_SCHEMA_INVALID'
    || value === 'BLOCKED_INDEX_SERIES_SOURCE'
    || value === 'BLOCKED_PYKRX_ARTIFACT_MISSING'
    || value === 'BLOCKED_REPORT_NOT_FOUND';
}

function isBlockedStatusReason(value: unknown): value is Exclude<V51StatusReason, 'READY'> {
  return typeof value === 'string' && value.startsWith('BLOCKED_') && isStatusReason(value);
}

function hasStatusReasonCoherence(status: unknown, reason: unknown): boolean {
  return (status === 'READY' && reason === 'READY') || (status === 'BLOCKED' && isBlockedStatusReason(reason));
}

function isExactCostInternalId(value: unknown): value is keyof typeof exactCostPercentByInternalId {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(exactCostPercentByInternalId, value);
}

function hasExactCostPercentPair(internalId: unknown, displayPercent: unknown): boolean {
  return isExactCostInternalId(internalId) && displayPercent === exactCostPercentByInternalId[internalId];
}

function hasStatusSourceStateCoherence(status: unknown, sourceState: unknown): boolean {
  return (status === 'READY' && sourceState === 'READY')
    || (status === 'BLOCKED' && typeof sourceState === 'string' && sourceState.startsWith('BLOCKED_'));
}

function hasBenchmarkSeriesOrder(value: readonly unknown[]): boolean {
  return value.length === benchmarkSeriesOrder.length
    && benchmarkSeriesOrder.every((seriesId, index) => {
      const item = value[index];
      return isRecord(item) && item.series_id === seriesId;
    });
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && sha256Pattern.test(value);
}

function isArtifactId(value: unknown): value is string {
  return typeof value === 'string' && artifactIdPattern.test(value);
}

function isRunId(value: unknown): value is string {
  return typeof value === 'string' && runIdPattern.test(value);
}

function isRfc3339Utc(value: unknown): value is string {
  return typeof value === 'string' && rfc3339UtcPattern.test(value);
}

function isDateOrNull(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && datePattern.test(value));
}

function isExactStringArray(value: unknown, expected: readonly string[]): boolean {
  return Array.isArray(value) && value.length === expected.length && expected.every((item, index) => value[index] === item);
}

function isFalseFlags(value: unknown, keys: readonly string[]): boolean {
  return isRecord(value) && hasExactKeys(value, keys) && keys.every((key) => value[key] === false);
}

function isAccountingContract(value: unknown): value is V51AccountingContract {
  return isRecord(value)
    && hasExactKeys(value, [
      'initial_capital_krw',
      'slot_count',
      'slot_budget_krw',
      'max_invested_krw',
      'reserve_cash_krw',
      'reserve_cash_display_percent',
      'max_target_investment_display_percent',
      'shorting_allowed',
      'leverage_allowed',
      'duplicate_symbol_slots_allowed',
    ])
    && value.initial_capital_krw === 60000000
    && value.slot_count === 10
    && value.slot_budget_krw === 5000000
    && value.max_invested_krw === 50000000
    && value.reserve_cash_krw === 10000000
    && value.reserve_cash_display_percent === '16.6667%'
    && value.max_target_investment_display_percent === '83.3333%'
    && value.shorting_allowed === false
    && value.leverage_allowed === false
    && value.duplicate_symbol_slots_allowed === false;
}

function isCostEntry(value: unknown, internalId: string, bp: number, percent: string): boolean {
  return isRecord(value)
    && hasExactKeys(value, ['internal_id', 'round_trip_cost_bp', 'display_percent'])
    && value.internal_id === internalId
    && value.round_trip_cost_bp === bp
    && value.display_percent === percent;
}

function isCostSchedule(value: unknown): value is V51CostSchedule {
  return isRecord(value)
    && hasExactKeys(value, ['primary', 'zero_cost_control', 'stress_control'])
    && isCostEntry(value.primary, 'base_23bp', 23, '0.23%')
    && isCostEntry(value.zero_cost_control, 'cost_00bp', 0, '0.00%')
    && isCostEntry(value.stress_control, 'stress_46bp', 46, '0.46%');
}

function isHorizonContract(value: unknown): value is V51HorizonContract {
  return isRecord(value)
    && hasExactKeys(value, ['primary_horizon', 'validation_horizons', 'label_columns'])
    && value.primary_horizon === 'H1'
    && isExactStringArray(value.validation_horizons, ['H3', 'H5'])
    && isExactStringArray(value.label_columns, ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy']);
}

function isSourcePolicy(value: unknown): value is V51SourcePolicy {
  return isRecord(value)
    && hasExactKeys(value, [
      'daily_1520_source_schema',
      'causal_panel_schema',
      'causal_cutoff_kst',
      'price_basis',
      'official_close',
      'nearest_fallback_allowed',
      'full_day_daily_ohlcv_allowed',
      'price_volume_amount_approximation_allowed',
      'pykrx_offline_only',
      'naver_fallback_allowed',
      'network_required',
    ])
    && value.daily_1520_source_schema === 'kronos_daily_1520_source.v1'
    && value.causal_panel_schema === 'kronos_daily_v51_causal_panel.v1'
    && value.causal_cutoff_kst === '15:20:00'
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false
    && value.nearest_fallback_allowed === false
    && value.full_day_daily_ohlcv_allowed === false
    && value.price_volume_amount_approximation_allowed === false
    && value.pykrx_offline_only === true
    && value.naver_fallback_allowed === false
    && value.network_required === false;
}

function isOverlayPolicy(value: unknown): value is V51OverlayPolicy {
  return isRecord(value)
    && hasExactKeys(value, ['allowed_index_provider', 'offline_artifact_required', 'naver_fallback_allowed', 'forbidden_provider', 'missing_index_state'])
    && value.allowed_index_provider === 'PYKRX'
    && value.offline_artifact_required === true
    && value.naver_fallback_allowed === false
    && value.forbidden_provider === 'NAVER'
    && value.missing_index_state === 'BLOCKED_INDEX_SERIES_SOURCE';
}

function isProtocol(routeId: V51RouteId, value: unknown): value is V51Protocol {
  const descriptor = v51RouteDescriptors[routeId];
  return isRecord(value)
    && hasExactKeys(value, protocolKeys)
    && value.schema_version === 'kronos_v51_research_api.v1'
    && value.api_version === 'v5.1'
    && value.method === 'GET'
    && value.read_only === true
    && value.route_id === routeId
    && value.route_path === descriptor.path
    && value.causal_cutoff_kst === '15:20:00'
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false
    && isAccountingContract(value.accounting)
    && isCostSchedule(value.cost_schedule)
    && isHorizonContract(value.horizon)
    && isSourcePolicy(value.source_policy)
    && isOverlayPolicy(value.overlay_policy);
}

function isSourceIdentity(value: unknown): value is V51SourceIdentity {
  return isRecord(value)
    && hasExactKeys(value, ['source_protocol', 'source_artifact_id', 'source_sha256', 'source_db_sha256', 'generated_at', 'causal_cutoff_kst', 'price_basis', 'official_close'])
    && value.source_protocol === 'kronos_daily_1520_source.v1'
    && isArtifactId(value.source_artifact_id)
    && isSha256(value.source_sha256)
    && isSha256(value.source_db_sha256)
    && isRfc3339Utc(value.generated_at)
    && value.causal_cutoff_kst === '15:20:00'
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false;
}

function isStableArtifactIds(value: unknown): value is V51StableArtifactIds {
  return isRecord(value)
    && hasExactKeys(value, ['source_coverage', 'causal_panel', 'accounting', 'evaluator', 'benchmark_overlay'])
    && isArtifactId(value.source_coverage)
    && isArtifactId(value.causal_panel)
    && isArtifactId(value.accounting)
    && isArtifactId(value.evaluator)
    && isArtifactId(value.benchmark_overlay);
}

function isRunIdentity(value: unknown): value is V51RunIdentity {
  return isRecord(value)
    && hasExactKeys(value, ['run_id', 'run_revision', 'run_artifact_id', 'source_sha256', 'protocol_sha256', 'stable_artifact_ids'])
    && isRunId(value.run_id)
    && isPositiveInt(value.run_revision)
    && isArtifactId(value.run_artifact_id)
    && isSha256(value.source_sha256)
    && isSha256(value.protocol_sha256)
    && isStableArtifactIds(value.stable_artifact_ids);
}

function isArtifactIdentity(kind: V51ArtifactIdentity['artifact_kind'], value: unknown): value is V51ArtifactIdentity {
  return isRecord(value)
    && hasExactKeys(value, ['artifact_id', 'artifact_kind', 'media_type', 'byte_length', 'sha256', 'stable_id'])
    && isArtifactId(value.artifact_id)
    && value.artifact_kind === kind
    && value.media_type === 'application/json; charset=utf-8'
    && isSafeInt(value.byte_length)
    && isSha256(value.sha256)
    && value.stable_id === true;
}

function isSourceCoverage(value: unknown): value is V51SourceCoverage {
  return isRecord(value)
    && hasExactKeys(value, [
      'coverage_status',
      'exact_1520_row_count',
      'symbol_count',
      'session_count',
      'first_valid_date',
      'last_valid_date',
      'sample_symbol',
      'sample_timestamp_yyyymmddhhmm',
      'volume_to_1520_status',
      'amount_to_1520_status',
      'missing_policy',
    ])
    && isStatus(value.coverage_status)
    && isSafeInt(value.exact_1520_row_count)
    && isSafeInt(value.symbol_count)
    && isSafeInt(value.session_count)
    && isDateOrNull(value.first_valid_date)
    && isDateOrNull(value.last_valid_date)
    && typeof value.sample_symbol === 'string'
    && symbolPattern.test(value.sample_symbol)
    && typeof value.sample_timestamp_yyyymmddhhmm === 'string'
    && compactTimestamp1520Pattern.test(value.sample_timestamp_yyyymmddhhmm)
    && value.volume_to_1520_status === 'NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY'
    && value.amount_to_1520_status === 'NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME'
    && value.missing_policy === 'MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK';
}

function isPanelPreviewRow(value: unknown): value is V51PanelPreviewRow {
  return isRecord(value)
    && hasExactKeys(value, ['symbol', 'session_date', 'timestamp_kst', 'price_basis', 'official_close', 'entry_status', 'h1_status', 'h3_status', 'h5_status'])
    && typeof value.symbol === 'string'
    && symbolPattern.test(value.symbol)
    && typeof value.session_date === 'string'
    && datePattern.test(value.session_date)
    && typeof value.timestamp_kst === 'string'
    && timestamp1520Pattern.test(value.timestamp_kst)
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false
    && isStatus(value.entry_status)
    && isStatus(value.h1_status)
    && isStatus(value.h3_status)
    && isStatus(value.h5_status);
}

function isCausalPanelSummary(value: unknown): value is V51CausalPanelSummary {
  return isRecord(value)
    && hasExactKeys(value, ['panel_schema', 'row_count', 'price_basis', 'official_close', 'primary_horizon', 'validation_horizons', 'label_columns', 'rows_preview'])
    && value.panel_schema === 'kronos_daily_v51_causal_panel.v1'
    && isSafeInt(value.row_count)
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false
    && value.primary_horizon === 'H1'
    && isExactStringArray(value.validation_horizons, ['H3', 'H5'])
    && isExactStringArray(value.label_columns, ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'])
    && Array.isArray(value.rows_preview)
    && value.rows_preview.length <= 20
    && value.rows_preview.every(isPanelPreviewRow);
}

function isAccountingSummary(value: unknown): value is V51AccountingSummary {
  return isRecord(value)
    && hasExactKeys(value, ['accounting_status', 'contract', 'cost_schedule', 'economic_nav_krw', 'cash_reserve_krw', 'slots_used', 'max_slots', 'internal_cost_id', 'display_cost_percent'])
    && isStatus(value.accounting_status)
    && isAccountingContract(value.contract)
    && isCostSchedule(value.cost_schedule)
    && isNonNegativeNumber(value.economic_nav_krw)
    && isNonNegativeNumber(value.cash_reserve_krw)
    && isNonNegativeNumber(value.slots_used)
    && Number.isInteger(value.slots_used)
    && value.slots_used <= 10
    && value.max_slots === 10
    && value.internal_cost_id === 'base_23bp'
    && value.display_cost_percent === '0.23%';
}

function isSplitStatuses(value: unknown): value is V51SplitStatuses {
  return isRecord(value)
    && hasExactKeys(value, ['train', 'validation', 'test'])
    && isStatus(value.train)
    && isStatus(value.validation)
    && isStatus(value.test);
}

function isEvaluationMetric(value: unknown): value is V51EvaluationMetric {
  return isRecord(value)
    && hasExactKeys(value, ['metric_id', 'split', 'horizon', 'internal_cost_id', 'display_cost_percent', 'value', 'display_percent'])
    && (value.metric_id === 'cumulative_return' || value.metric_id === 'max_drawdown' || value.metric_id === 'turnover' || value.metric_id === 'trade_count')
    && (value.split === 'train' || value.split === 'validation' || value.split === 'test')
    && (value.horizon === 'H1' || value.horizon === 'H3' || value.horizon === 'H5')
    && hasExactCostPercentPair(value.internal_cost_id, value.display_cost_percent)
    && isFiniteNumber(value.value)
    && typeof value.display_percent === 'string'
    && displayPercentPattern.test(value.display_percent);
}

function isEvaluatorSummary(value: unknown): value is V51EvaluatorSummary {
  return isRecord(value)
    && hasExactKeys(value, ['evaluation_status', 'primary_horizon', 'validation_horizons', 'cost_schedule', 'split_statuses', 'metrics'])
    && isStatus(value.evaluation_status)
    && value.primary_horizon === 'H1'
    && isExactStringArray(value.validation_horizons, ['H3', 'H5'])
    && isCostSchedule(value.cost_schedule)
    && isSplitStatuses(value.split_statuses)
    && Array.isArray(value.metrics)
    && value.metrics.every(isEvaluationMetric);
}

function isOverlaySeries(value: unknown): value is V51OverlaySeries {
  return isRecord(value)
    && hasExactKeys(value, ['series_id', 'status', 'source_state', 'provider', 'naver_used', 'index_100', 'cumulative_return_display_percent'])
    && (value.series_id === 'RL_PORTFOLIO' || value.series_id === 'KOSPI' || value.series_id === 'KOSDAQ')
    && isStatus(value.status)
    && (value.source_state === 'READY' || value.source_state === 'BLOCKED_INDEX_SERIES_SOURCE' || value.source_state === 'BLOCKED_PYKRX_ARTIFACT_MISSING')
    && hasStatusSourceStateCoherence(value.status, value.source_state)
    && (value.provider === 'PYKRX' || value.provider === null)
    && value.naver_used === false
    && (value.index_100 === null || isNonNegativeNumber(value.index_100))
    && (value.cumulative_return_display_percent === null || (typeof value.cumulative_return_display_percent === 'string' && displayPercentPattern.test(value.cumulative_return_display_percent)));
}

function isBenchmarkOverlay(value: unknown): value is V51BenchmarkOverlay {
  return isRecord(value)
    && hasExactKeys(value, ['overlay_status', 'provider_policy', 'common_start_index', 'series'])
    && isStatus(value.overlay_status)
    && isOverlayPolicy(value.provider_policy)
    && value.common_start_index === 100
    && Array.isArray(value.series)
    && hasBenchmarkSeriesOrder(value.series)
    && value.series.every(isOverlaySeries);
}

function isReportSource(value: unknown): value is V51ReportSource {
  return isRecord(value)
    && hasExactKeys(value, ['source_protocol', 'catalog_artifact_id', 'catalog_sha256', 'generated_at', 'price_basis', 'official_close'])
    && value.source_protocol === 'kronos_v51_report_catalog.v1'
    && isArtifactId(value.catalog_artifact_id)
    && isSha256(value.catalog_sha256)
    && isRfc3339Utc(value.generated_at)
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false;
}

function isReportSummary(value: unknown): value is V51ReportSummary {
  return isRecord(value)
    && hasExactKeys(value, ['report_id', 'title', 'relative_path', 'root_id', 'media_type', 'byte_length', 'sha256', 'updated_at', 'source_protocol', 'price_basis', 'official_close'])
    && isArtifactId(value.report_id)
    && typeof value.title === 'string'
    && value.title.length > 0
    && value.title.length <= 200
    && typeof value.relative_path === 'string'
    && value.relative_path.length <= 512
    && reportPathPattern.test(value.relative_path)
    && typeof value.root_id === 'string'
    && /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/u.test(value.root_id)
    && (value.media_type === 'text/markdown; charset=utf-8' || value.media_type === 'text/html; charset=utf-8')
    && isSafeInt(value.byte_length)
    && isSha256(value.sha256)
    && isRfc3339Utc(value.updated_at)
    && value.source_protocol === 'kronos_v51_report_catalog.v1'
    && value.price_basis === '15:20_bar_close_proxy'
    && value.official_close === false;
}

function isReportContent(value: unknown): value is V51ReportContent {
  return isRecord(value)
    && hasExactKeys(value, ['raw_text', 'safe_html'])
    && typeof value.raw_text === 'string'
    && typeof value.safe_html === 'string'
    && safeReportHtmlPattern.test(value.safe_html)
    && !unsafeReportHtmlPattern.test(value.safe_html);
}

function researchBodyStatusMatches(routeId: V51ResearchRouteId, status: unknown, payload: unknown): boolean {
  if (routeId === 'SOURCE_COVERAGE') return isSourceCoverage(payload) && payload.coverage_status === status;
  if (routeId === 'ACCOUNTING') return isAccountingSummary(payload) && payload.accounting_status === status;
  if (routeId === 'EVALUATOR') return isEvaluatorSummary(payload) && payload.evaluation_status === status;
  if (routeId === 'BENCHMARK_OVERLAY') return isBenchmarkOverlay(payload) && payload.overlay_status === status;
  return true;
}

function isResearchIdentityCoherent(routeId: V51ResearchRouteId, value: Record<string, unknown>): boolean {
  const stableKey = artifactKindByRoute[routeId];
  const source = value.source;
  const run = value.run;
  const artifact = value.artifact;
  if (!isRecord(source) || !isRecord(run) || !isRecord(artifact)) {
    return false;
  }
  const stableArtifactIds = run.stable_artifact_ids;
  if (!isRecord(stableArtifactIds)) {
    return false;
  }
  return source.source_sha256 === run.source_sha256
    && source.source_artifact_id === artifact.artifact_id
    && artifact.artifact_id === stableArtifactIds[stableKey];
}

function validateResearchRoot(routeId: V51ResearchRouteId, value: Record<string, unknown>): boolean {
  const payloadName = researchTopKeys[routeId][researchTopKeys[routeId].length - 1] as keyof typeof value;
  const payload = value[payloadName];
  const payloadValid = routeId === 'SOURCE_COVERAGE'
    ? isSourceCoverage(payload)
    : routeId === 'CAUSAL_PANEL'
      ? isCausalPanelSummary(payload)
      : routeId === 'ACCOUNTING'
        ? isAccountingSummary(payload)
        : routeId === 'EVALUATOR'
          ? isEvaluatorSummary(payload)
          : isBenchmarkOverlay(payload);

  return hasExactKeys(value, researchTopKeys[routeId])
    && value.route_id === routeId
    && isStatus(value.status)
    && isStatusReason(value.status_reason)
    && hasStatusReasonCoherence(value.status, value.status_reason)
    && isProtocol(routeId, value.protocol)
    && isSourceIdentity(value.source)
    && isRunIdentity(value.run)
    && isArtifactIdentity(artifactKindByRoute[routeId], value.artifact)
    && isResearchIdentityCoherent(routeId, value)
    && isFalseFlags(value.locks, falseLockKeys)
    && isFalseFlags(value.claims, noClaimKeys)
    && payloadValid
    && researchBodyStatusMatches(routeId, value.status, payload);
}

export function isV51RouteRoot<K extends V51RouteId>(routeId: K, value: unknown): value is V51RouteRootMap[K] {
  if (!isRecord(value)) return false;
  if (routeId === 'REPORTS') {
    return hasExactKeys(value, reportListTopKeys)
      && value.route_id === 'REPORTS'
      && isStatus(value.status)
      && isStatusReason(value.status_reason)
      && hasStatusReasonCoherence(value.status, value.status_reason)
      && isProtocol('REPORTS', value.protocol)
      && isReportSource(value.source)
      && isFalseFlags(value.locks, falseLockKeys)
      && isFalseFlags(value.claims, noClaimKeys)
      && Array.isArray(value.reports)
      && value.reports.every(isReportSummary);
  }
  if (routeId === 'REPORT_READ') {
    return hasExactKeys(value, reportReadTopKeys)
      && value.route_id === 'REPORT_READ'
      && isStatus(value.status)
      && isStatusReason(value.status_reason)
      && hasStatusReasonCoherence(value.status, value.status_reason)
      && isProtocol('REPORT_READ', value.protocol)
      && isReportSource(value.source)
      && isFalseFlags(value.locks, falseLockKeys)
      && isFalseFlags(value.claims, noClaimKeys)
      && isReportSummary(value.report)
      && isReportContent(value.content);
  }
  return validateResearchRoot(routeId, value);
}

function freezeV51Payload<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) {
      freezeV51Payload(child);
    }
    Object.freeze(value);
  }
  return value;
}

function validateQueryId(routeId: V51RouteId, name: string, value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  if (name === 'run_id' && !isRunId(value)) {
    throw new V51ApiError(routeId, 'INVALID_REQUEST', `invalid ${name}`);
  }
  if (name === 'artifact_id' && !isArtifactId(value)) {
    throw new V51ApiError(routeId, 'INVALID_REQUEST', `invalid ${name}`);
  }
  return value;
}

function v51Search(routeId: V51ResearchRouteId, query: V51ResearchQuery | undefined): string {
  if (query === undefined) return '';
  const params = new URLSearchParams();
  const runId = validateQueryId(routeId, 'run_id', query.runId);
  const artifactId = validateQueryId(routeId, 'artifact_id', query.artifactId);
  if (runId !== undefined) params.set('run_id', runId);
  if (artifactId !== undefined) params.set('artifact_id', artifactId);
  if (query.revision !== undefined) {
    if (!Number.isSafeInteger(query.revision) || query.revision < 1) {
      throw new V51ApiError(routeId, 'INVALID_REQUEST', 'invalid revision');
    }
    params.set('revision', String(query.revision));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

function v51Path(routeId: V51RouteId, pathParams: Readonly<Record<string, string>> = {}): string {
  const descriptor = v51RouteDescriptors[routeId];
  let path: string = descriptor.path;
  for (const name of descriptor.pathBindings as readonly string[]) {
    const value = pathParams[name];
    if (!value || (name === 'report_id' && !isArtifactId(value))) {
      throw new V51ApiError(routeId, 'INVALID_REQUEST', `invalid path binding ${name}`);
    }
    path = path.replace(`{${name}}`, encodeURIComponent(value));
  }
  return path;
}

function enforceV51ContentLength(routeId: V51RouteId, response: Response, maxBytes: number): void {
  const rawContentLength = response.headers?.get?.('Content-Length');
  if (rawContentLength === null || rawContentLength === undefined) return;
  const contentLength = rawContentLength.trim();
  if (!contentLengthPattern.test(contentLength)) {
    throw new V51ApiError(routeId, 'RESPONSE_TOO_LARGE', 'V5.1 response had invalid Content-Length', response.status);
  }
  const declaredBytes = Number(contentLength);
  if (!Number.isSafeInteger(declaredBytes) || declaredBytes > maxBytes) {
    throw new V51ApiError(routeId, 'RESPONSE_TOO_LARGE', 'V5.1 response exceeded closed size guard', response.status);
  }
}

async function readV51Json<K extends V51RouteId>(
  routeId: K,
  response: Response,
  maxBytes: number,
): Promise<V51RouteRootMap[K]> {
  if (!response.ok) {
    throw new V51ApiError(routeId, 'HTTP_STATUS', 'V5.1 request failed', response.status);
  }
  enforceV51ContentLength(routeId, response, maxBytes);
  const body = await response.text();
  if (responseTextEncoder.encode(body).byteLength > maxBytes) {
    throw new V51ApiError(routeId, 'RESPONSE_TOO_LARGE', 'V5.1 response exceeded closed size guard', response.status);
  }
  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    throw new V51ApiError(routeId, 'INVALID_JSON', 'V5.1 response was not valid JSON', response.status);
  }
  if (!isV51RouteRoot(routeId, payload)) {
    throw new V51ApiError(routeId, 'SCHEMA_INVALID', 'V5.1 response failed schema guard', response.status);
  }
  return freezeV51Payload(payload) as V51RouteRootMap[K];
}

async function fetchV51<K extends V51RouteId>(
  routeId: K,
  pathParams: Readonly<Record<string, string>> = {},
  query: V51ResearchQuery | undefined = undefined,
  options: V51FetchOptions = {},
): Promise<V51RouteRootMap[K]> {
  const descriptor = v51RouteDescriptors[routeId];
  const maxBytes = options.maxBytes ?? V51_MAX_RESPONSE_BYTES;
  if (!isSafeInt(maxBytes)) {
    throw new V51ApiError(routeId, 'INVALID_REQUEST', 'invalid maxBytes');
  }
  const path = v51Path(routeId, pathParams);
  const search = query && routeId !== 'REPORTS' && routeId !== 'REPORT_READ'
    ? v51Search(routeId as V51ResearchRouteId, query)
    : '';
  const response = await fetch(`${path}${search}`, { method: descriptor.method });
  return readV51Json(routeId, response, maxBytes);
}

export function fetchV51SourceCoverage(query?: V51ResearchQuery, options?: V51FetchOptions): Promise<V51SourceCoverageRoot> {
  return fetchV51('SOURCE_COVERAGE', {}, query, options);
}

export function fetchV51CausalPanel(query?: V51ResearchQuery, options?: V51FetchOptions): Promise<V51CausalPanelRoot> {
  return fetchV51('CAUSAL_PANEL', {}, query, options);
}

export function fetchV51Accounting(query?: V51ResearchQuery, options?: V51FetchOptions): Promise<V51AccountingRoot> {
  return fetchV51('ACCOUNTING', {}, query, options);
}

export function fetchV51Evaluator(query?: V51ResearchQuery, options?: V51FetchOptions): Promise<V51EvaluatorRoot> {
  return fetchV51('EVALUATOR', {}, query, options);
}

export function fetchV51BenchmarkOverlay(query?: V51ResearchQuery, options?: V51FetchOptions): Promise<V51BenchmarkOverlayRoot> {
  return fetchV51('BENCHMARK_OVERLAY', {}, query, options);
}

export function fetchV51Reports(options?: V51FetchOptions): Promise<V51ReportListRoot> {
  return fetchV51('REPORTS', {}, undefined, options);
}

export function fetchV51Report(reportId: string, options?: V51FetchOptions): Promise<V51ReportReadRoot> {
  return fetchV51('REPORT_READ', { report_id: reportId }, undefined, options);
}

export const v51Api = {
  sourceCoverage: fetchV51SourceCoverage,
  causalPanel: fetchV51CausalPanel,
  accounting: fetchV51Accounting,
  evaluator: fetchV51Evaluator,
  benchmarkOverlay: fetchV51BenchmarkOverlay,
  listReports: fetchV51Reports,
  readReport: fetchV51Report,
} as const;

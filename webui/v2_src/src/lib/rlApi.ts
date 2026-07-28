import type { ErrorRoot, V5DeepReadonly, V5RouteId } from './generated/kronosRlApiV2';
import {
  validateErrorRoot,
  v5RouteDescriptors,
  type V5RouteRootMap,
} from './generated/kronosRlApiV2.validators';
import { validateV5Semantic, V5SemanticError } from './generated/kronosRlApiV2.semantic';
import type { RunLifecycle } from './runLifecycle';
import { sanitizeV5SchemaDiagnostics, V5SchemaValidationError } from './v5SchemaValidationError';
import { fetchJson } from './http';

export type RlArtifactType =
  | 'contextual_bandit'
  | 'sb3_smoke'
  | 'cost_gate'
  | 'baseline'
  | 'episode_manifest'
  | 'opening_30m_rl_workflow'
  | 'portfolio_paper'
  | 'orderbook_rl_readiness'
  | string;

export type JsonScalar = string | number | boolean | null;
export type JsonValue = JsonScalar | readonly JsonValue[] | { readonly [key: string]: JsonValue };
export type JsonObject = { readonly [key: string]: JsonValue };
export type RlTableRow = JsonObject;

export interface RlRiskPolicySummary {
  readonly strategy?: string;
  readonly primary_filter?: string;
  readonly per_trade_fraction_pct?: number;
  readonly max_concurrent?: number;
  readonly max_deployed_fraction_pct?: number;
  readonly daily_loss_limit_pct?: number;
  readonly cost_bps?: number;
  readonly tp_pct?: number;
  readonly sl_pct?: number;
  readonly risk_unit_account_pct?: number;
}

export interface RlStrategyContext {
  readonly line?: 'rule_mainline' | 'rl_experiment' | 'evaluation' | 'unknown' | string;
  readonly label?: string;
  readonly primary_baseline?: string;
  readonly is_reinforcement_learning?: boolean;
  readonly is_environment_readiness?: boolean;
  readonly is_live_ready?: boolean;
  readonly is_profit_model?: boolean;
  readonly guardrail?: string;
  readonly readiness_status?: string | null;
  readonly risk_policy_summary?: RlRiskPolicySummary;
}

export interface RlRunRecord {
  readonly name: string;
  readonly artifact_type: RlArtifactType;
  readonly modified_at?: string;
  readonly summary?: JsonObject;
  readonly strategy_context?: RlStrategyContext;
  readonly policies?: readonly string[];
  readonly lifecycle?: RunLifecycle;
}

export interface RlRunDetail extends RlRunRecord {
  readonly artifacts?: readonly {
    readonly name: string;
    readonly suffix?: string;
    readonly size_bytes?: number;
    readonly modified_at?: string;
  }[];
  readonly detail?: JsonObject;
  readonly model?: {
    readonly model_type?: string;
    readonly feature_columns?: readonly string[];
    readonly train_summary?: JsonObject;
  };
}

export interface RlRunsResponse { readonly runs: readonly RlRunRecord[] }
export interface RlTableResponse {
  readonly run?: string;
  readonly artifact_type?: string;
  readonly table?: string;
  readonly policy?: string | null;
  readonly source_file?: string | null;
  readonly rows: readonly RlTableRow[];
  readonly row_count?: number;
  readonly truncated?: boolean;
  readonly policies?: readonly string[];
  readonly message?: string;
}
export interface RlCostGateResponse {
  readonly run?: string;
  readonly artifact_type?: string;
  readonly summary?: JsonObject;
  readonly gate?: RlTableResponse;
  readonly scenario?: RlTableResponse;
  readonly rolling?: RlTableResponse;
}
export interface RlProgressCriterion { readonly label: string; readonly passed: boolean; readonly evidence?: string }
export interface RlProgressPage {
  readonly page: string;
  readonly progress_pct: number;
  readonly status: 'complete' | 'in_progress' | string;
  readonly criteria?: readonly RlProgressCriterion[];
}
export interface RlProgressResponse {
  readonly mode?: string;
  readonly overall_progress_pct: number;
  readonly status: 'complete' | 'in_progress' | string;
  readonly pages: readonly RlProgressPage[];
  readonly evidence?: JsonObject;
}
export interface RlFactoryRunRecord {
  readonly run_id: string;
  readonly split_hash?: string | null;
  readonly cost_bps?: number | null;
  readonly seed?: number | null;
  readonly stage?: string | null;
  readonly parent_run?: string | null;
  readonly prereg_doc?: string | null;
  readonly status?: string | null;
  readonly verdict?: string | null;
  readonly created_utc?: string | null;
  readonly updated_utc?: string | null;
}
export interface RlFactoryQueueResponse {
  readonly available: boolean;
  readonly reason?: string;
  readonly guardrail?: string;
  readonly registry_path?: string;
  readonly counts_by_status?: Readonly<Record<string, number>>;
  readonly status_counts?: Readonly<Record<string, number>>;
  readonly latest_runs?: readonly RlFactoryRunRecord[];
  readonly read_only_dashboard_note?: string;
}
export interface RlFactoryLaneRun {
  readonly run: string;
  readonly verdict?: string | null;
  readonly mode?: string | null;
  readonly strategy_label?: string | null;
  readonly fill_mode?: string | null;
  readonly cost_bps?: number | null;
  readonly seed?: number | null;
  readonly split_seed?: number | null;
  readonly split_hash?: string | null;
  readonly parent_run?: string | null;
  readonly prereg_doc?: string | null;
  readonly oos_take_count?: number | null;
  readonly oos_take_mean_net_pct?: number | null;
  readonly oos_take_total_net_pct?: number | null;
  readonly take_all_mean_net_pct?: number | null;
  readonly ts_imb_mean_net_pct?: number | null;
  readonly ts_imb_count?: number | null;
  readonly ts_imb_total_net_pct?: number | null;
  readonly skipped_count?: number | null;
  readonly skipped_mean_net_pct?: number | null;
  readonly mean_trade_delta_pct?: number | null;
  readonly total_pp_delta?: number | null;
  readonly brier?: number | null;
  readonly brier_constant?: number | null;
  readonly consistent_folds?: number | null;
  readonly ablations_better_than_full?: number | null;
  readonly blocking_reasons?: readonly string[];
  readonly control_brier?: number | null;
  readonly control_oos_take_mean_net_pct?: number | null;
  readonly guardrail?: string | null;
}
export interface RlFactoryLaneRunsResponse { readonly runs: readonly RlFactoryLaneRun[] }
export interface RlFactoryReliabilityBin {
  readonly bin: number;
  readonly lo: number;
  readonly hi: number;
  readonly count: number;
  readonly mean_predicted: number | null;
  readonly observed_rate: number | null;
}
export interface RlFactoryCalibrationFold {
  readonly fold_id: number;
  readonly brier?: number | null;
  readonly reliability_bins?: readonly RlFactoryReliabilityBin[];
}
export interface RlFactoryCalibrationResponse {
  readonly available: boolean;
  readonly reason?: string;
  readonly run?: string;
  readonly guardrail?: string;
  readonly brier?: number | null;
  readonly brier_constant?: number | null;
  readonly folds?: readonly RlFactoryCalibrationFold[];
}
export interface RlFactoryEdgeLedgerSummary {
  readonly total_rows?: number;
  readonly take_count?: number;
  readonly skip_count?: number;
  readonly take_mean_net_pct?: number | null;
  readonly skip_mean_net_pct?: number | null;
  readonly mean_edge_pct?: number | null;
  readonly breakeven_note?: string | null;
  readonly cost_note?: string | null;
}
export interface RlFactoryEdgeLedgerRow extends JsonObject {
  readonly symbol?: string;
  readonly session?: string;
  readonly p_win?: number | null;
  readonly edge_pct?: number | null;
  readonly decision?: string;
  readonly net_pct_23bp?: number | null;
}
export type RlFactoryDecisionFilter = 'TAKE' | 'SKIP';
export interface RlFactoryEdgeLedgerResponse {
  readonly available: boolean;
  readonly reason?: string;
  readonly run?: string;
  readonly guardrail?: string;
  readonly summary?: RlFactoryEdgeLedgerSummary;
  readonly decision_filter?: string | null;
  readonly returned_rows?: number;
  readonly rows?: readonly RlFactoryEdgeLedgerRow[];
}
export interface RlFactorySizingRun {
  readonly run: string;
  readonly artifact_type?: string | null;
  readonly input_kind?: string | null;
  readonly fill_mode?: string | null;
  readonly strategy_label?: string | null;
  readonly baseline_label?: string | null;
  readonly guardrail?: string | null;
  readonly cost_note?: string | null;
  readonly strategy_trade_count?: number | null;
  readonly baseline_trade_count?: number | null;
  readonly strategy_session_count?: number | null;
  readonly baseline_session_count?: number | null;
  readonly basis_fraction?: number | null;
  readonly strategy_total_pct?: number | null;
  readonly baseline_total_pct?: number | null;
  readonly total_pct_delta?: number | null;
  readonly strategy_max_drawdown_pct?: number | null;
  readonly baseline_max_drawdown_pct?: number | null;
  readonly max_drawdown_delta?: number | null;
  readonly strategy_risk_adjusted_mean_over_std?: number | null;
  readonly baseline_risk_adjusted_mean_over_std?: number | null;
  readonly risk_adjusted_improvement?: boolean | null;
  readonly drawdown_improvement?: boolean | null;
  readonly strategy_mean_trade_pct?: number | null;
  readonly baseline_mean_trade_pct?: number | null;
  readonly mean_trade_delta_pct?: number | null;
  readonly strategy_capacity_skipped?: number | null;
  readonly baseline_capacity_skipped?: number | null;
  readonly strategy_daily_halt_5_total_pct?: number | null;
  readonly baseline_daily_halt_5_total_pct?: number | null;
  readonly strategy_daily_halt_5_sessions?: number | null;
  readonly baseline_daily_halt_5_sessions?: number | null;
  readonly strategy_worst_session_net_pct?: number | null;
  readonly baseline_worst_session_net_pct?: number | null;
  readonly p5_prerequisite_met?: boolean | null;
  readonly p5_status?: string | null;
  readonly p5_note?: string | null;
}
export interface RlFactorySizingRunsResponse { readonly runs: readonly RlFactorySizingRun[] }

export interface RlFactoryRiskPolicyRun {
  readonly run: string;
  readonly run_id?: string | null;
  readonly artifact_type?: string | null;
  readonly fill_mode?: string | null;
  readonly input_kind?: string | null;
  readonly strategy_label?: string | null;
  readonly baseline_label?: string | null;
  readonly guardrail?: string | null;
  readonly cost_bps?: number | null;
  readonly basis_fraction?: number | null;
  readonly selection_bias_note?: string | null;
  readonly edge_ledger_path?: string | null;
  readonly baseline_total_pct?: number | null;
  readonly baseline_max_drawdown_pct?: number | null;
  readonly baseline_risk_adjusted_mean_over_std?: number | null;
  readonly baseline_trade_count?: number | null;
  readonly baseline_session_count?: number | null;
  readonly best_policy_id?: string | null;
  readonly best_policy_description?: string | null;
  readonly candidate_total_pct?: number | null;
  readonly candidate_max_drawdown_pct?: number | null;
  readonly candidate_risk_adjusted_mean_over_std?: number | null;
  readonly candidate_trade_count?: number | null;
  readonly candidate_session_count?: number | null;
  readonly source_take_count?: number | null;
  readonly selected_before_halt?: number | null;
  readonly trades_skipped_filter?: number | null;
  readonly trades_skipped_halt?: number | null;
  readonly sessions_halted?: number | null;
  readonly mean_size_before_halt?: number | null;
  readonly total_pct_delta?: number | null;
  readonly max_drawdown_delta?: number | null;
  readonly risk_adjusted_delta?: number | null;
  readonly risk_adjusted_improvement?: boolean | null;
  readonly drawdown_improvement?: boolean | null;
  readonly total_noninferior?: boolean | null;
  readonly candidate_p2_pass?: boolean | null;
  readonly verdict?: string | null;
  readonly implementation_unlocked?: boolean | null;
  readonly unlock_note?: string | null;
}
export interface RlFactoryRiskPolicyRunsResponse { readonly runs: readonly RlFactoryRiskPolicyRun[] }

export interface RlFactoryFreshValidationRun {
  readonly run: string;
  readonly run_id?: string | null;
  readonly artifact_type?: string | null;
  readonly schema_version?: number | null;
  readonly fill_mode?: string | null;
  readonly validation_scope?: string | null;
  readonly is_fresh_validation?: boolean | null;
  readonly source_path?: string | null;
  readonly strategy_label?: string | null;
  readonly baseline_label?: string | null;
  readonly guardrail?: string | null;
  readonly cost_bps?: number | null;
  readonly selection_bias_guardrail?: string | null;
  readonly policy_id?: string | null;
  readonly policy_total_pct?: number | null;
  readonly policy_max_drawdown_pct?: number | null;
  readonly policy_risk_adjusted_mean_over_std?: number | null;
  readonly policy_trade_count?: number | null;
  readonly policy_session_count?: number | null;
  readonly selected_before_halt?: number | null;
  readonly sessions_halted?: number | null;
  readonly baseline_total_pct?: number | null;
  readonly baseline_max_drawdown_pct?: number | null;
  readonly baseline_risk_adjusted_mean_over_std?: number | null;
  readonly baseline_trade_count?: number | null;
  readonly baseline_session_count?: number | null;
  readonly total_pct_delta?: number | null;
  readonly max_drawdown_delta?: number | null;
  readonly risk_adjusted_delta?: number | null;
  readonly risk_adjusted_improvement?: boolean | null;
  readonly drawdown_improvement?: boolean | null;
  readonly total_noninferior?: boolean | null;
  readonly enough_trades?: boolean | null;
  readonly fresh_gate_pass?: boolean | null;
  readonly verdict?: string | null;
  readonly fresh_validation_pass?: boolean | null;
  readonly implementation_unlocked?: boolean | null;
  readonly unlock_note?: string | null;
  readonly min_trades?: number | null;
  readonly min_total_delta_pct?: number | null;
}
export interface RlFactoryFreshValidationRunsResponse { readonly runs: readonly RlFactoryFreshValidationRun[] }

export interface RlFactoryReadinessStep {
  readonly id: string;
  readonly label: string;
  readonly status: string;
  readonly evidence?: string | null;
}
export interface RlFactoryModelBuildReadinessResponse {
  readonly available: boolean;
  readonly artifact_type?: string;
  readonly strategy_label?: string;
  readonly baseline_label?: string;
  readonly guardrail?: string;
  readonly cost_bps?: number;
  readonly status?: string;
  readonly required_fill_modes?: readonly string[];
  readonly p1_status?: string;
  readonly original_p2_status?: string;
  readonly risk_policy_status?: string;
  readonly fresh_validation_status?: string;
  readonly p3_status?: string;
  readonly p4_status?: string;
  readonly restricted_rl_status?: string;
  readonly implementation_unlocked?: boolean;
  readonly selected_policy_ids?: readonly string[];
  readonly selection_bias_note?: string;
  readonly unlock_requirements?: readonly string[];
  readonly readiness_steps?: readonly RlFactoryReadinessStep[];
  readonly risk_policy_runs?: readonly RlFactoryRiskPolicyRun[];
  readonly fresh_validation_runs?: readonly RlFactoryFreshValidationRun[];
  readonly original_sizing_runs?: readonly RlFactorySizingRun[];
  readonly forward_ledger_runs?: readonly RlFactoryForwardLedgerRun[];
}

export interface RlFactoryForwardLedgerRun {
  readonly run: string;
  readonly run_id?: string | null;
  readonly model_version?: string | null;
  readonly fill_assumption?: string | null;
  readonly cost_bps?: number | null;
  readonly schema_version?: number | null;
  readonly total_count?: number | null;
  readonly pending_count?: number | null;
  readonly resolved_count?: number | null;
  readonly status_counts?: Readonly<Record<string, number>>;
  readonly duplicate_policy?: string | null;
  readonly skipped_duplicate_count?: number | null;
  readonly include_outcomes?: boolean | null;
  readonly source_edge_ledger_path?: string | null;
  readonly output_root?: string | null;
  readonly guardrail?: string | null;
}
export interface RlFactoryForwardLedgerRunsResponse { readonly runs: readonly RlFactoryForwardLedgerRun[] }
export interface RlFactoryForwardLedgerSummary {
  readonly total_rows?: number;
  readonly pending_count?: number;
  readonly resolved_count?: number;
  readonly status_counts?: Readonly<Record<string, number>>;
  readonly schema_version?: number | null;
  readonly duplicate_policy?: string | null;
  readonly fill_assumption?: string | null;
  readonly cost_bps?: number | null;
  readonly model_version?: string | null;
  readonly output_root?: string | null;
}
export interface RlFactoryForwardLedgerRow extends JsonObject {
  readonly record_id?: string;
  readonly recorded_at_utc?: string;
  readonly session?: string;
  readonly code?: string;
  readonly run_id?: string;
  readonly model_version?: string;
  readonly p_win?: number | null;
  readonly edge_pct?: number | null;
  readonly decision?: string;
  readonly fill_assumption?: string;
  readonly realized_outcome_pct?: number | null;
  readonly baseline_outcome_pct?: number | null;
  readonly outcome_status?: string;
  readonly cost_bps?: number | null;
  readonly schema_version?: number | null;
}
export interface RlFactoryForwardLedgerResponse {
  readonly available: boolean;
  readonly reason?: string;
  readonly run?: string;
  readonly guardrail?: string;
  readonly summary?: RlFactoryForwardLedgerSummary;
  readonly status_filter?: string | null;
  readonly returned_rows?: number;
  readonly rows?: readonly RlFactoryForwardLedgerRow[];
}


export interface RlRliableMetric {
  readonly point: number;
  readonly ci_lower: number;
  readonly ci_upper: number;
}
export interface RlRliableAggregate {
  readonly median?: RlRliableMetric;
  readonly iqm?: RlRliableMetric;
  readonly mean?: RlRliableMetric;
  readonly optimality_gap?: RlRliableMetric;
}
export interface RlRliableAlgoMetadata {
  readonly run_ids?: readonly string[];
  readonly seed_count?: number;
  readonly cost_bps?: readonly number[] | null;
  readonly run_scores?: Readonly<Record<string, number>>;
}
export interface RlRliableStatsResponse {
  readonly schema?: string;
  readonly generated_utc?: string;
  readonly research_only?: boolean;
  readonly note?: string;
  readonly score_definition?: string;
  readonly metric_names?: readonly string[];
  readonly confidence_interval?: number;
  readonly bootstrap_reps?: number;
  readonly min_seeds?: number;
  readonly scanned_file_count?: number;
  readonly algorithms?: readonly string[];
  readonly aggregates?: Readonly<Record<string, RlRliableAggregate>>;
  readonly metadata?: Readonly<Record<string, RlRliableAlgoMetadata>>;
  readonly available?: boolean;
  readonly error?: string;
}

let factoryLaneRunsRequest: Promise<RlFactoryLaneRunsResponse | null> | null = null;

function factoryLaneRuns(): Promise<RlFactoryLaneRunsResponse | null> {
  if (factoryLaneRunsRequest) return factoryLaneRunsRequest;

  const request = fetchJson<RlFactoryLaneRunsResponse>('/api/rl/factory/lane-runs');
  const sharedRequest = request.then(
    (payload) => {
      if (payload === null && factoryLaneRunsRequest === sharedRequest) factoryLaneRunsRequest = null;
      return payload;
    },
    (error: unknown) => {
      if (factoryLaneRunsRequest === sharedRequest) factoryLaneRunsRequest = null;
      throw error;
    },
  );
  factoryLaneRunsRequest = sharedRequest;
  return sharedRequest;
}

function resetFactoryLaneRuns(): void {
  factoryLaneRunsRequest = null;
}

const v5RunIdPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const v5CursorPattern = /^[A-Za-z0-9_-]{16,2048}$/u;
const v5RevisionForbiddenPattern = /[\u0000-\u001F\u007F]/u;
const v5LearningRunUidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const v5LearningRevisionPattern = /^[1-9][0-9]{0,15}$/u;
const v5LearningMaxSafeRevision = Number.MAX_SAFE_INTEGER;
const v5LearningTopLevelPaths = {
  MATRIX: '/api/v5/rl/matrix',
  LEDGER: '/api/v5/rl/ledger',
  ARTIFACTS: '/api/v5/rl/artifacts',
} as const satisfies Pick<Record<V5RouteId, string>, 'MATRIX' | 'LEDGER' | 'ARTIFACTS'>;

export type DeepReadonly<T> = V5DeepReadonly<T>;

export type V5ReadonlyRouteRootMap = {
  readonly [RouteId in V5RouteId]: DeepReadonly<V5RouteRootMap[RouteId]>;
};
type V5FetchOptions = {
  readonly cursor?: string;
  readonly revision?: string;
};
type V5LearningFetchOptions = {
  readonly cursor?: string;
  readonly runId?: string;
  readonly revision?: number;
};

export type V5LearningBoundedStatus = 409 | 410 | 422 | 503;

const v5LearningBoundedStatuses = new Set<number>([409, 410, 422, 503]);

function toV5LearningBoundedStatus(status: number): V5LearningBoundedStatus | null {
  return v5LearningBoundedStatuses.has(status) ? status as V5LearningBoundedStatus : null;
}

export class V5LearningFetchError extends Error {
  readonly name = 'V5LearningFetchError' as const;
  readonly routeId: V5RouteId;
  readonly status: number;
  readonly boundedStatus: V5LearningBoundedStatus | null;
  readonly payload: DeepReadonly<ErrorRoot>;
  readonly code: ErrorRoot['error']['code'];

  constructor(routeId: V5RouteId, status: number, payload: ErrorRoot) {
    super(payload.error.message);
    this.routeId = routeId;
    this.status = status;
    this.boundedStatus = toV5LearningBoundedStatus(status);
    this.payload = freezeV5Payload(payload) as DeepReadonly<ErrorRoot>;
    this.code = payload.error.code;
    Object.freeze(this);
  }
}


function v5Search(options: V5FetchOptions = {}): string {
  const params = new URLSearchParams();
  if (options.cursor !== undefined) {
    if (typeof options.cursor !== 'string' || !v5CursorPattern.test(options.cursor)) {
      throw new V5SemanticError('invalid cursor');
    }
    params.set('cursor', options.cursor);
  }
  if (options.revision !== undefined) {
    if (
      typeof options.revision !== 'string'
      || options.revision.length < 1
      || options.revision.length > 2048
      || v5RevisionForbiddenPattern.test(options.revision)
    ) {
      throw new V5SemanticError('invalid revision');
    }
    params.set('revision', options.revision);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}
function validateV5LearningRunUid(value: string): string {
  if (typeof value !== 'string' || !v5LearningRunUidPattern.test(value)) {
    throw new V5SemanticError('invalid run_uid');
  }
  return value;
}

function validateV5LearningRevision(value: number): string {
  if (
    typeof value !== 'number'
    || !Number.isSafeInteger(value)
    || value < 1
    || value > v5LearningMaxSafeRevision
    || !v5LearningRevisionPattern.test(String(value))
  ) {
    throw new V5SemanticError('invalid run_revision');
  }
  return String(value);
}

function v5LearningSearch(options: V5LearningFetchOptions = {}): string {
  const params = new URLSearchParams();
  if (options.runId !== undefined) {
    params.set('run_id', validateV5LearningRunUid(options.runId));
  }
  if (options.revision !== undefined) {
    params.set('revision', validateV5LearningRevision(options.revision));
  }
  if (options.cursor !== undefined) {
    if (typeof options.cursor !== 'string' || !v5CursorPattern.test(options.cursor)) {
      throw new V5SemanticError('invalid cursor');
    }
    params.set('cursor', options.cursor);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

function isV5ErrorRootForRoute(routeId: V5RouteId, value: unknown): value is ErrorRoot {
  return validateErrorRoot(value) && (value as ErrorRoot).route_id === routeId;
}

async function readV5LearningPayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
function isV5RouteRoot<K extends V5RouteId>(routeId: K, value: unknown): value is V5RouteRootMap[K] {
  return v5RouteDescriptors[routeId].validator(value);
}

function v5Path(routeId: V5RouteId, pathParams: Readonly<Record<string, string>>): string {
  const descriptor = v5RouteDescriptors[routeId];
  return descriptor.pathBindings.reduce((path, name) => {
    const value = pathParams[name];
    if (!value || (name === 'run_id' && !v5RunIdPattern.test(value))) {
      throw new V5SemanticError(`invalid path binding ${name}`);
    }
    return path.replace(`{${name}}`, encodeURIComponent(value));
  }, descriptor.path);
}

function freezeV5Payload<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) {
      freezeV5Payload(child);
    }
    Object.freeze(value);
  }
  return value;
}

function v5Url(path: string, search: string): string {
  if (!search) return path;
  return path.includes('?') ? `${path}&${search.slice(1)}` : `${path}${search}`;
}

function v5QueryParams(url: string): Readonly<Record<string, string>> {
  const parsed = new URL(url, 'https://kronos.local');
  const params: Record<string, string> = {};
  for (const [name, value] of parsed.searchParams) {
    params[name] = value;
  }
  return params;
}

function v5RequestContext(
  method: string,
  url: string,
  pathParams: Readonly<Record<string, string>>,
): { method: string; path: string; pathParams: Readonly<Record<string, string>>; queryParams: Readonly<Record<string, string>> } {
  const parsed = new URL(url, 'https://kronos.local');
  return { method, path: parsed.pathname, pathParams, queryParams: v5QueryParams(url) };
}

async function fetchV5Json<K extends V5RouteId>(
  routeId: K,
  pathParams: Readonly<Record<string, string>> = {},
  options: V5FetchOptions = {},
): Promise<V5ReadonlyRouteRootMap[K] | null> {
  const descriptor = v5RouteDescriptors[routeId];
  const path = v5Path(routeId, pathParams);
  const url = v5Url(path, v5Search(options));
  const init: RequestInit = { method: descriptor.method };
  const context = { method: descriptor.method, path, pathParams };
  const payload = await fetchJson<unknown>(url, init);
  if (payload === null) return null;
  if (!isV5RouteRoot(routeId, payload)) {
    throw new V5SchemaValidationError(routeId, sanitizeV5SchemaDiagnostics(descriptor.validator.errors));
  }
  await validateV5Semantic(routeId, payload, context);
  return freezeV5Payload(payload) as V5ReadonlyRouteRootMap[K];
}
async function fetchV5LearningJson<K extends V5RouteId>(
  routeId: K,
  path: string,
  pathParams: Readonly<Record<string, string>> = {},
  options: V5LearningFetchOptions = {},
): Promise<V5ReadonlyRouteRootMap[K]> {
  const descriptor = v5RouteDescriptors[routeId];
  const url = v5Url(path, v5LearningSearch(options));
  const context = v5RequestContext(descriptor.method, url, pathParams);
  const response = await fetch(url);
  const payload = await readV5LearningPayload(response);

  if (!response.ok) {
    if (!isV5ErrorRootForRoute(routeId, payload)) {
      throw new V5SchemaValidationError(routeId, sanitizeV5SchemaDiagnostics(undefined));
    }
    await validateV5Semantic(routeId, payload, context);
    throw new V5LearningFetchError(routeId, response.status, payload);
  }

  if (!isV5RouteRoot(routeId, payload)) {
    throw new V5SchemaValidationError(routeId, sanitizeV5SchemaDiagnostics(descriptor.validator.errors));
  }
  await validateV5Semantic(routeId, payload, context);
  return freezeV5Payload(payload) as V5ReadonlyRouteRootMap[K];
}
export const rlApi = {
  rlRuns: (limit: number = 20) => fetchJson<RlRunsResponse>(`/api/rl/runs?limit=${limit}`),
  rlProgress: () => fetchJson<RlProgressResponse>('/api/rl/progress'),
  rlRun: (run: string) => fetchJson<RlRunDetail>(`/api/rl/runs/${encodeURIComponent(run)}`),
  rlActions: (run: string, limit: number = 500) => fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/actions?limit=${limit}`),
  rlTrades: (run: string, limit: number = 500) => fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/trades?limit=${limit}`),
  rlEquity: (run: string, limit: number = 500) => fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/equity?limit=${limit}`),
  rlEpisodes: (run: string, limit: number = 500) => fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/episodes?limit=${limit}`),
  rlEvents: (run: string, limit: number = 500) => fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/events?limit=${limit}`),
  rlTable: (run: string, table: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/${encodeURIComponent(table)}?limit=${limit}`),
  rlWorkflowStages: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/stages?limit=${limit}`),
  rlWorkflowControls: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/controls?limit=${limit}`),
  rlProxyAvailability: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/proxy_availability?limit=${limit}`),
  rlOrderbookPersistence: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/orderbook_persistence?limit=${limit}`),
  rlParticipantStudyGroups: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/participant_study_groups?limit=${limit}`),
  rlFeatureAblation: (run: string, limit: number = 200) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/table/feature_ablation?limit=${limit}`),
  rlCostGate: (run: string, limit: number = 500) => fetchJson<RlCostGateResponse>(`/api/rl/runs/${encodeURIComponent(run)}/cost-gate?limit=${limit}`),
  factoryQueue: () => fetchJson<RlFactoryQueueResponse>('/api/rl/factory/queue'),
  factoryLaneRuns,
  resetFactoryLaneRuns,
  factoryLaneCalibration: (run: string) =>
    fetchJson<RlFactoryCalibrationResponse>(`/api/rl/factory/lane/${encodeURIComponent(run)}/calibration`),
  factoryLaneEdgeLedger: (run: string, limit: number = 200, decision?: RlFactoryDecisionFilter) =>
    fetchJson<RlFactoryEdgeLedgerResponse>(
      `/api/rl/factory/lane/${encodeURIComponent(run)}/edge-ledger?limit=${limit}${decision ? `&decision=${decision}` : ''}`
    ),
  factorySizingRuns: () => fetchJson<RlFactorySizingRunsResponse>('/api/rl/factory/sizing-runs'),
  factoryRiskPolicyRuns: () => fetchJson<RlFactoryRiskPolicyRunsResponse>('/api/rl/factory/risk-policy-runs'),
  factoryFreshValidationRuns: () =>
    fetchJson<RlFactoryFreshValidationRunsResponse>('/api/rl/factory/fresh-validation-runs'),
  factoryModelBuildReadiness: () =>
    fetchJson<RlFactoryModelBuildReadinessResponse>('/api/rl/factory/model-build-readiness'),
  factoryForwardLedgers: () => fetchJson<RlFactoryForwardLedgerRunsResponse>('/api/rl/factory/forward-ledgers'),
  factoryForwardLedger: (run: string, limit: number = 200, status?: 'pending' | 'resolved') =>
    fetchJson<RlFactoryForwardLedgerResponse>(
      `/api/rl/factory/forward-ledger/${encodeURIComponent(run)}?limit=${limit}${status ? `&status=${status}` : ''}`
    ),
  v5Runs: (cursor?: string) => fetchV5Json('RUNS', {}, { cursor }),
  v5RunDetail: (run: string, revision?: string) => fetchV5Json('RUN_DETAIL', { run_id: run }, { revision }),
  v5Events: (run: string, cursor?: string, revision?: string) => fetchV5Json('EVENTS', { run_id: run }, { cursor, revision }),
  v5Matrix: () => fetchV5Json('MATRIX'),
  v5Ledger: (cursor?: string) => fetchV5Json('LEDGER', {}, { cursor }),
  v5Artifacts: (cursor?: string, revision?: string) => fetchV5Json('ARTIFACTS', {}, { cursor, revision }),
  v5D0: () => fetchV5Json('D0'),
  v5D1: () => fetchV5Json('D1'),
  v5Fixture: () => fetchV5Json('FIXTURE'),
  v5LearningRuns: (cursor?: string) => fetchV5LearningJson('RUNS', v5Path('RUNS', {}), {}, { cursor }),
  v5LearningRunDetail: (runUid: string, revision: number) => {
    const uid = validateV5LearningRunUid(runUid);
    return fetchV5LearningJson('RUN_DETAIL', v5Path('RUN_DETAIL', { run_id: uid }), { run_id: uid }, { revision });
  },
  v5LearningEvents: (runUid: string, revision: number, cursor?: string) => {
    const uid = validateV5LearningRunUid(runUid);
    return fetchV5LearningJson('EVENTS', v5Path('EVENTS', { run_id: uid }), { run_id: uid }, { cursor, revision });
  },
  v5LearningMatrix: (runUid: string, revision: number) =>
    fetchV5LearningJson('MATRIX', v5LearningTopLevelPaths.MATRIX, {}, { runId: runUid, revision }),
  v5LearningLedger: (runUid: string, revision: number, cursor?: string) =>
    fetchV5LearningJson('LEDGER', v5LearningTopLevelPaths.LEDGER, {}, { cursor, runId: runUid, revision }),
  v5LearningArtifacts: (runUid: string, revision: number, cursor?: string) =>
    fetchV5LearningJson('ARTIFACTS', v5LearningTopLevelPaths.ARTIFACTS, {}, { cursor, runId: runUid, revision }),
  v5LearningD0: () => fetchV5LearningJson('D0', v5Path('D0', {})),
  v5LearningD1: () => fetchV5LearningJson('D1', v5Path('D1', {})),
  v5LearningFixture: () => fetchV5LearningJson('FIXTURE', v5Path('FIXTURE', {})),
  rliableStats: () => fetchJson<RlRliableStatsResponse>('/api/rl/rliable-stats'),
};

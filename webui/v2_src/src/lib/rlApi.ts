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
  factoryLaneRuns: () => fetchJson<RlFactoryLaneRunsResponse>('/api/rl/factory/lane-runs'),
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
};

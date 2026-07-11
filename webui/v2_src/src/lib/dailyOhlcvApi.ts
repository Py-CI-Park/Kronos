import { fetchJson } from './http';

export type DailyStageStatus = 'NOT_STARTED' | 'RUNNING' | 'PASS' | 'WATCH' | 'NO-GO' | 'BLOCKED' | string;

export interface DailyProgressStage {
  readonly id: string;
  readonly label: string;
  readonly status: DailyStageStatus;
  readonly evidence?: string;
  readonly lock_labels?: readonly string[];
  readonly verification_commands?: readonly string[];
  readonly usage_guide?: Readonly<Record<string, unknown>>;
  readonly can_do?: string;
  readonly must_not?: string;
  readonly next_action?: string;
}

export interface DailyProgressResponse {
  readonly mode: string;
  readonly overall_status: string;
  readonly guardrail: string;
  readonly stages: readonly DailyProgressStage[];
  readonly provenance_matrix?: readonly {
    readonly id: string;
    readonly status: DailyStageStatus;
    readonly lock_labels?: readonly string[];
    readonly verification_commands?: readonly string[];
  }[];
  readonly verification_commands?: Readonly<Record<string, readonly string[]>>;
  readonly page_usage_guide?: readonly Record<string, unknown>[];
}

export interface DailyDbSummaryResponse {
  readonly table_count?: number;
  readonly total_rows?: number;
  readonly first_date?: string;
  readonly latest_date?: string;
  readonly prefix_counts?: Readonly<Record<string, number>>;
  readonly price_basis?: string;
  readonly price_basis_evidence?: string;
  readonly price_basis_status?: string;
  readonly decision_grade_return_status?: string;
  readonly price_basis_blocking_implications?: readonly string[];
  readonly price_basis_audit?: Readonly<Record<string, unknown>>;
  readonly price_basis_required_evidence?: readonly string[];
  readonly price_basis_allowed_uses?: readonly string[];
  readonly price_basis_blocked_uses?: readonly string[];
  readonly price_basis_user_guidance?: readonly {
    readonly section?: string;
    readonly can_do?: string;
    readonly must_not_do?: string;
    readonly next_action?: string;
  }[];
  readonly adjustment_policy?: string;
  readonly decision_grade_status?: string;
  readonly quality_scan_scope?: string;
  readonly quality_scan_table_count?: number;
  readonly quality_scan_total_table_count?: number;
  readonly material_unknown_adjustment_windows?: readonly Record<string, unknown>[];
  readonly table_summaries?: readonly Record<string, unknown>[];
  readonly quality_flags?: readonly Record<string, unknown>[];
  readonly artifact_dir?: string;
  readonly read_only_dashboard_note?: string;
}

export interface DailyUniverseResponse {
  readonly verdict?: string;
  readonly review_status?: string;
  readonly table_count?: number;
  readonly stockinfo_matched_table_count?: number;
  readonly stockinfo_unmatched_table_count?: number;
  readonly unmatched_quarantine_count?: number;
  readonly include_count?: number;
  readonly quarantine_artifact_count?: number;
  readonly exclude_count?: number;
  readonly q_product_count?: number;
  readonly metadata_unmatched_count?: number;
  readonly official_metadata_status?: string;
  readonly official_metadata_coverage_status?: string;
  readonly official_metadata_required_columns?: readonly string[];
  readonly official_metadata_matched_table_count?: number;
  readonly official_metadata_unmatched_table_count?: number;
  readonly official_metadata_unmatched_quarantine_count?: number;
  readonly official_metadata?: Readonly<Record<string, unknown>>;
  readonly universe_review_status?: string;
  readonly universe_certification_status?: string;
  readonly universe_required_evidence?: readonly string[];
  readonly universe_allowed_uses?: readonly string[];
  readonly universe_blocked_uses?: readonly string[];
  readonly universe_user_guidance?: readonly Record<string, unknown>[];
  readonly required_fields?: readonly string[];
  readonly counts_by_type?: Readonly<Record<string, number>>;
  readonly counts_by_exclusion_reason?: Readonly<Record<string, number>>;
  readonly symbols?: readonly Record<string, unknown>[];
  readonly exclusions?: readonly Record<string, unknown>[];
  readonly manifest_sha?: string;
  readonly artifact_dir?: string;
  readonly read_only_dashboard_note?: string;
}

export interface DailySymbolResponse {
  readonly table: string;
  readonly code: string;
  readonly prefix: string;
  readonly row_count?: number;
  readonly first_date?: string;
  readonly last_date?: string;
  readonly price_basis?: string;
  readonly quality?: Record<string, unknown>;
  readonly sample_rows_desc?: readonly Record<string, unknown>[];
}

export interface DailyArtifactsResponse {
  readonly artifacts: readonly Record<string, unknown>[];
  readonly read_only: boolean;
}

export interface DailyDatasetResponse {
  readonly manifest_sha?: string;
  readonly universe_manifest_sha?: string;
  readonly cost_assumption_round_trip_bp?: number;
  readonly split_policy?: Readonly<Record<string, number | string>>;
  readonly status?: string;
  readonly run_id?: string;
  readonly artifact_scope?: string;
  readonly price_basis?: string;
  readonly universe_verdict?: string;
  readonly leakage_status?: string;
  readonly split_chronology_status?: string;
  readonly model_readiness?: string;
  readonly price_basis_status?: string;
  readonly decision_grade_return_status?: string;
  readonly official_metadata_status?: string;
  readonly official_metadata_coverage_status?: string;
  readonly universe_certification_status?: string;
  readonly upstream_gate_blockers?: readonly string[];
  readonly dataset_required_evidence?: readonly string[];
  readonly dataset_allowed_uses?: readonly string[];
  readonly dataset_blocked_uses?: readonly string[];
  readonly dataset_user_guidance?: readonly Record<string, unknown>[];
  readonly row_counts?: Readonly<Record<string, number>>;
  readonly source_counts?: Readonly<Record<string, number | string | boolean | null>>;
  readonly split_summary?: {
    readonly row_counts?: Readonly<Record<string, number>>;
    readonly date_ranges?: Readonly<Record<string, { readonly start?: string | null; readonly end?: string | null; readonly intervals?: readonly Record<string, string>[] }>>;
  };
  readonly samples?: Readonly<Record<string, readonly Record<string, unknown>[]>>;
  readonly leakage_report?: Record<string, unknown>;
  readonly normalization_stats?: Record<string, unknown>;
  readonly read_only_dashboard_note?: string;
}

export interface DailyDatasetChartResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly artifact_scope?: string;
  readonly leakage_status?: string;
  readonly split_chronology_status?: string;
  readonly price_basis?: string;
  readonly universe_verdict?: string;
  readonly model_readiness?: string;
  readonly upstream_gate_blockers?: readonly string[];
  readonly price_basis_status?: string;
  readonly decision_grade_return_status?: string;
  readonly official_metadata_status?: string;
  readonly official_metadata_coverage_status?: string;
  readonly universe_certification_status?: string;
  readonly split_series?: readonly { readonly label: string; readonly value: number }[];
  readonly row_series?: readonly { readonly label: string; readonly value: number }[];
  readonly guardrail?: string;
}
export interface DailyPredictionResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly price_basis?: string;
  readonly readiness_status?: string;
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly universe_review_status?: string;
  readonly verdict?: Record<string, unknown>;
  readonly baseline_metrics?: readonly Record<string, unknown>[];
  readonly baseline_delta_summary?: Record<string, unknown>;
  readonly d3_gate_blockers?: readonly string[];
  readonly d3_required_evidence?: readonly string[];
  readonly d3_allowed_uses?: readonly string[];
  readonly d3_blocked_uses?: readonly string[];
  readonly d3_user_guidance?: readonly Record<string, unknown>[];
  readonly baseline_freeze_contract?: Record<string, unknown>;
  readonly artifact_hashes?: Record<string, unknown>;
  readonly model_metrics?: readonly Record<string, unknown>[];
  readonly samples?: Readonly<Record<string, readonly Record<string, unknown>[]>>;
  readonly read_only_dashboard_note?: string;
}

export interface DailyPortfolioResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly verdict?: Record<string, unknown>;
  readonly readiness_status?: string;
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly no_live_broker_order_readiness?: boolean;
  readonly prediction_manifest_sha?: string;
  readonly prediction_artifact_hashes?: Record<string, unknown>;
  readonly prediction_artifact_hash_mismatches?: readonly string[];
  readonly artifact_hashes?: Record<string, unknown>;
  readonly baseline_comparison?: Record<string, unknown>;
  readonly policy_metrics?: { readonly metrics?: readonly Record<string, unknown>[] };
  readonly training_manifest?: Record<string, unknown>;
  readonly telemetry?: Record<string, unknown>;
  readonly reward_component_summary?: Record<string, unknown>;
  readonly policy_evaluation?: Record<string, unknown>;
  readonly observation_manifest?: Record<string, unknown>;
  readonly observation_manifest_validation?: Record<string, unknown>;
  readonly samples?: Readonly<Record<string, readonly Record<string, unknown>[]>>;
  readonly read_only_dashboard_note?: string;
}

export interface DailyWalkForwardResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly verdict?: Record<string, unknown>;
  readonly readiness_status?: string;
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly no_live_broker_order_readiness?: boolean;
  readonly prediction_manifest_sha?: string;
  readonly prediction_artifact_hashes?: Record<string, unknown>;
  readonly portfolio_manifest_sha?: string;
  readonly portfolio_artifact_hashes?: Record<string, unknown>;
  readonly artifact_hashes?: Record<string, unknown>;
  readonly selected_strategy?: string;
  readonly strategy_selection_policy?: string;
  readonly n_folds?: number;
  readonly samples?: Readonly<Record<string, readonly Record<string, unknown>[]>>;
  readonly d4_state_contract?: Record<string, unknown>;
  readonly read_only_dashboard_note?: string;
}

export interface DailyRegistryResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly promotion_status?: string;
  readonly model_build_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly no_live_broker_order_readiness?: boolean;
  readonly config_hash?: string;
  readonly data_hash?: string;
  readonly code_hash?: string;
  readonly candidate_registry?: Record<string, unknown>;
  readonly samples?: Readonly<Record<string, readonly Record<string, unknown>[]>>;
  readonly guardrail?: string;
  readonly read_only_dashboard_note?: string;
  readonly effective_gate_blockers?: readonly string[];
  readonly invariant_errors?: readonly string[];
}

export interface DailyModelChartResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly guardrail?: string;
  readonly baseline_series?: readonly Record<string, unknown>[];
  readonly baseline_delta_summary?: Record<string, unknown>;
  readonly d3_gate_blockers?: readonly string[];
  readonly d3_blocked_uses?: readonly string[];
  readonly readiness_status?: string;
  readonly d3_user_guidance?: readonly Record<string, unknown>[];
  readonly baseline_freeze_contract?: Record<string, unknown>;
  readonly artifact_hashes?: Record<string, unknown>;
  readonly best_strategy?: unknown;
  readonly cost_assumption_round_trip_bp?: number;
  readonly calibration?: readonly Record<string, unknown>[];
  readonly metrics?: readonly Record<string, unknown>[];
  readonly fold_metrics?: readonly Record<string, unknown>[];
  readonly cost_sensitivity?: readonly Record<string, unknown>[];
  readonly rl_fold_metrics?: readonly Record<string, unknown>[];
  readonly n_folds?: unknown;
  readonly selected_strategy?: unknown;
  readonly strategy_selection_policy?: unknown;
  readonly fold_consistency?: Record<string, unknown>;
  readonly fold_windows?: readonly Record<string, unknown>[];
  readonly fold_assignments?: readonly Record<string, unknown>[];
  readonly selected_fold_metrics?: readonly Record<string, unknown>[];
  readonly no_trade_control?: readonly Record<string, unknown>[];
  readonly d4_state_contract?: Record<string, unknown>;
  readonly d4_state_contract_status?: unknown;
  readonly d4_state_contract_artifacts_consumed?: boolean;
  readonly d4_observation_manifest_gate?: unknown;
  readonly d4_observation_manifest_validation_status?: unknown;
  readonly d4_reward_action_telemetry_sufficient_for_d4?: unknown;
  readonly d4_state_observation_rows?: unknown;
  readonly d4_artifact_issues?: readonly unknown[];
  readonly d4_reward_action_ablation_rows?: unknown;
  readonly d4_source_hash_count?: unknown;
  readonly no_oos_retuning?: boolean;
  readonly required_min_folds?: unknown;
  readonly purge_days?: unknown;
  readonly min_required_purge_days?: unknown;
  readonly min_required_embargo_days?: unknown;
  readonly embargo_days?: unknown;
  readonly cost_sensitivity_bp?: readonly unknown[];
  readonly price_basis?: unknown;
  readonly universe_review_status?: unknown;
  readonly baseline_comparison?: Record<string, unknown>;
  readonly reasons?: readonly string[];
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly no_live_broker_order_readiness?: boolean;
  readonly prediction_manifest_sha?: string;
  readonly prediction_artifact_hashes?: Record<string, unknown>;
  readonly portfolio_manifest_sha?: string;
  readonly portfolio_artifact_hashes?: Record<string, unknown>;
  readonly prediction_artifact_hash_mismatches?: readonly string[];
  readonly training_status?: unknown;
  readonly telemetry?: Record<string, unknown>;
  readonly learning_curve?: readonly Record<string, unknown>[];
  readonly reward_sample?: readonly Record<string, unknown>[];
  readonly reward_component_summary?: Record<string, unknown>;
  readonly action_distribution?: readonly Record<string, unknown>[];
  readonly turnover_series?: readonly Record<string, unknown>[];
  readonly drawdown_series?: readonly Record<string, unknown>[];
  readonly policy_evaluation?: Record<string, unknown>;
  readonly policy_baseline_comparison?: readonly Record<string, unknown>[];
  readonly policy_nav?: readonly Record<string, unknown>[];
  readonly observation_manifest?: Record<string, unknown>;
  readonly observation_manifest_validation?: Record<string, unknown>;
  readonly state_observations?: readonly Record<string, unknown>[];
  readonly invalid_actions?: readonly Record<string, unknown>[];
  readonly portfolio_trajectory?: readonly Record<string, unknown>[];
  readonly reward_stack?: readonly Record<string, unknown>[];
}

export interface DailyScenarioLabResponse {
  readonly mode: string;
  readonly platform_stage?: string;
  readonly scenario_generation_available?: boolean;
  readonly model_run_generation_available?: boolean;
  readonly read_only?: boolean;
  readonly status?: string;
  readonly scenario_count?: number;
  readonly assumption_dimensions?: Readonly<Record<string, unknown>>;
  readonly current_evidence?: Readonly<Record<string, unknown>>;
  readonly model_input_contract?: Readonly<Record<string, unknown>>;
  readonly scenario_rows?: readonly Record<string, unknown>[];
  readonly guardrail?: string;
}

export interface DailyScenarioRunLedgerResponse {
  readonly mode: string;
  readonly platform_stage?: string;
  readonly read_only?: boolean;
  readonly dashboard_mutation_available?: boolean;
  readonly cli_model_run_generation_available?: boolean;
  readonly model_run_generation_available?: boolean;
  readonly status?: string;
  readonly scenario_run_count?: number;
  readonly batch_count?: number;
  readonly runs?: readonly Record<string, unknown>[];
  readonly batches?: readonly Record<string, unknown>[];
  readonly quick_start_commands?: readonly string[];
  readonly required_controls?: readonly string[];
  readonly guardrail?: string;
}

export interface DailyRlEnvGuideResponse {
  readonly mode: string;
  readonly platform_stage?: string;
  readonly status?: string;
  readonly read_only?: boolean;
  readonly schema_version?: string;
  readonly source_run_id?: string;
  readonly source_stage?: string;
  readonly artifact_hashes?: Readonly<Record<string, unknown>>;
  readonly policy_type?: string;
  readonly action_schema_version?: string | number;
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly blockers?: readonly string[];
  readonly environment_built?: boolean;
  readonly maturity?: string;
  readonly plain_language_verdict?: string;
  readonly what_rl_means_here?: Readonly<Record<string, string>>;
  readonly visual_flow?: readonly Record<string, unknown>[];
  readonly state_contract?: Readonly<Record<string, unknown>>;
  readonly action_space?: Readonly<Record<string, unknown>>;
  readonly action_mask?: Readonly<Record<string, unknown>>;
  readonly reward_formula?: string;
  readonly reward_components?: readonly string[];
  readonly cost_round_trip_bp?: number;
  readonly fill_assumption?: string;
  readonly observation_manifest_status?: string;
  readonly observation_manifest_validation?: Readonly<Record<string, unknown>>;
  readonly learning_performance?: Readonly<Record<string, unknown>>;
  readonly current_artifact_evidence?: Readonly<Record<string, unknown>>;
  readonly active_replay?: Readonly<Record<string, unknown>>;
  readonly research_process_catalog?: Readonly<Record<string, unknown>>;
  readonly scenario_generator?: Readonly<Record<string, unknown>>;
  readonly signal_quality_audit_summary?: Readonly<Record<string, unknown>>;
  readonly market_regime_audit_readiness?: Readonly<Record<string, unknown>>;
  readonly market_regime_audit?: Readonly<Record<string, unknown>>;
  readonly improvement_queue?: Readonly<Record<string, unknown>>;
  readonly scenario_comparison?: Readonly<Record<string, unknown>>;
  readonly page_maturity_report?: Readonly<Record<string, unknown>>;
  readonly research_workflow_catalog?: Readonly<Record<string, unknown>>;
  readonly research_job_intent_ledger?: Readonly<Record<string, unknown>>;
  readonly rejection_analytics?: Readonly<Record<string, unknown>>;
  readonly dashboard_first_completion_report?: Readonly<Record<string, unknown>>;
  readonly well_built_checks?: readonly Record<string, unknown>[];
  readonly good_enough_for?: readonly string[];
  readonly not_good_enough_for?: readonly string[];
  readonly guardrail?: string;
}

export interface DailyVisualChartResponse {
  readonly status?: string;
  readonly run_id?: string;
  readonly guardrail?: string;
  readonly model_build_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly no_live_broker_order_readiness?: boolean;
  readonly readiness_status?: string;
  readonly effective_gate_blockers?: readonly string[];
  readonly selected_strategy?: string;
  readonly blockers?: readonly Record<string, unknown>[];
  readonly cards?: readonly Record<string, unknown>[];
  readonly nodes?: readonly Record<string, unknown>[];
  readonly edges?: readonly Record<string, unknown>[];
  readonly items?: readonly Record<string, unknown>[];
  readonly curves?: readonly Record<string, unknown>[];
  readonly cells?: readonly Record<string, unknown>[];
  readonly cost_series?: readonly Record<string, unknown>[];
  readonly points?: readonly Record<string, unknown>[];
  readonly counts_by_type?: Readonly<Record<string, number>>;
  readonly counts_by_market?: Readonly<Record<string, number>>;
  readonly counts_by_exclusion_reason?: Readonly<Record<string, number>>;
  readonly summary?: Readonly<Record<string, unknown>>;
  readonly usage_guide?: readonly Record<string, unknown>[];
  readonly ohlcv?: readonly Record<string, unknown>[];
  readonly code?: string;
  readonly table?: string;
  readonly price_basis?: string;
}

export interface DailyResearchWorkflowCatalogResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly read_only?: boolean;
  readonly execution_allowed_from_browser?: boolean;
  readonly job_intent_mode?: string;
  readonly workflow_count?: number;
  readonly completion_pct?: number;
  readonly allowed_workflow_ids?: readonly string[];
  readonly workflows?: readonly Record<string, unknown>[];
  readonly forbidden_fields?: readonly string[];
  readonly guardrail?: string;
}

export interface DailyResearchWorkflowDetailResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly workflow?: Readonly<Record<string, unknown>>;
  readonly inspector_sections?: readonly Record<string, unknown>[];
  readonly config_preview_contract?: Readonly<Record<string, unknown>>;
  readonly read_only?: boolean;
  readonly execution_allowed_from_browser?: boolean;
  readonly guardrail?: string;
}

export interface DailyResearchJobIntentLedgerResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly read_only?: boolean;
  readonly execution_allowed_from_browser?: boolean;
  readonly count?: number;
  readonly intents?: readonly Record<string, unknown>[];
  readonly guardrail?: string;
}

export interface DailyResearchJobIntentDetailResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly intent_id?: string;
  readonly workflow_id?: string;
  readonly read_only?: boolean;
  readonly execution_allowed_from_browser?: boolean;
  readonly model_build_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly guardrail?: string;
}

export interface DailyResearchJobIntentRequest {
  readonly approval_ref: string;
  readonly approval_ref_sha256: string;
  readonly approval_status: string;
  readonly idempotency_key: string;
  readonly requested_by?: string;
  readonly config?: Readonly<Record<string, unknown>>;
}

export interface DailyRejectionAnalyticsResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly run_id?: string;
  readonly read_only?: boolean;
  readonly promotion_allowed?: boolean;
  readonly row_counts?: Readonly<Record<string, number>>;
  readonly summary?: Readonly<Record<string, unknown>>;
  readonly gate_funnel_metrics?: readonly Record<string, unknown>[];
  readonly rejection_reason_taxonomy?: readonly Record<string, unknown>[];
  readonly calibration_metrics?: readonly Record<string, unknown>[];
  readonly threshold_sensitivity?: readonly Record<string, unknown>[];
  readonly false_negative_candidates?: readonly Record<string, unknown>[];
  readonly guardrail?: string;
}

export interface DailyMarketRegimeAuditResponse {
  readonly schema_version?: string;
  readonly status?: string;
  readonly verdict?: string;
  readonly run_id?: string;
  readonly read_only?: boolean;
  readonly promotion_allowed?: boolean;
  readonly summary?: Readonly<Record<string, unknown>>;
  readonly row_counts?: Readonly<Record<string, number>>;
  readonly source_hashes?: Readonly<Record<string, unknown>>;
  readonly artifact_hashes?: Readonly<Record<string, string>>;
  readonly validation_errors?: readonly string[];
  readonly guardrail?: string;
}

export interface DailyCloseSlotCostScenario {
  readonly scenario_id?: string;
  readonly sell_tax_bp?: number;
  readonly buy_commission_bp?: number;
  readonly sell_commission_bp?: number;
  readonly buy_slippage_bp?: number;
  readonly sell_slippage_bp?: number;
  readonly total_bp?: number;
}

export interface DailyCloseSlotThresholdSelection {
  readonly policy?: string;
  readonly split?: string;
  readonly threshold?: number;
  readonly threshold_text?: string;
  readonly metric?: string;
  readonly oos_rows_used_for_fit?: number;
  readonly max_slot_count?: number;
  readonly selection_cardinality?: string;
  readonly hold_cash_action?: boolean;
  readonly tie_break?: readonly string[];
}

export interface DailyCloseSlotWalkForwardSummary {
  readonly mode_id?: string;
  readonly window_count?: number;
  readonly threshold_grid_count?: number;
  readonly oos_rows_used_for_fit?: number;
  readonly held_out_replay_splits?: readonly string[];
  readonly held_out_window_count?: number;
  readonly windows?: readonly Record<string, unknown>[];
}

export interface DailyCloseSlotReplaySummary {
  readonly mode_id?: string;
  readonly episode_count?: number;
  readonly split_counts?: Readonly<Record<string, number>>;
  readonly slot_feedback_count?: number;
  readonly held_out_feedback_used_for_fit_count?: number;
}

export interface DailyCloseSlotDataRecency {
  readonly latest_data_date?: string | null;
  readonly configured_research_date?: string | null;
  readonly is_today?: boolean;
  readonly label?: string;
}

export interface DailyCloseSlotLatestSelectionSecondaryEntry {
  readonly date?: string | null;
  readonly split?: string;
  readonly label?: string;
}

export interface DailyCloseSlotLatestSelection {
  readonly policy?: string;
  readonly date?: string | null;
  readonly split?: string;
  readonly cost_scenario_id?: string;
  readonly seed?: number | null;
  readonly source_run_id?: string | null;
  readonly artifact_age_seconds?: number | null;
  readonly label?: string;
  readonly missing_test_split_evidence?: boolean;
  readonly secondary?: {
    readonly train?: DailyCloseSlotLatestSelectionSecondaryEntry;
    readonly val?: DailyCloseSlotLatestSelectionSecondaryEntry;
    readonly val_plus_test?: DailyCloseSlotLatestSelectionSecondaryEntry;
  };
}


export interface DailyCloseSlotSelectedHoldRow {
  readonly policy?: string;
  readonly split?: string;
  readonly cost_scenario_id?: string;
  readonly selected_count?: number;
  readonly hold_cash_count?: number;
  readonly total_component_bp?: number;
  readonly reward?: number;
}

export interface DailyCloseSlotSelectedHoldSummary {
  readonly primary_cost_scenario_id?: string;
  readonly max_slot_count?: number;
  readonly selection_cardinality?: string;
  readonly hold_cash_action?: boolean;
  readonly rows?: readonly DailyCloseSlotSelectedHoldRow[];
}

export interface DailyCloseSlotPolicyScoreRow {
  readonly date?: string;
  readonly split?: string;
  readonly table?: string;
  readonly code?: string;
  readonly score?: number | string;
  readonly policy?: string;
  readonly fill_mode?: string;
  readonly execution_realism?: string;
  readonly round_trip_cost_bp?: number | string;
  readonly upstream_gate_blockers?: string;
  readonly [key: string]: unknown;
}

export interface DailyCloseSlotSelectionRow {
  readonly date?: string;
  readonly policy?: string;
  readonly action_label?: string;
  readonly slot?: number | string;
  readonly code?: string;
  readonly status?: string;
  readonly unfilled_reason?: string;
  readonly shares?: number | string;
  readonly entry_close?: number | string;
  readonly next_close?: number | string;
  readonly net_pnl_krw?: number | string;
  readonly cost_krw?: number | string;
  readonly fill_mode?: string;
  readonly research_only?: boolean;
  readonly [key: string]: unknown;
}

export interface DailyCloseSlotSamples {
  readonly baseline_summary?: readonly Record<string, unknown>[];
  readonly policy_scores?: readonly DailyCloseSlotPolicyScoreRow[];
  readonly threshold_search?: readonly Record<string, unknown>[];
  readonly cost_scenario_summary?: readonly Record<string, unknown>[];
  readonly date_ledgers?: Record<string, unknown>;
}

export interface DailyCloseSlotDbAccess {
  readonly access_mode?: string;
  readonly sqlite_uri_mode?: string;
  readonly pragma_query_only?: boolean;
  readonly mutation_allowed?: boolean;
  readonly connection_helper?: string;
}


export interface DailyCloseSlotLatestResponse {
  readonly surface?: string;
  readonly status?: string;
  readonly readiness_status?: string;
  readonly artifact_status?: string;
  readonly dashboard_validation_status?: string;
  readonly lineage_validation_status?: string;
  readonly run_id?: string;
  readonly read_only?: boolean;
  readonly promotion_allowed?: boolean;
  readonly model_build_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly profitability_claim_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly labels?: readonly string[];
  readonly guardrail?: string;
  readonly read_only_dashboard_note?: string;
  readonly source_run_ids?: Readonly<Record<string, unknown>>;
  readonly train_schema_version?: number;
  readonly cost_model_schema_version?: number;
  readonly gate_report?: Readonly<Record<string, unknown>>;
  readonly daily_db_access?: DailyCloseSlotDbAccess;
  readonly dataset_db_access?: DailyCloseSlotDbAccess;
  readonly gate_report_dataset_db_access?: DailyCloseSlotDbAccess;
  readonly gate_report_train_dataset_db_access?: DailyCloseSlotDbAccess;
  readonly fit_summary?: Readonly<Record<string, unknown>>;
  readonly d3_comparator?: Readonly<Record<string, unknown>>;
  readonly required_baselines?: readonly string[];
  readonly present_baselines?: readonly string[];
  readonly round_trip_cost_bp?: number;
  readonly cost_sensitivity_bp?: readonly number[];
  readonly slot_count?: number;
  readonly primary_cost_scenario_id?: string;
  readonly cost_components?: readonly string[];
  readonly cost_scenarios?: Readonly<Record<string, DailyCloseSlotCostScenario>>;
  readonly max_slot_count?: number;
  readonly selection_cardinality?: string;
  readonly hold_cash_action?: boolean;
  readonly threshold_selection?: DailyCloseSlotThresholdSelection;
  readonly walk_forward_summary?: DailyCloseSlotWalkForwardSummary;
  readonly replay_summary?: DailyCloseSlotReplaySummary;
  readonly selected_hold_summary?: DailyCloseSlotSelectedHoldSummary;
  readonly false_locks?: Readonly<Record<string, boolean>>;
  readonly no_claim_labels?: readonly string[];
  readonly total_capital_krw?: number;
  readonly integer_shares_primary?: boolean;
  readonly fill_mode?: string;
  readonly execution_realism?: string;
  readonly price_basis?: string;
  readonly price_basis_status?: string;
  readonly decision_grade_return_status?: string;
  readonly universe_verdict?: string;
  readonly universe_review_status?: string;
  readonly current_required_blockers?: readonly string[];
  readonly upstream_gate_blockers?: readonly string[];
  readonly dataset_lineage?: Readonly<Record<string, unknown>>;
  readonly row_counts?: Readonly<Record<string, unknown>>;
  readonly dataset_source_counts?: Readonly<Record<string, unknown>>;
  readonly bounded_research_scope?: Readonly<Record<string, unknown>>;
  readonly samples?: DailyCloseSlotSamples;
  readonly artifact_age_seconds?: number | null;
  readonly data_recency?: DailyCloseSlotDataRecency;
  readonly close_slot_blockers?: readonly string[];
  readonly chosen_is_no_trade_sentinel?: boolean | null;
  readonly artifact_selection_errors?: readonly string[];
}

export interface DailyCloseSlotArtifactsResponse {
  readonly runs?: readonly Record<string, unknown>[];
  readonly read_only_dashboard_note?: string;
}

export interface DailyCloseSlotEquityResponse {
  readonly surface?: string;
  readonly status?: string;
  readonly readiness_status?: string;
  readonly run_id?: string;
  readonly source_run_ids?: Readonly<Record<string, unknown>>;
  readonly labels?: readonly string[];
  readonly round_trip_cost_bp?: number;
  readonly fill_mode?: string;
  readonly execution_realism?: string;
  readonly read_only?: boolean;
  readonly promotion_allowed?: boolean;
  readonly model_build_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly profitability_claim_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly guardrail?: string;
  readonly series?: readonly {
    readonly policy?: string;
    readonly points?: readonly Record<string, unknown>[];
  }[];
  readonly artifact_selection_errors?: readonly string[];
}

export interface DailyCloseSlotSelectionResponse {
  readonly surface?: string;
  readonly status?: string;
  readonly readiness_status?: string;
  readonly run_id?: string;
  readonly source_run_ids?: Readonly<Record<string, unknown>>;
  readonly labels?: readonly string[];
  readonly policy?: string;
  readonly slot_count?: number;
  readonly round_trip_cost_bp?: number;
  readonly threshold_selection?: DailyCloseSlotThresholdSelection;
  readonly selected_hold_summary?: DailyCloseSlotSelectedHoldSummary;
  readonly cost_scenarios?: Readonly<Record<string, DailyCloseSlotCostScenario>>;
  readonly cost_components?: readonly string[];
  readonly false_locks?: Readonly<Record<string, boolean>>;
  readonly no_claim_labels?: readonly string[];
  readonly read_only?: boolean;
  readonly promotion_allowed?: boolean;
  readonly model_build_allowed?: boolean;
  readonly paper_forward_allowed?: boolean;
  readonly live_broker_order_allowed?: boolean;
  readonly profitability_claim_allowed?: boolean;
  readonly go_summary_allowed?: boolean;
  readonly guardrail?: string;
  readonly selection_rows?: readonly DailyCloseSlotSelectionRow[];
  readonly selection_rows_label?: string;
  readonly latest_selection?: DailyCloseSlotLatestSelection;
  readonly data_recency?: DailyCloseSlotDataRecency;
  readonly close_slot_blockers?: readonly string[];
  readonly chosen_is_no_trade_sentinel?: boolean | null;
  readonly policy_score_sample?: readonly DailyCloseSlotPolicyScoreRow[];
  readonly artifact_selection_errors?: readonly string[];
}




export const dailyOhlcvApi = {
  progress: () => fetchJson<DailyProgressResponse>('/api/daily-ohlcv/progress'),
  dbSummary: () => fetchJson<DailyDbSummaryResponse>('/api/daily-ohlcv/db-summary?table_limit=25&flag_limit=25&window_limit=10'),
  universePreview: () => fetchJson<DailyUniverseResponse>('/api/daily-ohlcv/universe/preview?limit=25'),
  artifacts: () => fetchJson<DailyArtifactsResponse>('/api/daily-ohlcv/artifacts?limit=25'),
  datasetLatest: () => fetchJson<DailyDatasetResponse>('/api/daily-ohlcv/dataset/latest?limit=15'),
  datasetChart: () => fetchJson<DailyDatasetChartResponse>('/api/daily-ohlcv/charts/dataset'),
  predictionLatest: () => fetchJson<DailyPredictionResponse>('/api/daily-ohlcv/prediction/latest?limit=15'),
  portfolioLatest: () => fetchJson<DailyPortfolioResponse>('/api/daily-ohlcv/portfolio/latest?limit=15'),
  walkForwardLatest: () => fetchJson<DailyWalkForwardResponse>('/api/daily-ohlcv/walk-forward/latest?limit=15'),
  registryLatest: () => fetchJson<DailyRegistryResponse>('/api/daily-ohlcv/registry/latest?limit=15'),
  predictionChart: () => fetchJson<DailyModelChartResponse>('/api/daily-ohlcv/charts/prediction'),
  portfolioChart: () => fetchJson<DailyModelChartResponse>('/api/daily-ohlcv/charts/portfolio'),
  walkForwardChart: () => fetchJson<DailyModelChartResponse>('/api/daily-ohlcv/charts/walk-forward'),
  gateLatest: () => fetchJson<DailyModelChartResponse>('/api/daily-ohlcv/gate/latest'),
  decisionCockpitChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/decision-cockpit'),
  scenarios: () => fetchJson<DailyScenarioLabResponse>('/api/daily-ohlcv/scenarios'),
  scenarioRuns: () => fetchJson<DailyScenarioRunLedgerResponse>('/api/daily-ohlcv/scenario-runs?limit=25'),
  rlEnvGuide: () => fetchJson<DailyRlEnvGuideResponse>('/api/daily-ohlcv/rl-env-guide'),
  researchWorkflows: () => fetchJson<DailyResearchWorkflowCatalogResponse>('/api/daily-ohlcv/research-workflows'),
  researchWorkflowDetail: (workflowId: string) => fetchJson<DailyResearchWorkflowDetailResponse>(`/api/daily-ohlcv/research-workflows/${encodeURIComponent(workflowId)}`),
  researchJobIntents: (workflowId: string, payload: DailyResearchJobIntentRequest) => fetchJson<DailyResearchJobIntentDetailResponse>(
    `/api/daily-ohlcv/research-workflows/${encodeURIComponent(workflowId)}/job-intents`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }
  ),
  researchJobs: () => fetchJson<DailyResearchJobIntentLedgerResponse>('/api/daily-ohlcv/research-jobs?limit=25'),
  researchJobDetail: (intentId: string) => fetchJson<DailyResearchJobIntentDetailResponse>(`/api/daily-ohlcv/research-jobs/${encodeURIComponent(intentId)}`),
  rejectionAnalytics: () => fetchJson<DailyRejectionAnalyticsResponse>('/api/daily-ohlcv/rejection-analytics?limit=25'),
  marketRegimeAudit: () => fetchJson<DailyMarketRegimeAuditResponse>('/api/daily-ohlcv/market-regime-audit?limit=25'),
  closeSlotLatest: () => fetchJson<DailyCloseSlotLatestResponse>('/api/daily-ohlcv/close-slot/latest?limit=15'),
  closeSlotArtifacts: () => fetchJson<DailyCloseSlotArtifactsResponse>('/api/daily-ohlcv/close-slot/artifacts?limit=10'),
  closeSlotGate: () => fetchJson<DailyCloseSlotLatestResponse>('/api/daily-ohlcv/close-slot/gate/latest'),
  closeSlotEquity: () => fetchJson<DailyCloseSlotEquityResponse>('/api/daily-ohlcv/charts/close-slot-equity'),
  closeSlotSelection: () => fetchJson<DailyCloseSlotSelectionResponse>('/api/daily-ohlcv/charts/close-slot-selection?limit=20'),
  flowChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/flow'),
  glossaryChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/glossary'),
  researchDiagnosticsChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/research-diagnostics'),
  equityOverlayChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/equity-overlay'),
  walkForwardHeatmapChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/walk-forward-heatmap'),
  runScatterChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/run-scatter'),
  universeBreakdownChart: () => fetchJson<DailyVisualChartResponse>('/api/daily-ohlcv/charts/universe-breakdown'),
  symbolChart: (code: string, limit: number = 160) => fetchJson<DailyVisualChartResponse>(`/api/daily-ohlcv/charts/symbol/${encodeURIComponent(code)}?limit=${limit}`),
  symbol: (code: string, limit: number = 20) => fetchJson<DailySymbolResponse>(`/api/daily-ohlcv/symbol/${encodeURIComponent(code)}?limit=${limit}`),
};

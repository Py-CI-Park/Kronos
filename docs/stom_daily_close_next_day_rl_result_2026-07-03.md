# Daily Close-to-Next-Close 10-Slot 연구 결과 및 Dashboard Evidence (2026-07-03)

## Verdict

- **Verdict:** `WATCH_RESEARCH_ONLY`
- **Dashboard validation:** `PASS`
- **Artifact status:** `LOADED_GENERATED_ARTIFACT`
- **Scope:** bounded latest-evidence research artifact only (`max_symbols=120`, `max_rows_per_symbol=260`), not full-universe proof.
- **No claim:** live/broker/account/order/paper-forward/profitability/model-build/GO readiness claim 없음.
- **Blockers preserved:** `D0_PRICE_BASIS_NOT_VERIFIED`, `D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED`.

## Run IDs

|Lane|Run ID|
|---|---|
|Dataset|`daily_close_slot_research_dataset_2026_07_03`|
|Train/Policy|`daily_close_slot_research_policy_2026_07_03`|
|Gate|`daily_close_slot_research_gate_2026_07_03`|

## Artifact Paths and Hashes

|Kind|Path|Manifest/File hash|
|---|---|---|
|Dataset manifest|`webui/rl_runs/daily_close_slot_dataset/daily_close_slot_research_dataset_2026_07_03/close_slot_dataset_manifest.json`|manifest_sha `7eb208e68c4b6359d8c2c8ddaaf4c280700539f5f05bcd57f90316e630697829` / file `5c665e8c1e314543d8cc40fe96c9df1c0566a3d5c1b21b6d2087d6eebe5a0790`|
|Train manifest|`webui/rl_runs/daily_close_slot_train/daily_close_slot_research_policy_2026_07_03/close_slot_train_manifest.json`|manifest_sha `59e3bec0960e54ffe1f1157852077a392deee6687a305a0270abacd930b5183f` / file `699fb8bb01b2a01a99706fc9f7b0f582fbe52c81ed585879d45bc77c95e64563`|
|Gate report|`webui/rl_runs/daily_close_slot_gate/daily_close_slot_research_gate_2026_07_03/gate_report.json`|file `2196ce4d5c62c95e7a464461b38304085a772571677de08d4e02fb76694febc4`|
|Gate manifest|`webui/rl_runs/daily_close_slot_gate/daily_close_slot_research_gate_2026_07_03/close_slot_gate_manifest.json`|manifest_sha `7ec73f327f0222c17c4e73dfdea109f08e5ff8cd8c36f81c22beefce6e5b4a1a` / file `bc68f04b840f52716e151dacce81be03cac7d5e21bf6a438ea849184c292b665`|
|Dashboard evidence receipt|`artifacts/close_price_research_g003_dashboard_evidence.json`|generated in G003|

## Dataset Scope and Splits

|Item|Value|
|---|---|
|Universe symbols total|4727|
|Included symbols total|2599|
|Included symbols used|120|
|Max symbols|120|
|Max rows per symbol|260|
|Close-slot panel rows|31200|
|Eligible rows|28182|
|Train rows|18720|
|Blocked purge/embargo rows|1200|
|Validation rows|5640|
|Test rows|5640|
|Train date range|{'start': '20250520', 'end': '20260107', 'unique_dates': 156}|
|Validation date range|{'start': '20260115', 'end': '20260326', 'unique_dates': 47}|
|Test date range|{'start': '20260403', 'end': '20260612', 'unique_dates': 47}|

## Cost, Action, Replay Contract

|Item|Value|
|---|---|
|Primary cost scenario|`base_23bp`|
|Cost sensitivity bp|`[0, 23, 46]`|
|zero_control_0bp|`{'buy_commission_bp': 0.0, 'buy_slippage_bp': 0.0, 'scenario_id': 'zero_control_0bp', 'sell_commission_bp': 0.0, 'sell_slippage_bp': 0.0, 'sell_tax_bp': 0.0, 'total_bp': 0.0}`|
|base_23bp|`{'buy_commission_bp': 1.5, 'buy_slippage_bp': 0.0, 'scenario_id': 'base_23bp', 'sell_commission_bp': 1.5, 'sell_slippage_bp': 0.0, 'sell_tax_bp': 20.0, 'total_bp': 23.0}`|
|stress_46bp|`{'buy_commission_bp': 1.5, 'buy_slippage_bp': 11.5, 'scenario_id': 'stress_46bp', 'sell_commission_bp': 1.5, 'sell_slippage_bp': 11.5, 'sell_tax_bp': 20.0, 'total_bp': 46.0}`|
|Threshold policy|`contextual_bandit_linear_train_only_score_and_pick`|
|Threshold split|`train`|
|Threshold text|`1329615.44374`|
|Threshold metric|`mean_daily_reward_base_23bp`|
|OOS rows used for fit|`0`|
|Selection cardinality|`threshold_selected_0_to_10`|
|Hold cash action|`True`|
|Walk-forward mode|`expanding_train_replay_reward_weighted_refit_v1`|
|Walk-forward windows|`6`|
|Replay episodes|`190`|
|Held-out feedback used for fit|`0`|
|Selected/hold primary cost|`base_23bp`|

## Baseline Deltas (base_23bp, bounded research only)

|policy|cum_reward_base_23bp|delta_vs_no_trade|delta_vs_shuffle|action_allowed|
|---|---|---|---|---|
|no_trade_control|0|0|0.474792831715|False|
|deterministic_shuffle_top10_control|-0.474792831715|-0.474792831715|0|False|
|momentum_top10_score_and_pick|0.308848100415|0.308848100415|0.78364093213|True|
|contextual_bandit_linear_train_only_score_and_pick|0|0|0.474792831715|True|

해석 주의: 위 표는 bounded research artifact의 회계 요약이다. D0/D1 blockers가 살아 있으므로 decision-grade profitability, live/paper readiness, deployable-alpha 결론으로 사용하지 않는다. `deterministic_shuffle_top10_control`은 baseline/control이며 policy action이 아니다. `ts_imb`는 이 문서에서 RL로 분류하지 않는다.

## Dashboard/API Evidence

|endpoint|http|surface|status|dashboard_validation|artifact_status|
|---|---|---|---|---|---|
|latest|200|daily_close_slot|WATCH_RESEARCH_ONLY|PASS|LOADED_GENERATED_ARTIFACT|
|gate|200|daily_close_slot_gate|WATCH_RESEARCH_ONLY|PASS|LOADED_GENERATED_ARTIFACT|
|artifacts|200|None|None|n/a|n/a|
|equity|200|daily_close_slot_equity|WATCH_RESEARCH_ONLY|n/a|n/a|
|selection|200|daily_close_slot_selection|WATCH_RESEARCH_ONLY|n/a|n/a|

Read-only evidence:

|Item|Value|
|---|---|
|Dashboard note|`GET-only daily close-slot research evidence; no training/order/live/profit action from dashboard.`|
|DB access|`{'access_mode': 'read_only', 'connection_helper': 'stom_rl.daily_ohlcv_db.connect_readonly', 'mutation_allowed': False, 'pragma_query_only': True, 'sqlite_uri_mode': 'ro'}`|
|Bounded scope|`{'max_rows_per_symbol': 260, 'max_symbols': 120, 'scope_label': 'bounded_latest_evidence_not_full_universe_or_decision_grade'}`|
|Current required blockers|`['D0_PRICE_BASIS_NOT_VERIFIED', 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED']`|
|Upstream gate blockers|`['D0_PRICE_BASIS_NOT_VERIFIED', 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED']`|
|Gate report|`{'artifact_kind': 'daily_close_slot_gate_report', 'checked_at': '2026-07-03T14:51:52Z', 'cost_sensitivity_bp': [0, 23, 46], 'd3_comparator': {'present': False, 'reledgered_through_close_slot_accounting': False, 'source_score_path': None}, 'dataset_lineage_status': 'PASS', 'dataset_manifest_sha': '7eb208e68c4b6359d8c2c8ddaaf4c280700539f5f05bcd57f90316e630697829', 'dataset_run_id': 'daily_close_slot_research_dataset_2026_07_03', 'errors': [], 'fit_summary': {'feedback_weighted_refit_used': True, 'feedback_weighted_train_rows': 200, 'initial_threshold_text': '1327380.4019', 'oos_rows_used_for_fit': 0, 'policy': 'contextual_bandit_linear_train_only_score_and_pick', 'selection_threshold': 1329615.4437358805, 'threshold_text': '1329615.44374', 'train_rows': 17765, 'weights': {'foreign_holding_ratio': 6.16878978352081e-05, 'gap_from_prev_close': -1.0619584537994469e-07, 'hl_range': 1.2294127727196024e-07, 'institutional_net_buy': -0.9999010658820514, 'return_1d': 2.296466057561133e-07, 'return_5d': 5.398158154734178e-06, 'volatility_5d': 5.062430455053096e-07, 'volume_ratio_5d': 3.088303518477659e-05}}, 'gate_status': 'WATCH_RESEARCH_ONLY', 'lineage_schema_version': 1, 'present_baselines': ['contextual_bandit_linear_train_only_score_and_pick', 'deterministic_shuffle_top10_control', 'momentum_top10_score_and_pick', 'no_trade_control'], 'required_baselines': ['deterministic_shuffle_top10_control', 'no_trade_control'], 'research_lane': 'daily_close_slot', 'round_trip_cost_bp': 23, 'schema_version': 1, 'split_policy': {'embargo_days': 5, 'method': 'chronological_train_val_test_with_purge_embargo', 'purge_days': 5, 'test_fraction': 0.2, 'train_fraction': 0.6, 'val_fraction': 0.2}, 'status': 'PASS', 'train_manifest_sha': '59e3bec0960e54ffe1f1157852077a392deee6687a305a0270abacd930b5183f', 'train_only_fit': True, 'train_run_id': 'daily_close_slot_research_policy_2026_07_03', 'upstream_gate_blockers': ['D0_PRICE_BASIS_NOT_VERIFIED', 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED'], 'validation_test_no_retune': True}`|

## False Locks / No-Claim Flags

|flag|value|
|---|---|
|go_summary_allowed|False|
|live_broker_order_allowed|False|
|model_build_allowed|False|
|paper_forward_allowed|False|
|profitability_claim_allowed|False|
|promotion_allowed|False|

No-claim labels: `['NO_LIVE_BROKER_ORDER_ACCOUNT_SURFACE', 'NO_PAPER_FORWARD_EXECUTION', 'NO_MODEL_BUILD_GO', 'NO_PROFITABILITY_CLAIM', 'RULE_OR_REPLAY_EVIDENCE_ONLY']`

## Verification Commands

|command|result|
|---|---|
|py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_api.py::test_daily_close_slot_dashboard_endpoints_expose_read_only_gate_payload tests/test_daily_ohlcv_dashboard_api.py::test_daily_close_slot_dashboard_fails_closed_on_hash_and_current_d1_mismatch tests/test_daily_ohlcv_dashboard_tab.py -q|4 passed in 7.62s|
|py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_api.py tests/test_daily_ohlcv_dashboard_tab.py -q|56 passed in 18.47s|
|npm run build (cwd webui/v2_src)|svelte-check 0 errors / 4 existing warnings; vite build succeeded|

## Final G003 Interpretation

The latest dashboard evidence is available through GET-only Daily OHLCV close-slot API surfaces and the Svelte DailyCloseSlotCard markers. The dashboard surfaces the generated bounded artifacts, read-only DB proof, source scope, component costs, train-only threshold/replay, selected/cash-hold evidence, baseline deltas, and fail-closed blockers. The result remains **WATCH_RESEARCH_ONLY** and must not be presented as live trading readiness, broker readiness, paper-forward readiness, profitability, model-build permission, deployable alpha, or GO.

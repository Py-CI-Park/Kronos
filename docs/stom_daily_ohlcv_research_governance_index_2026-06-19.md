# Daily OHLCV Research Governance Index — 2026-06-19

Date: 2026-06-19 UTC  
Status: `ACTIVE_RESEARCH_LEDGER`  
Supersedes: `docs/stom_daily_ohlcv_research_governance_index_2026-06-18.md`  
Scope: Daily OHLCV D0-D9 research governance, market-regime data-quality audit preregistration, non-live maturity roadmap

## Purpose

This index keeps the Daily OHLCV research history findable and auditable after the dashboard-first platform and lane-based PR stack were merged. Durable decisions remain in `docs/`; generated/session evidence remains in `webui/rl_runs/` or explicitly selected `artifacts/`; source/tests remain in `stom_rl/`, `webui/`, and `tests/`.

The system remains research-only: no live/broker/orders, no profit claims, no paper-forward/model-build promotion while D5 is `NO-GO`.

## Latest merged platform stack

| PR | Lane | Status | Meaning |
|---:|---|---|---|
| #2 | Daily OHLCV/RL core | `MERGED` | Core research modules/tests landed on `feature/stom-rl-lab`. |
| #3 | Dashboard backend/API | `MERGED` | Read-only Daily OHLCV dashboard APIs landed. |
| #4 | Dashboard frontend source | `MERGED` | Dashboard source for Daily RL Guide/workflows landed. |
| #5 | Dashboard frontend dist | `MERGED` | Committed dist rebuilt after source lane. |
| #6 | Docs/governance | `MERGED` | Dashboard-first governance docs landed. |

Latest observed merged base for this plan: `origin/feature/stom-rl-lab` at `34dbe2af5a64`.

## Current latest research chain

| Order | Document | Type | Status | Artifact anchor |
|---:|---|---|---|---|
| 1 | `docs/stom_daily_ohlcv_rl_continuation_prereg_2026-06-14.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | D4 reward/action continuation plan |
| 2 | `docs/stom_daily_ohlcv_d4_rl_visualization_result_2026-06-14.md` | result | `RESEARCH_ONLY` | D4 visual/telemetry evidence |
| 3 | `docs/stom_daily_ohlcv_d4_no_trade_diagnostic_result_2026-06-16.md` | result | `NO-GO_RESEARCH_ONLY` | `scenario_batch_no_trade_diag_001` |
| 4 | `docs/stom_daily_ohlcv_d4_action_induction_v2_prereg_2026-06-16.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | D4 action-induction v2 frozen plan |
| 5 | `docs/stom_daily_ohlcv_d4_action_induction_v2_result_2026-06-17.md` | result | `NO-GO_RESEARCH_ONLY` | `scenario_batch_d4_action_induction_v2_001` |
| 6 | `docs/stom_daily_ohlcv_d4_trade_quality_filter_prereg_2026-06-17.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | D4 trade-quality/abstention plan |
| 7 | `docs/stom_daily_ohlcv_d4_trade_quality_filter_result_2026-06-17.md` | result | `NO-GO_RESEARCH_ONLY` | `scenario_batch_d4_trade_quality_filter_001` |
| 8 | `docs/stom_daily_ohlcv_d3_d4_signal_quality_audit_prereg_2026-06-18.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | D3/D4 signal-quality diagnostic contract |
| 9 | `docs/stom_daily_ohlcv_d3_d4_signal_quality_audit_result_2026-06-18.md` | result | `WATCH_DIAGNOSTIC_ONLY` / `NO-GO_RESEARCH_ONLY` | `scenario_batch_signal_quality_audit_001` |
| 10 | `docs/stom_daily_ohlcv_dashboard_scenario_generator_result_2026-06-18.md` | dashboard result | `IMPLEMENTED_RESEARCH_ONLY_DASHBOARD` / `NO-GO_RESEARCH_ONLY` | Daily RL Guide priority 1-5 scenario generator/maturity UI |
| 11 | `docs/stom_daily_ohlcv_dashboard_first_research_platform_adr_2026-06-18.md` | ADR | `ACCEPTED_FOR_RESEARCH_PLATFORM_EXECUTION` / `RESEARCH_ONLY` | Dashboard-first, CLI-internal, no-live job-intent contract |
| 12 | `docs/stom_daily_ohlcv_hypothesis_rejection_audit_prereg_2026-06-18.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | Gate-funnel / early-dropout / false-negative audit contract |
| 13 | `docs/stom_daily_ohlcv_dashboard_first_research_platform_completion_result_2026-06-18.md` | result | `IMPLEMENTED_RESEARCH_ONLY_DASHBOARD_PLATFORM` | Non-live dashboard/research platform `100%`; live/model/paper readiness `0%` |
| 14 | `docs/stom_daily_ohlcv_past_only_market_regime_data_quality_audit_prereg_2026-06-19.md` | preregistration | `PREREGISTERED_RESEARCH_ONLY` | D0/D1/market-regime data-quality audit contract |
| 15 | `docs/stom_daily_ohlcv_non_live_maturity_roadmap_2026-06-19.md` | roadmap | `NON_LIVE_MATURITY_ROADMAP` | PR-7 to PR-10 maturity gates |
| 16 | `docs/stom_daily_ohlcv_past_only_market_regime_data_quality_audit_result_2026-06-19.md` | result | `COMPLETED_RESEARCH_ONLY` / `BLOCKER_EVIDENCE_RECORDED_NO_PROMOTION` | `market_regime_audit_2026_06_19_001` |
| 17 | `docs/stom_daily_ohlcv_pr10_artifact_selection_hardening_result_2026-06-19.md` | result | `COMPLETED_RESEARCH_ONLY` / `FAIL_CLOSED_LATEST_INVALID` | PR-10 latest-artifact selection hardening |

## Latest generated evidence

| Evidence | Path | Meaning |
|---|---|---|
| Signal-quality audit manifest | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/signal_quality_manifest.json` | Main run metadata, source hashes, cost sensitivity, guardrails, and required artifact map. |
| Signal-quality bucket metrics | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/signal_quality_bucket_metrics.csv` | Score/sign/margin/confidence buckets with source timing, future-label flags, split/fold metadata, and 0/23/46bp rows. |
| Risk proxy metrics | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/risk_proxy_bucket_metrics.csv` | Past/current pre-action risk proxy buckets with proxy status, D3 deltas, turnover proxy, and cost rows. |
| Baseline controls | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/baseline_control_metrics.csv` | Measured no-trade, shuffle, equal-weight top-k, and frozen D3 controls. |
| Leakage audit | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/signal_quality_leakage_audit.json` | Feature timing and future-label evaluation-only audit. |
| Hypothesis rejection analytics manifest | `webui/rl_runs/daily_ohlcv_rejection_audit/hypothesis_rejection_audit_2026_06_18_001/audit_manifest.json` | Gate-funnel, rejection taxonomy, calibration, threshold sensitivity, false-negative review-only row counts, hashes, and research-only locks. |
| Market-regime audit preregistration plan | `artifacts/scenario_batch_market_regime_audit_001_plan.json` | Frozen PR-7 scenario matrix for the next evidence-producing audit; no run outputs yet. |
| Market-regime audit manifest | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/market_regime_audit_manifest.json` | Source-ref `0b46367` plus explicit source hashes; 4,727 table denominator, 25 sampled tables, D0/D1 blockers, leakage pass, stale-artifact pass, promotion false. |
| PR-10 artifact-selection hardening | `docs/stom_daily_ohlcv_pr10_artifact_selection_hardening_result_2026-06-19.md` | Latest malformed D2/D3/D4/D5 artifacts fail closed with `BLOCKED_INVALID_LATEST_ARTIFACT`; universe/dataset listing rows expose invalid-artifact errors instead of crashing or falling back. |

## Current findings snapshot

| Finding | Evidence | Status |
|---|---|---|
| D4 trade-quality filters | Abstention telemetry works, but all five D4 scenarios underperformed no-trade/best D3 after 23bp cost. | `NO-GO_RESEARCH_ONLY` |
| D3/D4 signal quality | Diagnostic artifacts expose score/margin/confidence/risk proxy timing and baseline controls. Fold evidence is mixed: test F05 favorable, test F03 negative, F04 near zero. | `WATCH_DIAGNOSTIC_ONLY` |
| Baseline controls | Signal-quality audit measures no-trade, shuffle, equal-weight top-k, and frozen D3 controls. | Required comparator visibility restored |
| Label leakage | Bucket/proxy rows include source timing and future-label flags; lagged drawdown-path proxies are t-1 generated-artifact inputs. | Current audit passes no-leakage checks but needs stronger market-regime provenance |
| D5 gate | Latest signal-quality run is diagnostic only and does not run or pass a D5 promotion gate. | Model-build/paper/live blocked |
| Dashboard-first completion | Workflow center, inspector, safe config preview, approval-gated intent ledger, rejection analytics, and completion panel are integrated. | Non-live platform `100%`; live/model/paper readiness `0%` |
| Market-regime data-quality audit | PR-8 runner emitted source-hashed artifacts for 25 sampled tables out of 4,727 denominator tables. D0 price basis is `UNKNOWN_CONFIRMED`; D1 missingness/universe remains WATCH/blocker evidence; leakage and stale-artifact checks pass. | `COMPLETED_RESEARCH_ONLY`; no D5/model/paper/live promotion |
| PR-10 artifact selection | D2 dataset, D3 prediction, D4 portfolio, D5 walk-forward, D1 universe listing, and D2 dataset listing now fail closed on malformed latest JSON evidence and do not fall back to older optimistic runs. | `COMPLETED_RESEARCH_ONLY`; non-live maturity evidence-selection gate complete |

## Data governance checklist

| Check | Required evidence |
|---|---|
| Source provenance | Source hashes in run manifests or documented commit/session reference. |
| Artifact provenance | Manifest paths and artifact hashes for generated outputs. |
| Cost accounting | 23bp default cost in docs and manifests; 0/23/46bp sensitivity before promotion discussion. |
| Split integrity | Train/val/test or fold metadata; no OOS retuning. |
| Label leakage | State/feature manifest and tests showing future labels are not used in decision-time features. |
| Baseline controls | no-trade, shuffle, equal-weight top-k, and frozen D3 comparison for D4/D5 claims. |
| Price basis | Adjusted/raw/split/dividend basis must be verified or explicitly blocked before decision-grade returns. |
| Universe quality | Universe breadth, missingness, and leading-zero code preservation must be measured. |
| Past-only regime proxies | Volatility/drawdown/breadth/dispersion/liquidity proxies must be computed from t or t-1 data, never future labels. |
| Status flags | `model_build_allowed=false`, `go_summary_allowed=false`, `paper_forward_allowed=false`, `live_broker_order_allowed=false`, `profitability_claim_allowed=false` unless a later approved gate changes them. |
| Generated vs durable separation | Generated artifacts under `webui/rl_runs/`; decisions under `docs/`. |
| Failure visibility | `NO-GO`/blocker reasons visible in docs and dashboard; no marketing language. |

## Current blockers that remain active

| Blocker | Current meaning |
|---|---|
| D0 price basis | Return labels are not independently verified as adjusted/raw/split/dividend safe. |
| D1 universe | Universe remains heuristic/WATCH without complete official/manual validation. |
| D3 baseline | Frozen D3 remains a comparator, not model-build approval. Signal-quality evidence is mixed and diagnostic only. |
| D4 RL | Action reachability and abstention telemetry exist, but D4 variants still lack cost-aware, fold-consistent superiority. |
| D5 gate | `NO-GO`; no model build, paper-forward, live trading, broker integration, or orders. |
| D8/D9 registry | Audit evidence only; live/broker/order readiness blocked. |

## Next research pointer

PR-7 through PR-10 are complete for the planned non-live research maturity lane. The next step is **final integration and maturity reporting**: verify the integrated branch state, document commit/PR readiness, and report the honest maturity score.

Allowed follow-up research remains separate and must be preregistered on a fresh branch:

- factory/probability/calibration work after data-quality blockers are acknowledged,
- opening_30m/intraday work under its own horizon-specific preregistration,
- D0 price-basis or D1 official-universe evidence collection.

Required locks stay unchanged: D5/model-build/paper-forward/live status remains `NO-GO`/`0%` until a future approved gate passes.

Latest completed dashboard platform result:

`docs/stom_daily_ohlcv_dashboard_first_research_platform_completion_result_2026-06-18.md`

Latest preregistration:

`docs/stom_daily_ohlcv_past_only_market_regime_data_quality_audit_prereg_2026-06-19.md`

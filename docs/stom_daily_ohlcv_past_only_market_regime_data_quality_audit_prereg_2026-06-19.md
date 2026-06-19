# Daily OHLCV Past-Only Market-Regime Data Quality Audit Preregistration — 2026-06-19

Date: 2026-06-19 UTC  
Status: `PREREGISTERED_RESEARCH_ONLY`  
Scope: D0 price-basis, D1 universe/missingness, and past-only market-regime proxy validation for Daily OHLCV research  
Default cost assumption: 23bp round trip  
Live/model/paper readiness: `0%`, blocked

## Executive intent

This preregistration freezes a data-quality audit before any new Daily OHLCV model, D4 overlay, factory/probability lane, or paper/live discussion. The audit is **not** a trading result. It is a research-only gate that determines whether Daily OHLCV labels, universe coverage, and market-regime proxies are trustworthy enough for later falsification work.

## Research questions

| ID | Question | Required evidence | Decision impact |
|---|---|---|---|
| D0-Q1 | Are Daily OHLCV price/return labels adjusted, raw, split-adjusted, dividend-adjusted, or unknown? | DB metadata/proxy checks, schema scan, anomaly windows, split/dividend red flags | If unknown, decision-grade returns remain blocked. |
| D1-Q1 | Is the universe broad enough and missingness bounded enough for fold comparisons? | table count, row count, prefix counts, symbol coverage, missing row windows, stale symbols | If incomplete, universe remains `WATCH`/blocked. |
| R1-Q1 | Can volatility, drawdown, breadth, dispersion, and liquidity proxies be computed using only past/current data? | Feature timing fields, source timestamp, no future-label use, leakage audit | If not, regime overlays remain blocked. |
| R2-Q1 | Do regime buckets explain D3/D4 diagnostic failures or only describe them post hoc? | no-trade, shuffle, equal-weight top-k, frozen D3 controls under 0/23/46bp costs | Descriptive-only results cannot unlock D5. |
| S1-Q1 | Do stale/missing/malformed artifacts fail closed? | Missing-artifact tests, hash checks, manifest schema validation | Dashboard/API must not show optimistic maturity without evidence. |

## Inputs frozen before execution

| Input | Path / source | Notes |
|---|---|---|
| Daily OHLCV DB | `_database/Stock_Database_ohlcv_1day.db` | Local evidence only; read-only access required. |
| Existing D0/D1 helpers | `stom_rl/daily_ohlcv_db.py`, `stom_rl/daily_ohlcv_dataset.py`, `stom_rl/daily_ohlcv_universe.py` | Reuse read-only conventions and leading-zero symbol handling. |
| Signal-quality artifacts | `webui/rl_runs/daily_ohlcv_signal_quality/signal_quality_audit_2026_06_18_001/` | Prior diagnostic evidence; not retuned. |
| Dashboard-first artifacts | `webui/rl_runs/daily_ohlcv_rejection_audit/hypothesis_rejection_audit_2026_06_18_001/` and docs | Guardrail context only. |
| Scenario matrix | `artifacts/scenario_batch_market_regime_audit_001_plan.json` | Frozen PR-7 plan; PR-8 may execute against it. |

## Required output artifacts for PR-8

All generated run artifacts must live under:

`webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_YYYY_MM_DD_001/`

Required files:

| Artifact | Required fields |
|---|---|
| `market_regime_audit_manifest.json` | schema version, run id, created_at_utc, source commit, input paths, source hashes, artifact hashes, guardrail flags, verdict |
| `price_basis_audit.json` | status, component_status for adjusted/raw/split/dividend, anomaly windows, blocker reasons |
| `universe_quality.csv` | symbol code string, prefix, row count, first/last date, missing_count, stale flag, coverage bucket |
| `regime_proxy_metrics.csv` | split/fold, date bucket, volatility/drawdown/breadth/dispersion/liquidity proxy values, source_timing, future_label_used=false |
| `baseline_control_metrics.csv` | no-trade, shuffle, equal-weight top-k, frozen D3 controls, 0/23/46bp rows |
| `leakage_audit.json` | feature timing, future-label policy, violations, verdict |
| `stale_artifact_audit.json` | latest-selection inputs, stale/missing/malformed handling, fail-closed verdict |

## Frozen scenario matrix

| Scenario ID | Name | Purpose | Pass condition |
|---|---|---|---|
| MR-D0 | Price-basis audit | Classify or block adjusted/raw/split/dividend status | `PASS` only with documented basis; otherwise `BLOCKER_CONFIRMED` |
| MR-D1 | Universe breadth/missingness | Measure coverage, missingness, stale symbols, leading-zero preservation | `PASS` only with complete coverage evidence; `WATCH/BLOCKER` allowed |
| MR-R1 | Past-only proxy construction | Build volatility/drawdown/breadth/dispersion/liquidity proxies without future labels | `PASS` only if all source timing fields are pre-action/current |
| MR-R2 | Regime/control comparison | Compare proxy buckets against no-trade/shuffle/equal-weight/frozen D3 under costs | Diagnostic only; cannot unlock D5 |
| MR-S1 | Stale/latest artifact fail-closed | Verify missing/stale/malformed artifacts do not produce optimistic states | `PASS` only if all unsafe cases fail closed |

## Guardrails

- `model_build_allowed=false`
- `paper_forward_allowed=false`
- `live_broker_order_allowed=false`
- `go_summary_allowed=false`
- `profitability_claim_allowed=false`
- Browser/dashboard POST behavior remains approval-gated intent-record-only.
- No shell/worker/model/paper/live execution may be started from dashboard routes.
- Positive-looking regime/control rows are review-only until a future preregistered gate passes.

## Cost and controls

Primary cost is 23bp round trip. Every metric that resembles a trading outcome must include 0bp, 23bp, and 46bp sensitivity rows or be marked non-comparable.

Mandatory controls:

- no-trade baseline,
- shuffle control,
- equal-weight top-k control,
- frozen D3 comparator,
- fold/split metadata,
- negative/missing artifact controls for stale/latest selection.

## Leakage policy

Allowed feature timing:

- current-day OHLCV fields only when the documented decision time includes them,
- lagged t-1 or earlier fields,
- precomputed artifact metadata whose source timestamps predate the decision point.

Forbidden:

- future returns used as state features,
- post-decision drawdown/profit labels used as regime features,
- selecting thresholds after seeing OOS outcomes,
- recomputing denominators after favorable outcomes.

## Acceptance criteria for PR-8

PR-8 passes only when:

1. A deterministic CLI or module emits all required artifacts with hashes.
2. Focused tests cover price-basis blocking, universe missingness, leading-zero codes, proxy timing, missing/stale/malformed artifacts, and research-only locks.
3. The result document records exact commands, artifact paths, row counts, hashes, baseline/control outcomes, 0/23/46bp costs, and verdict.
4. D0/D1 are either verified or explicitly blocked with complete evidence; blocked evidence still improves non-live maturity but does not count as trading readiness.
5. The audit does not modify old `NO-GO` result documents.

## Completion semantics

A completed audit can raise **non-live data-governance/reproducibility maturity**. It cannot by itself raise live trading, paper-forward, model-build, or profitability readiness above `0%`.

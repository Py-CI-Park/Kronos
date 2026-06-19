# Daily OHLCV Past-Only Market-Regime Data Quality Audit Result — 2026-06-19

Date: 2026-06-19 UTC  
Status: `COMPLETED_RESEARCH_ONLY` / `BLOCKER_EVIDENCE_RECORDED_NO_PROMOTION`  
Preregistration: `docs/stom_daily_ohlcv_past_only_market_regime_data_quality_audit_prereg_2026-06-19.md`  
Run id: `market_regime_audit_2026_06_19_001`  
Default cost assumption: 23bp round trip  
Live/model/paper/profit readiness: `0%`, blocked

## Executive verdict

The past-only market-regime data-quality audit runner was implemented and executed on a bounded sample of Daily OHLCV tables. The audit produced source-hashed artifacts and confirmed the intended research-only outcome:

- D0 price basis remains `UNKNOWN_CONFIRMED`.
- D1 universe/missingness remains `WATCH`/blocker evidence for sampled rows.
- Past-only regime proxies were generated without future-label state usage.
- Baseline controls include no-trade, shuffle, equal-weight top-k, and frozen D3 rows under 0/23/46bp cost sensitivity.
- Stale/missing/malformed artifact policy is fail-closed.
- Promotion/model-build/paper-forward/live/profit readiness remains blocked.

This result raises data-governance/reproducibility evidence maturity. It does **not** unlock D5, model build, paper-forward, broker/live order flow, or profitability claims.

## Command

```powershell
py -3.11 -m stom_rl.daily_market_regime_audit --db-path D:/Chanil_Park/Project/Programming/Kronos/_database/Stock_Database_ohlcv_1day.db --output-root webui/rl_runs/daily_ohlcv_market_regime --run-id market_regime_audit_2026_06_19_001 --table-limit 25 --row-limit 260 --source-ref 4b86a3302a37
```

Observed stdout:

```json
{"run_id": "market_regime_audit_2026_06_19_001", "status": "COMPLETED_RESEARCH_ONLY", "verdict": "BLOCKER_EVIDENCE_RECORDED_NO_PROMOTION", "promotion_allowed": false}
```

## Generated artifacts

| Artifact | Path | SHA-256 |
|---|---|---|
| Manifest | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/market_regime_audit_manifest.json` | manifest records child hashes |
| Price basis audit | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/price_basis_audit.json` | `6dde34279c02a92ac542f1964cb88ac68abe9ff124c83e54aa363b9341538054` |
| Universe quality | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/universe_quality.csv` | `2b4bb0db9179f38045303c42dac1913ac7f7b0eb9239dfe5921ad549b3ab585d` |
| Regime proxy metrics | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/regime_proxy_metrics.csv` | `3401fb152f1d2a9b5440461bf402dffec4973c6e4be86e23e4321999da32b92b` |
| Baseline control metrics | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/baseline_control_metrics.csv` | `7c53fa08e12f1d110ac52ac79d6e9373b3c0e9b02b75efdeb6000d4b616d2cb4` |
| Leakage audit | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/leakage_audit.json` | `79ec94836b2166d7482e87f11b63c23f9d56bdaf2d48a85a6445fe9d9c050e6e` |
| Stale artifact audit | `webui/rl_runs/daily_ohlcv_market_regime/market_regime_audit_2026_06_19_001/stale_artifact_audit.json` | `39934839cf2a630eceaf10def7a0aef9bcf34541ae6934cf1f2eb1e06e9fe41f` |

## Manifest snapshot

| Field | Value |
|---|---|
| `status` | `COMPLETED_RESEARCH_ONLY` |
| `verdict` | `BLOCKER_EVIDENCE_RECORDED_NO_PROMOTION` |
| `table_denominator_count` | `4727` |
| `sampled_table_count` | `25` |
| `row_limit_per_table` | `260` |
| `price_basis_status` | `UNKNOWN_CONFIRMED` |
| `leakage_status` | `PASS` |
| `stale_artifact_status` | `PASS` |
| `promotion_allowed` | `false` |

Blocker flags:

- `D0_PRICE_BASIS_NOT_VERIFIED`
- `D1_UNIVERSE_WATCH_OR_MISSINGNESS`

## Controls and costs

The audit writes control rows for:

- no-trade,
- shuffle,
- equal-weight top-k,
- frozen D3.

Each control includes cost rows for 0bp, 23bp, and 46bp. These rows are diagnostic controls only and do not imply tradability.

## Leakage and source timing

The regime proxy metrics mark `future_label_used=false` and `source_timing=past_or_current_ohlcv_only`. The leakage audit status is `PASS`; no proxy row is allowed to use future labels as state.

## Data governance verdict

| Area | Verdict | Meaning |
|---|---|---|
| D0 price basis | `BLOCKER_CONFIRMED` | Adjustment basis remains unknown; decision-grade returns blocked. |
| D1 universe quality | `WATCH/BLOCKER_EVIDENCE` | Universe breadth exists but missing/stale behavior still needs fuller review. |
| Past-only proxies | `BUILT_RESEARCH_ONLY` | Volatility/drawdown/breadth/dispersion/liquidity proxies are generated without future labels. |
| Controls | `VISIBLE` | Required controls and cost sensitivity are recorded. |
| D5 promotion | `NO-GO` | No model-build/paper/live unlock. |

## Verification

```powershell
py -3.11 -m pytest tests/test_stom_rl_daily_market_regime_audit.py -q
```

Observed result: `2 passed in 0.36s`.

## Next allowed action

Proceed to dashboard/API binding only as a read-only, fail-closed evidence viewer. Missing, stale, malformed, or blocker-positive audit artifacts must not become optimistic maturity/readiness states.

## Prohibited interpretations

- This is not alpha.
- This is not an RL/model success.
- This is not broker/order/account readiness.
- This is not paper-forward readiness.
- This is not a profitability claim.

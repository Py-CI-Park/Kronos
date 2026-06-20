# P5 Restricted RL Sizing/Exit Gate Decision — 2026-06-11

## Verdict

```text
P5 restricted RL sizing/exit controller: BLOCKED / NOT IMPLEMENTED
Reason: P2 account-level prerequisite failed
Live/broker/order readiness: NO
Profit guarantee: NO
```

P5 was intentionally not implemented. The approved plan allowed a restricted RL sizing/exit controller only when all prerequisites passed:

1. P1 realized_full/slgap_full hard gate passes.
2. P2 account-level sizing/risk prerequisite passes.
3. P3 forward/paper schema is frozen.

P1 and P3 passed, but P2 did not. Therefore the correct implementation result is an automatic hold with documentation, not RL code.

## Gate evidence

| Gate | Status | Evidence |
|---|---|---|
| P1 fill-mode robustness | PASS | `probability_lane_stacked_realized_full_2026_06_11` and `probability_lane_stacked_slgap_full_2026_06_11` are `GO_CANDIDATE` with split `cc0483b81cbb486b`, parent `probability_lane_stacked_2026_06_11`, cost_bps=23. |
| P2 account-level sizing/risk | FAIL | Both sizing artifacts set `p5_prerequisite_met=false` / `P5_BLOCKED_BY_P2`. Mean/std improves, but total pp is lower and max drawdown worsens. |
| P3 forward/paper schema | PASS | `forward_ledger.py` schema_version=1, pending/resolved split, duplicate policy `skip_existing_record_id`, output root guard under `webui/rl_runs/forward_ledger`. |
| P4 dashboard visibility | PASS | `/rl` exposes P5 block, 23bp, RULE baseline, supervised gate NOT RL, sizing/risk, and forward ledger evidence read-only. |

## P2 blocker details

| Fill mode | Strategy trades | Baseline trades | Total pp delta | MaxDD delta | Mean/std strategy/base | P5 status |
|---|---:|---:|---:|---:|---:|---|
| `realized_full` | 3,484 | 4,469 | -47.7355 | +2.5725 | 0.3093 / 0.2501 | `P5_BLOCKED_BY_P2` |
| `slgap_full` | 3,331 | 4,469 | -38.4420 | +1.9987 | 0.2965 / 0.2284 | `P5_BLOCKED_BY_P2` |

Interpretation: the supervised gate improved mean/trade and mean/std, but it skipped enough positive trades that total pp fell, and drawdown worsened under the account-level fixed-fraction comparison. That is not a safe foundation for an RL sizing/exit controller.

## What was deliberately not built

- No RL sizing/exit environment was added.
- No action space (`size bucket`, `de-risk`, `hold`, `early-exit`) was implemented.
- No reward model was implemented.
- No policy training/evaluation job was queued.
- No broker, order, live trading, or profit-claim path was added.

## Next acceptable research step

The next RL attempt requires a new preregistered hypothesis that first fixes P2 account-level risk. Acceptable directions:

1. Reduce drawdown without lowering total pp further, then rerun P2.
2. Add a non-RL risk filter/position policy and compare against same-fill `ts_imb` with 23bp.
3. Use the P3 forward/paper ledger for out-of-time evidence before any RL controller.

Until P2 passes, RL remains a research-only blocked lane, not a deployable profit model.

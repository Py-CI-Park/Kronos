# RL Dashboard Evidence Expansion 결과 — 2026-06-11

## Verdict

```text
P4 dashboard read-only evidence expansion: COMPLETE
Dashboard role: read-only evidence viewer
Live/broker/order readiness: NO
Profit guarantee: NO
P5 restricted RL: BLOCKED by P2 sizing/risk evidence
```

## Added read-only evidence surfaces

| Surface | Backend/API | Frontend card | Purpose |
|---|---|---|---|
| Factory lineage / fill-mode robustness | `/api/rl/factory/lane-runs` | `FactoryLineageCard` | parent lineage, fill_mode, split/hash/seed, 23bp, verdict, failed reasons, Brier/control, `ts_imb` RULE baseline, total pp vs mean/trade tradeoff |
| P2 sizing/risk | `/api/rl/factory/sizing-runs` | `SizingRiskCard` | stacked supervised TAKE vs same-fill `ts_imb` RULE baseline account return, maxDD, mean/std, daily halt, capacity, worst session, P5 gate |
| P3 forward/paper ledger | `/api/rl/factory/forward-ledgers`, `/api/rl/factory/forward-ledger/<run>` | `ForwardLedgerCard` | schema_version, pending/resolved counts, duplicate policy, 23bp, fill assumption, decision rows, realized/baseline outcome |

## Guardrails preserved

- Dashboard/API remains read-only: no write queue, training, broker, order, or live-trading side effect was added.
- Factory queue API uses a read-only SQLite snapshot path; dashboard GET does not initialize or migrate the registry table.
- `ts_imb` is displayed as a RULE baseline, not reinforcement learning.
- Probability-lane/stacked TAKE is labelled supervised gate / operations design, NOT RL.
- 23bp round-trip cost is exposed in lineage, edge ledger, sizing, and forward ledger surfaces.
- P5 remains blocked because P2 account-level gate did not pass: mean/std improved, but total pp decreased and max drawdown worsened.

## Verification

```powershell
py -3.11 -m pytest tests/test_stom_rl_dashboard_factory_api.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_dist_marker.py -q
# 28 passed

cd webui/v2_src
npm run build
# svelte-check: 0 errors, 4 pre-existing warnings; vite build succeeded
```

# Daily OHLCV Non-Live Research Maturity Roadmap — 2026-06-19

Date: 2026-06-19 UTC  
Status: `NON_LIVE_MATURITY_ROADMAP`  
Scope: research-process, dashboard, reproducibility, and data-governance maturity only  
Explicit exclusion: live trading, broker/order/account, paper-forward, model-build unlock, and profitability readiness

## Maturity definition

`100%` in this roadmap means the non-live research platform can make evidence findable, reproducible, falsifiable, and fail-closed. It does **not** mean profitable, production-ready, paper-forward-ready, or broker-ready.

## Current scorecard and target gates

| Area | Current approximate score | Target | What 100% means | Gate |
|---|---:|---:|---|---|
| Research docs/governance | 100% | 100% | Dated governance index, prereg/result links, dirty-lane notes, blocker propagation, and next pointer are current | PR-7/PR-10 complete |
| Non-live dashboard platform | 100% | 100% | New audit surfaces are artifact-backed, read-only, and fail closed on missing/stale/malformed data | PR-9 complete |
| Experiment reproduction/verification | 100% | 100% | Exact commands, source hashes, artifact hashes, split/fold metadata, controls, 0/23/46bp rows, deterministic tests, stale-artifact checks | PR-8/PR-10 complete |
| Data governance | 100% evidence maturity | 100% | D0 price basis and D1 universe/missingness are explicitly blocked with complete evidence; past-only regime proxy provenance is source-hashed | PR-7/PR-8 complete |
| RL/model performance research | 25% | 60% falsification maturity before any promotion discussion | Model variants are falsified against controls and costs; no model-build claim before fresh gate | Future separate preregistration |
| Overall non-live project maturity | 100% for planned PR-7–PR-10 lane | 100% | Clean lane discipline, reproducible audit evidence, dashboard fail-closed behavior, current roadmap, and governance completeness | PR-7 to PR-10 complete |
| Live/model/paper readiness | 0% | 0% until future approved gate | Remains blocked; no readiness increase is allowed by this roadmap | Blocked |

## PR ladder

| PR | Branch | Maturity increment | Exit condition |
|---:|---|---|---|
| PR-7 | `feature/daily-market-regime-governance-prereg` | Governance/data-contract maturity | Preregistration and roadmap merged from a clean base; dirty lanes excluded |
| PR-8 | `feature/daily-market-regime-audit-runner` | Reproducibility/data-governance maturity | Audit artifacts emitted with source hashes, controls, cost rows, leakage checks, result doc, tests |
| PR-9 | `feature/daily-market-regime-dashboard-binding` | Dashboard/fail-closed maturity | Read-only API/UI reads PR-8 manifests; missing/stale/malformed artifacts fail closed; frontend build/tests pass |
| PR-10 | `feature/daily-artifact-selection-hardening` | Evidence-selection maturity | Latest artifact selection is deterministic, hash-backed, and never optimistic when stale/missing/malformed; malformed newest runs do not fall back to older runs |

## Non-live maturity invariants

These remain true even after all PRs complete:

- `model_build_allowed=false`
- `paper_forward_allowed=false`
- `live_broker_order_allowed=false`
- `go_summary_allowed=false`
- `profitability_claim_allowed=false`
- Dashboard POST routes create approved research-intent records only; they do not execute shell commands or workers.
- `NO-GO` documents remain visible and are not rewritten to soften prior failures.

## Evidence ladder

| Stage | Evidence type | Required proof |
|---|---|---|
| Contract | docs/preregistration | Frozen questions, scenarios, controls, costs, leakage rules, blocked states |
| Execution | CLI/module run | Reproducible argv, source hashes, deterministic outputs, artifact hashes |
| Analysis | result doc | Row counts, split/fold metadata, controls, 0/23/46bp sensitivity, verdict |
| Dashboard | API/UI binding | Read-only surface, stale/missing/malformed fail-closed tests, no execution side effects |
| Hardening | artifact selection | deterministic latest run selection, hash validation, lock propagation |

## What counts as maturity progress

Allowed progress:

- Clear blocker evidence for D0 price basis or D1 universe quality, even when the verdict is `BLOCKER_CONFIRMED`.
- Better past-only regime proxies with source timing and no future labels.
- Stronger negative controls, stale/missing tests, and failure visibility.
- More honest dashboards that show `NO-GO`, `WATCH`, or blocked states without optimism.

Not allowed as maturity progress:

- A favorable single split without baseline/no-trade/shuffle/frozen D3 controls.
- A dashboard chart that hides failed runs or costs.
- Factory/model/paper-forward work that bypasses D0/D1/D5 blockers.
- Any live/broker/order/account integration.

## Final 100% non-live completion checklist

The project can claim `NON_LIVE_RESEARCH_MATURITY_100` only after:

1. PR-7 freezes the market-regime audit contract.
2. PR-8 emits and documents audit artifacts with tests.
3. PR-9 exposes those artifacts through read-only fail-closed dashboard/API surfaces.
4. PR-10 hardens stale/latest artifact selection.
5. Governance index links all relevant prereg/result/evidence paths.
6. All readiness locks remain explicit at `0%` for live/model/paper/profit.

## Current recommendation

Proceed with final integration/reporting for the PR-7 to PR-10 lane. Future factory/probability and opening_30m work remain separate research lanes requiring fresh preregistration, fresh branch scope, and the same research-only locks.

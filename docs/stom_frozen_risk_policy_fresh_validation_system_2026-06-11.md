# STOM Frozen Risk-Policy Fresh Validation System Result (2026-06-11)

## Verdict

`FRESH_VALIDATION_REQUIRED`.

The next-stage validation system is implemented, but actual restricted RL model implementation remains locked because no `fresh_oos` or `fresh_forward` validation artifact has passed both required fill modes yet.

This is research-only. No profit guarantee, no live/broker/order readiness, and no RL model has been created. `ts_imb` remains a RULE baseline. Net values use the 23bp round-trip cost assumption.

## What was implemented

| Item | Status | Location |
|---|---:|---|
| Frozen policy validator CLI/module | done | `stom_rl/factory/frozen_policy_validator.py` |
| Validator tests | done | `tests/test_stom_rl_factory_frozen_policy_validator.py` |
| Dashboard backend discovery/API | done | `webui/rl_dashboard_factory.py`, `webui/app.py` |
| Dashboard frontend fresh-validation table | done | `webui/v2_src/src/tabs/rlTrading/ModelBuildReadinessCard.svelte` |
| Preregistration doc | done | `docs/stom_frozen_risk_policy_fresh_validation_prereg_2026-06-11.md` |
| Current replay smoke artifacts | done, non-unlocking | `webui/rl_runs/fresh_policy_validation/frozen_policy_replay_*_2026_06_11/summary.json` |

## Current replay smoke results

The frozen policy was replayed on the already-reviewed current artifacts to prove the pipeline works. These are intentionally labeled `current_replay`, `is_fresh_validation: false`, and `NOT_FRESH_REPLAY`, so they do not unlock RL implementation.

| Fill mode | Scope | Verdict | Fresh pass | Implementation unlocked | Note |
|---|---|---|---:|---:|---|
| `realized_full` | `current_replay` | `NOT_FRESH_REPLAY` | false | false | metrics pass internally, but source is not fresh |
| `slgap_full` | `current_replay` | `NOT_FRESH_REPLAY` | false | false | metrics pass internally, but source is not fresh |

## Dashboard state after this change

| Dashboard field | Current value |
|---|---|
| Risk P2 candidate | `CANDIDATE_PASS` |
| Fresh validation | `FRESH_VALIDATION_REQUIRED` |
| RL implementation | `LOCKED_FRESH_OOS_FORWARD_REQUIRED` |
| Implementation unlocked | `false` |

The dashboard can now show both non-unlocking replay evidence and future true fresh-validation evidence without confusing them.

## How to run a true fresh validation later

Example for a future fresh edge ledger:

```powershell
py -3.11 -m stom_rl.factory.frozen_policy_validator `
  --source <fresh_edge_ledger_or_forward_ledger> `
  --run-id frozen_policy_fresh_realized_full_<date> `
  --fill-mode realized_full `
  --validation-scope fresh_forward `
  --output webui/rl_runs/fresh_policy_validation/frozen_policy_fresh_realized_full_<date>/summary.json
```

Repeat for `slgap_full`. Both must pass before restricted RL sizing/exit implementation begins.

## Next implementation step after pass

If both fresh validations pass, build a restricted RL sizing/exit environment with constrained actions only. It must compare against:

- no-trade baseline
- frozen deterministic risk policy
- same-fill `ts_imb` RULE baseline

The RL model must beat these under 23bp cost, drawdown, and risk-adjusted gates before any stronger claim is made.

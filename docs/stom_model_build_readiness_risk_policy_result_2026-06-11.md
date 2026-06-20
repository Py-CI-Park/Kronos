# STOM RL Model-Build Readiness: Risk-Policy Candidate Result (2026-06-11)

## Verdict

`MODEL_BUILD_CANDIDATE_NEEDS_FRESH_VALIDATION`.

A deterministic non-RL risk policy was found that improves the account-level P2 metrics on both currently reviewed full fill modes, but the actual restricted RL sizing/exit model remains `LOCKED_FRESH_OOS_FORWARD_REQUIRED`.

This is not a profit guarantee, not live/broker/order readiness, and not an RL model. `ts_imb` remains the same-fill RULE baseline. All figures use the 23bp round-trip cost assumption.

## What was added

| Item | Status | Location |
|---|---:|---|
| Risk-policy lab | done | `stom_rl/factory/risk_policy_lab.py` |
| Unit/API tests | done | `tests/test_stom_rl_factory_risk_policy_lab.py`, `tests/test_stom_rl_dashboard_factory_api.py` |
| Generated risk-policy summaries | done | `webui/rl_runs/risk_policy_lab/risk_policy_realized_full_2026_06_11/summary.json`, `webui/rl_runs/risk_policy_lab/risk_policy_slgap_full_2026_06_11/summary.json` |
| Aggregate decision artifact | done | `.omx/artifacts/model_build_readiness_risk_policy_decision_2026_06_11.json` |
| Dashboard model-build readiness card/API | done | `/api/rl/factory/model-build-readiness`, `/api/rl/factory/risk-policy-runs`, `ModelBuildReadinessCard.svelte` |

## Selected candidate policy

`pwin_gt_040_size_050_100_halt_25`

Rule definition: TAKE rows with `p_win > 0.40`; size `1.0` when `p_win >= 0.55`, otherwise size `0.5`; apply a causal per-session stop after `-2.5pp` accumulated session loss.

| Fill mode | Baseline total pct | Candidate total pct | Total delta | Baseline maxDD | Candidate maxDD | MaxDD delta | Risk-adjusted delta | Candidate P2 pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `realized_full` | 1693.0205 | 1828.4934 | +135.4729 | 15.7430 | 14.1956 | -1.5474 | +0.2570 | true |
| `slgap_full` | 1466.2756 | 1646.3304 | +180.0548 | 17.2799 | 15.0392 | -2.2407 | +0.2633 | true |

## Why the RL model is still locked

The policy was selected after reviewing the current full OOS artifacts. That makes it a useful hypothesis, not deployable proof. Implementing a restricted RL controller directly from this result would be selection-biased retuning.

Unlock requirements:

1. Preregister the selected policy and acceptance gates before any new validation run.
2. Run fresh OOS or forward/paper validation not used to select the policy.
3. Keep same-fill `ts_imb` RULE baseline, 23bp cost, drawdown, total delta, and risk-adjusted mean/std gates visible.
4. Only if that fresh validation passes, implement a restricted RL sizing/exit controller. The dashboard must remain read-only and must not place orders or claim live readiness.

## Dashboard development result

The dashboard can now answer whether the project is ready to build an actual RL sizing/exit model:

| Dashboard area | What it shows |
|---|---|
| P1 fill-mode evidence | `realized_full` and `slgap_full` risk summaries exist |
| Original P2 | fixed sizing account-risk gate remains failed/blocked |
| Risk-policy P2 | candidate policy passes current reviewed artifacts |
| P3 | forward/paper ledger evidence is present |
| P4 | read-only readiness card/API is present |
| RL implementation | locked until fresh validation passes |

## Development guide from here

| Step | Action | Gate |
|---|---|---|
| 1 | Freeze `pwin_gt_040_size_050_100_halt_25` in a preregistered validation spec | no parameter changes after spec |
| 2 | Generate a fresh forward/paper validation ledger for the frozen policy | no live orders; read-only outcomes only |
| 3 | Re-run the model-build readiness API and dashboard card | both fill assumptions must remain visible |
| 4 | If fresh validation passes, build the restricted RL sizing/exit environment | constrained action space only; no broker integration |
| 5 | Compare restricted RL against no-trade, fixed policy, and `ts_imb` RULE baseline | RL must beat baselines under 23bp cost and drawdown gates |

Current state: platform is improved for model-build decisioning, but no profitable RL model has been created or claimed.

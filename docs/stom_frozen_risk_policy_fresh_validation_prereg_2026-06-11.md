# STOM Frozen Risk-Policy Fresh Validation Preregistration (2026-06-11)

## Purpose

Validate the selected deterministic risk policy on data not used to choose the policy before any restricted RL sizing/exit implementation is allowed.

This is research-only. It is not a profit guarantee, not live/broker/order readiness, and not an RL model. `ts_imb` remains the RULE baseline. All net figures use the 23bp round-trip cost assumption.

## Frozen policy

Policy id: `pwin_gt_040_size_050_100_halt_25`

Frozen rules:

| Rule | Value |
|---|---:|
| Entry universe | rows already marked `TAKE` by the stacked supervised probability lane |
| Minimum `p_win` | `p_win > 0.40` |
| Low size | `0.5` |
| High size | `1.0` when `p_win >= 0.55` |
| Session halt | stop remaining selected trades after session cumulative contribution <= `-2.5pp` |
| Cost | 23bp round trip |
| Baseline | same-fill `ts_imb` RULE baseline at 0.5 basis fraction |

No threshold or sizing search is allowed during fresh validation.

## Required validation scopes

A run can count for unlock only when `validation_scope` is one of:

- `fresh_oos`
- `fresh_forward`

The following are allowed only for pipeline smoke/replay and must not unlock implementation:

- `current_replay`
- `smoke`

## Required fill modes

Both must pass:

- `realized_full`
- `slgap_full`

## Pass gates

Each required fill mode must satisfy all gates:

| Gate | Required |
|---|---:|
| Fresh scope | `fresh_oos` or `fresh_forward` |
| Total delta vs baseline | `>= 0.0pp` |
| Max drawdown delta vs baseline | `< 0.0pp` |
| Risk-adjusted mean/std vs baseline | improvement |
| Minimum policy trades | `>= 100` default unless a smaller preregistered smoke-only fixture is explicitly labeled non-unlocking |

## Unlock rule

Restricted RL sizing/exit implementation may be considered only when both required fill modes produce `FRESH_VALIDATION_PASS` artifacts with `implementation_unlocked: true`.

Even after this unlock, the dashboard remains read-only. No broker integration, live order routing, or profit claim is allowed.

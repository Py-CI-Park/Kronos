# Daily Portfolio SB3 R3b full-gate result — 2026-07-12

## Verdict

| Scope | Verdict | Meaning |
|---|---|---|
| G018 engineering completion | **COMPLETE — OPTION B PREREGISTERED STOP** | The full gate stopped during pre-compute protocol audit on an actual `prereg_criterion` trigger. The stop artifact preserves the evidence and missing-cell matrix required by Todo 18. |
| Full experiment | **INCONCLUSIVE — NOT RUN** | No 200k seed/fold was started. No partial full model or full event stream exists. |
| Model verdict | **NOT_RUN / NOT_PROMOTED** | There is no full multi-seed model-quality result and no promotion basis. |
| Existing G017 smoke | **COMPLETED_RESEARCH_ONLY** | G017 plumbing/data/dashboard gates passed, but a single 5k seed remains smoke-only evidence. |

This is an **RL experiment governance result**, not the `ts_imb` RULE baseline. It makes no alpha, profitability, live-trading, broker, paper-trading, order, account, model-build, or deployment-readiness claim.

## Stop trigger

- Code: `PREREG_CRITERION_INCOMPLETE`
- Class: `prereg_criterion`
- Phase: pre-compute protocol audit
- Research verdict: `INCONCLUSIVE`
- Convenience stop: `false`
- Triggered by positive/negative reward: `false`
- Triggered by resource exhaustion: `false`

The frozen preregistration requires shuffled-label retraining and core input/normalization/reward ablations, but it does not define the reproducible transformations, seeds/scopes, or abnormal invalid-action stop threshold needed to execute them. Filling those fields after observing G017 would be retrospective protocol invention. Todo 18 explicitly accepts a complete stop artifact when a preregistration criterion blocks the exact protocol; forcing approximately-defined 18–24 hour compute would produce inadmissible evidence, not a valid full result.

## G017 prerequisite was satisfied

The stop is not caused by G017 learning quality or reward.

| Evidence | Value |
|---|---|
| G017 run | `daily_sb3_ppo_smoke_2026_07_12_seed7` |
| G017 gate | `PASS_PLUMBING_DATA_GATES_ONLY` |
| G017 result SHA-256 | `23a30c0fa06854c4eb977ad0547e9881879ae641c56200909936eee31d82ca78` |
| G017 verification SHA-256 | `ae5d448d04dd330a7b86479663c947ef95eafc967654e7f9ea780b635756dcd1` |
| Frozen prereg SHA-256 | `ebd4c2e3ddbdf0b7e2a4c494a9b3de7bb14f9d109d999836c1d5f84395941e1f` |

G017 completed PPO seed 7 at 5,000 timesteps per fold with 23bp primary, 0/46 controls, finite metrics, official-test fit rows equal to zero, model/hash evidence, truthful events, and `LIVE → COMPLETED` dashboard lineage. Those facts permit G018 preflight; they do not repair an under-specified full protocol.

## Blocking frozen-protocol gaps

| Gap | Required evidence | Why execution did not infer it |
|---|---|---|
| Ablation definitions | Exact input, normalization, and reward transforms; fixed seeds, fold scope, and budget | Selecting score-zero, raw observation, or no-turnover variants now would add protocol after the smoke result. |
| Shuffled-label retraining | Which label/score is permuted, grouping/scope, RNG mapping, and compute budget | The adapter contains both rank scores and next-day returns; choosing one changes the falsification control. |
| Invalid-action stop threshold | Numeric definition of “abnormal” for mandatory full stop | The existing 5% value is a MaskablePPO recommendation trigger, not a frozen G018 stop threshold. |
| Fold seed semantics | Base seed in every fold versus current worker `base_seed + fold_index` | The full identical-config seed identity cannot be audited without a frozen choice. |
| Full baseline scope | Per-frame no-trade/momentum/RULE/buy-hold applicability and construction | Existing source baseline rows combine validation and test and are explicitly secondary, so they cannot silently become untouched-test comparators. |

## Current implementation preflight

Independent planner and architect reviews also found that the current G017 worker cannot represent the required authoritative full protocol without new code:

1. authoritative/completed metadata is smoke-only and rejects `stage=full`, 200k, seeds 17/29;
2. validation evidence is final-only, not a 10k `phase=eval` ledger;
3. there is no deterministic seed/control/ablation run plan;
4. full artifacts would still be classified as `sb3_smoke`;
5. exceptions do not automatically preserve the accepted G018 stop schema.

These code gaps could be implemented only after the control/ablation semantics were fixed. Implementing hooks first and choosing semantics later would not satisfy the frozen experiment.

## Preserved and skipped evidence

No G018 full process was started. A filesystem preflight found no `*full*2026_07_12*` run directory, full model ZIP, or full event stream. The skipped primary matrix is exactly:

- seed 7: fold 0, fold 1
- seed 17: fold 0, fold 1
- seed 29: fold 0, fold 1

Shuffled-retraining and ablation cells are recorded as undefined by the frozen preregistration rather than fabricated. No negative seed was omitted because no full seed ran.

## Evidence and verification

- Stop artifact: `.omo/evidence/task-18-r3b-full/g018_stop_artifact.json`
- Stop validator: `.omo/evidence/task-18-r3b-full/verification.json`
- Validation result: **14/14 checks passed**
- Independent architecture review: `BLOCK` for full execution, with the same protocol/implementation gaps and explicit recommendation not to launch through the current worker.
- G017 prerequisite evidence remains under `.omo/evidence/task-17-r3b-smoke/`.

A future full experiment requires a new dated preregistration that fixes every missing transform, seed mapping, threshold, baseline definition, 10k validation contract, and stop schema before any new compute. That future experiment would be a new protocol; it cannot be backfilled into this frozen G018 result.

# Kronos RL model lifecycle and full-page execution review

**Evidence completed:** 2026-07-27 KST

**Final review:** 2026-07-28 KST
**Work branch:** `codex/rl-model-lifecycle-v1`  
**Base release:** `fork-v1.8.0-kronos-rl-discovery-scorecard`  
**Research verdict:** `NO-GO`  
**Fresh OOS:** `NOT_RUN_NO_READ`  
**Live trading:** `BLOCKED`

## 1. Outcome

Kronos can now create and save real SB3 reinforcement-learning model files in the
Type2-D0 discovery lane. An expensive run creates its evidence directory before
training, saves each completed arm/seed model and normalizer, records its outcome
immediately, and resumes without retraining completed arm/seed units.

This is a research execution capability, not evidence of profitability,
generalization, or live readiness. The `ts_imb` gap-up baseline remains a RULE
strategy and is not relabeled as RL.

## 2. Delivered changes

| Area | Delivered | Evidence | Completion |
|---|---|---|---:|
| Run lifecycle | `lifecycle.json` is created before training | Strict Pydantic schema and atomic JSON writes | 100% |
| Partial evidence | One outcome JSON is written after every arm/seed | `outcomes/<arm>/seed-<n>.json` | 100% |
| Model generation | SB3 model ZIP and normalizer are saved per arm/seed | `models/<arm>/seed-<n>/model.zip`, `normalizer.pkl` | 100% |
| Resume | Completed arm/seed units are skipped | `--resume <run-dir>` and immutable identity checks | 100% |
| Contract protection | Experiment/profile/prereg/fixture/matrix changes cannot resume | Strict lifecycle v2 validation | 100% |
| Terminal immutability | A completed receipt cannot be resumed or overwritten | Fail-closed terminal boundary | 100% |
| Evidence inventory | 40 ignored run files are bound by committed SHA-256 manifest | Legacy fixture runtime binding remains unverified | 90% |
| Future unit custody | Lifecycle v2 binds exact input snapshots and every outcome/model/normalizer digest | Resume rejects missing or changed completed units | 100% |
| Dashboard evidence | Running and terminal summaries share scanner format | `sb3_smoke_summary.json` | 100% |
| Full-page visibility | All V6 pages show one execution strip | Score, branch, next action, ETA, safety gates | 100% |
| Page control table | All 12 surfaces have progress/action/ETA/merge gate | Program Scorecard page | 100% |
| Primary research result | 4 arms × 3 seeds at preregistered budget | `PRIMARY_COMPLETE / PPO_ONLY_OVERFIT_NOT_CONFIRMED` | 100% |

## 3. Actual reinforcement-learning smoke result

The following is a real local MaskablePPO smoke execution, not a fabricated UI
fixture. It is intentionally too small to support an alpha claim.

**Run:** `webui/rl_runs/rl_discovery/type2-d0-smoke-lifecycle-qa-20260727`

| Arm | Seed | PPO steps | Oracle reward ratio | Exact basket accuracy | Dominant action rate | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| A_PPO_ONLY | 0 | 256 | -0.347458 | 0.25 | 0.625 | Smoke wiring only; threshold failed |
| B_BC_THEN_PPO | 0 | 256 | 0.000000 | 0.25 | 1.000 | Collapsed action behavior |
| C_BC_ONLY | 0 | 0 | 0.000000 | 0.25 | 1.000 | Collapsed action behavior |
| D_SHUFFLED_REWARD_PPO | 0 | 256 | -0.347458 | 0.25 | 0.625 | Negative control did not separate |

| Terminal field | Value |
|---|---|
| Status | `SMOKE_COMPLETE` |
| Verdict | `SMOKE_INCOMPLETE` |
| Type1 outcome | `COMPLETE_NO_GO` |
| Promotion allowed | `false` |
| Profitability claim allowed | `false` |
| Fresh OOS | `NOT_RUN_NO_READ` |

## 4. Program score

The score measures platform and research-program completeness. It does not
measure expected return.

| Lane | Score | Weight | Weighted points | State | Remaining gate |
|---|---:|---:|---:|---|---|
| Platform | 94 | 30% | 28.2 | STRONG | Bind future D1 prereg artifact |
| RL evidence | 65 | 30% | 19.5 | PARTIAL | Close D0 NO-GO and preregister D1 |
| Engineering | 92 | 20% | 18.4 | STRONG | Mid-arm checkpoint remains separate |
| Governance | 78 | 10% | 7.8 | PARTIAL | CI/PR protection |
| Live readiness | 0 | 10% | 0.0 | BLOCKED | No action before research gates |
| **Overall** |  | **100%** | **74 / 100** | **PARTIAL** | D0 evidence complete; hypothesis failed |

## 5. Full-page execution table

Progress is UI implementation plus evidence linkage, not trading performance.
ETA is the expected time for the listed next action on the current local setup.

| Priority | Page | Progress | Current evidence | Next action | ETA | PR merge gate |
|---|---|---:|---|---|---|---|
| P1 | Home | 97% | PRIMARY_NO_GO | Link D1 entry condition | 30 min | Verdict values agree |
| P1 | Program Scorecard | 96% | AUDITED | Freeze score after PR review | 20 min | Weights total 100% |
| P0 | Discovery Lab | 96% | PRIMARY_COMPLETE | Close D0 and preregister D1 | 4–8 h design | 12/12 and receipt verified |
| P1 | Data | 90% | TRAIN_ONLY_LOCKED | Write D1 input contract | 1–2 h | Fresh OOS sealed and SHA matches |
| P0 | Experiment | 95% | D0_TERMINAL | Preregister D1 reward/action redesign | 4–8 h | D0 immutable, new hypothesis separate |
| P1 | Training | 96% | PRIMARY_COMPLETE | Run only a new D1 smoke after prereg | 30 min compute | 12 models and outcomes preserved |
| P0 | Evaluation | 94% | NO_GO | Record PPO attribution failure | 30 min | Control and collapse visible |
| P1 | Compare | 92% | PRIMARY_COMPARED | Freeze A/B/C/D aggregate comparison | 20 min | RULE and RL remain separated |
| P1 | Report | 94% | PRIMARY_RECEIPT | Attach result and receipt to PR | 30 min | NO-GO reason, SHA, 12 outcomes included |
| P2 | Insights | 70% | OBSERVATION | Strengthen observation boundary | 30–60 min | No alpha claim |
| P2 | Other Lanes | 68% | INELIGIBLE_FOR_RL_RANK | Recheck exclusion label | 30 min | Not counted as RL performance |
| HOLD | Settings | 80% | LOCAL_ONLY | Keep execution controls disabled | 15 min | Read-only boundary maintained |

## 6. How to run the Primary model research

The recorded D0 run is terminal and immutable. The command below documents how
the run was started; rerunning the same ID is intentionally rejected:

```powershell
py -3.11 -m stom_rl.rl_discovery.runner `
  --profile PRIMARY `
  --run-id type2-d0-primary-20260727
```

Only while a future run is still partial, resume the same immutable experiment:

```powershell
py -3.11 -m stom_rl.rl_discovery.runner `
  --profile PRIMARY `
  --resume webui/rl_runs/rl_discovery/type2-d0-primary-20260727
```

The resume boundary is arm/seed level. A process interrupted inside one arm/seed
restarts that incomplete unit; completed units are not retrained. A terminal
receipt rejects resume. Mid-gradient checkpoint resumption is a separate future
improvement and must not be claimed as implemented.

## 7. Branch, commit, PR, and merge plan

| Order | Object | Name / rule | Status |
|---:|---|---|---|
| 1 | Base tag | `fork-v1.8.0-kronos-rl-discovery-scorecard` | Fixed |
| 2 | Work branch | `codex/rl-model-lifecycle-v1` | Active |
| 3 | Lifecycle commit | `54d5a3b feat(discovery): persist resumable model lifecycle` | Complete |
| 4 | UI commit | `4546b81 feat(v6): expose lifecycle across all research pages` | Complete |
| 5 | Documentation commit | `bf6ffb7`, `d067d67` | Complete |
| 6 | Dist commit | `3d867e8`, `9b555f5` | Complete |
| 7 | Evidence hardening | `bc9e7ad`, `e9f2b00` | Complete |
| 8 | Primary UX correction | `acc4f6f` | Complete |
| 9 | PR target | `research/type1-closing-rl-v1` | Local target exists; push after final QA |
| 10 | Release tag | `fork-v1.9.0-kronos-rl-model-lifecycle` | Create after merge approval |

Recommended PR policy:

1. Review source commits independently from generated frontend assets.
2. Require Python tests, Ruff, Basedpyright, Svelte tests/check, production build,
   and desktop/mobile visual QA.
3. Confirm that the PR says `NO-GO`, `NOT_RUN_NO_READ`, and `research-only`.
4. Merge with a merge commit when lineage visibility is preferred; otherwise use
   squash only if the generated-dist commit remains attributable in the PR.
5. Create the annotated release tag only after the target branch contains the
   reviewed changes.

## 8. Verification receipt

| Check | Result |
|---|---|
| RL/V6/dashboard/V4 expanded Python regression | 176 passed, 2 skipped |
| Ruff | Passed |
| Basedpyright | 0 errors, 0 warnings |
| V6 TypeScript tests | 383 passed |
| Svelte check | 0 errors, 0 warnings |
| Production build | 956 modules transformed |
| Actual SB3 smoke | 4 models + 4 normalizers + 4 outcomes persisted |
| Resume QA | Partial-run interruption test passes; terminal resume rejects |
| Runtime browser load | HTTP 200; V6 assets and read-only APIs loaded successfully |
| Desktop/mobile screenshots | Not captured: Orca runtime unavailable; automated responsive checks/build passed |

## 9. Immediate next decision

The platform generated and evaluated 12 Primary research models. D0 is complete
and the PPO-only attribution hypothesis failed. The next meaningful step is not
post-hoc tuning of D0; it is a separately preregistered D1 reward/action-design
falsification experiment. Fresh OOS and live trading remain blocked.

The observed Primary receipt was produced by the reduced executable D0 contract,
not by every diagnostic proposed in earlier planning drafts. Those richer checks
remain future D1 work and are not retroactively claimed.

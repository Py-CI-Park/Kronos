# Kronos RL model lifecycle and full-page execution review

**Reviewed:** 2026-07-27 KST  
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
| Contract protection | Changed experiment/profile/prereg SHA cannot resume | `ResumeMismatchError` | 100% |
| Dashboard evidence | Running and terminal summaries share scanner format | `sb3_smoke_summary.json` | 100% |
| Full-page visibility | All V6 pages show one execution strip | Score, branch, next action, ETA, safety gates | 100% |
| Page control table | All 12 surfaces have progress/action/ETA/merge gate | Program Scorecard page | 100% |
| Primary research result | 4 arms × 3 seeds at preregistered budget | Not executed in this change | 0% |

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
| Platform | 92 | 30% | 27.6 | STRONG | Bind Primary terminal artifact |
| RL evidence | 40 | 30% | 12.0 | PARTIAL | Complete preregistered Primary |
| Engineering | 90 | 20% | 18.0 | STRONG | Long-run interruption E2E |
| Governance | 74 | 10% | 7.4 | PARTIAL | CI/PR protection |
| Live readiness | 0 | 10% | 0.0 | BLOCKED | No action before research gates |
| **Overall** |  | **100%** | **65 / 100** | **PARTIAL** | Primary remains the critical path |

## 5. Full-page execution table

Progress is UI implementation plus evidence linkage, not trading performance.
ETA is the expected time for the listed next action on the current local setup.

| Priority | Page | Progress | Current evidence | Next action | ETA | PR merge gate |
|---|---|---:|---|---|---|---|
| P1 | Home | 95% | READ_ONLY | Verify Primary status link | 15 min | Verdict values agree |
| P1 | Program Scorecard | 92% | AUDITED | Recalculate after Primary | 20 min | Weights total 100% |
| P0 | Discovery Lab | 80% | SMOKE_COMPLETE | Run D0 Primary, 4 arms × 3 seeds | CPU 3–4 h+ | All arms/seeds and control complete |
| P1 | Data | 85% | MIXED | Recheck Primary input provenance | 30 min | Train-only and SHA match |
| P0 | Experiment | 88% | PREREGISTERED | Freeze run ID and prereg SHA | 20 min | No prereg mutation |
| P0 | Training | 72% | RESUME_READY | Execute and interrupt/resume Primary | CPU 3–4 h+ | Model, normalizer, outcome persisted |
| P0 | Evaluation | 78% | NO_GO | Calculate Primary terminal gate | 20–40 min after run | 23bp, control, collapse visible |
| P1 | Compare | 75% | RESEARCH_ONLY | Compare all 12 Primary results | 20 min | RULE and RL remain separated |
| P1 | Report | 82% | HAS_REPORTS | Add Primary terminal receipt | 30 min | Verdict, reason, SHA included |
| P2 | Insights | 70% | OBSERVATION | Strengthen observation boundary | 30–60 min | No alpha claim |
| P2 | Other Lanes | 68% | INELIGIBLE_FOR_RL_RANK | Recheck exclusion label | 30 min | Not counted as RL performance |
| HOLD | Settings | 80% | LOCAL_ONLY | Keep execution controls disabled | 15 min | Read-only boundary maintained |

## 6. How to run the Primary model research

Start a stable run ID so the same directory can be resumed:

```powershell
py -3.11 -m stom_rl.rl_discovery.runner `
  --profile PRIMARY `
  --run-id type2-d0-primary-20260727
```

If interrupted, resume the same immutable experiment:

```powershell
py -3.11 -m stom_rl.rl_discovery.runner `
  --profile PRIMARY `
  --resume webui/rl_runs/rl_discovery/type2-d0-primary-20260727
```

The resume boundary is arm/seed level. A process interrupted inside one arm/seed
restarts that incomplete unit; completed units are not retrained. Mid-gradient
checkpoint resumption is a separate future improvement and must not be claimed as
implemented.

## 7. Branch, commit, PR, and merge plan

| Order | Object | Name / rule | Status |
|---:|---|---|---|
| 1 | Base tag | `fork-v1.8.0-kronos-rl-discovery-scorecard` | Fixed |
| 2 | Work branch | `codex/rl-model-lifecycle-v1` | Active |
| 3 | Lifecycle commit | `54d5a3b feat(discovery): persist resumable model lifecycle` | Complete |
| 4 | UI commit | `4546b81 feat(v6): expose lifecycle across all research pages` | Complete |
| 5 | Documentation commit | Review, commands, ETAs, merge gates | Pending at document authoring time |
| 6 | Dist commit | Generated V6 assets only | Pending at document authoring time |
| 7 | PR target | `research/type1-closing-rl-v1` | Create after final QA |
| 8 | Release tag | `fork-v1.9.0-kronos-rl-model-lifecycle` | Create after merge approval |

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
| Discovery/dashboard Python regression | 44 passed, 2 skipped |
| Lifecycle targeted tests | 4 passed |
| Ruff | Passed |
| Basedpyright | 0 errors, 0 warnings |
| V6 TypeScript tests | 22 passed |
| Svelte check | 0 errors, 0 warnings |
| Production build | 955 modules transformed |
| Actual SB3 smoke | 4 models + 4 normalizers + 4 outcomes persisted |
| Resume QA | 4 completed units skipped, no retraining |
| Desktop/mobile visual QA | Passed at 1440×1100 and 390×844 |

## 9. Immediate next decision

The platform can generate and test RL models now. The next meaningful research
step is the immutable D0 Primary attribution run. Its purpose is deliberately
narrow: determine whether PPO can overfit the train-only synthetic task better
than the shuffled-reward control. Even a pass does not unlock Fresh OOS or live
trading; it only permits the next preregistered research question.

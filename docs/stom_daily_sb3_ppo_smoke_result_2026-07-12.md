# Daily Portfolio SB3 R3b 5k smoke result — 2026-07-12

## Verdict

| Scope | Verdict | Meaning |
|---|---|---|
| Engineering / artifact-to-dashboard plumbing | **PASS** | The preregistered 5k PPO smoke completed with finite metrics, model artifacts, hashes, fold-validation callbacks, an advancing event stream, and dashboard `LIVE → COMPLETED` evidence. |
| Smoke research result | **COMPLETED_RESEARCH_ONLY** | This is a single-seed smoke, not a full experiment or model-promotion result. |
| Model verdict | **INCONCLUSIVE_SMOKE_ONLY / NOT_PROMOTED** | The smoke cannot establish alpha, profitability, live readiness, broker readiness, or a deployable model. |
| G018 expansion gate | **PASS_PLUMBING_DATA_GATES_ONLY** | No schema, NaN/Inf, split, baseline, event, dashboard-lineage, or invalid-action stop gate fired. Positive reward was not required and is not the reason for expansion. |

This result is an **RL experiment**. It is not the `ts_imb` RULE baseline and does not change any existing `NO-GO`, `RESEARCH_ONLY`, or not-live-ready guardrail.

## Frozen run contract

| Field | Executed value |
|---|---|
| Run ID | `daily_sb3_ppo_smoke_2026_07_12_seed7` |
| Algorithm | PPO |
| Timesteps | 5,000 per fold |
| Seed | 7 |
| Device requested / used | `auto` / CUDA (`NVIDIA GeForce RTX 4080 SUPER`) |
| Folds | 2, fold-local training |
| Primary cost | 23bp round trip |
| Controls | 0bp and 46bp, evaluated without retraining |
| Stage / status | `smoke` / `completed` |
| Authority | `G017_PREREGISTERED_SMOKE_RESEARCH_ONLY` |
| Official rows | train 47,996; validation 15,500; untouched test OOS 15,384 |
| OOS rows used for fit | 0 |
| Preregistration SHA-256 | `ebd4c2e3ddbdf0b7e2a4c494a9b3de7bb14f9d109d999836c1d5f84395941e1f` |

The first compute attempt stopped before training because deterministic CUDA required `CUBLAS_WORKSPACE_CONFIG=:4096:8`. The retry used the identical frozen configuration with that process-level deterministic CuBLAS setting. The failed pre-training attempt is preserved in `.omo/evidence/task-17-r3b-smoke/compute_attempt1_failure.json`; it was not counted as a completed run.

## Primary and validation evidence

Untouched test OOS is the primary report-only evidence. Validation callback results are training-process evidence only. The source baseline table combines validation and test and therefore remains secondary reference evidence; it is not used as a model-GO source.

| Fold | Validation 23bp return | Untouched test OOS 23bp return | Test MDD | Test invalid-action rate | Model SHA-256 |
|---:|---:|---:|---:|---:|---|
| 0 | +23.7703% | +58.7386% | -13.2885% | 3.2468% | `c64d3e9be84d2f4c0863ef90414fbc73cc111f4d7bf94cc8094f2f0a760a3a55` |
| 1 | -2.6638% | +26.6719% | -2.9638% | 0.6494% | `40a7a9317937a070bc8e351f726db539bffda26215eb715e1e2a639c710fa6d8` |

The mixed validation result and single seed are sufficient reasons not to make a model-quality claim. The positive untouched-test curves are recorded without promotion: G018 must reproduce the fixed protocol across at least three 200k seeds, shuffled-label retraining, ablations, uncertainty, drawdown, and baseline gates.

Required secondary source references were present at 23bp:

- `no_trade_cash`
- `shuffle_control`
- `equal_weight_topk_momentum` RULE baseline
- distinct `vol_adjusted_momentum` RULE baseline

## Event and dashboard lineage

- 45 append-only events: 42 `train`, 2 `fold_completed`, 1 `completed`.
- Global steps were non-decreasing; final step was 10,243.
- Training rows preserved `action=null` / `action_recorded=false`; the dashboard rendered `NOT_RECORDED` rather than HOLD or zero.
- Reward metadata was `raw_reward` / `score`; equity metadata was `krw_nav` / `krw`.
- Running capture observed `LIVE` at step 9,473.
- Completed capture observed `COMPLETED`, phase `completed`, step 10,243, and backend `is_live=false`.
- UI guardrail remained `RESEARCH_ONLY · NO live / broker / order / profit / GO`.

## Lineage and artifact hashes

| Artifact | SHA-256 |
|---|---|
| Promoted D3 prediction manifest | `bac0efdaeec1fbd452802b162116ff65c86acd227015ae49ff7c03b985ac7ae7` |
| Predictions | `78ad01d796ae75bccbe87753c7843f256cf2af28cf0ce8b24249c1989daa344a` |
| D2 dataset manifest | `632ae210a45cbe6eb746c5ae3223ab27ccefa55b290a5a3531aa7a57f52e13fb` |
| Daily DB | `9a363b33a9c2d125f3df7010e54efcec9d53fd6a40dbf16a39b538c20247a09c` |
| Adapter candidates | `3fb93ea5e5780787c443e2420c02e8693f0031747f20926353a0829868c2a0fe` |
| `rl_manifest.json` | `b275c5b93abdc51e2d260534f74446ab7b66033d30ddaff9c4448625469258e8` |
| `training_manifest.json` | `b8e0079c05d9ebc6ba2aa2c4cd9187404c951844b3ec1904ffabedc7b95479a5` |
| `source_hashes.json` | `4fc81cf8f86bb8e46e373d65eebe3c7527bf27e04235e2878e86973326096c35` |
| `rl_live_events.jsonl` | `c322f23c001b3454428c9125fd49f468b7f0f7f6bb9fad14d6800b6bc945a76d` |

## Verification

- Focused adapter/trainer/E2E regression: **62 passed**.
- `py_compile`: passed for all five changed Python/test files.
- `git diff --check`: passed before the implementation commit.
- LSP diagnostics: zero errors on the changed trainer, dataset, and focused test.
- Independent architecture/code review: `VERDICT: PASS`, `CLEAR`, `APPROVE`, no findings.
- Evidence validator: all 15 checks passed in `.omo/evidence/task-17-r3b-smoke/verification.json`.

Generated evidence is under `.omo/evidence/task-17-r3b-smoke/`. The canonical run artifact is under `webui/rl_runs/daily_ohlcv_portfolio_sb3/daily_sb3_ppo_smoke_2026_07_12_seed7/`; generated run files are not committed.

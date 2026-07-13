# Daily D4 stability sweep preregistration — 2026-07-12

## Research-only question

Does the existing tabular-Q daily portfolio policy remain directionally and behaviorally stable across the fixed seed × replay-episode grid, or are return sign and trade participation dominated by seed noise?

This is a **portfolio RL research diagnostic**. It is not the `ts_imb` RULE baseline, and it cannot authorize live trading, broker/order/account access, paper-forward use, model build, deployment, or a profit claim.

## Frozen source lineage

- Prediction run: `prediction_2026_06_14_g004_d3_baseline_hardened`
- Prediction manifest SHA-256: `b1d4b26d8561444dd826c66bb1fdc092200f52d0dd1d05a0ab6f24b4c0439936`
- Predictions SHA-256: `78ad01d796ae75bccbe87753c7843f256cf2af28cf0ce8b24249c1989daa344a`
- Dataset run: `dataset_2026_06_14_g003_d2_refresh`
- Declared dataset manifest SHA-256: `0b3ebec9ef8929ef1e26c8c2399a62fcb092fbd026f8e126e0c5f10f4e37ea74`
- D3 status: `WATCH`; D0 price-basis, D1 universe, and D5 walk-forward blockers remain.
- Cost: 23bp round trip. No cost or split is changed after results.

## Frozen grid and policy

Execute all 15 cells in lexicographic product order:

- seeds: `{7, 17, 29, 41, 53}`
- replay episodes: `{8, 32, 128}`

Each cell uses:

- `run_and_write_daily_rl`
- `score_column=score_supervised_linear_ranker`
- `candidate_limit=20`
- `max_positions=5`
- `observation_mode=v1`
- `action_prior_mode=none`
- `action_prior_strength=0.0`
- `action_filter_mode=none`
- `val_eval_every=1`
- 23bp policy accounting inherited from the frozen D4 environment
- train split for fit only; validation and test never update the Q table
- stage `smoke` for 8/32 episodes and `full` for 128 episodes

Run IDs are fixed as `daily_d4_stability_2026_07_12_seed{seed}_ep{episodes}`. A failed cell remains in the summary with its error and hashes available at failure; it is never silently dropped or retried with changed settings.

## Required cell evidence

For every cell, record:

- seed, episodes, stage, status, run ID, config hash, source hashes, and artifact hashes;
- validation, test, and val+test total net return separately;
- validation, test, and val+test trade count;
- validation, test, and val+test never-trade flag;
- test and val+test maximum drawdown;
- 23bp deltas versus no-trade, equal-weight momentum, and best frozen RULE baseline when present;
- checkpoint readiness separately from D4 environment readiness;
- research-only verdict and all D0/D1/D5/blocking reasons.

**Test OOS is the primary headline.** `val+test` is retained only as a secondary historical comparison and may not replace or hide test results.

## Stability decision

- `SEED_NOISE_NO_GO`: within any episode budget, test-return sign or never-trade behavior differs across seeds.
- `STABLE_NO_GO`: all cells are behaviorally consistent but remain blocked by D0/D1/D5 or fail frozen baseline/cost evidence.
- `INCONCLUSIVE`: one or more cells fail, required metric/hash/source evidence is missing/non-finite, aliases are counted as seeds, or the grid/config differs.

There is no model `GO` branch in this sweep. Positive cells earn no promotion bonus and negative/high-drawdown cells cannot be excluded.

## Registry and aliases

Each of the 15 new real runs is registered exactly once with stage, status, verdict, prereg path, 23bp cost, seed, split hash, source Git SHA, run directory, and artifact hashes. Registry selection uses explicit metadata, never mtime or directory names.

Known historical duplicate directories are marked, but are not added as independent seeds:

- `portfolio_2026_06_13_d4b_telemetry`
- `portfolio_2026_06_13_d4c_policy_eval`
- `portfolio_2026_06_13_g003_state_visualization`

Each alias receives an `ALIAS_OF.txt` pointing to the canonical historical seed-7 run identified by manifest equality. Alias files are governance markers only; they do not modify historical metrics.

## Readiness separation

- `checkpoint_readiness`: whether the configured predictor checkpoint directory actually exists.
- `environment_readiness`: whether the D4 research environment/artifacts are structurally runnable.
- `model_ready`: true only if both are true and all upstream gates allow it. Under current D0/D1/D5 locks it remains false.

Environment availability must never be presented as checkpoint/model readiness.

## Reproducibility

`stability_summary.json` is sorted by `(episodes, seed)`, includes all 15 planned cells or explicit failures, and has a deterministic content hash excluding generation timestamps. Re-running the aggregator from raw cell manifests must reproduce all metrics and the decision byte-for-byte.

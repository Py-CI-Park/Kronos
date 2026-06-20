# Probability Lane Full-Universe Fill-Mode 재검증 사전등록 — 2026-06-11

## 목적

`probability_lane_stacked_2026_06_11`은 사전등록 gate를 통과한 `supervised gate` 후보이지 RL이 아니다. 본 재검증은 같은 frozen universe/split/model-lane 구조를 유지한 채 체결 가정만 `realized_full` 및 `slgap_full`로 바꿔 edge가 유지되는지 확인한다. `ts_imb`는 RULE baseline이며 수익 보장/실거래 준비 주장이 아니다.

## 고정 입력

- Source universe: `.omx/artifacts/gap_up_full/instances.json`
- Repriced realized instances: `.omx/artifacts/gap_up_realized_full_2026_06_11/instances.json`
- Repriced sl-gap-stress instances: `.omx/artifacts/gap_up_slgap_full_2026_06_11/instances.json`
- Parent run: `probability_lane_stacked_2026_06_11`
- Mode: `stacked_ts_imb`
- Cost basis: source logs are 25bp; probability lane applies frozen `+0.02pp` conversion to report 23bp net values.
- Expected split hash: `cc0483b81cbb486b`
- Seed: `100`
- Folds: 5 chronological expanding folds

## Hypothesis

The stacked supervised gate should preserve positive incremental edge over the same-fill `ts_imb` RULE baseline under both full-universe fill modes. This is a robustness test, not a new threshold search.

## Hard gate

Each fill mode must independently satisfy all items below before it can unlock later RL sizing/exit work:

1. OOS TAKE count >= 100.
2. TAKE mean net pct > 0 at the 23bp converted cost basis.
3. TAKE mean net pct > same-fill `ts_imb` RULE baseline mean.
4. Fold consistency >= 3/5 positive fold deltas.
5. Shuffle/negative control must fail to beat the baseline.
6. Brier <= constant-rate Brier.
7. Ablation fragility < 3/5 ablations beating the full feature set.
8. Verdict must not be `NO-GO_CONTROL`.
9. `INCONCLUSIVE` is analysis-only and fails RL-opening eligibility.

## Required reporting fields

Each result report must include `split_hash`, parent lineage, `fill_mode`, `cost_bps=23`, OOS TAKE count, TAKE mean, same-fill `ts_imb` baseline mean, fold deltas, failed controls, Brier vs constant, ablation count, and total pp vs mean/trade tradeoff.

## Commands

```powershell
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_stacked_realized_full_2026_06_11 --mode stacked_ts_imb --fill-mode realized_full --prereg-doc docs/stom_probability_lane_full_fill_prereg_2026-06-11.md --expected-split-hash cc0483b81cbb486b --parent-run probability_lane_stacked_2026_06_11 --instances .omx/artifacts/gap_up_realized_full_2026_06_11/instances.json
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_stacked_slgap_full_2026_06_11 --mode stacked_ts_imb --fill-mode slgap_full --prereg-doc docs/stom_probability_lane_full_fill_prereg_2026-06-11.md --expected-split-hash cc0483b81cbb486b --parent-run probability_lane_stacked_2026_06_11 --instances .omx/artifacts/gap_up_slgap_full_2026_06_11/instances.json
```

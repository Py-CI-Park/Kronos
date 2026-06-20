# Probability Lane Full-Universe Fill-Mode 재검증 결과 — 2026-06-11

## Verdict

```text
realized_full: GO_CANDIDATE
slgap_full   : GO_CANDIDATE
P1 hard gate : PASS — P2/P3 진행 가능, P5는 아직 보류(P2/P3 필요)
```

본 결과는 `probability_lane_stacked_2026_06_11`의 full-universe 체결모드 강건성 재검증이다. 이것은 `supervised gate` 후보 검증이지 RL 성공이 아니며, 수익 보장/실거래 준비/브로커 준비 주장이 아니다. `ts_imb`는 RULE baseline이다.

## 사전등록 및 lineage

- Prereg: `docs/stom_probability_lane_full_fill_prereg_2026-06-11.md`
- Parent: `probability_lane_stacked_2026_06_11`
- Mode: `stacked_ts_imb`
- Expected split hash: `cc0483b81cbb486b`
- Cost basis: source logs 25bp → probability lane `+0.02pp` conversion으로 23bp net 표시
- Repriced source universe: `.omx/artifacts/gap_up_full/instances.json`

## Artifact generation

```powershell
py -3.11 -m stom_rl.factory.fill_mode_instances --fill-mode realized --output-dir .omx/artifacts/gap_up_realized_full_2026_06_11
py -3.11 -m stom_rl.factory.fill_mode_instances --fill-mode sl_gap_stress --output-dir .omx/artifacts/gap_up_slgap_full_2026_06_11
```

두 artifact 모두 source 29,139건 → repriced 29,139건, missing 0, symbols 2,314, date range 20220323→20260227.

## Lane commands

```powershell
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_stacked_realized_full_2026_06_11 --mode stacked_ts_imb --fill-mode realized_full --prereg-doc docs/stom_probability_lane_full_fill_prereg_2026-06-11.md --expected-split-hash cc0483b81cbb486b --parent-run probability_lane_stacked_2026_06_11 --instances .omx/artifacts/gap_up_realized_full_2026_06_11/instances.json
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_stacked_slgap_full_2026_06_11 --mode stacked_ts_imb --fill-mode slgap_full --prereg-doc docs/stom_probability_lane_full_fill_prereg_2026-06-11.md --expected-split-hash cc0483b81cbb486b --parent-run probability_lane_stacked_2026_06_11 --instances .omx/artifacts/gap_up_slgap_full_2026_06_11/instances.json
```

Outputs:

- `webui/rl_runs/probability_lane/probability_lane_stacked_realized_full_2026_06_11/`
- `webui/rl_runs/probability_lane/probability_lane_stacked_slgap_full_2026_06_11/`

## Aggregate 결과

| Fill mode | Verdict | OOS TAKE | TAKE mean% | same-fill ts_imb mean% | Delta pp | TAKE total pp | ts_imb total pp | SKIP n | SKIP mean% | Brier | Const Brier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| realized_full | GO_CANDIDATE | 3,484 | +0.944 | +0.758 | +0.187 | +3,291 | +3,386 | 985 | +0.097 | 0.2286 | 0.2438 |
| slgap_full | GO_CANDIDATE | 3,331 | +0.857 | +0.656 | +0.201 | +2,856 | +2,933 | 1,138 | +0.068 | 0.2286 | 0.2438 |

Tradeoff는 여전히 존재한다. 모델은 평균/trade를 높이지만 양수 저가치 trade를 일부 스킵하므로 비복리 총합 pp는 same-fill `ts_imb` 단독보다 작다. 이 결과의 의미는 "더 많은 총 pp"가 아니라 "위험예산·사이징에 사용할 trade quality 개선 후보"다.

## Fold별 결과

### realized_full

| Fold | ts_imb n | TAKE | TAKE mean% | ts_imb mean% | Delta pp | SKIP n | SKIP mean% |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 743 | 365 | +1.476 | +0.941 | +0.534 | 378 | +0.425 |
| 1 | 775 | 697 | +0.859 | +0.722 | +0.138 | 78 | −0.509 |
| 2 | 844 | 643 | +1.071 | +0.800 | +0.271 | 201 | −0.067 |
| 3 | 1,039 | 969 | +0.686 | +0.597 | +0.089 | 70 | −0.635 |
| 4 | 1,068 | 810 | +0.987 | +0.779 | +0.208 | 258 | +0.125 |

Consistency: 5/5 positive.

### slgap_full

| Fold | ts_imb n | TAKE | TAKE mean% | ts_imb mean% | Delta pp | SKIP n | SKIP mean% |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 743 | 365 | +1.317 | +0.824 | +0.493 | 378 | +0.347 |
| 1 | 775 | 609 | +0.798 | +0.615 | +0.183 | 166 | −0.056 |
| 2 | 844 | 578 | +1.040 | +0.707 | +0.334 | 266 | −0.018 |
| 3 | 1,039 | 969 | +0.587 | +0.501 | +0.086 | 70 | −0.691 |
| 4 | 1,068 | 810 | +0.887 | +0.680 | +0.207 | 258 | +0.032 |

Consistency: 5/5 positive.

## Control / calibration / ablation

| Fill mode | Shuffle control | Calibration | Ablations better than full | Hard-gate status |
|---|---|---|---:|---|
| realized_full | Shuffle takes all, delta 0 → baseline 초과 실패 | 0.2286 <= 0.2438 | 2/5 | PASS |
| slgap_full | Shuffle takes all, delta 0 → baseline 초과 실패 | 0.2286 <= 0.2438 | 1/5 | PASS |

## P1 hard gate 판정

| Gate | realized_full | slgap_full |
|---|---|---|
| OOS TAKE >= 100 | PASS (3,484) | PASS (3,331) |
| TAKE mean > 0 | PASS (+0.944%) | PASS (+0.857%) |
| same-fill ts_imb baseline 초과 | PASS (+0.187pp) | PASS (+0.201pp) |
| fold consistency >= 3/5 | PASS (5/5) | PASS (5/5) |
| shuffle/negative control baseline 초과 실패 | PASS | PASS |
| Brier <= constant | PASS | PASS |
| ablation fragility < 3/5 | PASS (2/5) | PASS (1/5) |
| NO-GO_CONTROL 없음 | PASS | PASS |

## 결론

P1 full-universe fill-mode 재검증은 통과했다. 따라서 P2 stacked TAKE sizing/risk simulation과 P3 read-only forward/paper evidence ledger로 진행할 수 있다. 그러나 P5 RL sizing/exit controller는 아직 열리지 않는다. P5는 P2 account-level risk-adjusted improvement와 P3 schema freeze까지 통과해야 한다.

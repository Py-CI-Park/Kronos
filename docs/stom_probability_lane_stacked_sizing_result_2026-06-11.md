# Stacked Probability Lane Sizing/Risk 결과 — 2026-06-11

## Verdict

```text
P2 sizing/risk simulation: COMPLETE
P5 account-level prerequisite: NOT MET
Reason: mean/std improves, but fixed-0.5 total pp is lower and maxDD is worse than same-fill ts_imb baseline in both realized_full and slgap_full.
```

이 문서는 `probability_lane_stacked_*_full_2026_06_11` edge ledger를 사용한 account-level sizing/risk 비교다. 이것은 `supervised gate` 운영 가설 검증이며 RL, 수익 보장, live/broker/order readiness가 아니다. `ts_imb`는 RULE baseline이다.

## Inputs

| Fill mode | Edge ledger | Sizing artifact |
|---|---|---|
| realized_full | `webui/rl_runs/probability_lane/probability_lane_stacked_realized_full_2026_06_11/edge_ledger.json` | `webui/rl_runs/sizing_lab/probability_lane_stacked_realized_full_2026_06_11/sizing_summary.json` |
| slgap_full | `webui/rl_runs/probability_lane/probability_lane_stacked_slgap_full_2026_06_11/edge_ledger.json` | `webui/rl_runs/sizing_lab/probability_lane_stacked_slgap_full_2026_06_11/sizing_summary.json` |

Commands:

```powershell
py -3.11 -m stom_rl.factory.sizing_lab --decision-ledger webui/rl_runs/probability_lane/probability_lane_stacked_realized_full_2026_06_11/edge_ledger.json --run-id probability_lane_stacked_realized_full_2026_06_11 --output webui/rl_runs/sizing_lab/probability_lane_stacked_realized_full_2026_06_11/sizing_summary.json
py -3.11 -m stom_rl.factory.sizing_lab --decision-ledger webui/rl_runs/probability_lane/probability_lane_stacked_slgap_full_2026_06_11/edge_ledger.json --run-id probability_lane_stacked_slgap_full_2026_06_11 --output webui/rl_runs/sizing_lab/probability_lane_stacked_slgap_full_2026_06_11/sizing_summary.json
```

## Fixed fraction 0.5 비교

| Fill mode | Strategy trades | Baseline trades | Strategy total pp | Baseline total pp | Delta pp | Strategy MDD pp | Baseline MDD pp | MDD delta | Strategy mean/std | Baseline mean/std | P5 P2 pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| realized_full | 3,484 | 4,469 | +1,645.3 | +1,693.0 | −47.7 | 18.3 | 15.7 | +2.6 worse | 0.309 | 0.250 | NO |
| slgap_full | 3,331 | 4,469 | +1,427.8 | +1,466.3 | −38.4 | 19.3 | 17.3 | +2.0 worse | 0.296 | 0.228 | NO |

해석: stacked gate는 trade-level mean/std는 개선하지만, skipped 양수 trade 때문에 총합 pp가 낮고, deterministic chronological account curve의 max drawdown도 baseline보다 나쁘다. 따라서 P5의 account-level prerequisite을 충족하지 못한다.

## Concurrency / capacity cap 10

| Fill mode | Strategy p95 conc. | Baseline p95 conc. | Strategy max conc. | Baseline max conc. | Strategy skipped cap10 | Baseline skipped cap10 | Strategy cap total pp | Baseline cap total pp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| realized_full | 9.0 | 10.7 | 22 | 23 | 92 | 158 | +3,191.1 | +3,254.6 |
| slgap_full | 9.0 | 10.7 | 22 | 23 | 88 | 158 | +2,764.9 | +2,815.2 |

Stacked gate는 concurrency/capacity 부담을 줄이지만, cap10 총합 pp에서도 same-fill `ts_imb` baseline보다 낮다.

## Daily loss halt -5%

| Fill mode | Strategy halted sessions | Baseline halted sessions | Strategy skipped | Baseline skipped | Strategy total pp | Baseline total pp |
|---|---:|---:|---:|---:|---:|---:|
| realized_full | 70 | 115 | 134 | 289 | +3,243.8 | +3,229.6 |
| slgap_full | 60 | 116 | 119 | 289 | +2,815.3 | +2,800.0 |

일중 -5% halt에서는 stacked가 baseline보다 약간 높은 총합 pp와 낮은 halt 수를 보인다. 그러나 P2의 보수적 prerequisite은 fixed-fraction account curve의 maxDD 악화를 통과로 보지 않는다.

## Worst session

| Fill mode | Strategy worst session | Strategy net pp | Baseline worst session | Baseline net pp |
|---|---|---:|---|---:|
| realized_full | 20250408 | −14.5 | 20250408 | −21.0 |
| slgap_full | 20250408 | −14.7 | 20250408 | −21.2 |

Worst-session 손실은 stacked가 개선한다. 하지만 maxDD는 악화되어 RL opening 조건으로는 부족하다.

## 결론

P2는 필요한 account-level 비교 산출물을 생성했고, stacked gate의 장단점을 분리했다.

- 장점: trade mean/std 개선, concurrency 감소, cap skip 감소, daily halt/worst-session 일부 개선.
- 단점: fixed-0.5 total pp 감소, fixed-0.5 maxDD 악화.
- P5 상태: **자동 보류**. P3 schema freeze와 P4 dashboard evidence는 계속 진행할 수 있지만, 현재 P2 evidence만으로 RL sizing/exit controller를 열지 않는다.

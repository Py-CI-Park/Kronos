# Probability Lane 결과 — `NO-GO_BASELINE` — 2026-06-11

## Verdict

```text
NO-GO_BASELINE (failed_baseline:ts_imb_rule)
```

이 실험은 `supervised gate`(메타라벨)다. RL이 아니다. `ts_imb`는 RULE baseline이며
RL이라 부르지 않는다. 실거래/브로커/수익 보장 주장 없음. 사전등록
`docs/stom_probability_lane_prereg_2026-06-11.md`의 gate를 그대로 적용했고,
OOS 결과를 본 후 어떤 임계치도 수정하지 않았다.

## 실행

```powershell
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_tp5sl1_2026_06_11
```

| 항목 | 값 |
|---|---|
| 데이터 | `.omx/artifacts/gap_up_full/instances.json` (full-universe 갭상승 로그) |
| 후보 수 | 27,311 (feature 결측 제거 후) / 세션 951개 |
| 결과 그리드 | `tp5_sl1` 고정 (TP5/SL1/09:25) |
| 비용 | 23bp (25bp 캐시 + `+0.02%p` 환산) |
| 분할 | expanding-window walk-forward 5 folds, split hash `cc0483b81cbb486b` |
| 모델 | HistGradientBoostingClassifier(seed 100) + isotonic 보정 |
| 산출물 | `webui/rl_runs/probability_lane/probability_lane_tp5sl1_2026_06_11/` |
| Registry | `webui/rl_runs/factory_registry.sqlite` (stage `walkforward`, status `done`) |

## Gate 결과

| Gate | 기준 | 결과 | 통과 |
|---|---|---|---|
| G1 표본력 | OOS TAKE ≥ 100 | **12,194** | **통과** (기존 실험 2~8건 대비 ~1,500배) |
| G2 절대 수익 | TAKE 평균 > 0 | +0.627%/trade | **통과** |
| G3 무선별 baseline | TAKE 평균 > take-all 평균 | +0.627% > +0.258% | **통과** (전 5 fold 일관) |
| G4 RULE baseline | TAKE 평균 ≥ ts_imb 평균 | +0.627% < **+0.820%** | **실패 → 차단** |
| G5 음성 컨트롤 | 라벨 셔플 시 G3 실패해야 함 | 셔플 TAKE 평균 = take-all 평균 (선별 붕괴) | **통과** |
| G6 보정 skill | Brier ≤ 상수 예측기 | 0.1929 ≤ 0.2044 (전 fold) | **통과** |
| G7 Ablation | 과반이 full 우위면 실패 | 5/5 전부 full보다 마진 열위 | **통과** |

## Fold별 증거

| Fold | OOS 후보 | TAKE | TAKE 평균% | take-all% | ts_imb n | ts_imb% | Brier | Brier(상수) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 5,120 | 1,524 | **+1.124** | +0.286 | 743 | +0.979 | 0.1934 | 0.2075 |
| 1 | 4,577 | 3,087 | +0.505 | +0.217 | 775 | +0.781 | 0.1853 | 0.1993 |
| 2 | 3,633 | 1,808 | +0.954 | +0.426 | 844 | +0.860 | 0.2019 | 0.2185 |
| 3 | 4,747 | 3,154 | +0.395 | +0.179 | 1,039 | +0.671 | 0.1953 | 0.1974 |
| 4 | 4,651 | 2,621 | +0.535 | +0.218 | 1,068 | +0.850 | 0.1887 | 0.1994 |

Ablation (margin = TAKE 평균 − take-all 평균; full margin +0.369):

| Ablation | TAKE 평균% | margin |
|---|---:|---:|
| no_entry_change_rate | +0.563 | +0.305 |
| no_entry_trade_strength | +0.560 | +0.302 |
| no_entry_bid_ask_imbalance | +0.479 | +0.221 |
| no_entry_sec_amount | +0.461 | +0.203 |
| no_entry_price | +0.515 | +0.257 |

모든 ablation이 full보다 열위 → feature 기여가 처음으로 안정적으로 양(+)이다.
과거 RL smoke의 attribution collapse(전부 동일 수익)와 대조적이다.

## 해석

1. **사상 첫 유의미한 학습 신호.** 표본력 있는 OOS(12,194 TAKE)에서 선별 skill
   (G3, 전 fold), 보정 skill(G6, 전 fold), 컨트롤 정상(G5), ablation 정합(G7)이
   동시에 성립했다. 과거 `NO-GO`들과 질적으로 다른 실패다: 모델은 작동하나
   수작업 룰을 아직 못 이긴다.
2. **차단 사유는 G4 하나.** ts_imb RULE(전 universe OOS 4,469 trades, +0.820%)이
   모델 TAKE(+0.627%)보다 trade당 평균이 높다. fold 0에서는 모델이 ts_imb를
   이겼으나(+1.124 vs +0.979) 5 fold 중 1개뿐이다.
3. **탐색적 관찰 (verdict에 미반영, 차기 사전등록 후보).** 모델 TAKE 총합은
   +7,645.9%(12,194건)로 ts_imb 총합 +3,664.2%(4,469건)의 약 2.1배다. mean 기준
   gate(G4)는 자본 배치량 차이를 무시한다. 또한 edge 임계치를 0보다 높여
   trade 수를 ts_imb 수준으로 줄였을 때의 평균 비교는 본 실험에서 사전등록되지
   않았으므로 수행하지 않았다. 차기 실험에서 사전등록 후 검증할 것.

## P6 (Full-Train RL) 차단 결정

사전등록 해석 경계에 따라, verdict가 `NO-GO_*`이므로 **P6 Full-Train RL 경로는
착수하지 않는다.** `STOP_RL_EXPANSION` 결정 유지. 차단 해제 조건: probability
lane 계열 실험이 G1~G7 전부 통과(`GO_CANDIDATE`).

## 다음 유효 단계 (사전등록 필요)

1. edge 임계치 상향(정밀도-재현율 트레이드오프) 후 G4 재검: 모델 TAKE 수를
   ts_imb 규모로 맞춘 매칭 비교.
2. ts_imb 필터를 feature가 아닌 **사전 필터**로 두고, 모델은 ts_imb 통과 후보의
   2차 선별/사이징만 담당하는 stacked gate.
3. realized / sl_gap_stress fill 모드 재검 (현재는 idealized 로그 기반).

## 가드레일

- 이 결과는 수익 보장이 아니다. idealized fill 로그 기반 백테스트 증거다.
- `ts_imb`는 RULE baseline. 모델 곡선을 RL이라 부르지 않는다.
- 대시보드는 read-only 증거 뷰어다.

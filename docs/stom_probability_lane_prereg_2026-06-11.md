# Probability Lane 사전등록 — P(win) 보정 분류기 + 엣지 회계 — 2026-06-11

## 상태

`supervised gate` 사전등록 문서다. RL이 아니다. `ts_imb`는 RULE baseline이며 RL이라
부르지 않는다. 실거래/브로커/수익 보장 주장 없음. 이 문서 커밋 이후에 실험을
실행하며, OOS 결과를 본 뒤 본 문서의 가설·임계치·gate를 수정하지 않는다.

## 가설

시초 갭상승(등락율 >= 2%) 진입 후보의 **진입 시점 causal feature**만으로
P(win | 후보)를 보정(calibrated) 추정하면, "전부 진입(take-all)" 무선별 baseline보다
trade당 평균 net 수익이 높은 TAKE 부분집합을 OOS에서 선택할 수 있다.

## 데이터 (고정)

| 항목 | 값 |
|---|---|
| 소스 | `.omx/artifacts/gap_up_full/instances.json` (full-universe 갭상승 백테스트 로그) |
| N | 29,139 진입 후보 (필터 없음, 전 universe) |
| 기간 | 세션 날짜 기준 전체 구간 (2022~2026) |
| 결과 그리드 | `tp5_sl1` (TP 5% / SL 1% / 09:25 시간청산) 고정 — 주력 룰과 동일 |
| 비용 | 캐시 net pct는 25bp 기준. 23bp 환산 = `+0.02%p` 가산 (resume 2026-05-29 문서 규칙). 이후 모든 수치는 23bp 환산값 |

## Feature (진입 시점 causal만, 고정)

`entry_change_rate`, `entry_trade_strength`, `entry_bid_ask_imbalance`,
`entry_sec_amount`, `entry_price` — 5개.

제외(미래 누수): `n_path_bars`, `baseline_net_pct`, `baseline_hold_seconds`,
모든 `tp*_sl*` 결과 필드. `pass_ts`/`pass_ts_imb`는 feature가 아니라 baseline
부분집합 정의로만 사용.

## 라벨

`win = (tp5_sl1_net_pct_23bp > 0)`.

## 모델/보정 (고정)

- 분류기: `sklearn.ensemble.HistGradientBoostingClassifier` (기본 하이퍼파라미터,
  `random_state=100`). 하이퍼파라미터 탐색 없음.
- 보정: train 내부 분할로 isotonic calibration (validation 세션으로 fit).
- 평가: Brier score + reliability bins (10 bins).

## 분할 (고정)

`stom_rl/factory/walk_forward.chronological_folds`, 세션 날짜 오름차순,
`n_folds=5`, expanding window. OOS 세션은 어떤 fold에서도 학습/보정/선택에
사용하지 않는다. split hash는 manifest에 기록 후 동결.

## 엣지 회계 (고정)

- `E[win_net]`, `E[loss_net]`: 각 fold의 train+validation에서만 추정 (승/패 조건부
  평균 net %).
- `edge(x) = P(win|x)·E[win_net] + (1−P(win|x))·E[loss_net]` (net은 비용 포함이므로
  breakeven은 0).
- TAKE 규칙: `edge > 0`. 임계치 탐색 없음.

## Gate (고정 — 실행 전 동결)

| ID | Gate | 기준 | 실패 라벨 |
|---|---|---|---|
| G1 | 표본력 | 전 fold 합산 OOS TAKE ≥ 100 | `INCONCLUSIVE` (insufficient_oos_take_trades) |
| G2 | 절대 수익 | OOS TAKE 평균 net/trade > 0 | `NO-GO` (failed_absolute) |
| G3 | 무선별 baseline | OOS TAKE 평균 > take-all 평균 (동일 fold OOS 후보 전체) | `NO-GO_BASELINE` (failed_baseline:take_all) |
| G4 | RULE baseline | OOS TAKE 평균 ≥ ts_imb 부분집합(OOS, `pass_ts_imb`) 평균 | `NO-GO_BASELINE` (failed_baseline:ts_imb_rule) |
| G5 | 음성 컨트롤 | 라벨 셔플 재학습 시 G3가 실패해야 함 (셔플이 통과하면 회계/파이프라인 누수 의심) | `NO-GO_CONTROL` (failed_controls) |
| G6 | 보정 skill | OOS Brier ≤ 상수 예측기(훈련 승률) Brier | `NO-GO_CONTROL` (failed_calibration_skill) |
| G7 | Ablation 안정성 | 단일 feature 제거 변형 5개 중 과반(≥3)이 full보다 G3 마진 우위면 실패 | `NO-GO_ABLATION` (failed_ablations) |

종합 verdict: `stom_rl/factory/walk_forward.synthesize_fold_verdicts` + 위 차단
사유. 모든 gate 통과 시에만 `GO_CANDIDATE`. `GO_CANDIDATE`여도 수익 보장이
아니며 다음 단계(전향 검증/사이징 통합) 진입 자격일 뿐이다.

## 산출물

`webui/rl_runs/probability_lane/<run_id>/` 아래: manifest(split hash, 비용 규칙,
guardrail), fold별 metrics, calibration(reliability bins, Brier), edge ledger
(trade별 P/edge/TAKE-SKIP), controls, ablations, verdict JSON. 대시보드는
read-only로만 읽는다.

## 실행 등록

run id: `probability_lane_tp5sl1_2026_06_11`. 실험 큐
(`stom_rl/factory/experiment_queue.enqueue_experiment`)에 본 문서를 `prereg_doc`로
등록 후 실행한다. cost_bps=23.0, seed=100, stage=`walkforward`.

## 해석 경계

- 이 실험은 P6(Full-Train RL) 차단 해제 여부를 결정하는 선행 gate다.
- `NO-GO_*`/`INCONCLUSIVE`면 P6은 `STOP_RL_EXPANSION` 결정대로 차단 유지.
- 로그 데이터(idealized fill) 기반이므로, 통과해도 체결 스트레스(realized,
  sl_gap_stress) 재검증 전에는 운영 후보가 아니다.

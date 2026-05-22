# STOM 2025 full-small predictor 평가 및 대시보드 연결 보고

작성일: 2026-05-22 KST

## 1. 목적

완료된 `stom_1s_grid_pred60_2025_full_small` predictor checkpoint가 실제로 예측에 사용 가능한지 확인하고, 사용자가 웹 대시보드에서 실제값과 예측값, 방향 적중률, 종목별 통계, Top-K 후보를 이해하기 쉽게 확인하도록 연결했다.

## 2. 사용 모델과 데이터

| 항목 | 값 |
| --- | --- |
| 모델 run | `stom_1s_grid_pred60_2025_full_small` |
| predictor checkpoint | `finetune/outputs/stom_1s_grid_pred60_2025_full_small/finetune_predictor/checkpoints/best_model` |
| tokenizer checkpoint | `finetune/outputs/stom_1s_grid_pred60_2025_full_small/finetune_tokenizer/checkpoints/latest_train_model` |
| 데이터셋 | `finetune/qlib_exports/stom_1s_grid_pred60_2025/processed_datasets` |
| split | test split |
| 예측 horizon | 60초 |
| lookback | 300초 |
| 평가 범위 | 2025-11-07 ~ 2025-12-30 test session 전체, 각 session 3개 as-of, 최대 50종목 |

## 3. 실행 명령

```powershell
C:\Python\64\Python3119\python.exe finetune\evaluate_stom_1s_checkpoint.py `
  --dataset-path finetune\qlib_exports\stom_1s_grid_pred60_2025\processed_datasets `
  --model-path finetune\outputs\stom_1s_grid_pred60_2025_full_small\finetune_predictor\checkpoints\best_model `
  --tokenizer-path finetune\outputs\stom_1s_grid_pred60_2025_full_small\finetune_tokenizer\checkpoints\latest_train_model `
  --output-dir webui\stom_predictions `
  --prefix stom_1s_pred60_2025_full_small_walkforward36x3x50_eval `
  --lookback-window 300 `
  --predict-window 60 `
  --max-symbols 50 `
  --max-asofs 3 `
  --max-sessions 36 `
  --stride 300 `
  --batch-size 8 `
  --top-k 5 `
  --device cuda:0
```

Qlib-style Top-K 비용 반영 점검:

```powershell
C:\Python\64\Python3119\python.exe finetune\qlib_stom_pipeline.py score-backtest `
  --prediction-csv webui\stom_predictions\stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos.csv `
  --output-dir webui\qlib_backtests `
  --top-k 5 `
  --cost-bps 15 `
  --slippage-bps 10
```

## 4. 산출물

| 종류 | 경로 |
| --- | --- |
| Kronos 예측 CSV | `webui/stom_predictions/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos.csv` |
| persistence baseline CSV | `webui/stom_predictions/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_persistence.csv` |
| random baseline CSV | `webui/stom_predictions/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_random.csv` |
| 비교 JSON | `webui/stom_predictions/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_comparison.json` |
| Qlib Top-K JSON | `webui/qlib_backtests/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos.qlib_topk5.json` |

## 5. 핵심 결과

| 지표 | Kronos | Persistence | Random |
| --- | ---: | ---: | ---: |
| rows | 40,860 | 40,860 | 40,860 |
| windows | 681 | 681 | 681 |
| symbols | 155 | 155 | 155 |
| direction accuracy | 0.4479 | 0.1204 | 0.4493 |
| MAPE | 0.8730 | 0.3852 | 0.3906 |
| 평균 예측 등락률 | -0.0218% | 0.0000% | 0.0041% |
| 평균 실제 등락률 | 0.0598% | 0.0598% | 0.0598% |
| Top-K hit rate | 0.4667 | 0.1241 | 0.4352 |
| Top-K 평균 실제 등락률 | 0.0459% | 0.0711% | 0.0758% |

비용 반영 Qlib-style Top-K:

| 항목 | 값 |
| --- | ---: |
| period count | 108 |
| trade count | 540 |
| avg gross return | 0.0459% |
| avg net return | -0.2041% |
| cumulative return | -19.8646% |
| max drawdown | -20.4773% |
| direction hit rate | 0.4667 |

## 6. 해석

- 모델은 정상 로드되고 2025년 test split 전체 거래일 범위에서 예측 CSV를 생성했다.
- direction accuracy는 0.4479로 0.40 기준선은 넘었지만 random baseline 0.4493과 거의 같아, 방향성만으로 우위가 확정되지는 않는다.
- MAPE는 persistence/random보다 높아 가격 경로 자체는 baseline보다 거칠다.
- Top-K hit rate는 persistence보다 높지만, 비용 25bp를 반영하면 평균 순수익과 누적수익이 음수다.
- 따라서 현재 checkpoint는 “탐색/시각화/조건식 연구용”으로는 의미가 있지만, 실전 자동매매 신호로 바로 사용하기에는 부족하다.

## 7. 대시보드 업데이트

`http://127.0.0.1:5070/training` → `예측 진단` 탭에서 최신 Kronos CSV를 자동 선택하고 다음을 표시한다.

1. 사용자용 판정 카드: 탐색 가치 / 조건식 보완 / 실전 보류
2. 방향 적중률, MAPE, 평가 windows/symbols/sessions, 평균 실제 등락률 KPI
3. 조건식/Top-K 필터별 hit rate와 실제 수익률
4. 선택 window의 실제 종가 vs Kronos 예측 종가 차트
5. 전체 window의 예측 등락률 vs 실제 등락률 산점도
6. Kronos 점수 상위 후보 테이블
7. 상위/주의 종목별 방향 적중률과 MAPE

## 8. 다음 단계

1. 비용 음수 문제를 줄이기 위해 score filter, 거래대금/체결강도/변동성 조건을 추가한다.
2. random과 거의 같은 direction accuracy를 개선하기 위해 seed/epoch/model size 비교를 진행한다.
3. full as-of 평가를 원하면 `max-asofs`를 3보다 크게 늘려 더 촘촘한 walk-forward 평가를 실행한다.
4. 대시보드에서 후보를 클릭하면 해당 window 차트로 전환하는 상호작용을 추가한다.

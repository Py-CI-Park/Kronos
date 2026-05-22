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

## 9. 조건식 / 비용 필터 최적화 1차 실행 결과

작성일: 2026-05-22 KST

위 8번의 다음 단계 중 “비용 음수 문제를 줄이기 위한 score filter / 거래대금 / 변동성 조건”을 먼저 실행했다.

### 9.1 실행 명령

```powershell
$pred = 'webui\stom_predictions\stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos.csv'
$prefix = 'stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos_cost25'

C:\Python\64\Python3119\python.exe finetune\search_stom_1s_filters.py `
  --prediction-csv $pred `
  --output-dir webui\qlib_backtests `
  --prefix $prefix `
  --top-k 5 `
  --cost-bps 15 `
  --slippage-bps 10 `
  --min-trades 10 `
  --min-periods 3 `
  --min-coverage 0.5

C:\Python\64\Python3119\python.exe finetune\search_stom_1s_filters.py `
  --prediction-csv $pred `
  --output-dir webui\qlib_backtests `
  --prefix $prefix `
  --top-k 5 `
  --cost-bps 15 `
  --slippage-bps 10 `
  --min-trades 10 `
  --min-periods 3 `
  --min-coverage 0.5 `
  --rolling-validate `
  --rolling-train-periods 30 `
  --rolling-test-periods 10 `
  --rolling-step-periods 10

C:\Python\64\Python3119\python.exe finetune\search_stom_1s_filters.py `
  --output-dir webui\qlib_backtests `
  --prefix $prefix `
  --gate-analysis `
  --filter-report webui\qlib_backtests\${prefix}.filter_search.json `
  --rolling-report webui\qlib_backtests\${prefix}.rolling_filter_validation.json `
  --total-cost-bps-grid 5,10,15,25 `
  --min-avg-test-net-pct 0 `
  --min-positive-test-fold-rate 0.5 `
  --min-improvement-net-pct 0 `
  --min-total-test-trades 100
```

### 9.2 산출물

| 종류 | 경로 |
| --- | --- |
| 필터 탐색 JSON | `webui/qlib_backtests/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos_cost25.filter_search.json` |
| 필터 Top20 CSV | `webui/qlib_backtests/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos_cost25.filter_search_top20.csv` |
| rolling 검증 JSON | `webui/qlib_backtests/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos_cost25.rolling_filter_validation.json` |
| cost gate JSON | `webui/qlib_backtests/stom_1s_pred60_2025_full_small_walkforward36x3x50_eval_kronos_cost25.cost_gate.json` |

### 9.3 기본 Top-K 대비 최적 필터

| 항목 | 기본 Top-K | 최적 필터 |
| --- | ---: | ---: |
| 필터 | 없음 | `ret>=0.05`, `cons>=0.5`, `amount q>=0.75` |
| 평가 period | 108 | 56 |
| trade 수 | 540 | 87 |
| coverage | 100.00% | 51.85% |
| 평균 gross return | 0.0459% | 0.1590% |
| 평균 net return, 비용 25bp | -0.2041% | -0.0168% |
| direction hit rate | 46.67% | 47.13% |
| 누적수익 | -19.8646% | -1.1639% |

해석:

- 필터를 걸면 무조건 매수하는 기본 Top-K보다 손실은 크게 줄어든다.
- 하지만 25bp 비용을 넣으면 평균 순수익이 아직 음수다.
- 방향 적중률도 47.13%로 50%를 넘지 못했다.

### 9.4 Rolling validation 결과

| 항목 | 값 |
| --- | ---: |
| fold 수 | 7 |
| 총 test trade | 66 |
| 평균 train net return | 0.0831% |
| 평균 test net return | -0.2043% |
| 평균 test baseline net return | -0.1726% |
| test 개선폭 | -0.0317% |
| test 방향 적중률, weighted | 39.39% |
| 양수 fold 비율 | 28.57% |
| overfit gap | 0.2874% |

Cost sensitivity:

| 총 비용 | rolling test net | passes gate |
| ---: | ---: | --- |
| 5bp | -0.0043% | false |
| 10bp | -0.0543% | false |
| 15bp | -0.1043% | false |
| 25bp | -0.2043% | false |

### 9.5 결정

`cost_gate.json`의 결정은 다음과 같다.

| 항목 | 값 |
| --- | --- |
| decision | `hold_expand_200k` |
| expand_training_allowed | `false` |
| reason | target cost scenario failed at least one rolling profitability/stability gate |

즉, 현재 checkpoint와 현재 조건식만으로는 200k / 전체 확장 학습을 바로 진행하기보다, 먼저 다음 문제를 해결하는 것이 안전하다.

1. 방향 적중률이 random 수준을 넘지 못하는 문제
2. train 구간에서 고른 필터가 test 구간에서 무너지는 과최적화 문제
3. 1초/60초 초단기 horizon에서 25bp 비용을 이기기 어려운 문제
4. 가격 경로 MAPE가 persistence/random보다 높은 문제

### 9.6 현재 결론

파인튜닝은 실패라기보다 “학습은 정상 완료됐지만 현재 설정에서는 실전 신호력이 부족한 상태”다. 모델이 CSV를 만들고, checkpoint가 정상 로드되고, 대시보드에서 실제/예측 비교까지 가능하므로 파이프라인은 동작한다. 다만 예측 품질은 아직 실전 기준을 통과하지 못했다.

다음 권장 작업은 모델을 무작정 크게 돌리는 것이 아니라, 먼저 아래 중 하나를 비교 실험하는 것이다.

1. horizon을 30초, 60초, 120초, 300초로 나눠 실제로 비용을 이길 수 있는 구간 찾기
2. 방향 분류 / 등락률 회귀를 분리해 loss와 평가 지표를 목적에 맞게 조정
3. 종목별 정규화와 장초반 이벤트성 특징을 강화
4. rolling validation에서 통과하는 조건식만 대시보드에 “실전 후보”로 표시

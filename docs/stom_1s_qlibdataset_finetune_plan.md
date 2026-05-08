# STOM 1초봉 Kronos QlibDataset 전체 파인튜닝 계획

작성일: 2026-05-08

## 현재 단계 결론

1초봉을 pyqlib provider로 직접 학습하는 경로가 아니라, **STOM 1초봉을 Kronos `QlibDataset` pickle 형식으로 변환한 뒤 `finetune/train_predictor.py`로 파인튜닝**하는 경로가 맞다.

이번 단계에서는 전체 데이터 학습 전에 필요한 데이터 품질 게이트를 추가했다.

- `--regularize-1s`: 1초 grid 보정
- `--split-by session`: 날짜/session 기준 train/val/test split
- `--horizon-seconds`: 30초/60초 후 target을 명시하는 horizon preset
- export report에 `split_sessions`, `grid_summary`, `effective_predict_window` 기록
- `dump_bin` command에 export freq 보존

## 전체 페이지 진행률

| 페이지 | 내용 | 상태 | 완료율 |
| ---: | --- | --- | ---: |
| 1 | STOM DB 구조 분석 | 완료 | 100% |
| 2 | STOM tick 기본 OHLCV 변환 | 완료 | 100% |
| 3 | 기존 all-table bounded 학습 | 완료/품질 낮음 | 60% |
| 4 | 1초봉 QlibDataset 전체 학습 데이터 구축 | 진행 중 | 65% |
| 5 | 30초/60초 모델 파인튜닝 | 남음 | 0% |
| 6 | baseline/walk-forward/Top-K 검증 | 남음 | 0% |
| 7 | 대시보드/추천/Future_Trading 적용 | 부분 완료 | 45% |

현재 전체 진행률: 약 **60~65%**.

## 왜 이 단계가 필요한가

기존 모델의 `direction_accuracy=0.40`은 실전 매매 신호로 사용하기 어렵다. 특히 기존 경로에는 다음 문제가 있었다.

1. `predict_window=30/60`이 실제 30초/60초가 아니라 30/60 row일 수 있음.
2. train/val/test가 group 단위라 같은 거래일이 여러 split에 나뉠 수 있음.
3. 전체 universe 대상이라도 모든 가능한 window를 끝까지 학습한 것이 아니라 bounded 학습임.

따라서 재학습 전에 먼저 **정확한 시간 grid와 날짜 기준 split**을 고정해야 한다.

## 파일럿 검증 결과

### 30초 horizon 파일럿

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1s_grid_pred30_stage_pilot `
  --max-tables 2 `
  --lookback-window 30 `
  --horizon-seconds 30 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 090200 `
  --freq 1s `
  --regularize-1s `
  --split-by session `
  --max-groups 6 `
  --train-ratio 0.5 `
  --val-ratio 0.25 `
  --test-ratio 0.25
```

결과:

- exported groups: 4
- exported rows: 435
- grid inserted rows: 239
- train/val/test session 중복 없음
- `QlibDataset` load smoke 성공

### 60초 horizon 파일럿

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1s_grid_pred60_stage_pilot `
  --max-tables 2 `
  --lookback-window 60 `
  --horizon-seconds 60 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 090300 `
  --freq 1s `
  --regularize-1s `
  --split-by session `
  --max-groups 6 `
  --train-ratio 0.5 `
  --val-ratio 0.25 `
  --test-ratio 0.25
```

결과:

- exported groups: 4
- exported rows: 675
- grid inserted rows: 382
- train/val/test session 중복 없음

## 전체 데이터 export 명령

### 30초 후 예측용 전체 데이터

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1s_grid_pred30_full `
  --max-tables 0 `
  --lookback-window 300 `
  --horizon-seconds 30 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 093000 `
  --freq 1s `
  --regularize-1s `
  --split-by session `
  --train-ratio 0.70 `
  --val-ratio 0.15 `
  --test-ratio 0.15
```

### 60초 후 예측용 전체 데이터

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1s_grid_pred60_full `
  --max-tables 0 `
  --lookback-window 300 `
  --horizon-seconds 60 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 093000 `
  --freq 1s `
  --regularize-1s `
  --split-by session `
  --train-ratio 0.70 `
  --val-ratio 0.15 `
  --test-ratio 0.15
```

## 파인튜닝 연결

30초 모델:

```powershell
$env:KRONOS_DATASET_PATH="D:\Chanil_Park\Project\Programming\Kronos\finetune\qlib_exports\stom_1s_grid_pred30_full\processed_datasets"
$env:KRONOS_LOOKBACK_WINDOW="300"
$env:KRONOS_PREDICT_WINDOW="30"
$env:KRONOS_USE_COMET="0"
$env:KRONOS_SAVE_PATH="finetune\outputs\stom_1s_grid_pred30"
python finetune\train_predictor.py
```

60초 모델:

```powershell
$env:KRONOS_DATASET_PATH="D:\Chanil_Park\Project\Programming\Kronos\finetune\qlib_exports\stom_1s_grid_pred60_full\processed_datasets"
$env:KRONOS_LOOKBACK_WINDOW="300"
$env:KRONOS_PREDICT_WINDOW="60"
$env:KRONOS_USE_COMET="0"
$env:KRONOS_SAVE_PATH="finetune\outputs\stom_1s_grid_pred60"
python finetune\train_predictor.py
```

## 남은 검증

1. 전체 데이터 export를 장시간 실행하고 manifest를 보관한다.
2. 30초/60초 모델을 각각 학습한다.
3. persistence baseline과 같은 holdout 날짜에서 비교한다.
4. `direction_accuracy=0.40` 기존 모델보다 개선되는지 확인한다.
5. 개선되지 않으면 실전 추천에는 계속 사용하지 않는다.

## 2026-05-08 전체 export 완료 결과

`--regularize-1s`, `--split-by session`, `--horizon-seconds`를 적용한 STOM 1초봉 전체 export를 30초/60초 horizon 모두 완료했다. 상세 근거는 `docs/stom_1s_full_export_report.md`에 고정했다.

| 항목 | 30초 horizon | 60초 horizon |
| --- | ---: | ---: |
| 성공 stock table | 2,425 | 2,425 |
| 제외 non-stock table | 2 | 2 |
| export group | 73,900 | 73,900 |
| export row | 131,470,857 | 131,470,857 |
| train sessions | 665 | 665 |
| val sessions | 143 | 143 |
| test sessions | 143 | 143 |
| session overlap | 0 | 0 |

현재 페이지 판단:

```text
Page 1 DB 구조 분석                    [██████████] 100%
Page 2 STOM tick OHLCV 변환            [██████████] 100%
Page 3 bounded/pilot 학습 검증          [██████░░░░] 60%
Page 4 1초봉 전체 QlibDataset 구축      [██████████] 100%
Page 5 30초/60초 Kronos 파인튜닝        [░░░░░░░░░░] 0%
Page 6 baseline/walk-forward 검증       [█░░░░░░░░░] 10%
Page 7 웹 대시보드/Future 연동          [█████░░░░░] 50%
```

전체 진행률은 약 **70%**로 본다. 다음 commit 단위는 실제 파인튜닝을 실행하고, 기존 `direction_accuracy=0.40` 결과와 동일 holdout 기준으로 비교하는 것이다.

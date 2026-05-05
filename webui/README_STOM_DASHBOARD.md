# STOM Kronos 대시보드 사용법

## 목적

`/stom` 페이지는 STOM tick DB에서 만든 Kronos OHLCV 학습/검증 결과를 확인하는 연구용 대시보드입니다.

확인할 수 있는 것:

- 전체 DB 학습 가능 요약
- 파일럿/전체 학습 진행 명령
- 실제값 vs 예측값 차트
- MAE/RMSE/MAPE/방향정확도
- 예상등락률 Top-K 검증

## 1. 대시보드 의존성 설치

기존 webui requirements를 사용합니다.

```powershell
python -m pip install -r webui/requirements.txt
```

## 2. 파일럿 데이터 생성

```powershell
python finetune_csv/prepare_stom_1tick.py export `
  --db _database/stock_tick_back.db `
  --output finetune_csv/data/stom_1tick_kline_pilot.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-tables 100 `
  --price-mode close_only
```

## 3. 예측 검증 파일 생성

모델이 아직 없으면 baseline으로 먼저 대시보드를 확인합니다.

```powershell
python finetune_csv/stom_prediction_eval.py `
  --data finetune_csv/data/stom_1tick_kline_pilot.csv `
  --output webui/stom_predictions/pilot_predictions.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 20 `
  --mode baseline
```

학습 모델이 있으면:

```powershell
python finetune_csv/stom_prediction_eval.py `
  --data finetune_csv/data/stom_1tick_kline_pilot.csv `
  --output webui/stom_predictions/kronos_predictions.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 20 `
  --mode kronos `
  --model-path finetune_csv/finetuned/stom_1tick_lookback300_pred60/basemodel/best_model `
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base `
  --device cuda:0
```

## 4. 실행

```powershell
python webui/run.py
```

접속:

```text
http://localhost:7070/stom
```

## 주의

- `webui/stom_predictions/*.csv`는 생성 결과이므로 기본 커밋 대상이 아닙니다.
- baseline 결과는 모델 성능이 아니라 대시보드 smoke test용입니다.
- 실제 학습 모델 검증은 `--mode kronos`로 생성한 prediction CSV를 사용해야 합니다.

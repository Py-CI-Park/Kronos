# STOM Qlib Kronos 파이프라인 개발/사용 문서

작성일: 2026-05-07

## 1. 목적

기존 STOM 파인튜닝은 `finetune_csv`의 grouped CSV 경로로 진행되었다. 이 문서는 STOM `stock_tick_back.db`를 Qlib 연구 흐름에 연결하기 위한 새 pilot-first 파이프라인을 설명한다.

목표 흐름:

```text
STOM SQLite DB
→ Qlib dump-ready CSV
→ Kronos QlibDataset pickle split
→ Kronos predictor fine-tuning
→ Kronos prediction CSV
→ Qlib-style Top-K score backtest
→ 웹 대시보드 시각화
```

참고:

- Qlib 공식 문서는 CSV를 Qlib `.bin` format으로 변환할 때 `scripts/dump_bin.py dump_all`을 사용하며, `date_field_name`, `symbol_field_name`, `include_fields`를 지정할 수 있다고 설명한다.
- Qlib의 기본 목적은 데이터 계층, feature retrieval, dataset, backtest/risk analysis를 표준화하는 것이다.
- 현재 구현은 pyqlib을 강제 dependency로 추가하지 않고, Qlib dump-ready CSV와 Kronos `QlibDataset` pickle split을 먼저 생성한다. pyqlib 설치 후에는 생성된 command로 `.bin` 변환을 이어갈 수 있다.

## 2. 새로 추가된 구성

| 파일 | 역할 |
| --- | --- |
| `finetune/qlib_stom_pipeline.py` | STOM→Qlib export, Qlib-style Top-K score backtest CLI |
| `tests/test_stom_qlib_pipeline.py` | synthetic STOM DB export/backtest 검증 |
| `webui/stom_dashboard.py` | Qlib backtest artifact list/load/chart helper |
| `webui/app.py` | `/api/stom/qlib-backtests` API |
| `webui/templates/stom_dashboard.html` | Qlib Top-K equity curve와 metrics 표시 |
| `.gitignore` | 대용량 Qlib export/backtest 산출물 제외 |

## 3. STOM DB → Qlib pilot export

### 3.1 1초 pilot

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1s_pilot `
  --max-tables 50 `
  --lookback-window 300 `
  --predict-window 60 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 093000 `
  --freq 1s `
  --max-groups 500 `
  --train-ratio 0.70 `
  --val-ratio 0.15 `
  --test-ratio 0.15
```

### 3.2 1분 pilot

1분봉은 Qlib daily/minute 연구 흐름에 더 자연스럽다. 단, `lookback + predict + 1` row를 만족해야 하므로 window를 1분 단위에 맞게 줄여야 한다.

```powershell
python finetune\qlib_stom_pipeline.py export `
  --db _database\stock_tick_back.db `
  --output-dir finetune\qlib_exports\stom_1min_pilot `
  --max-tables 50 `
  --lookback-window 20 `
  --predict-window 5 `
  --price-mode close_only `
  --time-start 090000 `
  --time-end 093000 `
  --freq 1min `
  --max-groups 500
```

## 4. Export 산출물

예: `finetune\qlib_exports\stom_1s_pilot`

```text
qlib_csv/
  KR000001_20260102.csv
  ...
processed_datasets/
  train_data.pkl
  val_data.pkl
  test_data.pkl
meta/
  calendar_1s.txt
  instruments_all.txt
  qlib_dump_bin_command.txt
stom_qlib_export_report.json
```

### 4.1 Qlib dump-ready CSV

각 CSV는 다음 컬럼을 가진다.

```text
symbol,date,open,high,low,close,volume,amount,money,factor
```

이 구조는 Qlib `dump_bin.py`에 연결하기 위한 전단계다.

### 4.2 Kronos QlibDataset pickle

`finetune/dataset.py`의 `QlibDataset`은 다음 pickle을 읽는다.

```text
train_data.pkl
val_data.pkl
test_data.pkl
```

각 pickle은 다음 형태다.

```python
{
    "KR000001_20260102": DataFrame(
        index=datetime,
        columns=["open", "high", "low", "close", "vol", "amt"]
    )
}
```

주의: key를 `symbol + session`으로 만든 이유는 기존 `QlibDataset`이 symbol 단위로 연속 window를 만들기 때문이다. session을 분리하지 않으면 하루 끝 window가 다음날로 넘어가는 누수가 생길 수 있다.

## 5. pyqlib `.bin` 변환

export 후 다음 파일에 command가 저장된다.

```text
meta\qlib_dump_bin_command.txt
```

예:

```powershell
python scripts/dump_bin.py dump_all `
  --csv_path finetune/qlib_exports/stom_1s_pilot/qlib_csv `
  --qlib_dir finetune/qlib_exports/stom_1s_pilot/qlib_bin `
  --date_field_name date `
  --symbol_field_name symbol `
  --include_fields open,high,low,close,volume,amount,money,factor
```

현재 repo에는 pyqlib을 강제 설치하지 않는다. pyqlib 설치/경로 확정 후 위 command를 실행한다.

## 6. Kronos predictor 학습 연결

export된 pickle을 기존 `finetune/dataset.py`가 읽게 하려면 환경변수를 지정한다.

```powershell
$env:KRONOS_DATASET_PATH="D:\Chanil_Park\Project\Programming\Kronos\finetune\qlib_exports\stom_1s_pilot\processed_datasets"
$env:KRONOS_LOOKBACK_WINDOW="300"
$env:KRONOS_PREDICT_WINDOW="60"
$env:KRONOS_EPOCHS="1"
$env:KRONOS_BATCH_SIZE="8"
$env:KRONOS_N_TRAIN_ITER="2000"
$env:KRONOS_N_VAL_ITER="400"
$env:KRONOS_USE_COMET="0"
$env:KRONOS_PRETRAINED_TOKENIZER_PATH="NeoQuasar/Kronos-Tokenizer-base"
$env:KRONOS_PRETRAINED_PREDICTOR_PATH="NeoQuasar/Kronos-small"
```

그 다음 기존 Qlib predictor fine-tune entry를 사용한다.

```powershell
python finetune\train_predictor.py
```

주의:

- 이 script는 DDP/CUDA 전제를 포함한다.
- 실전 장시간 학습 전에는 작은 pilot pickle로 loader smoke test를 먼저 수행한다.
- 현재 `finetune_csv/train_sequential.py` 경로가 이미 검증되어 있으므로, Qlib 경로는 pilot부터 단계적으로 확대한다.

## 7. Kronos prediction CSV → Qlib-style Top-K backtest

기존 예측 CSV를 score로 사용한다.

```powershell
python finetune\qlib_stom_pipeline.py score-backtest `
  --prediction-csv webui\stom_predictions\kronos_all_predictions.csv `
  --output-dir webui\qlib_backtests `
  --top-k 10 `
  --cost-bps 15 `
  --slippage-bps 10
```

산출물:

```text
webui/qlib_backtests/*.json
webui/qlib_backtests/*.curve.csv
webui/qlib_backtests/*.trades.csv
```

실제 실행 예시 결과:

```text
period_count: 300
trade_count: 300
avg_gross_return_pct: 0.0094
avg_net_return_pct: -0.2406
hit_rate: 0.4567
direction_hit_rate: 0.4
cumulative_return_pct: -51.77
max_drawdown_pct: -52.11
```

중요 해석:

- 기존 `kronos_all_predictions.csv`는 각 window의 `asof_timestamp`가 대부분 달라 진짜 cross-sectional Top-K가 아니다.
- 그래서 평균 선택 수가 Top-K보다 작으면 artifact에 warning을 남긴다.
- 진짜 Qlib Top-K를 하려면 같은 `asof_timestamp`에서 여러 종목 score를 생성하는 prediction export가 필요하다.

## 8. 웹 대시보드

실행:

```powershell
python webui\run.py
```

접속:

```text
http://localhost:7070/stom
```

추가된 기능:

- Qlib Top-K backtest artifact 선택
- period/trade/top-k metrics
- gross/net return
- cumulative return / MDD
- hit / direction / Sharpe
- equity curve
- top trades table

API:

```text
GET /api/stom/qlib-backtests
GET /api/stom/qlib-backtests?file=<artifact.json>
```

## 9. 전체 DB로 확대하는 순서

1. `--max-tables 50`, `--max-groups 500` pilot
2. 변환 report 확인
3. `QlibDataset` loader smoke test
4. predictor 1 epoch smoke 학습
5. prediction CSV 생성
6. score-backtest와 dashboard 확인
7. `--max-tables 300`
8. `--max-tables 1000`
9. 제한 해제 또는 날짜 구간별 batch export

## 10. 아직 남은 중요한 과제

1. pyqlib 설치 후 실제 `.bin` provider init 검증
2. 동일 asof timestamp의 cross-sectional prediction 생성기
3. Qlib `TopkDropoutStrategy` 직접 연결
4. 1초 데이터의 Qlib calendar/frequency 호환성 검증
5. 비용/슬리피지 모델 정교화
6. 최근 날짜 완전 holdout 기준 학습/평가

## 11. 최종 판단

이번 구현은 Qlib 적용의 첫 단계를 완료한다.

```text
완료: STOM DB → Qlib dump-ready CSV/pickle split → Qlib-style score backtest → dashboard
미완료: pyqlib .bin provider 직접 변환/로드, Qlib TopkDropoutStrategy 실연동, 전체 DB 장시간 학습
```

따라서 이제는 “Qlib을 써야 하나?”를 논의하는 단계에서 벗어나, STOM 데이터를 Qlib 연구 체계로 넣어 검증할 수 있는 기반이 생겼다.

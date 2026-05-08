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

### 3.1.1 1초 grid + 실제 초 단위 horizon

30초 후/60초 후 예측은 단순히 `30 row 후`, `60 row 후`가 아니라 실제 시간 기준이어야 한다. STOM tick row가 중간에 비어 있을 수 있으므로 1초봉 전체 파인튜닝용 export는 다음 옵션을 사용한다.

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

핵심 옵션:

- `--regularize-1s`: 누락된 초를 1초 grid로 보정한다. 가격은 직전가 forward-fill, 거래량/거래대금은 0으로 채운다.
- `--horizon-seconds`: 1초 grid 기준 실제 N초 후 target을 명시한다.
- `--split-by session`: 같은 거래일이 train/val/test에 섞이지 않도록 날짜/session 기준으로 분리한다.

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

현재 Qlib upstream `scripts/dump_bin.py` 기준 인자는 `--csv_path`가 아니라 `--data_path`이다. 예:

```powershell
python scripts/dump_bin.py dump_all `
  --data_path finetune/qlib_exports/stom_1min_pilot/qlib_csv `
  --qlib_dir finetune/qlib_exports/stom_1min_pilot/qlib_bin `
  --date_field_name date `
  --symbol_field_name symbol `
  --include_fields open,high,low,close,volume,amount,money,factor `
  --freq 1min
```

pyqlib은 repo 필수 dependency가 아니라 실행 환경 dependency이다. 현재 워크스테이션에서는 `python -m pip install pyqlib`로 `pyqlib 0.9.7` 설치를 완료했고, pip 패키지에는 `dump_bin.py`가 포함되지 않아 Microsoft Qlib source를 `.omx/external/qlib`에 clone하여 `scripts/dump_bin.py`를 사용했다. `.omx`는 실행 보조 산출물이며 commit 대상이 아니다.

### 5.1 Qlib 환경 점검

먼저 현재 Python 환경에 pyqlib과 `dump_bin.py`가 준비되어 있는지 확인한다.

```powershell
python finetune\qlib_stom_pipeline.py qlib-env-check
```

현재 워크스테이션 점검 결과:

```json
{
  "qlib_installed": true,
  "qlib_version": "0.9.7",
  "dump_bin_script_found": true,
  "dump_bin_script": "D:\\Chanil_Park\\Project\\Programming\\Kronos\\.omx\\external\\qlib\\scripts\\dump_bin.py"
}
```

### 5.2 dump_bin 실행

export report에서 Qlib 변환 command를 재생성한다. `--execute`를 빼면 dry-run만 수행한다.

```powershell
python finetune\qlib_stom_pipeline.py dump-bin `
  --export-report finetune\qlib_exports\stom_1min_pilot\stom_qlib_export_report.json `
  --qlib-dir finetune\qlib_exports\stom_1min_pilot\qlib_bin `
  --dump-bin-script .omx\external\qlib\scripts\dump_bin.py `
  --freq 1min `
  --execute
```

2026-05-07 파일럿 검증 결과:

| 구분 | 결과 |
| --- | --- |
| 1초봉 export | 성공: 4개 instrument/session, 4,792 rows |
| 1초봉 dump_bin | 성공: `--freq 1s` bin 생성 |
| 1초봉 pyqlib provider smoke | 실패/제약 확인: pyqlib `D.calendar(freq="1s")`는 초봉 freq를 지원하지 않음 |
| 1분봉 export | 성공: 4개 instrument/session, 112 rows |
| 1분봉 dump_bin | 성공: `--freq 1min` bin 생성 |
| 1분봉 pyqlib provider smoke | 성공: calendar 112개 로드 |

따라서 **Qlib provider/전략 연구는 1분봉 이상을 우선 사용**하고, **1초봉은 Kronos fine-tuning용 `processed_datasets/*.pkl` 경로를 우선 사용**한다.

### 5.3 Qlib provider smoke test

`.bin` 변환이 완료되면 provider를 초기화하고 calendar를 읽어본다.

```powershell
python finetune\qlib_stom_pipeline.py provider-smoke `
  --provider-uri finetune\qlib_exports\stom_1min_pilot\qlib_bin `
  --region cn `
  --freq 1min
```

성공 예:

```json
{
  "mode": "qlib_provider_smoke",
  "freq": "1min",
  "calendar_count": 112,
  "calendar_sample": [
    "2022-12-12 09:00:00",
    "2022-12-12 09:01:00"
  ]
}
```

주의: `dump_bin.py`는 `--freq 1s` 변환 자체는 수행하지만, pyqlib provider의 `Freq` parser는 `1s`를 공식 지원하지 않는다. `provider-smoke --freq 1s`는 의도적으로 명확한 오류를 반환하게 했다.

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

1. 동일 asof timestamp의 cross-sectional prediction 생성기
2. Qlib `TopkDropoutStrategy` 직접 연결
3. 1초 데이터는 pyqlib provider 공식 freq 제약 때문에 Kronos pickle 경로와 분리 운영
4. 비용/슬리피지 모델 정교화
5. 최근 날짜 완전 holdout 기준 학습/평가
6. 전체 DB 장시간 export/train의 재개/로그/대시보드 상태 표시

## 11. 최종 판단

이번 구현은 Qlib 적용의 실제 실행 게이트까지 통과했다.

```text
완료: STOM DB → Qlib dump-ready CSV/pickle split → dump_bin 실제 변환 → 1분봉 pyqlib provider smoke → Qlib-style score backtest → dashboard
제약: 1초봉 dump_bin 변환은 가능하지만 pyqlib provider freq는 1s를 지원하지 않아 Kronos pickle 학습 경로를 우선 사용
미완료: Qlib TopkDropoutStrategy 실연동, cross-sectional prediction 생성, 전체 DB 장시간 학습
```

따라서 이제는 “Qlib을 써야 하나?”를 논의하는 단계에서 벗어나, 1분봉 이상 STOM 데이터를 Qlib 연구 체계로 넣어 검증할 수 있는 기반이 생겼다.

# STOM Kronos 학습 진행 현황

이 문서는 STOM 1tick DB를 Kronos OHLCV 학습 데이터로 변환하고, GPU 학습/예측/웹 대시보드 검증까지 이어가기 위한 **진행 관리 문서**이다.

생성/갱신 기준일: 2026-05-06

## 전체 진행률

```text
██████████████████░░  9A / 9 진행 중, 약 93%
```

현재 단계:

```text
현재 단계: 9B — 1,000개 테이블 학습 확대 준비
직전 완료: 9A — 300개 테이블 export/train/predict/dashboard 검증
다음 목표: 300개 검증 결과를 기준으로 1,000개 테이블로 확대한다.
```

## 단계별 현황

| 단계 | 내용 | 상태 | 산출물/증거 |
|---:|---|---|---|
| 1 | STOM DB 구조 분석 | 완료 | 전체 2,427 테이블, 학습 가능 주식 테이블 2,425개 확인 |
| 2 | Kronos OHLCV 학습 데이터 파이프라인 구현 | 완료 | `finetune_csv/stom_tick_dataset.py`, `prepare_stom_1tick.py` |
| 3 | 예측 검증 CLI 및 웹 대시보드 구현 | 완료 | `stom_prediction_eval.py`, `/stom` 대시보드 |
| 4 | CUDA PyTorch 세팅 및 RTX 4080 SUPER 검증 | 완료 | `torch 2.9.0+cu128`, `cuda_available=True` |
| 5 | 파일럿 데이터 export | 완료 | `finetune_csv/data/stom_1tick_kline.csv` 생성 |
| 6 | GPU 파일럿 학습 실행 | 완료 | `finetune_csv/finetuned/stom_1tick_gpu_pilot_lookback300_pred60/basemodel/best_model` 생성 |
| 7 | 학습 모델 예측 CSV 생성 | 완료 | `webui/stom_predictions/kronos_gpu_pilot_predictions.csv` 생성 |
| 8 | 웹 대시보드 실제값/예측값 검증 | 완료 | `http://127.0.0.1:7071/stom` API/HTML/headless screenshot 검증 |
| 9 | 전체 2,425개 테이블 학습으로 확대 | 진행 중 | 9A 300개 테이블 검증 완료, 9B 1,000개 테이블 예정 |

## 5단계 완료 상세: 파일럿 데이터 export

실행 명령:

```powershell
python finetune_csv\prepare_stom_1tick.py export `
  --db _database\stock_tick_back.db `
  --output finetune_csv\data\stom_1tick_kline.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-tables 100 `
  --price-mode close_only
```

결과:

```text
selected_table_count: 100
written_rows: 6,164,390
written_groups: 3,704
skipped_groups: 22
min_rows_per_group: 361
price_mode: close_only
trainable_csv_created: true
CSV size: 약 460.3 MB
```

CSV 헤더:

```text
symbol,session,timestamps,open,high,low,close,volume,amount
```

주의:

- STOM DB에 `종가` 컬럼이 없어 `현재가`를 close로 사용한다.
- `close_only` 모드에서는 `현재가`를 open/high/low/close 모두에 매핑한다.
- `시가/고가/저가`가 실제 1초봉 OHLC인지 확정되기 전까지는 `close_only`가 안전하다.

## 5단계 검증

파일 존재/크기 확인:

```text
exists: True
size_mb: 460.3
```

baseline 예측 smoke test:

```powershell
python finetune_csv\stom_prediction_eval.py `
  --data finetune_csv\data\stom_1tick_kline.csv `
  --output webui\stom_predictions\pilot_export_smoke.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 3 `
  --stride 120 `
  --mode baseline
```

결과:

```text
mae: 6.6722222222222225
rmse: 8.617488677747776
mape: 0.6785394903231754
direction_accuracy: 0.3333333333333333
windows: 3
rows: 180
```

이 smoke test는 모델 품질 측정이 아니라 **생성된 CSV가 예측 검증 파이프라인 입력으로 정상 사용 가능한지 확인**하기 위한 검증이다.

## 6단계 완료 상세: GPU 파일럿 학습

6단계는 기본 config를 바로 사용하지 않고, 런타임을 제한한 별도 파일럿 config로 진행했다.

파일럿 config:

```text
finetune_csv/configs/config_stom_1tick_pilot.yaml
```

핵심 설정:

```text
data_path: finetune_csv/data/stom_1tick_kline.csv
sample_stride: 20
max_samples: 4096
basemodel_epochs: 1
batch_size: 8
num_workers: 0
device: cuda:0
pretrained_tokenizer: NeoQuasar/Kronos-Tokenizer-base
pretrained_predictor: NeoQuasar/Kronos-small
```

실행 명령:

```powershell
python finetune_csv\train_sequential.py --config finetune_csv\configs\config_stom_1tick_pilot.yaml
```

학습 결과:

```text
device: cuda:0
model parameters: 24,741,376
train groups: 3,148
validation groups: 556
train samples: 4,096
validation samples: 4,096
epoch: 1 / 1
steps: 512
training loss: 2.4667
validation loss: 2.4311
epoch time: 41.82 seconds
basemodel training time: 1.40 minutes
total training time: 1.47 minutes
exit code: 0
```

생성 checkpoint:

```text
finetune_csv/finetuned/stom_1tick_gpu_pilot_lookback300_pred60/basemodel/best_model/config.json
finetune_csv/finetuned/stom_1tick_gpu_pilot_lookback300_pred60/basemodel/best_model/model.safetensors
finetune_csv/finetuned/stom_1tick_gpu_pilot_lookback300_pred60/basemodel/best_model/README.md
```

주의:

- checkpoint는 대용량/재생성 가능 산출물이므로 commit하지 않는다.
- `finetune_csv/finetuned/`는 `.gitignore`에 추가했다.

## 6단계 중 발견/수정한 문제

문제:

```text
python finetune_csv\train_sequential.py --config ...
ModuleNotFoundError: No module named 'model'
```

원인:

```text
Python 파일 경로 실행 시 sys.path[0]이 finetune_csv로 잡히고, 기존 sys.path.append('../')는 현재 작업 디렉터리 기준이라 프로젝트 루트를 안정적으로 가리키지 않았다.
```

수정:

```text
finetune_csv/train_sequential.py
finetune_csv/finetune_tokenizer.py
finetune_csv/finetune_base_model.py
finetune_csv/stom_prediction_eval.py
```

위 파일들이 `__file__` 기준으로 프로젝트 루트를 계산해 `sys.path`에 추가하도록 수정했다.

회귀 테스트:

```text
tests/test_cli_import_paths.py
```

## 6단계 검증

실행한 검증:

```powershell
python -m compileall -q finetune_csv webui tests docs
python -m pytest tests/test_stom_tick_dataset.py tests/test_stom_training_cli.py tests/test_stom_prediction_eval.py tests/test_stom_dashboard_helpers.py tests/test_cli_import_paths.py -q
```

결과:

```text
12 passed, 1 warning
```

## 7단계 완료 상세: 학습 모델 예측 CSV 생성

실행 명령:

```powershell
python finetune_csv\stom_prediction_eval.py `
  --data finetune_csv\data\stom_1tick_kline.csv `
  --output webui\stom_predictions\kronos_gpu_pilot_predictions.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 20 `
  --stride 120 `
  --mode kronos `
  --model-path finetune_csv\finetuned\stom_1tick_gpu_pilot_lookback300_pred60\basemodel\best_model `
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base `
  --device cuda:0
```

첫 실행에서 발견한 명령어 문제:

```text
--tokenizer-path NeoQuasar\Kronos-Tokenizer-base
```

PowerShell에서 백슬래시를 사용하면 HuggingFace repo id가 잘못 해석된다. 반드시 `/`를 사용한다.

```text
--tokenizer-path NeoQuasar/Kronos-Tokenizer-base
```

결과:

```text
mode: kronos
windows: 20
rows: 1,200
mae: 5.330419387817383
rmse: 10.139999867404422
mape: 0.8288770468725435
direction_accuracy: 0.5
avg_pred_return: -0.28066592835209236
avg_actual_return: 0.15233856575055293
exit code: 0
```

생성 산출물:

```text
webui/stom_predictions/kronos_gpu_pilot_predictions.csv
webui/stom_predictions/kronos_gpu_pilot_predictions.metrics.json
```

CSV 구조:

```text
window_id,symbol,session,asof_timestamp,target_timestamp,horizon_step,horizon_seconds,actual_close_t0,pred_close,actual_close,error,abs_error,pred_return_window,actual_return_window,direction_hit_window,mode
```

주의:

- 예측 CSV와 metrics JSON은 대용량/재생성 산출물이므로 commit하지 않는다.
- 이번 결과는 작은 파일럿 학습 모델의 검증용 결과이며, 실제 매매 정확도 판단용 최종 모델이 아니다.

## 7단계 중 발견/수정한 문제

문제:

```text
from webui.app import app
/api/stom/prediction-files -> 500
Warning: STOM dashboard helpers cannot be imported (No module named 'stom_dashboard')
```

원인:

```text
webui.app을 패키지로 import할 때 webui/stom_dashboard.py 상대 import가 처리되지 않았다.
```

수정:

```text
webui/app.py
tests/test_stom_dashboard_helpers.py
```

`webui.app`에서 `.stom_dashboard` 상대 import를 우선 사용하고, 단독 실행 호환을 위해 기존 `stom_dashboard` import를 fallback으로 유지했다.

## 7단계 검증

대시보드 helper 검증:

```text
has_kronos_file: True
rows: 1,200
windows: 20
symbols: 2
chart_json 생성: 성공
topk_count: 5
```

Flask route 검증:

```text
/stom -> 200
/api/stom/prediction-files -> 200
/api/stom/prediction?file=kronos_gpu_pilot_predictions.csv -> 200
```

회귀 검증:

```powershell
python -m compileall -q finetune_csv webui tests docs
python -m pytest tests/test_stom_tick_dataset.py tests/test_stom_training_cli.py tests/test_stom_prediction_eval.py tests/test_stom_dashboard_helpers.py tests/test_cli_import_paths.py -q
python -m pip check
```

결과:

```text
13 passed, 1 warning
No broken requirements found
```

## 8단계 완료 상세: 웹 대시보드 실제값/예측값 검증

사전 발견:

```text
7070 포트는 AnyDesk 서비스가 사용 중이었다.
```

대응:

```text
webui/run.py가 환경변수로 host/port/browser-open 여부를 받을 수 있도록 보완했다.
KRONOS_WEBUI_HOST
KRONOS_WEBUI_PORT 또는 PORT
KRONOS_WEBUI_OPEN_BROWSER
```

추가 발견:

```text
Windows PowerShell 리다이렉션 환경에서 이모지 로그가 cp949 인코딩으로 실패했다.
```

대응:

```text
webui/run.py에서 stdout/stderr를 UTF-8, errors=replace로 재설정했다.
```

검증 서버 실행 명령:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:KRONOS_WEBUI_HOST='127.0.0.1'
$env:KRONOS_WEBUI_PORT='7071'
$env:KRONOS_WEBUI_OPEN_BROWSER='0'
python webui\run.py
```

검증 URL:

```text
http://127.0.0.1:7071/stom
```

서버 실행 증거:

```text
Access URL: http://127.0.0.1:7071
Running on http://127.0.0.1:7071
```

HTTP/API 검증:

```text
/stom -> 200 text/html; charset=utf-8
/api/stom/summary -> 200 application/json
/api/stom/prediction-files -> 200 application/json
/api/stom/prediction?file=kronos_gpu_pilot_predictions.csv -> 200 application/json
```

예측 파일 API 검증:

```text
file_count: 3
has_kronos_file: True
names:
  - kronos_gpu_pilot_predictions.csv
  - pilot_export_smoke.csv
  - pilot_predictions.csv
```

예측 payload 검증:

```text
metrics.rows: 1,200
metrics.windows: 20
metrics.symbols: 2
metrics.mae: 5.330419387817383
metrics.rmse: 10.139999867404422
metrics.mape: 0.8288770468725435
metrics.direction_accuracy: 0.5
windows_count: 20
topk_count: 20
chart_len: 12,328
```

Headless browser fallback 검증:

```text
Browser Use plugin skill은 로드했지만 이 세션에는 Node REPL js 실행 도구가 노출되지 않았다.
대신 Chrome headless로 실제 페이지 screenshot 생성을 검증했다.
```

생성된 screenshot 증거:

```text
.omx/specs/stom-dashboard-stage8/stom_dashboard_stage8.png
format: PNG
size: 1500 x 1200
file size: 206,607 bytes
non_blank: True
```

검증 후 서버는 종료했고 `7071` 포트가 해제되었다.

## 9A 완료 상세: 300개 테이블 학습 확대

9단계는 전체 2,425개 테이블로 바로 확대하지 않고 다음 순서로 진행한다.

```text
9A: 300개 테이블 검증
9B: 1,000개 테이블 검증
9C: 전체 2,425개 테이블 검증
```

이번 9A에서는 300개 테이블 기준으로 export, GPU 학습, 예측 CSV 생성, 대시보드 API 검증까지 완료했다.

### 9A config

추가한 config:

```text
finetune_csv/configs/config_stom_1tick_300.yaml
```

핵심 설정:

```yaml
data:
  data_path: "finetune_csv/data/stom_1tick_kline_300.csv"
  sample_stride: 10
  max_samples: 50000

training:
  basemodel_epochs: 1
  batch_size: 8
  num_workers: 0

model_paths:
  exp_name: "stom_1tick_300_lookback300_pred60"
```

### 9A-1. 300개 테이블 export

실행 명령:

```powershell
python finetune_csv\prepare_stom_1tick.py export `
  --db _database\stock_tick_back.db `
  --output finetune_csv\data\stom_1tick_kline_300.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-tables 300 `
  --price-mode close_only
```

결과:

```text
selected_table_count: 300
written_rows: 15,895,090
written_groups: 9,590
skipped_groups: 76
CSV size: 약 1,181.11 MB
trainable_csv_created: true
exit code: 0
```

### 9A-2. 300개 테이블 GPU 학습

실행 명령:

```powershell
python finetune_csv\train_sequential.py --config finetune_csv\configs\config_stom_1tick_300.yaml
```

결과:

```text
device: cuda:0
model parameters: 24,741,376
train groups: 8,151
validation groups: 1,439
train samples: 50,000
validation samples: 50,000
epoch: 1 / 1
steps: 6,250
training loss: 2.3893
validation loss: 2.3258
epoch time: 460.48 seconds
total training time: 9.34 minutes
exit code: 0
```

생성 checkpoint:

```text
finetune_csv/finetuned/stom_1tick_300_lookback300_pred60/basemodel/best_model
```

checkpoint는 대용량 산출물이므로 commit하지 않는다.

### 9A-3. 300개 모델 예측 CSV 생성

실행 명령:

```powershell
python finetune_csv\stom_prediction_eval.py `
  --data finetune_csv\data\stom_1tick_kline_300.csv `
  --output webui\stom_predictions\kronos_300_predictions.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 100 `
  --stride 120 `
  --mode kronos `
  --model-path finetune_csv\finetuned\stom_1tick_300_lookback300_pred60\basemodel\best_model `
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base `
  --device cuda:0
```

결과:

```text
mode: kronos
windows: 100
rows: 6,000
symbols: 3
mae: 35.33297971089681
rmse: 74.68674727395761
mape: 0.668662828066495
direction_accuracy: 0.58
avg_pred_return: -0.1966529845790984
avg_actual_return: 0.02022996986114153
exit code: 0
```

생성 산출물:

```text
webui/stom_predictions/kronos_300_predictions.csv
webui/stom_predictions/kronos_300_predictions.metrics.json
```

예측 CSV와 metrics JSON은 재생성 가능 산출물이므로 commit하지 않는다.

### 9A-4. 대시보드/API 검증

대시보드 helper 검증:

```text
has_kronos_300: True
rows: 6,000
windows: 100
symbols: 3
chart_len: 12,311
topk_count: 20
```

Flask route 검증:

```text
/stom -> 200
/api/stom/prediction-files -> 200
/api/stom/prediction?file=kronos_300_predictions.csv -> 200
```

회귀 검증:

```powershell
python -m compileall -q finetune_csv webui tests docs
python -m pytest tests/test_stom_tick_dataset.py tests/test_stom_training_cli.py tests/test_stom_prediction_eval.py tests/test_stom_dashboard_helpers.py tests/test_cli_import_paths.py -q
python -m pip check
```

결과:

```text
13 passed, 1 warning
No broken requirements found
```

## 다음 단계: 9B 1,000개 테이블 학습 확대

남은 확대 순서:

```text
1. 1,000개 테이블 export/train/predict/dashboard 검증
2. 전체 2,425개 테이블 export/train/predict/dashboard 검증
```

다음 실행 명령 예시:

### 1,000개 테이블 export

```powershell
python finetune_csv\prepare_stom_1tick.py export `
  --db _database\stock_tick_back.db `
  --output finetune_csv\data\stom_1tick_kline_1000.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-tables 1000 `
  --price-mode close_only
```

### 학습 config 복사 후 data_path/max_samples 조정

```powershell
Copy-Item finetune_csv\configs\config_stom_1tick_300.yaml finetune_csv\configs\config_stom_1tick_1000.yaml
```

`config_stom_1tick_1000.yaml`에서 최소 조정:

```yaml
data:
  data_path: "finetune_csv/data/stom_1tick_kline_1000.csv"
  sample_stride: 10
  max_samples: 200000

training:
  basemodel_epochs: 1
  batch_size: 8

model_paths:
  exp_name: "stom_1tick_1000_lookback300_pred60"
```

### 1,000개 테이블 GPU 학습

```powershell
python finetune_csv\train_sequential.py --config finetune_csv\configs\config_stom_1tick_1000.yaml
```

### 1,000개 테이블 예측 검증

```powershell
python finetune_csv\stom_prediction_eval.py `
  --data finetune_csv\data\stom_1tick_kline_1000.csv `
  --output webui\stom_predictions\kronos_1000_predictions.csv `
  --lookback-window 300 `
  --predict-window 60 `
  --max-windows 200 `
  --stride 120 `
  --mode kronos `
  --model-path finetune_csv\finetuned\stom_1tick_1000_lookback300_pred60\basemodel\best_model `
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base `
  --device cuda:0
```

### 대시보드 실행

```powershell
python webui\run.py
```

7070 충돌 시:

```powershell
$env:KRONOS_WEBUI_PORT='7071'
python webui\run.py
```

접속:

```text
http://localhost:7070/stom
또는
http://localhost:7071/stom
```

9단계에서 확인할 항목:

```text
1. export row/group 수가 예상 범위인지
2. GPU 학습 시간이 감당 가능한지
3. OOM 없이 checkpoint가 저장되는지
4. 예측 CSV의 MAE/RMSE/MAPE/방향정확도가 파일럿 대비 개선/악화되는지
5. 대시보드에서 신규 prediction 파일을 정상 표시하는지
```

## OMX 사용 기록

이번 단계에서는 다음 OMX 흐름을 사용했다.

```text
1. plan 성격의 단계/진행률 관리
2. note 성격의 진행 기록을 .omx/notepad.md에 보존
3. explore 시도: Windows POSIX 래퍼 미지원으로 실패
4. sparkshell 시도: 경로 오류로 실패
5. 일반 PowerShell fallback으로 실행/검증 지속
```

## Commit 관리 원칙

각 단계 완료 시 다음을 commit한다.

```text
1. 코드 변경
2. 테스트/검증 결과가 반영된 문서
3. 현재 단계/다음 단계/남은 단계 진행표
4. 실행 명령과 산출물 위치
```

대용량 산출물은 commit하지 않는다.

```text
_database/
finetune_csv/data/stom_*.csv
finetune_csv/finetuned/
webui/stom_predictions/*.csv
webui/stom_predictions/*.json
모델 checkpoint
```

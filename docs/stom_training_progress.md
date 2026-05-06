# STOM Kronos 학습 진행 현황

이 문서는 STOM 1tick DB를 Kronos OHLCV 학습 데이터로 변환하고, GPU 학습/예측/웹 대시보드 검증까지 이어가기 위한 **진행 관리 문서**이다.

생성/갱신 기준일: 2026-05-06

## 전체 진행률

```text
███████████░░░░░░░░░  5 / 9 완료, 약 56%
```

현재 단계:

```text
현재 단계: 6단계 — GPU 파일럿 학습 실행 준비
직전 완료: 5단계 — 파일럿 데이터 export
다음 목표: 생성된 100개 테이블 파일럿 CSV로 Kronos GPU 학습을 실행한다.
```

## 단계별 현황

| 단계 | 내용 | 상태 | 산출물/증거 |
|---:|---|---|---|
| 1 | STOM DB 구조 분석 | 완료 | 전체 2,427 테이블, 학습 가능 주식 테이블 2,425개 확인 |
| 2 | Kronos OHLCV 학습 데이터 파이프라인 구현 | 완료 | `finetune_csv/stom_tick_dataset.py`, `prepare_stom_1tick.py` |
| 3 | 예측 검증 CLI 및 웹 대시보드 구현 | 완료 | `stom_prediction_eval.py`, `/stom` 대시보드 |
| 4 | CUDA PyTorch 세팅 및 RTX 4080 SUPER 검증 | 완료 | `torch 2.9.0+cu128`, `cuda_available=True` |
| 5 | 파일럿 데이터 export | 완료 | `finetune_csv/data/stom_1tick_kline.csv` 생성 |
| 6 | GPU 파일럿 학습 실행 | 다음 | `train_sequential.py` 실행 예정 |
| 7 | 학습 모델 예측 CSV 생성 | 남음 | `webui/stom_predictions/kronos_predictions.csv` 예정 |
| 8 | 웹 대시보드 실제값/예측값 검증 | 남음 | `http://localhost:7070/stom` 확인 예정 |
| 9 | 전체 2,425개 테이블 학습으로 확대 | 남음 | 파일럿 결과 안정화 후 단계적 확대 |

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

## 다음 단계: 6단계 GPU 파일럿 학습

현재 config:

```text
finetune_csv/configs/config_stom_1tick.yaml
data.data_path = finetune_csv/data/stom_1tick_kline.csv
device.use_cuda = true
device.device_id = 0
```

다음 실행 명령:

```powershell
python finetune_csv\train_sequential.py --config finetune_csv\configs\config_stom_1tick.yaml
```

학습 중 확인할 항목:

```text
1. RTX 4080 SUPER GPU 메모리 사용량
2. batch_size=32에서 OOM 발생 여부
3. train/validation loss 출력 여부
4. checkpoint 저장 여부
5. 1 epoch 학습 시간
```

OOM 발생 시 조정 순서:

```text
1. batch_size 32 → 16
2. num_workers 4 → 2
3. max_samples 설정
4. sample_stride 증가
```

## OMX 사용 기록

이번 단계에서는 다음 OMX 흐름을 사용했다.

```text
1. plan 성격의 단계/진행률 관리
2. explore 시도: Windows POSIX 래퍼 미지원으로 실패
3. sparkshell 시도: 경로 오류로 실패
4. 일반 PowerShell fallback으로 검증 지속
5. note 성격의 진행 기록은 .omx/notepad.md에 별도 보존
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
webui/stom_predictions/*.csv
webui/stom_predictions/*.json
모델 checkpoint
```


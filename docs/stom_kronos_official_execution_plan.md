# STOM tick Kronos 공식 준수 실행 계획

작성일: 2026-05-09

## 1. 반드시 기억할 최종 원칙

Kronos 공식 README 기준의 fine-tuning 순서는 다음이다.

```text
Config 설정
-> Qlib/STOM 데이터 준비
-> Tokenizer fine-tuning
-> Predictor fine-tuning
-> Backtesting / evaluation / visualization
```

따라서 지금부터의 공식 준수 작업은 `pretrained tokenizer + predictor만 fine-tuning`이 아니라,
**STOM 데이터로 tokenizer를 먼저 fine-tuning하고 그 tokenizer checkpoint로 predictor를 fine-tuning**하는 흐름이다.

## 2. 1~8 단계

| 단계 | 목적 | 현재 상태 |
| --- | --- | --- |
| 1 | tokenizer 학습 경로 안정화 | 완료/커밋 대기 |
| 2 | tokenizer 20k benchmark로 시간 계수 측정 | 예정 |
| 3 | pred60 tokenizer expand_200k 실행 | 예정 |
| 4 | pred60 predictor expand_200k 실행 | 예정 |
| 5 | holdout 실제값 vs 예측값 그래프 생성 | 예정 |
| 6 | 성과 보고서 작성 | 예정 |
| 7 | pred30 진행 여부 판단 | 예정 |
| 8 | 1M/5M/full-window 확대 안내 | 예정 |

## 3. pred 길이 결정

우선순위는 `pred60`이다.

```text
lookback_window = 300
predict_window = 60
```

`pred30`은 학습 목표가 다른 별도 모델이므로 pred60 official pilot 결과를 보고 반복 여부를 판단한다.

## 4. full-window의 정확한 의미

기존 dataset 기본 동작은 전체 possible window에서 무작위 샘플링하는 방식이다. “전체 window를 학습했다”고 말하려면 `full_sequential` 방식이 필요하다.

인정 기준:

```text
visited_window_count == total_available_windows
unique_visited_window_count == total_available_windows
duplicate_count == 0
missing_count == 0
```

이번 1단계에서 `sample_random`과 `full_sequential` mode를 코드에서 분리했다.

## 5. 대형 실행 확대 기준

200k official pilot은 공식 절차와 그래프 확인 목적이다. 수익성 승인 단계가 아니다.

1M/5M/full-window 성과 목적 확대에는 다음 중 하나가 필요하다.

```text
1. target 25bp cost_sensitivity_gate 통과
2. 사용자가 수익성 근거 없이도 공식 준수 대형 실행을 하겠다고 명시적으로 override
```

## 6. 현재 예상 시간

| 범위 | pred60 예상 |
| --- | ---: |
| tokenizer 20k benchmark | 약 7~15분 |
| pred60 tokenizer 200k | 약 1.2~3시간 |
| pred60 predictor 200k | 약 1.5~2시간 |
| pred60 200k 예측/그래프 검증 | 약 40~60분 |
| pred60 official 200k 전체 | 약 3~5시간 |
| pred60 official full-window | 약 40~75시간 |

시간은 기존 predictor 20k 실측 549초를 기준으로 한 추정이며, tokenizer는 20k benchmark 후 재계산한다.

## 7. 1단계 검증 근거

- `KRONOS_DATASET_SAMPLE_MODE=sample_random|full_sequential` 지원 추가.
- tokenizer/predictor 학습 runner에 `--train-stage tokenizer|predictor|both` 추가.
- `both` 실행 시 tokenizer checkpoint를 predictor 학습에 자동 전달.
- Windows 단일 GPU/단일 프로세스에서도 tokenizer 학습 스크립트 실행 가능하도록 DDP 필수 조건 완화.
- 테스트: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; C:\Python\64\Python3119\python.exe -m pytest tests\test_stom_1s_finetune_runner.py -q` → 6 passed.
- 컴파일: `C:\Python\64\Python3119\python.exe -m compileall finetune\config.py finetune\dataset.py finetune\run_stom_1s_finetune.py finetune\train_predictor.py finetune\train_tokenizer.py tests\test_stom_1s_finetune_runner.py` → 성공.
- dry-run: pred60 `--train-stage both --sample-stage budget_20k --dataset-sample-mode full_sequential` → tokenizer/predictor manifest 생성 및 handoff 확인.

주의: 기본 pytest 플러그인 자동 로딩 상태에서는 Windows PyTorch DLL 초기화 오류가 발생했다. 실제 Python 프로세스의 `import torch`와 플러그인 비활성화 테스트는 정상이다.

## 8. 2단계 tokenizer 20k benchmark 실측 결과

실행 명령:

```powershell
C:\Python\64\Python3119\python.exe finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --train-stage tokenizer `
  --sample-stage budget_20k `
  --dataset-dir finetune\qlib_exports\stom_1s_grid_pred60_full\processed_datasets `
  --output-root finetune\outputs `
  --run-name stom_1s_grid_pred60_official_tokenizer_20k `
  --dataset-sample-mode full_sequential `
  --batch-size 4 `
  --num-workers 0 `
  --log-interval 100
```

실측 결과:

| 항목 | 값 |
| --- | ---: |
| train possible windows | 73,718,875 |
| val possible windows | 15,938,107 |
| 실제 train samples | 20,000 |
| 실제 val samples | 4,000 |
| train steps | 5,000 |
| val steps | 1,000 |
| duration_seconds | 567.944628초 |
| 총 경과 | 약 9분 28초 |
| best tokenizer val_loss | 0.004013419676455669 |
| checkpoint | `finetune/outputs/stom_1s_grid_pred60_official_tokenizer_20k/finetune_tokenizer/checkpoints/best_model` |

이 실측을 단순 선형 환산하면 tokenizer 학습 예상 시간은 다음이다.

| tokenizer 범위 | 단순 환산 시간 |
| --- | ---: |
| 200k | 약 1.58시간 |
| 1M | 약 7.89시간 |
| 5M | 약 39.44시간 |
| pred60 train full-window 73,718,875 | 약 581.5시간, 약 24.2일 |

주의: full-window 환산은 train sample 기준의 보수적 단순 환산이며, 전체 validation을 같이 full로 돌리면 더 길어진다. 따라서 8단계 대형 확대는 반드시 목적을 분리해야 한다.

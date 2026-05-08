# STOM 1초봉 staged full-training 실행 계획

작성일: 2026-05-09

## 1. 목적

STOM tick 전체 데이터는 이미 1초봉 `QlibDataset` pickle로 변환되어 Kronos 학습 루프에 연결되어 있다.
하지만 현재 실제 fine-tuning은 `20,000` train sample budget으로 수행되었고, 가능한 모든 train window를 전량 학습한 것은 아니다.

이 문서는 전체 데이터 학습을 다음처럼 단계형으로 확대하기 위한 실행 계획이다.

```text
20k baseline 완료
→ 200k 확대
→ 1M 확대
→ 5M 장시간 학습
→ full-window 전량 epoch 후보
```

## 2. 현재 완료 상태

| 항목 | pred30 | pred60 |
| --- | ---: | ---: |
| 전체 주식 table | 2,425 | 2,425 |
| export group | 73,900 | 73,900 |
| export row | 131,470,857 | 131,470,857 |
| possible train samples | 75,277,195 | 73,718,875 |
| possible val samples | 16,275,307 | 15,938,107 |
| 현재 실제 train samples | 20,000 | 20,000 |
| 현재 실제 val samples | 4,000 | 4,000 |

따라서 현재 상태는 다음과 같이 정의한다.

```text
전체 데이터셋 구축: 완료
전체 데이터셋 학습 루프 연결: 완료
전체 window 전량 학습: 미완료
```

## 3. staged training budget

| stage | train samples | val samples | 목적 |
| --- | ---: | ---: | --- |
| `budget_20k` | 20,000 | 4,000 | 현재 baseline 재현 |
| `expand_200k` | 200,000 | 40,000 | 학습량 10배 확대 후 방향성/Top-K 변화 확인 |
| `expand_1m` | 1,000,000 | 100,000 | 의미 있는 장시간 학습 후보 |
| `expand_5m` | 5,000,000 | 250,000 | overnight급 장시간 학습 후보 |
| `full_window` | horizon별 possible train 전체 | horizon별 possible val 전체 | 최종 전량 epoch 후보 |

`full_window`는 pred30 기준 75,277,195 train samples, pred60 기준 73,718,875 train samples다.

## 4. 실행 CLI

이번 단계에서 `finetune/run_stom_1s_finetune.py`에 `--sample-stage` 옵션을 추가했다.

### 4.1 pred60 200k 확대 학습 dry-run

```powershell
python finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --sample-stage expand_200k `
  --output-root finetune\outputs `
  --dry-run
```

### 4.2 pred60 200k 실제 학습

```powershell
python finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --sample-stage expand_200k `
  --output-root finetune\outputs
```

### 4.3 pred60 1M 실제 학습

```powershell
python finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --sample-stage expand_1m `
  --output-root finetune\outputs
```

### 4.4 pred60 full-window 전량 후보 dry-run

```powershell
python finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --sample-stage full_window `
  --output-root finetune\outputs `
  --dry-run
```

## 5. 실행 순서

현재 모델의 비용 후 net return이 아직 양수가 아니므로, 바로 full-window 전량 학습으로 가지 않는다.

권장 순서:

1. 기존 pred60 checkpoint로 `max_sessions 100`, `max_asofs 5`, `max_symbols 50` 대형 walk-forward를 먼저 실행한다.
2. rolling filter validation을 다시 실행한다.
3. rolling avg_test_net이 0 이상이거나 baseline 대비 개선폭이 강하면 `expand_200k` 학습을 실행한다.
4. `expand_200k` checkpoint를 같은 방식으로 평가한다.
5. 개선되면 `expand_1m`, 이후 `expand_5m`로 확대한다.
6. `expand_5m`에서도 개선이 반복될 때만 `full_window` 전량 학습을 검토한다.

## 6. 성공/중단 기준

확대 학습 성공 기준:

- rolling avg_test_net_return_pct > 0
- baseline 대비 개선폭이 여러 fold에서 반복
- random baseline 대비 방향성/Top-K 모두 우위
- 거래 수가 너무 적지 않음

중단 기준:

- 학습량을 늘렸는데 direction accuracy와 Top-K net이 개선되지 않음
- 조건식이 특정 기간에서만 작동하고 rolling test에서 무너짐
- 비용 후 net이 계속 음수

## 7. 현재 진행률 반영

```text
전체 데이터셋 구축                      [█████] 100%
학습 루프 연결                          [█████] 100%
20k budgeted 학습                       [█████] 100%
200k 확대 학습 준비                     [████░] 80%
1M/5M/full-window 실행                  [░░░░░] 0%
대형 walk-forward 후 확대 여부 판단      [███░░] 60%
```

전체 프로젝트 진행률은 이번 단계 이후 **89%**로 본다.

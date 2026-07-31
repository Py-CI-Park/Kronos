# Type2-D6R TRAIN_ONLY 반증 연구 계획

## 목적

D6는 D5S 100K 정책이 reused validation에서 일반화되지 않았고, Native 정책이 거의 매일 거래하면서 shuffled control보다 낮아졌음을 보였다. D6R은 이미 읽은 validation을 다시 사용하지 않고, `HOLD=0`이 존재하는 동일한 6-action 환경에서 고정 10bp trade penalty가 churn을 줄이는지 TRAIN_ONLY 시간 순서에서 반증한다.

## 고정 연구 행렬

| 축 | 값 |
|---|---|
| 데이터 | custody-bound 573 TRAIN_ONLY episodes |
| Fold | expanding 5 folds; evaluation window 각 50 sessions |
| Reward profile | `COST_ONLY`, `TURNOVER_10BP` |
| Reward arm | `NATIVE`, `SHUFFLED` |
| Seed | 0, 1, 2 |
| 알고리즘 | 실제 SB3 DQN, 3e-4 LR, 50K steps |
| Primary unit | 5 × 2 × 2 × 3 = 60 models, 총 3.0M steps |
| 평가 비용 | 23bp Primary, 0bp diagnostic |
| 모델 선택 | fold·seed·profile별 사후 선택 금지; `TURNOVER_10BP` 고정 Primary |

Smoke는 fold 0 × 두 profile × Native/Shuffle × seed 0, 총 4개 4,096-step 모델로 실행 경로만 검사한다. Smoke 완료 전 Primary를 실행하지 않는다.

## 판정 질문

| Gate | 기준 |
|---|---:|
| Native median accuracy | ≥ 0.20 |
| Native median reward ratio | ≥ 0 |
| Native median total reward | ≥ 0 |
| Native − Shuffled reward delta | ≥ 0.10 |
| 양수 fold | ≥ 4/5 |
| 양수 seed | ≥ 2/3 |
| Native median trade rate | ≤ 0.65 |
| COST_ONLY 대비 trade-rate 감소 | ≥ 0.15 |
| Native median reward drawdown | ≤ 0.25 |
| Invalid action | 0 |

모든 기준을 통과해도 verdict는 `CANDIDATE`다. 기존 normalizer가 전체 TRAIN_ONLY에서 fit됐기 때문에 이 실험은 원인 분리용이며 새 확인 기간의 증거가 아니다. 하나라도 실패하면 `D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED`로 기록하고 D7을 열지 않는다.

## 데이터 금지선

- D6 validation 128 sessions, event, reward, seed별 결과는 코드·학습·선택 입력으로 읽지 않는다.
- D6 수치는 실패 질문과 고정 gate의 배경 설명에만 사용한다.
- Fresh OOS는 `NOT_RUN_NO_READ`로 유지한다.
- `ts_imb`는 RULE이며 D6R RL 결과로 재라벨링하지 않는다.
- validation에 맞춘 threshold, reward penalty, checkpoint 또는 seed 선택을 하지 않는다.

## 실행·개발 순서

1. 이 prereg와 계획을 코드보다 먼저 commit한다.
2. fold identity, penalty environment, exact matrix, gate를 RED 테스트로 고정한다.
3. 4-unit Smoke를 실행하고 terminal receipt를 확인한다.
4. 동일 producer commit에서 60-unit Primary를 실행한다.
5. 결과·실패 원인·custody를 새 문서로 기록한다.
6. dashboard에는 성공보다 fold 안정성, 거래율 감소, control 분리, D7 봉인을 우선 표시한다.
7. Python·frontend·build·browser QA 후 research→master PR과 annotated tag를 연결한다.

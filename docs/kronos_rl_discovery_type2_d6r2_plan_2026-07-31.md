# Type2-D6R2 MDP 오지정 반증 연구 계획

- 기준 릴리스: `fork-v1.19.0-kronos-rl-d6r-train-falsification`
- 범위: 573개 `TRAIN_ONLY` episode와 그 원천 `public_rows.json`
- 금지: D6 reused validation 및 D7 Fresh OOS 읽기, fold별/seed별 사후 선택, 수익성·실거래 준비 주장
- 비용: 학습·주평가 왕복 23bp, 0bp는 진단만 허용

## 왜 이 연구를 하는가

D6R의 DQN은 행동이 다음 날짜 상태를 바꾸지 않는 환경에서 `gamma=1`로 서로 독립적인 다음 날짜의 Q값을 부트스트랩했다. 고정 10bp 거래 페널티는 거래율을 줄이지 못했고 10개 gate 중 invalid-action 하나만 통과했다. D6R2는 성능을 다시 튜닝하는 연구가 아니라, 실패가 약한 신호 때문인지 MDP 오지정 때문인지 분리하는 반증 연구다.

## 고정 비교표

| Arm | 성격 | 핵심 질문 | Primary 규모 |
|---|---|---|---:|
| `DQN_GAMMA_0_CONTEXTUAL` | 실제 SB3 DQN, contextual 진단 | 무관한 다음 날짜 부트스트랩을 제거하면 나아지는가 | 5 folds × 2 controls × 3 seeds |
| `DQN_GAMMA_1_SEQUENCE_CONTROL` | 실제 SB3 DQN, 기존 구조 대조 | 동일 데이터·정규화에서 기존 실패가 재현되는가 | 5 × 2 × 3 |
| `RIDGE_REWARD_CEILING` | 비RL supervised 상한 | 현재 관측치에 비용 후 선택 신호 자체가 있는가 | 5 × 2 × 1 |

총 70개 unit이며 DQN 학습량은 3,000,000 step이다. 모든 fold는 평가구간을 제외한 과거 training row로만 Type-7 median/IQR 정규화를 fit한다. 원천 7개 특성, 7개 missing indicator, 14개 market context, progress를 사용한다.

## 판정 순서

| 순서 | 질문 | 판정 의미 |
|---:|---|---|
| 1 | fold-local normalizer가 평가 row 0개로 재현되는가 | 실패 시 연구 중단·입력 계보 오류 |
| 2 | Ridge가 23bp no-trade와 shuffled를 이기는가 | 실패 시 현재 top-5 표현의 signal floor 종료 |
| 3 | gamma=0 DQN이 gamma=1보다 reward ratio 0.05 이상 높은가 | 실패 시 MDP 오지정 제거 효과 없음 |
| 4 | gamma=0가 절대 보상·fold·seed·거래율·MDD gate를 모두 통과하는가 | 통과해도 sealed confirmatory 후보일 뿐 |

## 결과별 다음 액션

| 결과 | 다음 단계 |
|---|---|
| Ridge 실패 | 현재 14-feature/top-5 lane을 종료하고 새 특성·새 horizon 없이는 RL 반복 금지 |
| Ridge 통과, gamma=0 실패 | 알고리즘/표현학습 실패로 기록하고 비용 제약이 transition에 들어가는 stateful portfolio MDP의 단위테스트 설계만 허용 |
| gamma=0까지 통과 | 별도 승인·새 사전등록·새 봉인 구간이 있을 때만 confirmatory 연구 검토 |

D7은 어떤 결과에서도 자동 개방되지 않는다. `ts_imb`는 계속 RULE baseline이며 이 연구 결과와 강화학습 성과로 합산하지 않는다.

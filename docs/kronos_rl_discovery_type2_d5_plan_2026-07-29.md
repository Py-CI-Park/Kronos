# Type2-D5 전체 TRAIN·23bp DQN 사전등록

> 상태: `APPROVED_EXECUTABLE`  
> 부모 릴리스: `fork-v1.14.0-kronos-rl-d4-algorithm-objective`  
> 범위: `TRAIN_ONLY / RESEARCH_ONLY`

## 질문

D4에서 128개 train 세션을 학습한 DQN이 전체 573개 적격 train 세션과 23bp 비용에서도 학습 가능한가?

## 고정 설계

| 항목 | 값 |
|---|---|
| 데이터 | 동일 custody-bound `type1-close-20260803-005` |
| 세션 | 적격 train 전체 573개, 2019-05-10~2023-12-26 |
| 알고리즘 | D4의 `C_DQN_DISCRETE` 설정 동결 |
| 비용 | 학습·Primary 평가 모두 왕복 23bp |
| 대조군 | Native 5 seeds 대 Shuffled 5 seeds |
| 학습량 | seed당 200,000 steps |
| Primary | 10개 실제 RL 모델 |
| Smoke | Native/Shuffled seed 0, 각 2,048 steps |

## Gate

- Native와 shuffled 자기-fit 각각 5개 seed 중 최소 3개가 accuracy와 reward ratio 0.90 이상이어야 한다.
- Native 평균과 shuffled→native 평균의 차이는 0.20 이상이어야 한다.
- invalid action은 0이어야 한다.
- 이 gate는 train-only 학습 가능성만 확인한다. 재사용 validation과 Fresh OOS는 읽지 않는다.

## 실행 순서

1. 이 preregistration을 코드보다 먼저 커밋한다.
2. TDD로 exact 10-unit matrix, 전체 573 episode, 23bp training을 구현한다.
3. Smoke 2/2 완료 후 별도 operator approval을 생성한다.
4. 승인된 Smoke만 Primary 10개 모델 실행을 허용한다.
5. 결과가 실패해도 receipt·모델·원인을 보존하고 D6를 열지 않는다.

# Type2-D4 알고리즘·목적함수 연구 사전계획

> 상태: `PREREGISTERED / NOT_YET_EXECUTED`
> 부모 릴리스: `fork-v1.13.0-kronos-rl-d3-representation-action`
> 데이터: D3와 동일한 실제 일봉 train-only 128개 세션
> Fresh OOS: `NOT_RUN_NO_READ`

## 질문

D3에서 top-5·시장문맥·4배 학습량이 모두 개선을 만들었지만 최선 fit reward ratio는 0.533에 머물렀다. D4는 표현 자체의 예측 상한과 RL 최적화 실패를 분리한다.

| Arm | 유형 | 질문 | RL로 주장 가능한가 |
|---|---|---|---|
| A | Supervised ceiling | 현재 관측치로 정답 행동을 0.90 이상 외울 수 있는가 | 아니오 |
| B | MaskablePPO | D3 최선 설정을 동일 조건에서 재현하는가 | 예 |
| C | Discrete DQN | PPO 목적함수·온폴리시 경로가 병목인가 | 예 |
| D | Auxiliary PPO | 지도 사전학습 표현이 PPO 최적화를 해제하는가 | 예, 단 train-only 과적합 진단 |

모든 arm은 native/shuffled와 seed 0·1·2를 사용한다. Supervised 결과는 RL 성공으로 합산하지 않는다. RL arm 중 2/3 seed가 0.90 fit·control separation을 통과하지 못하면 D4는 `NO-GO`이며 Fresh OOS를 열지 않는다.

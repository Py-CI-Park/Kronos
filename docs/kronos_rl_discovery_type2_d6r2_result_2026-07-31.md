# Type2-D6R2 MDP 오지정 반증 연구 결과

- Primary: `type2-d6r2-primary-20260731-001`
- 범위: 573개 `TRAIN_ONLY`, 5개 expanding chronological fold
- 실행: DQN gamma 0/1 × Native/Shuffled × 3 seeds × 5 folds + ridge × Native/Shuffled × 5 folds = 70/70
- 비용: 학습·주평가 왕복 23bp
- D6 reused validation 및 D7 Fresh OOS: `NO_READ` / `NOT_RUN_NO_READ`

## 최종 판정

`D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED` — **NO-GO**

| Gate | 기준 | 결과 | 판정 |
|---|---:|---:|---|
| gamma0 median accuracy | ≥ 0.2000 | 0.1600 | FAIL |
| gamma0 median 23bp reward ratio | ≥ 0 | -0.127615 | FAIL |
| gamma0 lift vs gamma1 | ≥ +0.0500 | -0.031489 | FAIL |
| gamma0 delta vs shuffled | ≥ +0.1000 | +0.013654 | FAIL |
| gamma0 positive folds | ≥ 0.8000 | 0.0000 | FAIL |
| gamma0 positive seeds | ≥ 0.6667 | 0.0000 | FAIL |
| gamma0 median trade rate | ≤ 0.6500 | 0.9000 | FAIL |
| gamma0 median drawdown | ≤ 0.2500 | 0.442444 | FAIL |
| ridge median 23bp reward ratio | ≥ 0 | -0.152520 | FAIL |
| ridge delta vs shuffled | ≥ +0.1000 | -0.009730 | FAIL |
| ridge positive folds | ≥ 0.8000 | 0.2000 | FAIL |
| invalid action | 0 | 0 | PASS |
| normalizer evaluation rows | 0 | 0 | PASS |

총 13개 gate 중 2개만 통과했다.

## 해석

| 질문 | 증거 | 결론 |
|---|---|---|
| gamma=1 부트스트랩이 주원인인가 | gamma=0가 gamma=1보다 -0.031489 낮음 | 주원인으로 확인되지 않음 |
| fold-local 정규화로 회복되는가 | gamma0 ratio -0.127615 | 회복되지 않음 |
| 비용 후 contextual 신호가 있는가 | ridge ratio -0.152520, shuffled delta -0.009730 | 현재 표현의 signal floor 실패 |
| 과도 거래가 줄었는가 | trade rate 0.90 | 실패 |
| 안정적인가 | positive fold 0/5, seed 0/3 | 실패 |

따라서 같은 top-5, 같은 14-feature, 같은 horizon에서 DQN 구조·gamma·penalty만 바꾸는 반복 연구는 종료한다. `RIDGE_REWARD_CEILING`은 비RL supervised 진단이며 RL 성과로 집계하지 않는다. gamma=0 DQN은 실제 SB3 DQN 학습 결과지만 sequential portfolio control이 아니라 contextual 진단이다.

## 다음 연구 허용 범위

| 우선순위 | 액션 | 진입 조건 |
|---:|---|---|
| P0 | 현 top-5 lane 종료 기록 및 대시보드 NO-GO 표시 | 즉시 |
| P1 | 새로운 관측 특성·새 horizon의 cheap supervised signal prereg | 기존 14-feature 재사용만으로는 금지 |
| P1 | action이 보유 종목·현금·교체비용·다음 상태를 바꾸는 stateful portfolio MDP 단위테스트 | transition invariant와 synthetic learnability 먼저 통과 |
| HOLD | D7 Fresh OOS | 새 candidate·별도 승인 전 계속 `LOCKED` |

`ts_imb`는 계속 RULE baseline이며 이 결과와 결합해 RL 성과로 주장하지 않는다.

## 증거

| 항목 | 값 |
|---|---|
| Prereg commit | `6468c97` |
| Producer commit/tree | `fc1a1e24e21c921cf6f5cb5816d16b42efa1a8e7` / `7b434a3c62dd58f46fdccd7a523cde762c7e4ddf` |
| Source episode SHA | `8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40` |
| Artifact manifest | `7f3b8b02d11664cb01dec85fe82baeac07098a342b9f4c2e482616ffa4b94115` |
| Summary SHA | `484864bddd45f5e91f047f89927bf8c37b7a7977180fdc5995634239643e4d92` |
| Receipt SHA | `c68ff3d6bb8ca90fe9d65275a2aa3fc1e222fb70895c6bda494ed9f909390987` |

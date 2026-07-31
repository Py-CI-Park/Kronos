# Type2-D6R TRAIN_ONLY 반증 연구 결과

- 작성일: 2026-07-31 KST
- Primary run: `type2-d6r-primary-20260731-001`
- 연구 경계: 573개 `TRAIN_ONLY` episode만 사용. D6 reused validation과 D7 Fresh OOS는 읽지 않았다.
- 비용: 학습·1차 평가 23bp, 0bp는 진단 전용
- 해석: 로컬 연구 evidence이며 수익성·promotion·paper-forward·live/broker 준비도를 뜻하지 않는다.

## 1. 최종 판정

`D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED` — **NO-GO**

사전등록된 전역 10bp 거래 페널티는 거래 빈도를 낮추거나 23bp 보상·fold·seed 안정성을 확보하지 못했다. 10개 중 invalid-action gate 1개만 통과했으며 D7은 계속 `LOCKED`다.

| 게이트 | 사전등록 기준 | 실측 | 판정 |
|---|---:|---:|---|
| Native median accuracy | ≥ 0.200000 | 0.160000 | FAIL |
| Native median 23bp reward ratio | ≥ 0 | -0.106835 | FAIL |
| Native median 23bp total reward | ≥ 0 | -0.348605 | FAIL |
| Native − Shuffled reward ratio | ≥ +0.100000 | +0.016968 | FAIL |
| Positive fold fraction | ≥ 0.800000 | 0.200000 (1/5) | FAIL |
| Positive seed fraction | ≥ 0.666667 | 0.000000 (0/3) | FAIL |
| Native median trade rate | ≤ 0.650000 | 0.880000 | FAIL |
| Trade-rate reduction vs COST_ONLY | ≥ 0.150000 | 0.000000 | FAIL |
| Native median reward drawdown | ≤ 0.250000 | 0.486807 | FAIL |
| Invalid actions | 0 | 0 | PASS |

0bp 진단 median reward ratio도 -0.077106으로 음수다. 비용 제거만으로 실패를 설명할 수 없다.

## 2. Fold·seed 안정성

### Fold별 TURNOVER_10BP/Native median

| Fold | 평가 위치 | 23bp total reward | 23bp reward ratio | 양수 여부 |
|---:|---|---:|---:|---|
| 0 | [323, 373) | -0.727788 | -0.343437 | FAIL |
| 1 | [373, 423) | -0.788066 | -0.295499 | FAIL |
| 2 | [423, 473) | -0.120613 | -0.050309 | FAIL |
| 3 | [473, 523) | -0.348605 | -0.102211 | FAIL |
| 4 | [523, 573) | +0.205361 | +0.064788 | PASS |

### Seed별 TURNOVER_10BP/Native median

| Seed | 23bp total reward | 23bp reward ratio | 판정 |
|---:|---:|---:|---|
| 0 | -0.348605 | -0.102211 | FAIL |
| 1 | -0.364374 | -0.132906 | FAIL |
| 2 | -0.140783 | -0.041278 | FAIL |

## 3. 무엇을 배웠는가

| 관찰 | 증거 | 결론 |
|---|---|---|
| 거래 페널티가 행동을 바꾸지 못함 | COST_ONLY와 TURNOVER_10BP median trade rate 모두 0.88 | 고정 10bp penalty 가설 반증 |
| Native 신호 약함 | accuracy 0.16, 6-action random reference 0.1667 부근 | candidate 선택 구조를 학습하지 못함 |
| 비용만의 문제가 아님 | 0bp median reward ratio -0.077106 | gross signal 자체가 음수 |
| 시간 안정성 없음 | 5개 fold 중 마지막 1개만 양수 | 특정 구간 의존 |
| seed 안정성 없음 | 3개 seed median 모두 음수 | 초기화에 무관하게 가설 실패 |
| 경로 위험 큼 | median drawdown 0.486807 > 0.25 | 평균뿐 아니라 경로 gate도 실패 |

## 4. 계속 실패한 구조적 원인

현재 `HistoricalTopKEnv`는 날짜별 후보를 순서대로 보여 주지만 당일 행동이 다음 날짜의 상태·후보·포지션을 바꾸지 않는다. 반면 DQN은 `gamma=1.0`으로 서로 독립적인 다음 날짜의 Q값을 부트스트랩한다. 이 문제는 현재 형태에서 순차 MDP라기보다 비용 포함 contextual selection에 가깝다.

따라서 같은 표현·DQN에 penalty 크기만 바꾸는 연구는 과적합 가능성이 높다. 573일 전체로 미리 계산된 normalizer도 D6/D7 값은 포함하지 않지만 fold 시점 이후 TRAIN_ONLY 정보를 포함하므로, 만약 통과했더라도 확인 결과가 아닌 후보에 불과했을 것이다.

## 5. 다음 연구 대책

| 우선순위 | 연구 질문 | 방법 | 성공/종료 기준 |
|---:|---|---|---|
| P0 | 문제는 MDP 오지정인가? | fold-local normalizer + `gamma=0` DQN을 contextual-bandit 진단으로 사전등록 | Native가 shuffle/no-trade를 못 이기면 현재 top-k RL 종료 |
| P0 | 비용 후 선택 신호가 존재하는가? | cost-sensitive supervised ranking ceiling과 linear/neural contextual bandit 비교 | ceiling도 실패하면 RL 확장 중단 |
| P1 | 진짜 순차 행동 효과가 필요한가? | 현금·보유종목·보유기간·교체비용을 상태에 넣고 action이 다음 포지션을 바꾸는 portfolio MDP | 독립 env/action/transition 테스트 선행 |
| P1 | 과도한 거래를 구조적으로 막을 수 있는가? | 학습 reward가 아니라 cooldown·최소 보유·교체 action mask를 환경 계약으로 명시 | train-only nested folds에서 ≤65% |
| HOLD | D7 Fresh OOS | 새 가설·새 prereg·새 봉인 기간이 생길 때만 별도 승인 | 현재 `NOT_RUN_NO_READ` 유지 |

`ts_imb` 시초 갭상승 곡선은 계속 RULE baseline이며 이 DQN 결과와 혼동하지 않는다.

## 6. 증거 계보

| 증거 | 값 |
|---|---|
| Prereg commit | `91d88ce6d2dfbab7b388bca32b85e552c4ec0150` |
| Prereg SHA-256 | `37304fa366b55077341d1dd826478e834d6fcbb50664e2463bc946067f920907` |
| Producer commit | `bbbdf5a3d5553126337b24f11d831ee879673b9b` |
| Producer tree | `da7c65c800b5982e672e7e130e620f57aa82b925` |
| Source episode SHA-256 | `8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40` |
| Artifact manifest SHA-256 | `83e71bc3bf9d5bfae66c7af3ac76521e1e1a6f700ec81fb6eb90d0ffe53aeee4` |
| Summary SHA-256 | `2d492a295066d8e29beb8b1d4f04af6986fc625a3512b63fe78ec0ee6dc23a92` |
| Receipt SHA-256 | `ab159550c080c88f545e2e16d0936bb7346f37fa61b65cb3b74b8e5547d205b4` |
| Models/outcomes | 60/60 |
| Fresh OOS | `NOT_RUN_NO_READ` |

본 결과는 강화학습 모델을 실제로 생성·학습·평가한 결과지만, 거래 가능한 모델의 성공을 뜻하지 않는다.

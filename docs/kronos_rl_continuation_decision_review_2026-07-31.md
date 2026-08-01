# Kronos 강화학습 계속 진행 타당성 중간 의사결정 검토

- 작성일: 2026-07-31 KST
- 기준 릴리스: `fork-v1.20.0-kronos-rl-d6r2-mdp-falsification`
- 기준 커밋: `2cba97218d75cb773a8015f4142da9701fe629f7`
- 검토 범위: Type2 D4~D6R2 일봉 종가 선택 RL 계보, 연구 플랫폼, 다음 연구의 정보가치
- 현재 모델 성과: `18/100`
- 의사결정: **`CONDITIONAL-GO · PIVOT_REQUIRED`**

## 1. 결론

현재 모델 점수 18/100인 상태에서 **같은 top-5 후보, 같은 14개 feature, 같은 horizon, 같은 날짜별 독립 선택 환경에 DQN/PPO의 학습량·seed·gamma·penalty만 바꾸어 계속 학습하는 것은 의미가 없다. 이 연구 lane은 종료한다.**

그러나 Kronos의 강화학습 연구 전체를 종료할 근거는 아직 없다. 다음 연구는 아래 두 질문만 저비용으로 분리해 답하는 조건부 전환이어야 한다.

1. 새로운 feature/horizon에 왕복 23bp 이후에도 시간적으로 안정된 선택 신호가 존재하는가?
2. action이 포지션·현금·교체비용·다음 상태를 실제로 바꾸는 stateful portfolio MDP가 합성 문제에서 학습 가능한가?

두 질문 중 하나라도 실패하면 실제 시장 데이터의 대규모 RL 학습으로 넘어가지 않는다. 두 질문이 모두 통과할 때만 작은 nested walk-forward RL pilot을 허용한다. D7 Fresh OOS는 새 후보와 새 사전등록, 별도 승인 전까지 계속 잠근다.

즉 현재 결정은 다음과 같다.

| 범위 | 결정 | 이유 |
|---|---|---|
| 기존 top-5/14-feature RL 반복 | **STOP** | D6 validation, D6R, D6R2에서 일반화·신호·안정성 모두 실패 |
| 기존 validation 재사용 튜닝 | **PROHIBITED** | 이미 읽은 validation에 맞추면 확인이 아니라 추가 과적합 |
| D7 Fresh OOS 실행 | **LOCKED** | 진입 가능한 새 candidate가 없음 |
| 새 feature/horizon supervised floor | **GO** | 가장 싸게 시장 신호 존재 여부를 판별 |
| stateful MDP 합성 learnability | **GO** | RL 환경 자체가 올바른지 시장 데이터 전에 판별 |
| 실제 데이터 stateful RL | **HOLD** | signal floor와 합성 MDP가 모두 통과해야 함 |
| 대시보드 compact index/cache | **GO** | 연구 결론과 독립적인 명확한 제품 성능 부채 |

## 2. 18점의 정확한 의미

18/100은 연구 플랫폼이나 코드 품질 점수가 아니라 **현재 학습된 정책이 비용 후 거래 후보로서 보인 성과 점수**다. 성공 확률 18%를 의미하지 않으며, 점수를 올리기 위해 기준을 사후 완화해서도 안 된다.

| 평가 축 | 현재 관찰 | 의미 |
|---|---:|---|
| 비용 후 보상 | gamma=0 median ratio `-0.127615` | 기대 보상이 0 이하 |
| 행동 정확도 | `0.1600` | 6-action 무작위 기준 `0.1667` 부근 |
| 시간 안정성 | positive fold `0/5` | 특정 기간에조차 반복 가능한 양의 성과 없음 |
| seed 안정성 | positive seed `0/3` | 초기화 변경으로 회복되지 않음 |
| control 분리 | Native−Shuffled `+0.013654` | 등록 기준 `+0.1000`에 크게 미달 |
| 거래 빈도 | `0.9000` | 약한 신호로 거의 매일 거래 |
| drawdown | `0.442444` | 등록 상한 `0.2500` 초과 |
| 비-RL 신호 바닥 | ridge ratio `-0.152520` | 현재 표현에서는 RL 이전의 선택 신호도 확인되지 않음 |

따라서 18점은 “조금 더 학습하면 20~30점이 될 모델”보다 “현재 문제 정의로는 승격 불가이며 연구 질문을 바꿔야 하는 모델”로 해석해야 한다.

## 3. 실패 계보 재검토

| 단계 | 질문 | 결과 | 후속 판단에 주는 증거 |
|---|---|---|---|
| D4 | 작은 TRAIN_ONLY 구간에서 RL이 reward를 fit할 수 있는가 | DQN fit ratio 약 `0.988`, 확인 | 구현이 전혀 학습하지 못하는 문제는 아님. 일반화 증거는 아님 |
| D5 | 573 TRAIN_ONLY·23bp에서 절대 gate를 재현하는가 | Native `0/5`, NO-GO | 소규모 fit이 전체 train으로 안정적으로 확장되지 않음 |
| D5R | 200K→800K 장기학습으로 개선되는가 | accuracy lift `-0.176265`, reward lift `-0.233700` | 단순 학습량 부족 가설 기각 |
| D5S | 전역 100K 조기종료로 train 안정성을 보존하는가 | 7/7, TRAIN_ONLY CONFIRMED | train 내부 후보는 만들었지만 외부 확인은 아님 |
| D6 | 고정 100K 후보가 reused validation에서 유지되는가 | accuracy `0.179688`, ratio `-0.037396`, NO-GO | train 성공이 validation에서 무작위 수준으로 붕괴 |
| D6R | fold·seed·거래 penalty로 실패를 회복하는가 | 1/10 gate, ratio `-0.106835` | 비용·seed·단일 penalty 문제가 아님 |
| D6R2 | gamma=0·fold-local scaler·ridge floor로 MDP 오지정과 신호 부재를 분리하는가 | 2/13 gate, DQN `-0.127615`, ridge `-0.152520` | 현재 표현의 signal floor와 contextual RL 모두 실패 |

이 계보는 한 번의 나쁜 seed나 한 번의 시장 구간 때문에 18점이 나온 것이 아님을 보여 준다. 작은 train fit → 전체 train 불안정 → 조기종료 train 성공 → validation 붕괴 → fold/seed 실패 → 비-RL signal floor 실패가 순차적으로 관찰됐다.

## 4. 계속 실패하는 구조적 원인

| 원인 | 근거 | 심각도 | 단순 튜닝으로 해결 가능성 |
|---|---|---:|---:|
| 현재 feature/horizon의 비용 후 신호 부족 | ridge native `-0.152520`, shuffle delta `-0.009730` | 매우 높음 | 낮음 |
| 환경이 순차 MDP보다 contextual selection에 가까움 | 당일 action이 다음 후보·포지션·현금을 바꾸지 않음 | 매우 높음 | gamma 변경만으로 해결 불가 |
| TRAIN_ONLY 선택 과적합 | D5S accuracy `0.827225` → D6 `0.179688` | 매우 높음 | 동일 validation 튜닝 금지 |
| 과도한 거래 | D6 `0.883~0.938`, D6R2 median `0.90` | 높음 | penalty 하나로 실패 확인 |
| 시간·seed 불안정 | D6R2 positive fold `0/5`, seed `0/3` | 매우 높음 | seed 추가만으로 해결 불가 |
| 학습 후반부 붕괴 | D5R 400K→800K 세 seed 모두 악화 | 중간 | early-stop은 train fit만 개선했음 |
| 비용만의 문제 아님 | D6R 0bp ratio도 `-0.077106` | 높음 | 수수료 완화로 해결 불가 |

## 5. 다음 단계별 의미와 기대가치

점수가 낮아도 다음 실험이 의미 있으려면 모델 점수를 즉시 높이는 대신 **서로 다른 실패 원인을 싼 비용으로 제거하는 정보가치**가 있어야 한다.

| 후보 액션 | 정보가치 | 비용 | 과적합 위험 | 시장 모델 성공에 직접 기여 | 결정 |
|---|---:|---:|---:|---:|---|
| 기존 DQN seed·step 추가 | 1/5 | 4/5 | 5/5 | 1/5 | STOP |
| 기존 gamma·penalty 추가 sweep | 1/5 | 3/5 | 5/5 | 1/5 | STOP |
| 현재 validation 기준 재튜닝 | 0/5 | 3/5 | 5/5 | 0/5 | PROHIBITED |
| 새 feature/horizon supervised 5-fold+shuffle | 5/5 | 2/5 | 2/5 | 4/5 | GO |
| 합성 stateful MDP learnability | 5/5 | 2/5 | 1/5 | 3/5 | GO |
| 실제 데이터 stateful MDP 전체 학습 | 3/5 | 5/5 | 4/5 | 4/5 | HOLD |
| D7 Fresh OOS 즉시 실행 | 1/5 | 2/5 | 5/5 | 0/5 | LOCKED |
| 대시보드 cold-load 캐시 | 4/5 | 1/5 | 1/5 | 0/5 | GO |

## 6. 허용할 다음 연구의 단계와 강제 종료 기준

### Phase A — 새로운 신호 바닥

RL을 돌리기 전에 새로운 feature/horizon이 비용 후 신호를 갖는지 ridge, logistic/ranking 또는 작은 tree 모델로 검사한다. 이는 RL 성과가 아니며 입력 표현의 최소 조건 검사다.

| 항목 | 제안 사전등록 기준 |
|---|---|
| 데이터 | TRAIN_ONLY 내부 chronological expanding 5-fold |
| 정규화 | fold train만 fit, evaluation row 사용 0 |
| 비용 | 왕복 23bp primary |
| 대조군 | label/reward shuffle 필수 |
| 최소 후보 조건 | native median post-cost reward ratio `> 0` |
| control 조건 | native−shuffled `≥ +0.10` |
| 시간 안정성 | positive fold `≥ 4/5` |
| 위험 조건 | 비용 포함 drawdown `≤ 0.25` |
| 종료 규칙 | 위 조건 중 하나라도 실패하면 해당 feature/horizon RL 금지 |

예상 시간은 1~2일이다. 이 단계가 실패하면 모델을 더 크게 만드는 대신 feature/horizon 가설을 폐기한다.

### Phase B — stateful MDP 계약과 합성 학습

시장 데이터보다 먼저 정답 정책을 아는 합성 가격 경로에서 환경과 알고리즘을 검증한다.

| 필수 계약 | 완료 기준 |
|---|---|
| 포지션 전이 | buy/hold/sell/switch가 다음 step의 position을 변경 |
| 현금·평가액 | 체결 가격·비용·보유 수량으로 정확히 ledger 재계산 |
| 비용 | 교체·진입·청산 때만 23bp 계약대로 반영 |
| Markov observation | position, cash, holding age, pending constraint 포함 |
| 누출 방지 | 미래 가격·eval scaler row 접근 0 |
| 불변식 | 현금·수량·자산 합계·action mask 테스트 100% 통과 |
| 합성 learnability | 알려진 최적 정책을 3 seed 중 3개에서 안정적으로 회복하도록 별도 prereg |
| 대조군 | random policy와 shuffled transition을 명확히 하회/상회 분리 |

예상 시간은 계약·테스트 0.5~1일, 최소 환경 구현 1~2일이다. 합성 환경도 학습하지 못하면 실제 시장 RL 실행은 금지한다.

### Phase C — 최소 실제 데이터 pilot

Phase A와 B를 모두 통과한 단 하나의 사전등록 후보만 작은 nested walk-forward로 실행한다.

| 제한 | 이유 |
|---|---|
| 알고리즘 1~2개 | 사후 best-of-many 선택 방지 |
| seed 3개 | 초기화 안정성 확인 |
| chronological fold 5개 이상 | 시장 구간 의존성 확인 |
| 작은 고정 compute budget | 실패한 탐색에 계산 예산 무한 투입 방지 |
| no-trade·rule·shuffle 비교 | RL이 실제 추가 가치를 주는지 확인 |
| 실패 결과도 terminal receipt 보존 | 성공 run만 선택하는 편향 방지 |

예상 시간은 구현·학습 포함 1~3일 이상이며 연산 환경에 따라 달라진다. 여기서 통과해도 연구 candidate일 뿐 수익 가능한 모델 확정이 아니다.

### Phase D — 새 봉인 기간

현재 D6 validation은 이미 읽었으므로 다시 승인 데이터로 사용할 수 없다. Phase C까지 통과한 뒤에만 새로운 봉인 기간과 새로운 사전등록을 만들고 D7 상당의 단 한 번 검증을 검토한다.

## 7. 연구 예산과 중단선

| 구간 | 최대 권장 예산 | 실패 시 액션 |
|---|---:|---|
| Phase A 신호 바닥 | 1~2일 | 해당 feature/horizon 종료 |
| Phase B 합성 MDP | 1.5~3일 | 환경/보상 계약 수정 후 1회 재검증, 계속 실패하면 RL 환경 연구 중단 |
| Phase C 실제 pilot | 1~3일+연산 | 후보 종료, D7 금지 |
| 전체 1차 전환 연구 | 약 4~8 작업일 | 통과 단계 없이 예산 연장 금지 |

다음 연구의 목적은 “무엇이든 점수를 20점 넘기기”가 아니다. 첫 번째 목적은 최대 1~2일 안에 새 입력 신호의 존재 여부를 판단하는 것이고, 두 번째 목적은 실제 RL이 필요한 순차 의사결정 문제를 올바르게 구현했는지 검증하는 것이다.

## 8. 목표별 최종 답변

| 사용자의 실제 목표 | 이대로 계속할 의미 | 답 |
|---|---|---|
| 기존 모델을 더 오래 돌려 수익 모델 만들기 | 없음 | 중단해야 함 |
| 실제 RL 모델 파일을 하나 더 생성하기 | 기술적으로 가능하지만 연구가치 낮음 | 권장하지 않음 |
| 강화학습이 정상적으로 배울 수 있는 플랫폼 만들기 | 있음 | 합성 stateful MDP로 진행 |
| 일봉 종가 데이터에서 새 alpha 후보 찾기 | 조건부로 있음 | RL 전에 새 signal floor부터 진행 |
| 실거래 가능한 모델을 곧 확보하기 | 현재 증거로 보장 불가 | 일정·성과 보장 금지 |
| 실패 이유를 과학적으로 줄여 나가기 | 있음 | 단계별 kill gate를 지키면 진행 가치 높음 |

## 9. 최종 권고

1. `D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED`를 현재 lane의 종료 판정으로 유지한다.
2. D7은 열지 않고 기존 D6 validation에 맞춘 수정도 금지한다.
3. 다음 구현 순서는 `새 feature/horizon signal floor → stateful MDP synthetic test → 최소 실제 pilot`로 고정한다.
4. 각 단계는 구현 전에 별도 prereg와 hard stop을 커밋한다.
5. Phase A 또는 B가 실패하면 실제 데이터 RL 학습을 실행하지 않는다.
6. 모델 성과 18점과 연구 플랫폼 완성도 90점을 대시보드에서 계속 분리한다.

이 조건을 지키는 한 다음 단계는 의미가 있다. 조건을 지키지 않고 동일 데이터·환경에서 튜닝을 반복하는 다음 단계는 의미가 없으며 과적합 가능성만 높인다.

직접 화면 검토 순서, 12페이지별 체크 항목과 정확한 기대 수치는 [`kronos_rl_dashboard_direct_review_guide_2026-08-01.md`](kronos_rl_dashboard_direct_review_guide_2026-08-01.md)에 기록했다.

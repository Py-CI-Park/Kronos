# Kronos 강화학습 발견 실험실 검토 및 Type2 연구 제안

**작성일:** 2026-07-26 KST  
**상태:** `PROPOSED / DISCOVERY_ONLY`  
**기준 커밋:** `73c4c1bd4885ae5cfb33595d3973ce289cd4daf9`  
**기존 Type1 판정:** `COMPLETE / NO_GO`  
**Fresh OOS:** `NOT_RUN/no-read` 유지  
**목적:** 수익성이나 실거래 준비를 주장하지 않고, 실제 강화학습이 무엇을 학습할 수 있는지 단계적으로 발견하는 연구 플랫폼을 제안한다.

## 1. 결론

Kronos에서 강화학습이 실행되지 않은 것은 아니다. Type1 공개 연구에서 MaskablePPO 기본 5 seed와 shuffled-reward 통제군 5 seed가 각각 200,000 step 학습됐고 최종 판정은 `NO_GO`였다. 합성 train-only 과적합 경로도 존재하며, 104,000 step에서 oracle reward ratio 1.0을 기록했다.

다만 현재 증거에는 큰 간격이 있다.

```text
합성 fixture + oracle behavior cloning 포함 과적합 성공
                       ↓ 큰 증거 공백
전체 역사 데이터 MaskablePPO 학습 및 reused validation NO_GO
```

따라서 다음 연구는 동일한 전체시장 실험을 반복하거나 학습 step만 무작정 늘리는 것이 아니라, 다음 질문을 순서대로 답해야 한다.

1. **PPO만으로** 합성 환경을 과적합할 수 있는가?
2. PPO가 소수의 실제 역사 episode를 반복 학습해 암기할 수 있는가?
3. 행동 공간과 보상 구조를 단순화하면 실제 경제 reward를 학습하는가?
4. 0bp에서 학습된 행동이 23bp 비용에서 어떻게 붕괴하는가?
5. train-only에서 발견한 현상이 reused validation에서도 남는가?

추천안은 기존 Type1을 변경하지 않고 별도의 **RL Discovery Lab**을 만드는 것이다. 이 실험실에서는 과적합을 실패가 아니라 환경·보상·알고리즘의 학습 가능성을 확인하는 진단 단계로 사용한다. 과적합 성공은 `OVERFIT_CONFIRMED`일 뿐 `GO`, 수익성, 일반화 또는 실거래 준비를 의미하지 않는다.

## 2. 검토한 현재 증거

| 증거 | 관측 내용 | 올바른 해석 |
|---|---|---|
| Type1 공개 학습 | MaskablePPO primary 5 seed + shuffled reward 5 seed, seed당 200,000 step | 실제 RL 학습은 수행됨 |
| Type1 최종 판정 | `COMPLETE / NO_GO` | 파이프라인 완료와 모델 채택 실패를 동시에 의미 |
| Fresh OOS | `NOT_RUN/no-read` | 아직 일반화 최종 검증을 하지 않음 |
| 합성 과적합 | reward ratio 1.0, exact basket accuracy 1.0 | 환경·모델·mask·decoder 배선은 동작함 |
| 합성 과적합 보정 | PPO 전후 oracle behavior cloning 각 200 epoch 포함 | PPO 단독 학습 가능성을 증명하지는 않음 |
| Type1 observation | 8,514차원 Dict observation | 표본 대비 지나치게 넓고 정책 최적화가 어려울 수 있음 |
| Type1 action | STOP 또는 500개 stable slot 중 선택, 총 501 action | 탐색 난도가 높고 action collapse 가능성이 큼 |
| 경제 reward | 고정 23bp 비용 차감 NAV 변화 | 연구 정직성은 높지만 초기 학습 신호가 매우 약할 수 있음 |
| 기존 orderbook RL | DQN/PPO 계열 smoke와 action diagnostics 존재 | 환경 falsification에는 유용하지만 usable model 증거는 아님 |
| 규칙 baseline | `ts_imb` opening gap-up은 RULE | RL 성과로 표시하면 안 됨 |

## 3. 현재 문제의 재정의

현재 목표를 곧바로 “23bp 비용 후 미지 데이터에서 수익을 내는 RL”로 두면 실패 원인을 구분하기 어렵다. `NO_GO`가 발생해도 다음 중 무엇이 원인인지 알 수 없다.

| 가능한 실패 원인 | 현재 전체시장 실험만으로 구분 가능한가 |
|---|---|
| 환경 상태 전이가 잘못됨 | 제한적 |
| reward가 너무 희소하거나 scale이 작음 | 제한적 |
| 501-way 행동 공간 탐색 실패 | 제한적 |
| observation 8,514차원의 표본 효율 문제 | 제한적 |
| 정책이 STOP 또는 특정 slot으로 붕괴 | 일부만 가능 |
| 거래비용이 모든 edge를 제거 | 일부 가능 |
| feature에 실제 예측 정보가 없음 | 일부 가능 |
| 알고리즘 또는 hyperparameter 부적합 | 제한적 |
| 단순 과적합은 되지만 일반화가 안 됨 | 중간 단계가 없어 판별 어려움 |

새 연구의 첫 목표는 수익이 아니라 **실패 원인의 위치를 특정하는 것**이다.

## 4. 과적합을 허용해야 하는 이유

과적합은 일반화 증거로 사용하면 잘못이지만, 학습 시스템 진단에는 필수적인 positive control이다.

| 결과 | 의미 | 다음 결정 |
|---|---|---|
| 한 episode도 암기하지 못함 | 환경, reward, 행동 공간 또는 optimizer 문제 가능성이 큼 | 전체시장 학습 중단, mechanics 수정 |
| 한 episode는 암기하지만 32 episode는 실패 | 정책 용량·표현·credit assignment 문제 | action/reward 구조 단순화 |
| 32~128 episode 암기 성공 | RL이 역사 데이터의 반복 패턴을 학습할 능력은 있음 | 비용 사다리로 이동 |
| 0bp 성공, 23bp 실패 | 시장 신호보다 비용 장벽이 핵심 | turnover와 holding horizon 연구 |
| 23bp train 성공, reused validation 실패 | 전형적인 과적합 | feature·regularization·분할 연구 |
| shuffled reward와 차이가 없음 | 의미 있는 reward 학습이 아님 | 정책 붕괴 또는 우연으로 분류 |
| reused validation에서도 차이가 남음 | 후속 연구 후보 | Fresh OOS는 여전히 열지 않음 |

## 5. 연구 상태 명칭

`GO/NO_GO` 하나만 사용하면 발견 단계의 진전을 표현하기 어렵다. 다음 상태를 추가하되 Type1의 기존 `NO_GO`는 바꾸지 않는다.

| 상태 | 의미 | 허용되는 주장 |
|---|---|---|
| `MECHANICS_BROKEN` | 합성 PPO-only 과적합도 실패 | 환경 또는 학습 배선 문제 |
| `PPO_ONLY_OVERFIT_CONFIRMED` | behavior cloning 없이 합성 문제 암기 | PPO 학습 경로가 동작함 |
| `HISTORICAL_MEMORIZATION_CONFIRMED` | 소규모 역사 train episode 암기 | 역사 reward를 학습할 수 있음 |
| `COST_BARRIER_IDENTIFIED` | 0bp 성공, 23bp 실패 | 비용이 핵심 실패 원인 |
| `DEGENERATE_POLICY` | STOP/한 행동으로 정책 붕괴 | 학습 성공으로 간주하지 않음 |
| `DISCOVERY_CANDIDATE` | train-only 여러 seed와 control에서 현상 확인 | 후속 검증 가치가 있음 |
| `REUSED_VALIDATION_CANDIDATE` | 재사용 검증에서도 control 우위 | 연구 후보일 뿐 GO 아님 |
| `NO_GO_MECHANICS` | 학습 mechanics 단계 실패 | 전체시장 확장 금지 |
| `NO_GO_ECONOMIC` | 학습은 되지만 23bp 경제 gate 실패 | 수익성 주장 금지 |
| `NO_GO_GENERALIZATION` | train 성공, validation 실패 | 과적합으로 종료 |

## 6. 강화학습 발견 사다리

| 단계 | 데이터 | 알고리즘/행동 | 비용 | 목표 | 통과 후 이동 |
|---|---|---|---:|---|---|
| D0-A | 기존 합성 fixture | PPO-only, BC 없음 | 합성 계약 | PPO 단독 overfit 확인 | D0-B |
| D0-B | 기존 합성 fixture | BC-only / BC→PPO / PPO-only 3-arm | 합성 계약 | PPO의 순수 기여 분해 | D1 |
| D1 | train-only 역사 1 episode | binary 또는 top-K action | 0bp | 단일 episode 암기 | D2 |
| D2 | train-only 역사 8→32→128 episode | MaskablePPO, 3~5 seed | 0bp | 규모 증가에 따른 암기 한계 측정 | D3 |
| D3 | D2와 동일 | reward/action ablation | 0bp | reward와 action 병목 분리 | D4 |
| D4 | train-only 고정 episode | 최적 D3 설정 | 0→5→10→23→46bp | 비용 붕괴 지점 측정 | D5 |
| D5 | train-only 전체 범위 | 5 seed + shuffled control 5 seed | 23bp primary | 발견 설정의 확장성 확인 | D6 |
| D6 | reused validation | 설정 변경 금지 | 23bp primary | 일반화 징후 확인 | 연구 후보 또는 NO_GO |
| D7 | Fresh OOS | 외부 권한·명시적 승인 후 한 번 | 23bp primary | 최종 일반화 확인 | 별도 판정 |

D0~D5는 train-only discovery다. D6 결과를 본 뒤 D0~D5 설정을 다시 바꾸면 새로운 preregistration과 새로운 연구 계보를 만들어야 한다.

## 7. 첫 번째 권장 실험: Type2-D0 PPO 귀속성 시험

현재 합성 overfit 성공에는 PPO 전후 oracle behavior cloning이 포함돼 있다. 따라서 가장 먼저 모델이 PPO reward만으로 실제 학습했는지를 분리해야 한다.

### 7.1 실험군

| arm | 초기화 | PPO 학습 | PPO 후 oracle 보정 | 목적 |
|---|---|---|---|---|
| A | random | 실행 | 없음 | 순수 PPO 학습 가능성 |
| B | oracle BC warm start | 실행 | 없음 | warm start 후 RL 기여 |
| C | oracle BC | 없음 | 없음 | imitation 단독 기준 |
| 기존 방식 참고 | oracle BC | 실행 | oracle BC | 배선 positive control, 귀속성 판단에서는 제외 |

### 7.2 고정 조건

| 항목 | 제안 값 |
|---|---|
| 환경 | 기존 `Type1ClosingEnv` 변경 없이 사용 |
| fixture | 기존 합성 fixture SHA 고정 |
| seeds | 0, 1, 2 |
| PPO budget | 104,000 step 우선, 미달 시 200,000까지 사전 고정 확장 |
| checkpoint | 0, 10k, 25k, 50k, 104k, 200k |
| action mask | 기존 native mask 유지 |
| 평가 | deterministic evaluation + stochastic action distribution 모두 저장 |
| 금지 | 결과를 본 뒤 seed 또는 checkpoint 선택 |

### 7.3 필수 지표

| 지표 | 이유 |
|---|---|
| oracle reward ratio | 기존 합성 결과와 직접 비교 |
| exact basket accuracy | 행동 암기 여부 |
| PPO 시작 대비 reward improvement | RL update의 실제 기여 |
| entropy | 정책 붕괴 탐지 |
| action histogram | STOP/특정 slot 집중 탐지 |
| explained variance | value function 학습 상태 |
| approximate KL / clip fraction | PPO update 유효성 |
| policy parameter update norm | 실제 가중치 변화 확인 |
| shuffled reward arm | reward 의미성 확인 |

### 7.4 제안 gate

| gate | 통과 조건 |
|---|---|
| PPO mechanics | PPO-only 3 seed 중 3 seed가 oracle reward ratio 0.90 이상 |
| attribution | PPO-only 또는 BC→PPO가 각자의 PPO 시작 checkpoint보다 명확히 개선 |
| action validity | invalid/block/no-fill 0 |
| collapse | 단일 행동 비율 95% 이상이면 `DEGENERATE_POLICY`, 단 oracle 정답 분포가 동일한 경우 제외 |
| control | shuffled reward가 동일 수준이면 통과 불가 |

통과하면 `PPO_ONLY_OVERFIT_CONFIRMED`, 실패하면 `NO_GO_MECHANICS`로 기록한다. 어느 쪽도 수익성 판정이 아니다.

## 8. 두 번째 권장 실험: 실제 역사 데이터 암기

### 8.1 데이터 선택

수익이 좋은 날짜를 골라서는 안 된다. train-only 구간에서 다음의 결정적 규칙으로 episode를 선택한다.

1. 기존 Type1 train partition만 사용한다.
2. episode identity를 SHA-256으로 정렬한다.
3. 실험 크기별로 앞에서 1, 8, 32, 128개를 사용한다.
4. 최소한 하나의 양의 oracle action이 필요한 진단군은 별도 `POSITIVE_OPPORTUNITY_DIAGNOSTIC`으로 표시한다.
5. 선택 규칙과 episode SHA 목록을 학습 전에 manifest로 고정한다.

### 8.2 행동 공간 사다리

| 단계 | 행동 | 목적 |
|---|---|---|
| A0 | 사전 고정 후보에 대해 `SELECT/HOLD` | binary RL mechanics 확인 |
| A1 | STOP + 상위 K 후보, K=8 | 작은 discrete 탐색 |
| A2 | STOP + 상위 K 후보, K=32 | 행동 수 증가 영향 |
| A3 | 기존 STOP + 500 stable slot | Type1 전체 행동 계약 재현 |
| A4 | 후보별 shared scorer + STOP head | 501-way 고정 head의 표현 병목 완화 |

A0~A2는 발견용 축소 환경이며 Type1과 동일한 연구라고 부르면 안 된다. A3에서 기존 계약으로 연결하고, A4는 Type2의 새 정책 구조로 사전등록한다.

### 8.3 reward 사다리

| 단계 | reward | 해석 |
|---|---|---|
| R0 | 정답 행동 일치 reward | 학습 mechanics positive control, 경제성 없음 |
| R1 | 0bp gross marginal NAV reward | 시장 reward 자체 학습 여부 |
| R2 | 23bp net marginal NAV reward | 기본 경제 gate |
| R3 | 23bp + turnover/drawdown 분해 reward | 위험 조정 연구 |

R0 성공은 R1 성공을 의미하지 않는다. R1 성공 후 R2가 실패하면 비용 장벽으로 분류한다. 최종 보고에서는 reward 구성 요소를 합계 하나로 숨기지 않고 gross PnL, transaction cost, turnover penalty, drawdown penalty를 각각 기록한다.

## 9. 알고리즘 우선순위

| 순위 | 알고리즘 | 사용 이유 | 보류/주의점 |
|---:|---|---|---|
| 1 | MaskablePPO | 기존 환경·mask·artifact 경로 재사용 가능 | PPO-only 귀속성부터 확인 |
| 2 | factorized actor PPO | 후보별 공통 scorer로 universe 확장 가능 | 새 정책 구현과 계약 테스트 필요 |
| 3 | RecurrentPPO | 상태가 부분 관측일 때 유용 | MLP overfit 성공 전 도입 금지 |
| 4 | DQN/QR-DQN | 작은 discrete action에서 비교 가능 | 501 action과 mask 처리가 불리함 |
| baseline | contextual bandit | 단일 의사결정 문제의 강한 비교군 | episodic RL로 부르지 않음 |
| 후순위 | offline CQL/IQL | logged-policy 편향 연구 가능 | behavior policy와 action coverage가 확보된 뒤 검토 |

처음부터 Transformer, LSTM, multi-agent, 대규모 hyperparameter search로 확장하지 않는다. 가장 작은 모델이 단일 역사 episode를 암기하지 못하면 모델 크기보다 환경·reward·action 계약을 먼저 고친다.

## 10. 플랫폼 구조 제안

```text
stom_rl/discovery_lab/
  contract.py          # discovery 단계, 비용, seed, status 계약
  dataset.py           # train-only deterministic episode registry
  env_adapter.py       # 기존 Type1/orderbook 환경을 축소 단계에 연결
  policies.py          # PPO-only, BC-only, BC→PPO, factorized actor
  trainer.py           # checkpoint와 optimizer/entropy/KL 로그
  evaluator.py         # oracle, random, no-trade, shuffled 비교
  gates.py             # mechanics/memorization/cost/generalization 판정
  artifacts.py         # manifest, hashes, append-only 결과
  cli.py               # prereg 기반 실행 진입점

tests/
  test_rl_discovery_contract.py
  test_rl_discovery_dataset.py
  test_rl_discovery_env.py
  test_rl_discovery_attribution.py
  test_rl_discovery_gates.py
  test_rl_discovery_artifacts.py

webui/rl_runs/rl_discovery/{experiment_id}/
  preregistration.json
  dataset_manifest.json
  checkpoints/
  training_metrics.jsonl
  action_metrics.jsonl
  evaluation.json
  controls.json
  gate.json
  terminal_receipt.json
```

### 플랫폼이 반드시 제공해야 하는 화면

| 화면 | 표시 항목 |
|---|---|
| 학습 곡선 | reward, value loss, policy loss, entropy, KL, clip fraction |
| 행동 진단 | action histogram, STOP 비율, invalid action, mask 사용률 |
| 과적합 지도 | episode 수별 train reward와 oracle regret |
| 비용 사다리 | 0/5/10/23/46bp 결과와 붕괴 지점 |
| 귀속성 비교 | PPO-only, BC-only, BC→PPO, shuffled reward |
| 일반화 간격 | train과 reused validation의 reward·turnover·MDD 차이 |
| 실험 계보 | prereg SHA, dataset SHA, parent run, code SHA |
| 판정 | `OVERFIT_CONFIRMED`, `DEGENERATE_POLICY`, 각 종류의 `NO_GO` |

대시보드는 계속 GET-only 증거 viewer로 유지하고 학습 시작, 주문, 브로커, 실계좌 제어 기능을 추가하지 않는다.

## 11. 실험 레지스트리와 과잉 탐색 방지

“뭐라도 찾기”가 무제한 탐색과 결과 선별로 변하면 발견한 신호의 의미가 사라진다. 자유로운 discovery는 허용하되 모든 시도를 ledger에 남긴다.

| 규칙 | 구현 |
|---|---|
| 모든 run 보존 | 성공·실패·중단 run에 terminal receipt 생성 |
| best seed 선택 금지 | seed 중앙값과 전체 분포 보고 |
| best checkpoint 선택 제한 | train-only 사전 고정 규칙으로 선택 |
| validation 확인 후 수정 | 새 experiment lineage와 prereg 생성 |
| 가설 개수 기록 | hypothesis ledger에 시도 수 누적 |
| reward 변경 추적 | reward component와 변경 이유를 manifest에 기록 |
| 데이터 선택 추적 | episode selection algorithm과 SHA 목록 보존 |
| 실패 세분화 | mechanics/economic/generalization NO_GO 분리 |

## 12. 권장 작업 패키지

| 순서 | 작업 | 산출물 | 완료 조건 |
|---:|---|---|---|
| 1 | Type2-D0 사전등록 | 고정 JSON prereg | arm, seed, budget, gate SHA 고정 |
| 2 | 기존 합성 trainer의 BC/PPO 분리 | attribution runner | PPO-only/BC-only/BC→PPO 독립 실행 |
| 3 | 학습 진단 로깅 | metrics JSONL | entropy, KL, clip, update norm 저장 |
| 4 | D0 3-arm 실행 | D0 terminal receipt | mechanics 판정 생성 |
| 5 | 역사 episode registry | dataset manifest | deterministic 1/8/32/128 episode 집합 |
| 6 | binary/top-K 축소 환경 | env adapter + tests | 기존 accounting과 mask 보존 |
| 7 | D1/D2 암기 실행 | memorization curves | episode 수별 암기 한계 확인 |
| 8 | reward/action ablation | comparison report | 병목을 feature/action/reward로 분류 |
| 9 | 비용 사다리 | cost report | 23bp 붕괴 여부 확인 |
| 10 | 전체 train 확장 | 5+5 seed artifacts | shuffled control 비교 |
| 11 | reused validation | immutable result | 설정 변경 없이 후보/NO_GO 판정 |
| 12 | 대시보드 탭 | read-only evidence UI | 실패·과적합·비용·seed 분산 노출 |

## 13. 자원 예산 제안

| 단계 | seeds | step 예산 | 중단 조건 |
|---|---:|---:|---|
| D0 PPO 귀속성 | 3 | 104k, 필요 시 사전 고정 200k | mechanics gate 확정 |
| D1 단일 episode | 3 | 최대 100k | 3 seed 모두 plateau |
| D2 8/32/128 episode | 3 | 각 최대 300k | reward/oracle regret 개선 없음 |
| D3 ablation | 3 | 후보당 최대 300k | shuffled와 차이 없음 |
| D4 비용 사다리 | 3 | 최적 train checkpoint 재평가 우선 | 23bp에서 전부 음수 |
| D5 전체 train | 5+5 | seed당 200k~1m 사전 고정 | control gate 확정 |

학습량 증가는 단계 통과 후에만 허용한다. 학습이 되지 않는 환경에 1m~10m step을 투입하는 것은 원인 규명이 아니라 계산 낭비다.

## 14. 다음 연구에서 하지 말아야 할 것

| 금지 사항 | 이유 |
|---|---|
| Type1 `NO_GO`를 수정하거나 덮어쓰기 | 기존 연구 계보 훼손 |
| 합성 BC 성공을 PPO 성공으로 표현 | 학습 기여 귀속 오류 |
| 과적합 성공을 수익성으로 표현 | 일반화 증거가 아님 |
| 가장 좋은 seed/checkpoint만 보고 | selection bias |
| 0bp 성과만 보고 | 기본 23bp 비용 계약 회피 |
| 미래 수익이나 oracle action을 observation에 포함 | 누수 |
| reward에 미래 가격 사용 사실을 숨김 | reward와 observation 경계 불투명 |
| RULE 성과를 RL 성과로 표시 | 연구 유형 오표기 |
| Fresh OOS를 자동 다음 단계로 실행 | 외부 권한·명시적 승인 필요 |
| 대시보드에 live/broker/order 제어 추가 | 현재 연구 범위 밖 |

## 15. 최종 권고

가장 먼저 수행할 실제 작업은 **Type2-D0 PPO 귀속성 시험**이다. 현재 합성 overfit 경로에서 oracle behavior cloning을 분리하고, PPO-only가 합성 fixture를 스스로 암기하는지 확인한다.

그다음 실제 역사 train episode를 1→8→32→128개로 늘리는 암기 사다리를 만든다. 이 단계가 성공하면 비용을 0→5→10→23→46bp로 높여 신호 학습 실패와 비용 실패를 구분한다. 23bp train-only에서 shuffled control보다 일관되게 나은 설정만 전체 train과 reused validation으로 확장한다.

이 접근을 사용하면 결과가 계속 `NO_GO`여도 다음 중 하나를 명확히 얻을 수 있다.

- PPO mechanics가 실제로 작동하는지;
- 역사 데이터 암기가 가능한지;
- 행동 공간이 병목인지;
- reward 설계가 병목인지;
- 비용이 edge를 제거하는지;
- 학습은 되지만 일반화가 안 되는지.

즉 목표는 당장 `GO`를 만들어내는 것이 아니라, 매 실험에서 **왜 안 되는지 또는 어느 단계까지 되는지**를 축적하는 강화학습 연구 플랫폼을 만드는 것이다.


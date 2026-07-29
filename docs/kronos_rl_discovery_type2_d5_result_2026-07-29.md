# Type2-D5 전체 TRAIN·23bp 비용 연구 결과

## 판정

| 항목 | 결과 |
|---|---|
| 최종 verdict | `D5_FULL_TRAIN_COST_NOT_CONFIRMED` |
| 실제 강화학습 | SB3 DQN 10개 모델 학습 완료 |
| 학습 범위 | TRAIN_ONLY 573 세션, 278,097 eligible rows, 500 symbols |
| 학습/Primary 평가 비용 | 왕복 23bp |
| Native 통과율 | 0/5 = 0% (필수 60%) |
| Shuffled 통과율 | 0/5 = 0% (필수 60%) |
| Native–Shuffled native replay 차이 | 0.985472 (필수 0.20 이상, 통과) |
| Invalid action | 전 모델 0 (통과) |
| 재사용 validation | `NOT_RUN_NO_READ` |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Promotion / 수익성 주장 | 차단 |

D5는 실제 강화학습을 수행하는 데 성공했지만, 사전등록한 “정확 행동 accuracy 0.90과 reward ratio 0.90을 동시에 3/5 seed에서 재현”하는 데 실패했다. 따라서 모델 생성 성공과 연구 가설 확인 실패를 분리한다.

## 모델별 결과

| Reward | Seed | Fit accuracy | Fit reward ratio (23bp) | Native replay (23bp) | Native replay (0bp) | Invalid | 동시 gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Native | 0 | 0.712042 | 0.872779 | 0.872779 | 0.875731 | 0 | FAIL |
| Native | 1 | 0.661431 | 0.850386 | 0.850386 | 0.855519 | 0 | FAIL |
| Native | 2 | 0.727749 | 0.903753 | 0.903753 | 0.904180 | 0 | FAIL (accuracy) |
| Native | 3 | 0.734729 | 0.902424 | 0.902424 | 0.906614 | 0 | FAIL (accuracy) |
| Native | 4 | 0.739965 | 0.907233 | 0.907233 | 0.911518 | 0 | FAIL (accuracy) |
| Shuffled | 0 | 0.668412 | 0.869210 | -0.104827 | -0.066483 | 0 | FAIL |
| Shuffled | 1 | 0.689354 | 0.845359 | -0.090722 | -0.052776 | 0 | FAIL |
| Shuffled | 2 | 0.678883 | 0.867859 | -0.107310 | -0.075251 | 0 | FAIL |
| Shuffled | 3 | 0.710297 | 0.867153 | -0.122051 | -0.084028 | 0 | FAIL |
| Shuffled | 4 | 0.738220 | 0.898084 | -0.065873 | -0.031260 | 0 | FAIL |

## 평균과 해석

| Arm | 평균 fit accuracy | 평균 fit reward ratio | 평균 native 23bp | 평균 native 0bp |
|---|---:|---:|---:|---:|
| Native | 0.715183 | 0.887315 | 0.887315 | 0.890712 |
| Shuffled | 0.697033 | 0.869533 | -0.098157 | -0.061960 |

관찰된 실패 구조는 다음과 같다.

1. **학습이 실행되지 않은 실패가 아니다.** 10개 DQN이 각각 200,000 step을 완료했고 모델·outcome·terminal receipt가 모두 존재한다.
2. **비용 포함 reward 근사는 유의미하지만 exact-action 복원은 부족하다.** Native 평균 reward ratio는 0.887이지만 정확 행동 accuracy는 0.715다. 여러 후보 행동이 비슷한 보상을 내는 상황에서 보상은 상당 부분 회수해도 oracle과 동일한 종목을 고르는 비율은 낮았다.
3. **negative control 분리는 강하다.** Shuffled 모델은 자체 shuffled fit에서 평균 0.870 reward ratio를 보이지만 원래 Native 보상으로 replay하면 -0.098이다. 평균 Native delta 0.985는 등록 기준을 크게 넘었다.
4. **D4의 128세션 확인은 573세션·23bp 학습으로 그대로 확장되지 않았다.** 데이터 규모 확대와 비용 직접 반영 후 DQN의 고정 200,000-step/256×128 용량으로는 exact-action 기준을 만족하지 못했다.
5. **사후 기준 완화는 하지 않는다.** reward ratio만 보고 GO로 바꾸거나 accuracy 기준을 낮추면 사전등록을 위반한다.

## 증거 보관

| 증거 | 값 |
|---|---|
| Run | `type2-d5-primary-20260729-001` |
| Prereg SHA-256 | `861360b06dc1107c053bbfe887a58bbd7c7e3b225fbc40d1e8d01eeb3a07319a` |
| Episode snapshot SHA-256 | `8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40` |
| Artifact manifest SHA-256 | `369e6f1ee4068012c31dffb30d9a32b3eaadeb2b0f582262f75076dd1d9964af` |
| Summary SHA-256 | `487ff3cbf01ddffd4d3c5bae378caaf9d14093441f5fa7bd17c965cc99c44e7c` |
| Terminal receipt SHA-256 | `d45ffe903f0f1417340d81556f36c24573c94ed7c58376d27388b6a931d63d33` |
| 모델 / outcome | 10 / 10 |
| Primary HMAC | 존재, 비밀 키는 저장하지 않음 |
| 장기 dashboard custody | `docs/evidence/type2-d5-primary-20260729-001.custody.json` |

## 다음 연구 제안: D5R 용량·목적 분해

D6 재사용 validation은 열지 않는다. D5가 실패했으므로 다음 연구도 TRAIN_ONLY에서 원인을 분해한다.

| 단계 | 연구 질문 | 제안 실험 | 성공 조건 | 목적 |
|---|---|---|---|---|
| D5R-1 | exact accuracy가 낮은 이유가 동률·근접 보상인가 | top-1 대비 선택 행동 regret, 5/10/25bp 이내 near-optimal accuracy 계산 | reward ratio와 exact accuracy 차이를 수치 설명 | gate 설계 진단 |
| D5R-2 | 200k step이 부족한가 | DQN 400k/800k learning curve, Native 3 seed 우선 | 사전등록한 accuracy·reward 동시 향상 | 계산 예산 검증 |
| D5R-3 | 네트워크/탐색 용량이 부족한가 | 512×256, dueling/Double-DQN 계열 또는 QR-DQN 비교 | shuffled control 분리 유지 + Native 안정성 증가 | 알고리즘 용량 검증 |
| D5R-4 | 과적합 가능성 자체를 확인할 수 있는가 | TRAIN_ONLY oracle 행동 모방 pretrain 뒤 DQN fine-tune, `HYBRID_RL`로 명시 | exact accuracy 0.90 이상 3/5 | 표현/최적화 상한 확인 |
| D6 | 재사용 validation으로 넘어가도 되는가 | D5R이 새 prereg gate 통과할 때만 별도 승인 | TRAIN_ONLY 확인 선행 | 데이터 누출 방지 |

D5R-4는 순수 RL로 부르지 않는다. 모방학습으로 초기화한 뒤 RL fine-tune한 하이브리드 연구이며, TRAIN_ONLY 과적합 가능성을 확인하는 진단이다. 실제 alpha나 수익성을 주장하려면 이후 D6와 Fresh OOS가 별도로 필요하다.

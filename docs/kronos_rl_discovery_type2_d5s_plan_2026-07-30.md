# Type2-D5S 안정성·글로벌 Early-Stop 연구 계획

## 연구 질문

D5R은 실제 DQN 6개 계보와 4.8M step을 완료했지만 Native 3개 seed가 모두 장기 학습에서 악화됐다. D5S는 모델을 더 크게 만들거나 OOS를 여는 대신 다음 한 질문만 검증한다.

> DQN 학습률을 `1e-3`에서 `3e-4`로 낮추고, 사전 고정된 체크포인트 집합에서 3-seed Native 중앙값으로 하나의 글로벌 체크포인트만 선택하면 D5 200k 성능을 보존하면서 400k 붕괴를 5%p 이내로 제한할 수 있는가?

## 고정 실행 행렬

| 항목 | 고정값 |
|---|---|
| 분류 | 실제 강화학습 연구, `SB3 DQN` |
| 알고리즘 | `D_DQN_STABLE_LR` |
| 학습률 | `0.0003` constant |
| Reward arms | `NATIVE`, `SHUFFLED` |
| Seeds | `0, 1, 2` |
| Checkpoints | `50k, 100k, 150k, 200k, 300k, 400k` |
| 신규 학습량 | 6 lineages × 400k = 2.4M RL step |
| 학습·Primary 비용 | 왕복 23bp |
| 진단 비용 | 0bp, 별도 표시 |
| 데이터 | 기존 573개 `TRAIN_ONLY` episode |
| Reused validation / Fresh OOS | `NOT_RUN_NO_READ` / `NOT_RUN_NO_READ` |

## 선택 규칙

체크포인트는 seed별 또는 arm별로 따로 선택하지 않는다. Native 3개 seed의 23bp reward-ratio 중앙값이 가장 높은 step을 선택하고, 동률이면 accuracy 중앙값, 다시 동률이면 더 이른 step을 사용한다. 선택된 하나의 step을 Native와 Shuffled 전 seed에 동일하게 적용한다. 선택 후 재학습과 gate 변경은 금지한다.

이 선택은 TRAIN_ONLY 과적합 가능성과 학습 안정성을 진단하기 위한 것이다. validation/OOS 선택이나 수익성 근거가 아니다.

## 사전등록 Gate

| Gate | 성공 기준 |
|---|---:|
| 선택 Native median accuracy | ≥ 0.7120418848 |
| 선택 Native median reward ratio | ≥ 0.8727793885 |
| 선택 Native−Shuffle reward delta | ≥ 0.20 |
| 선택→400k accuracy 악화 | ≤ 0.05 |
| 선택→400k reward-ratio 악화 | ≤ 0.05 |
| D5 seed별 accuracy·reward 보존 비율 | ≥ 2/3 |
| Invalid action | 0 |

모든 조건을 통과할 때만 `D5S_STABILITY_CONFIRMED`, 하나라도 실패하면 `D5S_STABILITY_NOT_CONFIRMED`로 기록한다. CONFIRMED여도 D6 진입 후보라는 뜻일 뿐 alpha·수익성·실거래 승인이 아니다.

## 실행·Git 계보

| 단계 | 산출물 | 커밋 경계 | 예상 시간 |
|---|---|---|---:|
| Prereg | 본 문서와 JSON 계약 | 코드 전 선행 커밋 | 완료 |
| Contract/TDD | typed contract, selection, gate tests | 구현 커밋 | 2–4시간 |
| Smoke | Native/Shuffle seed 0, 4,096 step | 승인 커밋 | 1–2시간 |
| Primary | 6개 uninterrupted lineages, 2.4M step | 실행 코드 고정 후 | 6–12시간 |
| Evidence/UI | summary, receipt, custody, 전체 페이지 | 결과 커밋 | 2–4시간 |
| Release | 연구 PR → 부모 브랜치 → master PR → tag | 리뷰 PASS 후 | 1–2시간 |

## 정지 규칙

- prereg·source custody·Smoke HMAC 중 하나라도 불일치하면 Primary를 만들지 않는다.
- 계획된 36개 outcome 또는 36개 checkpoint model 중 하나라도 없으면 `NO-GO`다.
- 실패한 seed를 제거하거나 재시도 seed로 대체하지 않는다.
- D5/D5R verdict는 변경하지 않는다.
- `ts_imb`는 RULE baseline이며 RL 성과에 합산하지 않는다.
- D5S 실패 시 D6 reused validation과 D7 Fresh OOS를 열지 않는다.

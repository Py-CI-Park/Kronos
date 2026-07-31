# Type2-D6 reused-validation 연구 계획

## 연구 질문

D5S가 TRAIN_ONLY에서 선택한 단일 100K DQN 체크포인트가 기존 validation 구간에서도 23bp 비용 후 양의 보상과 Native/Shuffle 분리를 유지하는가?

## 실행 전 봉인

| 항목 | 고정값 |
|---|---|
| 부모 릴리스 | `fork-v1.17.0-kronos-rl-d5s-stability-earlystop` |
| 원본 run | `type2-d5s-primary-20260730-001` |
| 모델 | Native/Shuffle × seed 0/1/2의 100K 모델 6개 |
| validation | 최초 128개 chronological eligible validation session |
| 정규화 | train-only normalizer 재사용, refit 금지 |
| 비용 | 왕복 23bp, 0bp는 진단 전용 |
| 학습 | 금지. 저장 모델 로드와 deterministic 평가만 허용 |
| 선택 | seed별·arm별 재선택 금지 |
| 임계값 수정 | validation read 후 수정 금지 |
| Fresh OOS | `NOT_RUN_NO_READ` 유지 |

## 성공 게이트

모든 조건을 동시에 만족해야 `D6_REUSED_VALIDATION_CONFIRMED`다.

1. Native median accuracy ≥ 0.20.
2. Native median 23bp reward ratio ≥ 0.
3. Native median 23bp total reward ≥ 0.
4. Native median reward ratio − Shuffled median reward ratio ≥ 0.10.
5. Native seed 중 accuracy와 total reward를 함께 통과한 비율 ≥ 2/3.
6. Native median cumulative-reward maximum drawdown ≤ 0.25.
7. 모든 평가의 invalid action 수 = 0.

하나라도 실패하면 판정은 `D6_REUSED_VALIDATION_NOT_CONFIRMED`다. 결과가 좋아도 Fresh OOS, 수익성, promotion, paper-forward, broker 또는 live 승인은 발생하지 않는다.

## 구현·실행 순서

1. 이 prereg와 계획 문서를 별도 커밋으로 고정한다.
2. synthetic fixture에서 validation split만 읽는 loader와 exact 6-unit gate를 TDD로 구현한다.
3. source SHA와 모델 SHA를 fail-closed로 검증한다.
4. 실제 reused validation은 한 번만 materialize하고 평가한다.
5. summary, outcome, terminal receipt, custody, 결과 문서를 원자적으로 발행한다.
6. API와 전체 페이지에 D6 상태를 연결하되 Fresh OOS 봉인을 유지한다.

# Kronos RL Discovery Type2-D5R 연구 계획

## 목적

D5는 실제 DQN 10개와 2,000,000 RL step을 완료했지만 exact-action gate를 통과하지 못했다. D5R은 이 실패를 숨기거나 gate를 소급 변경하지 않고 다음 두 질문으로 분해한다.

1. exact-action 불일치가 실제 reward regret도 큰 실패인가?
2. regret가 크다면 동일 seed/config의 0→400k→800k deterministic replay가 성능을 개선하는가?

## 단계와 정지 규칙

| 단계 | 입력 | 실행 | 진입/정지 기준 | 예상 시간 |
|---|---|---|---|---:|
| D5R-1 | D5 10개 outcome, 573 TRAIN_ONLY episodes | 5/10/25bp near-optimal accuracy와 regret 계산 | Native median 25bp accuracy가 0.85 미만이거나 median regret가 25bp 초과면 D5R-2 진입 | 30–60분 |
| D5R-2 Smoke | D5 custody-bound 비교 기준 | Native/Shuffled seed 0을 0부터 2,048 step deterministic replay | custody·비용·terminal receipt가 모두 유효할 때만 Primary 승인 | 30–90분 |
| D5R-2 Primary | 6개 신규 uninterrupted lineage | seeds 0–2를 0→400k→800k 연속 학습 | 등록된 accuracy/reward lift와 control delta를 동시에 평가 | 8–16시간 |
| D6 | 별도 승인 전 금지 | reused validation | D5R-2 gate 통과 시에만 새 prereg | 미정 |

## 해석 원칙

- D5R-1 near-optimal 지표는 D5의 `NO-GO`를 뒤집지 않는다. 실패 원인을 분해하는 진단 지표다.
- D5R-2는 D5 200k를 비교 기준으로만 사용하고, 동일 seed/config를 0부터 재현하는 실제 강화학습이다. 400k와 800k checkpoint를 동일 uninterrupted lineage에서 비교한다.
- `ts_imb`는 계속 RULE baseline이며 RL로 부르지 않는다.
- no-trade, oracle ceiling, Native, Shuffled를 모두 노출한다.
- reused validation과 Fresh OOS는 전 단계에서 `NOT_RUN_NO_READ`로 봉인한다.
- 성공해도 수익성·실거래·broker readiness를 주장하지 않는다.

## 산출물

| 산출물 | 위치 |
|---|---|
| 사전등록 | `docs/kronos_rl_discovery_type2_d5r_prereg_2026-07-30.json` |
| D5R-1 진단 | `webui/rl_runs/rl_discovery/type2-d5r-diagnostic-*/` |
| D5R-2 Smoke/Primary | `webui/rl_runs/rl_discovery/type2-d5r-*/` |
| 최종 결과 | `docs/kronos_rl_discovery_type2_d5r_result_2026-07-30.md` |

## D5R-2 실행 보정

D5 `model.zip`에는 replay buffer가 포함되지 않으므로 weight-only load를 uninterrupted continuation으로 부르지 않는다. D5R-2는 동일 seed/config를 0부터 결정적으로 재현하고, 한 학습 프로세스 안에서 400k checkpoint를 저장한 뒤 replay buffer를 유지한 채 800k까지 학습한다. 보정 계약은 `docs/kronos_rl_discovery_type2_d5r_amendment_2026-07-30.json`에 고정한다.

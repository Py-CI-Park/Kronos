# Type2-D4 Algorithm / Objective

## 판정

`D4_ALGORITHM_OBJECTIVE_CONFIRMED`

- 동일 실제 일봉 train-only 128 sessions
- supervised/PPO/DQN/Aux-PPO × native/shuffled × 3 seeds
- 실제 모델 24/24
- supervised ceiling: 1.000 — 비-RL 진단
- DQN native: 0.988, 23bp: 0.985
- DQN shuffled fit: 0.991, shuffled→native: -0.111
- 확인된 실제 RL arm: `C_DQN_DISCRETE`
- Fresh OOS: `NOT_RUN_NO_READ`
- 수익성·승격·실거래: 차단

## 해석

표현 용량은 충분했고 PPO 목적함수·온폴리시 최적화 경로가 주요 병목이었다. DQN의 성공은 train-only 과적합 확인이며 일반화 성공이 아니다. 다음 D5에서 전체 train과 5+5 seeds, 23bp primary를 고정한다.

## 권위 문서

- 결과: `docs/kronos_rl_discovery_type2_d4_result_2026-07-29.md`
- 사전등록: `docs/kronos_rl_discovery_type2_d4_prereg_2026-07-29.json`
- 계획·amendment: `docs/kronos_rl_discovery_type2_d4_plan_2026-07-29.md`
- custody: `docs/evidence/type2-d4-primary-20260729-v2.custody.json`

# Type2-D2 실제 일봉 규모 연구

## 판정

`D2_PARTIAL_CAPACITY_CONFIRMED`

- 실제 train-only 일봉 MaskablePPO Primary 모델: 24/24
- 규모: 1/8/32/128 episodes
- 과적합 확인 최대 규모: 8 episodes
- 128 episode native−shuffle 원래 수익률 보상비 차이: +0.535502
- 0bp 학습, 23bp 진단
- Fresh OOS: `NOT_RUN_NO_READ`
- 수익성·승격·라이브: 차단

## 권위 문서

- 결과: `docs/kronos_rl_discovery_type2_d2_result_2026-07-28.md`
- 사전등록: `docs/kronos_rl_discovery_type2_d2_prereg_2026-07-28.json`
- custody: `docs/evidence/type2-d2-primary-20260728-v1.custody.json`

다음은 D3 representation/action ablation이다. 128 episode에서 top-1/top-5 표현과
1×/4× 학습예산을 분리하며 Fresh OOS는 열지 않는다.

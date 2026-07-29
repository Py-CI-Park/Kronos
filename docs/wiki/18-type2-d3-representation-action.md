# Type2-D3 Representation / Action

## 판정

`D3_REPRESENTATION_ACTION_NOT_CONFIRMED`

- 실제 일봉 MaskablePPO Primary: 24/24 모델
- 4 policy representations × native/shuffled × 3 seeds
- 최선 arm: `D_TOP5_CONTEXT_4X`
- 최선 native reward ratio: 0.533
- 4× budget lift: +0.068
- native−shuffle separation: +0.760
- 0.90 게이트 통과 arm: 0/4
- Fresh OOS: `NOT_RUN_NO_READ`
- 수익성·승격·실거래: 차단

## 권위 문서

후속 보안 검토에서 Smoke→Primary 승인은 운영자 HMAC과 동일 held-handle artifact snapshot을 필수화했다. 기존 D3 Primary는 이 변경 전 실행된 역사적 증거이며 HMAC 적용을 소급 주장하지 않는다. 새 실행은 `KRONOS_D3_APPROVAL_KEY_HEX` 없이는 시작할 수 없다.

- 결과: `docs/kronos_rl_discovery_type2_d3_result_2026-07-29.md`
- 사전등록: `docs/kronos_rl_discovery_type2_d3_prereg_2026-07-29.json`
- custody: `docs/evidence/type2-d3-primary-20260729-v1.custody.json`

다음 D4는 비용 사다리를 먼저 확장하지 않는다. supervised ceiling은 진단 기준으로만 사용하고, PPO와 discrete Q 또는 auxiliary objective를 동일 train-only/shuffle 조건에서 비교한다.

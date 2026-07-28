# Type2-D1 Action / Reward Reviewed Evidence

> Final review: 2026-07-28 KST
> Authority: `REVIEWED_SNAPSHOT`

## 판정

| 항목 | 값 |
|---|---|
| Run | `type2-d1-primary-v3-20260728` |
| Matrix | 3 arms × 3 seeds = 9/9 |
| Status | `PRIMARY_COMPLETE` |
| Verdict | `D1_ACTION_REWARD_CONFIRMED` |
| 범위 | 합성 `TRAIN_ONLY / RESEARCH_ONLY` |
| Primary cost | 23bp round trip (0.23%) |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Promotion / profitability / live | blocked / blocked / blocked |

2-action 정책은 native와 diagnostic 신호를 세 seed에서 학습했고, shuffled
대조군은 세 seed 모두 실패했다. 이는 D1의 행동·보상 메커니즘만 확인한다.
시장 일반화와 수익성은 확인하지 않았다.

## 결과 요약

| Arm | Ratio | Accuracy | Dominant action |
|---|---:|---:|---:|
| A binary native | 1.000 | 1.000 | 0.750 |
| B binary diagnostic | 1.000 | 1.000 | 0.750 |
| C binary shuffled | 0.000 | 0.250 | 1.000 |

권위 경로는 `docs/kronos_rl_discovery_type2_d1_result_2026-07-28.md`와
`docs/evidence/type2-d1-primary-v3-20260728.custody.json`이다. Evidence manifest는
`ef4403f2e7926008e2e58f1c83d04ccb5191ff43fba245479a80cbae4c117ede`이며 51개
artifact, 1,796,873 bytes를 producer commit `24e79cd`에 연결한다.

다음 연구는 D2 episode scale(1/8/32/128)이며 별도 사전등록이 필요하다.
D6 reused validation 이전에는 D7 Fresh OOS를 열 수 없다.

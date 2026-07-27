# Kronos Type2-D0 강화학습 Discovery Smoke 실행 결과

**실행일:** 2026-07-26 KST  
**기준 커밋:** `73c4c1bd4885ae5cfb33595d3973ce289cd4daf9`  
**브랜치:** `research/type1-closing-rl-v1`  
**실험:** `type2-d0-ppo-attribution-v0`  
**프로필:** `SMOKE`  
**최종 아티팩트:** `webui/rl_runs/rl_discovery/type2-d0-smoke-20260726T214113+0900`  
**사전등록 SHA-256:** `2c3bced20fc6b718f7c2f37963501e962b2198b8b620fd6a1e4a91e20ff0ce4d`

## 1. 결론

Type2-D0 네 arm의 실제 학습·평가·대시보드 아티팩트 생성 경로가 끝까지 실행됐다. 판정은 `SMOKE_COMPLETE / SMOKE_INCOMPLETE`다. Smoke는 실행 가능성과 배선만 확인하며 PPO 귀속성, 일반화, 수익성, 실거래 준비도를 판정하지 않는다.

PPO-only와 shuffled-reward PPO는 모두 oracle reward ratio `-0.347457627119`, exact basket accuracy `0.25`였다. 256 step에서는 native reward와 shuffled reward의 학습 분리가 관찰되지 않았다. BC→PPO와 BC-only는 reward ratio `0.0`, initial-decision dominant action rate `1.0`으로 행동 집중/붕괴 신호가 있었다. 모든 arm의 invalid action, block, no-fill은 0이었다.

## 2. 실행 결과

| Arm | 구성 | PPO step | Oracle reward ratio | Exact basket accuracy | Dominant initial action | Invalid / Block / No-fill | Smoke 해석 |
|---|---|---:|---:|---:|---:|---:|---|
| A | PPO-only | 256 | -0.347457627119 | 25.0% | 62.5% | 0 / 0 / 0 | 짧은 budget에서 mechanics 미확인 |
| B | Oracle BC → PPO | 256 | 0.0 | 25.0% | 100.0% | 0 / 0 / 0 | 행동 집중/붕괴 신호 |
| C | Oracle BC-only | 0 | 0.0 | 25.0% | 100.0% | 0 / 0 / 0 | 행동 집중/붕괴 신호 |
| D | Shuffled-reward PPO | 256 | -0.347457627119 | 25.0% | 62.5% | 0 / 0 / 0 | A와 동일, negative control 분리 없음 |

## 3. 판정 경계

| 항목 | 상태 | 의미 |
|---|---|---|
| Type1 결과 | `COMPLETE / NO_GO` | 기존 연구 판정 변경 없음 |
| Type2-D0 smoke | `SMOKE_COMPLETE / SMOKE_INCOMPLETE` | 실행 배선 완료, primary 판정 아님 |
| Promotion | `false` | 모델 승격 금지 |
| Profitability claim | `false` | 수익성 주장 금지 |
| Fresh OOS | `NOT_RUN_NO_READ` | 미실행·봉인 유지 |
| Live/broker | `NOT_ALLOWED` | 실거래 준비도 증거 아님 |

## 4. 구현 범위

| 영역 | 구현 내용 | 상태 |
|---|---|---|
| 사전등록 | executable JSON, 고정 arm/seed/budget/claims boundary | 완료 |
| 실행기 | PPO-only, BC→PPO, BC-only, shuffled PPO | 완료 |
| 게이트 | smoke/primary 분리, 승격·수익성 차단 | 완료 |
| 아티팩트 | summary, outcomes, terminal receipt | 완료 |
| 기존 대시보드 연동 | `sb3_smoke` scanner를 통한 read-only 노출 | 완료 |
| V6 UX/UI | Discovery Lab step과 전체 evidence page | 완료 |
| 반응형 | 1440px 및 390px 실제 브라우저 확인 | 완료 |
| Fresh OOS | 어떠한 loader/read 경로도 추가하지 않음 | 유지 |

## 5. UX/UI 검증

V6 RL workspace의 첫 단계로 `RL 발견 실험실`을 추가했다. 페이지는 safety strip, D0~D6 사다리, terminal verdict, prereg lineage, 네 arm 비교, reward/accuracy/collapse/validity 지표, smoke 해석을 제공한다.

실제 Chromium 검증 결과는 다음과 같다.

| Viewport | 결과 |
|---|---|
| 1440×1000 | 제목, verdict, safety 4개, arm 4개 렌더링; page error 0 |
| 390×844 | V6 main 326px, Discovery page 306px; `scrollWidth=innerWidth=390`; 수평 overflow 없음 |

검증 과정에서 V6의 일반 `.sidebar` 클래스가 기존 전역 모바일 sidebar CSS와 충돌해 본문이 64px로 축소되는 문제를 발견했다. 이를 `v6-sidebar`와 `v6-main`으로 격리했고 회귀 테스트를 추가했다.

## 6. 검증 기록

| 검증 | 결과 |
|---|---|
| Discovery Python unit tests | 8 passed |
| V6 focused Bun tests | 7 passed |
| Ruff | 통과 |
| Basedpyright | 0 errors, 0 warnings |
| Svelte check | 0 errors, 0 warnings |
| Vite production build | 성공, 949 modules transformed |
| Actual Type2-D0 smoke CLI | exit 0, terminal artifact 생성 |
| Chromium desktop/mobile QA | 통과 |

## 7. 남은 연구 단계

다음 실행은 `PRIMARY`로 seeds 0/1/2, PPO budget 104,000 step을 네 arm에 동일하게 적용하는 것이다. Primary 전에는 smoke 결과를 근거로 설정을 변경하지 않는다. Primary에서 A가 모든 seed에서 oracle reward ratio 0.90 이상이고 shuffled control을 명확히 상회해야만 `PPO_ONLY_OVERFIT_CONFIRMED`가 가능하다. 이 상태도 수익성이나 일반화 GO가 아니다.

Primary 이후에만 train-only 역사 데이터 D1(1 episode) → D2(8/32/128) → D3(reward/action ablation) → D4(cost ladder) → D5(full train) → D6(reused validation) 순으로 진행한다. Fresh OOS는 별도 명시 승인 전까지 계속 봉인한다.

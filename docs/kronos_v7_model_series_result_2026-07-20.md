# V7 모델 시리즈 종합 연구 결과 (M1·M2·M3·M4) — 2026-07-20

> 문서 ID: `KRONOS-V7-MODEL-SERIES-RESULT-2026-07-20`
> 데이터: `v6_dataset_full_001` 786,872행 (SHA `ae44c805…`), exact 15:20 proxy 라벨, ₩60M/10슬롯 회계, 1차 비용 0.23%
> **종합 판정: 3개 모델 모두 GO 후보 없음** — untouched test 전부 `NOT_RUN` 유지
> 본 문서는 수익성·승격·실거래·paper-forward 주장을 하지 않는다. 모든 run의 16절 HTML 보고서가 대시보드 보고서 STEP에서 열람 가능하다.

## 모델별 판정 요약

| 모델 | 사전등록 | smoke | full 판정 | qualifying | 대조군 |
|---|---|---|---|---|---|
| **M1** tabular-Q v2 (seed 5) | `KRONOS-V7-PREREG-M1-2026-07-20` | `INCONCLUSIVE`(1/1) | **`INCONCLUSIVE`** (1/5, seed0 +7.10%) | 0번 | 5/5 통과 |
| **M2** SB3 PPO (seed 3) | `KRONOS-V7-PREREG-M2-2026-07-20` | `INCONCLUSIVE`(1/1) | **`NO_GO`** (0/3) | 없음 | 3/3 통과 |
| **M3** LinUCB (seed 3) | `KRONOS-V7-PREREG-M3-2026-07-20` | `NO_GO`(대조군 1건 발동) | **`INCONCLUSIVE`** (1/3, seed2 +8.91%) | 2번 | 3/3 통과 |
| **M4** 필터 게이트 결합 | 등록 안 함 | — | **`NOT_RUN_DEFERRED`** | — | — |

## full run 상세 @0.23% (validation)

### M1 tabular-Q v2 — `train_20260720T070920Z` (보고서 SHA `bf04fb81…`)
seed0 ₩64.26M(+7.10%) / seed1 ₩54.96M(−8.40%) / seed2·3 ₩59.44M(−0.93%, 동일 정책 수렴) / seed4 ₩60.0M(무거래 수렴). 탐색 경로 민감성 지속.

### M2 PPO — `train_20260720T080217Z` (보고서 SHA `49fd6f8d…`)
seed0 ₩57.60M(−4.00%) / seed1 ₩41.76M(−30.41%) / seed2 ₩58.43M(−2.62%). 어느 seed도 no-trade 미달 → 다수결 이전에 기준 자체 미충족 `NO_GO`.

### M3 LinUCB — `train_20260720T072529Z` (보고서 SHA `bdf98254…`)
seed0 ₩50.79M(−15.35%) / seed1 ₩58.74M(−2.09%) / seed2 ₩65.35M(+8.91%). **해석 가능 계수(전 seed 일관)**: `ret_5d_prev` 음(−) — 단기 역추세 방향, `inst_netbuy_norm_5` 양(+) — 기관 순매수 우호. 방향 신호는 안정적이나 크기가 seed 경로에 따라 손익을 가르지 못함.

### 기준선 (공통)
no_trade ₩60.0M · rule_topk_ret5 ₩37.4M · rule_topk_low_vol ₩31.7M · rule_topk_inst ₩37.8M · random_topk ₩30.1M — **RULE/random 기준선 전부 대폭 손실 구간**으로, "기준선 상회"는 낮은 문턱이며 실질 문턱은 no-trade였음.

## v2 음성 대조군 설계 검증 (연구 방법 결론)

- exposure-matched 대조군은 full run 11/11 seed에서 허위 발동 없이 통과 — v1의 "시장 표류로 인한 셔플 대조군 오발동" 결함이 교정됨.
- M3 smoke에서 1건 발동(`NO_GO`)은 소표본(50종목)에서 2σ 초과가 가능함을 보여주는 정상 작동 — 원문 그대로 기록.

## M4 결합 게이트 — NOT_RUN_DEFERRED 근거

M4는 "최선 정책 + 거래품질 필터" 결합 변형이다. M1~M3에 GO 후보가 없어 "최선 정책"의 선택 자체가 **사후 선택(post-hoc)** 이 된다. 사전등록 원칙(사후 재조정 금지)에 따라 GO 후보가 나오는 시점의 새 사전등록으로 이연한다.

## 후속 (새 사전등록으로만)

1. seed 간 정책 분산 축소가 3개 모델 공통 병목 — 앙상블/평균화 정책(seed-ensemble)을 다음 버전 가설로 등록 가치.
2. M3의 일관된 계수 방향(역추세+기관수급)은 RULE 기준선 후보로 승격해 검증 가능.
3. KOSPI/KOSDAQ 지수 절은 전 보고서에 `PRESENT`로 포함됨 — 시장 대비 서술은 관측 전용.

## 변경 히스토리

| 날짜 | 변경 | 작성자 |
|---|---|---|
| 2026-07-20 | 최초 기록 — M1/M2/M3 full 완주, M4 이연 | GJC |

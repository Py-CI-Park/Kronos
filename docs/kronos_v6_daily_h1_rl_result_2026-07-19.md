# Kronos V6 일봉 종가매매 H1 강화학습 결과 보고서 — 2026-07-19

> 문서 ID: `KRONOS-V6-DAILY-H1-RL-RESULT-2026-07-19`
> 실행 기간: `2026-07-19 KST` (smoke 및 full run 동일 일자)
> 데이터 기간: `2018-01-01 ~ 2026-06-12` (train ≤2023-12-31 / val 2024-01-01~2025-06-30 / test 2025-07-01~2026-06-12)
> 상태: `COMPLETE / RESULT_RECORDED`
> 모델 판정: **`INCONCLUSIVE` (full) / `NO_GO` (smoke)** — 승격 불가, untouched test 미접근
> 연구 단계: smoke(50종목·seed 0) + full(500종목·seeds 0,1,2)
> 브랜치·commit: `feature/dashboard-v6-rl-platform`, 트레이너 `e5758a7`, dataset 스트리밍 수정 `70ee784`

## 목차

1. [연구 목적](#1-연구-목적)
2. [사전등록과 가설](#2-사전등록과-가설)
3. [데이터와 계보](#3-데이터와-계보)
4. [환경](#4-환경)
5. [자본·slot·비용](#5-자본slot비용)
6. [알고리즘과 실행](#6-알고리즘과-실행)
7. [비교 기준](#7-비교-기준)
8. [결과](#8-결과)
9. [원인 분석](#9-원인-분석)
10. [결론과 판정](#10-결론과-판정)
11. [한계와 blocker](#11-한계와-blocker)
12. [검증](#12-검증)
13. [Artifact](#13-artifact)
14. [관련 문서](#14-관련-문서)
15. [관련 commit·branch·tag](#15-관련-commitbranchtag)
16. [변경 히스토리](#16-변경-히스토리)

## 1. 연구 목적

- 질문: 일봉 DB의 D-1 이전 가격·거래량·수급 feature로 학습한 제약형 10-slot 종가매매 정책이 0.23% 왕복 비용에서 no-trade와 RULE 기준선을 validation에서 능가하는가.
- RL(강화학습형 정책 학습)이 필요한 이유: slot 제약·비용·보유 상태가 있는 순차 선택 문제이기 때문.
- 성공해도 주장하지 않는 것: 실거래 수익성, live/broker/order 준비, paper-forward, 모델 승격, `GO`.

## 2. 사전등록과 가설

- prereg: `docs/kronos_v6_prereg_h1_2026-07-19.json` (`e5c8ae0`에서 동결)
- 주가설: 정책 val 경제 NAV > no-trade AND ≥ best RULE baseline @0.23%, 3-seed 중 ≥2 일관.
- negative control: shuffled-label 정책이 no-trade를 넘으면 신호 무효.
- 판정 규칙: `GO_CANDIDATE_VALIDATION_ONLY / NO_GO / INCONCLUSIVE` — 1-of-3 seed 동의는 INCONCLUSIVE.
- OOS 정책: test split은 GO 후보일 때만 동결 checkpoint로 1회 접근.

## 3. 데이터와 계보

| 항목 | 값 |
|---|---|
| feature 권위 | `_database/Stock_Database_ohlcv_1day.db` (4,727테이블), **체결일 이전 세션만** |
| 체결·라벨 권위 | `_database/Stock_Database_ohlcv_5min.db` exact 15:20 bar만, fallback 없음 |
| universe | `docs/kronos_v6_universe_manifest_2026-07-19.json` 상위 500 (SHA-256 `8695ca76…`), instrument_type UNVERIFIED 캐비앗 유지 |
| dataset 계약 | `kronos_v6_joined_dataset.v1` (`stom_rl/daily_v6_dataset.py`) |
| smoke dataset | `v6_dataset_smoke_001`, 82,319행, SHA `02e7be1a…` |
| full dataset | `v6_dataset_full_001`, **786,872행** (train 490,435 / val 175,870 / test 115,567 / embargo 5,000), SHA `ae44c805…` |
| purge/embargo | 최대 horizon exit이 split 경계를 넘는 행은 `embargo_dropped` |
| price basis | 일봉 DB `UNKNOWN_CONFIRMED` — feature 입력만 허용, 수익률 증거 사용 금지. 15:20은 공식 종가 아님(`official_close=false`) |

## 4. 환경

- observation: `ret_1d/5d/20d_prev, vol_z_20, foreign_ratio_prev, foreign_ratio_delta_5, inst_netbuy_norm_5` (train 통계로만 bucket 동결)
- action: `hold_cash, enter` (advantage 상위 최대 10종목)
- reward: H1 exact 15:20 수익률 − 0.23% (Q-update 기준)
- invalid/중복 slot: 구조적으로 금지
- label 누락(`missing_exit`)은 학습·평가에서 제외되고 개수만 기록

## 5. 자본·slot·비용

- 초기 자본 60,000,000원 / slot 10개 × 5,000,000원 / 최대 투자 50,000,000원 / reserve 10,000,000원
- 비용: primary `0.23%`, control `0.00%`, stress `0.46%`
- 체결·슬리피지: 15:20 bar close proxy 단일가 가정(슬리피지 미모델링 — 한계 11장)

## 6. 알고리즘과 실행

- tabular Q (contextual-bandit 갱신), α=0.1, ε=0.1→0.98/ep 감쇠
- seeds {0,1,2}, 최대 300 episodes, checkpoint = rolling-3 val NAV 최대, 조기중단 = rolling-3 slope 3연속 음수
- 실행 명령(사전등록 허용 목록 그대로):
  - `py -3.11 -m stom_rl.daily_v6_train --dataset v6_dataset_smoke_001 --seeds 0 --smoke`
  - `py -3.11 -m stom_rl.daily_v6_train --dataset v6_dataset_full_001 --seeds 0,1,2`

## 7. 비교 기준

no_trade(60M 고정), rule_topk_ret5(모멘텀 RULE), random_topk(무작위 RULE control), shuffled_label_control(negative control), 비용 3종.

## 8. 결과

### 8.1 Smoke (50종목, seed 0, 12 episodes)

| 항목 | 값 |
|---|---:|
| val NAV @0.23% | ₩63,091,022 (+5.15%) |
| MDD / trades | 7.78% / 698 |
| no_trade / RULE / random | ₩60.0M / ₩59.4M / ₩36.1M |
| **판정** | **`NO_GO`** — shuffled-label 대조군이 no-trade 초과(신호 무효화 규칙 발동) |

### 8.2 Full (500종목, seeds 0,1,2)

run: `train_20260719T111201Z` (dataset `v6_dataset_full_001`)

| seed | episodes(best) | val NAV @0.23% | 수익률 | MDD | trades | NAV @0.00% | NAV @0.46% |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 21 (18) | ₩64,257,140 | **+7.10%** | 12.40% | 977 | ₩75,492,640 | ₩53,021,640 |
| 1 | 38 (35) | ₩54,960,959 | **−8.40%** | 11.29% | 607 | ₩61,941,459 | ₩47,980,459 |
| 2 | 10 (6) | ₩59,443,163 | **−0.93%** | 6.30% | 613 | ₩66,492,663 | ₩52,393,663 |

기준선(val): no_trade ₩60.0M · random_topk ₩58.5M · **rule_topk_ret5 ₩37.4M(−37.6%)**

| 판정 요소 | 결과 |
|---|---|
| validation 기준 충족 seed | **1/3** (seed 0만) |
| untouched test | **NOT_RUN** (GO 후보 아님 → 접근 안 함) |
| six false locks | 전부 false 유지 |
| **최종 판정** | **`INCONCLUSIVE`** — "only one seed satisfies validation criterion" |

## 9. 원인 분석

1. **seed 간 분산이 지배적**: +7.1% ~ −8.4% — 학습된 정책이 안정적 신호가 아니라 탐색 경로에 민감. tabular bucket state(4 feature 조합)의 표현력 한계와 val 구간(2024-01~2025-06)의 국면 의존성이 결합된 결과로 해석.
2. **RULE 모멘텀 붕괴**: ret_5d 상위 매수 RULE이 val에서 −37.6% — 해당 구간에서 단기 모멘텀 추종이 강한 역효과. 정책이 이 RULE보다 나은 것은 낮은 기준 대비 우위일 뿐 절대 우위 증거가 아님.
3. **smoke NO_GO vs full INCONCLUSIVE**: smoke(50종목)에서는 shuffled 대조군이 no-trade를 초과(전반 상승 편향 구간에서 임의 매수 우위). full에서는 대조군 규칙이 아닌 seed 불일치가 판정 근거. 두 판정 모두 사전등록 규칙의 서로 다른 방어선이 작동한 것.
4. **회계·인과 방어는 유효**: 비용 순서 NAV(0%)≥NAV(0.23%)≥NAV(0.46%)가 전 seed에서 성립, feature poison 테스트·slot/budget 상한 테스트 통과 — 실패는 파이프라인이 아니라 신호 부재/불안정에 있음.

## 10. 결론과 판정

- **판정: `INCONCLUSIVE` (full run), `NO_GO` (smoke run)**
- 승격 가능 여부: 불가. `promotion/model_build/paper_forward/live/profit/go` locks 전부 false 유지.
- 이 결과는 "일봉 수급·가격 feature + tabular Q + H1 종가매매" 조합이 현재 사전등록 조건에서 **판정 가능한 완결 증거를 생산했으나 신호를 입증하지 못했음**을 의미한다. 후속 가설(state 표현 강화, 필터 게이트 결합, horizon 변형)은 **새 사전등록 버전**으로만 진행한다.

## 11. 한계와 blocker

- 슬리피지·호가·체결 잔량 미모델링(15:20 bar close 단일가 가정).
- 일봉 DB price basis 미검증(UNKNOWN_CONFIRMED) — feature 노이즈 가능.
- universe instrument-type 미검증(ETF/ETN 혼입 가능) — D1 게이트 과제.
- KOSPI/KOSDAQ 오프라인 지수 artifact 부재(`BLOCKED_INDEX_SERIES_SOURCE`, KRX 자격증명 필요) — 시장 대비 상대 성과 미평가.
- 수급 컬럼 point-in-time 공시 지연 미감사.
- H3/H5 변형 검증 `NOT_RUN`.

## 12. 검증

```text
py -3.11 -m pytest tests/test_v6_daily_dataset.py tests/test_v6_daily_train.py -q -W error   # 6 passed
스트리밍 재작성 등가성: smoke_002 SHA == smoke_001 SHA (02e7be1a…)
full run manifest: verdict INCONCLUSIVE, test NOT_RUN, locks 전부 false
대시보드: 평가/비교 페이지가 manifest 그대로 렌더링(NO_GO/INCONCLUSIVE 완화 없음)
```

## 13. Artifact

| 파일 | 역할 | SHA-256 |
|---|---|---|
| `docs/kronos_v6_universe_manifest_2026-07-19.json` | universe 동결 | `8695ca76f8944a55055c9dcbbeea39f00214d8dbd11e56235d06fde5d41a6f95` |
| `docs/kronos_v6_prereg_h1_2026-07-19.json` | 사전등록 동결 | repo 파일 참조 |
| `webui/rl_runs/v6_daily_h1/v6_dataset_smoke_001/dataset.csv` | smoke dataset | `02e7be1a03eacf4e28fdbdf13d2a7775e886c89771bdc53984a1235e2b6b763f` |
| `webui/rl_runs/v6_daily_h1/v6_dataset_full_001/dataset.csv` | full dataset | `ae44c8056be90124c715f9accff51feabe767291ab65e8a5654e67d6ccf849b5` |
| `webui/rl_runs/v6_daily_h1/v6_dataset_smoke_001/train_20260719T093304Z/` | smoke run(NO_GO) | run_manifest 참조 |
| `webui/rl_runs/v6_daily_h1/v6_dataset_full_001/train_20260719T111201Z/` | full run(INCONCLUSIVE) | run_manifest 참조 |

## 14. 관련 문서

- `docs/kronos_v6_goal_review_and_plan_2026-07-19.md` (3-Track 계획)
- `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md`
- `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` (회계·15:20 고정값)
- `docs/wiki/13-research-ledger.md`

## 15. 관련 commit·branch·tag

- branch `feature/dashboard-v6-rl-platform`
- `e89e52b` dataset 계약 · `e5c8ae0` prereg 동결 · `e5758a7` 트레이너 · `70ee784` 스트리밍/O(n²) 수정
- tag 생성·push·merge: 수행하지 않음

## 16. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-19 | smoke(NO_GO)와 full(INCONCLUSIVE) 결과 최초 기록. untouched test 미접근, locks 전부 false 유지. | GJC | 본 문서 커밋 |

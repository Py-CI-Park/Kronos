# Kronos Dashboard V5.1 구현·릴리스 결과 보고서 — 2026-07-18

> 문서 ID: `KRONOS-DASHBOARD-V51-IMPLEMENTATION-RESULT-2026-07-18`  
> 작성일: `2026-07-18 KST`  
> 실행 기간: `2026-07-18 05:44–검증 종료 KST`, 최초 구현·보강·최종 브라우저 재검증 포함
> 상태: `COMPLETE / IMPLEMENTED_RESEARCH_FOUNDATION`  
> 모델·실거래 판정: `NOT_RUN / NO-GO 유지 / LIVE_READY 아님 / PROFIT_CLAIM 없음`  
> 범위: V5.1 연구 기반, 대시보드 정보구조, 15:20 인과 source/panel, 6,000만원 10-slot 회계, H1/H3/H5 freeze, PyKRX-only offline custody, read-only API/report viewer  
> 브랜치: `feature/dashboard-v5-learning-evidence`  
> 기준 commit: `4c8ba1f`  
> 최종 브라우저 검증 대상 HEAD: `6a8fd02ccdbd4d7cb28a4f283a865ad0f91454b3`
> 기본 UI: `V3 유지`  
> tag/push/merge/release-default: 수행하지 않음  
> 대체 문서: 없음. 이전 `docs/kronos_dashboard_v5_development_result_2026-07-16.md`는 보존하고 본 문서는 V5.1 증분 결과만 기록한다.

## 목차

1. [요약 판정](#1-요약-판정)
2. [원래 의도와 이번에 고정한 결정](#2-원래-의도와-이번에-고정한-결정)
3. [구현 결과](#3-구현-결과)
4. [점수 전후 비교](#4-점수-전후-비교)
5. [검증 명령과 결과](#5-검증-명령과-결과)
6. [브라우저 증거와 사용자 확인 경로](#6-브라우저-증거와-사용자-확인-경로)
7. [한계·blocker·금지 주장](#7-한계blocker금지-주장)
8. [Rollback과 V3 기본 정책](#8-rollback과-v3-기본-정책)
9. [관련 문서·artifact](#9-관련-문서artifact)
10. [관련 commit](#10-관련-commit)
11. [변경 히스토리](#11-변경-히스토리)

## 1. 요약 판정

V5.1은 **일봉 종가매매 RL 연구를 실행하기 전 필요한 연구 기반**을 구현했다. 결과는 `IMPLEMENTED_RESEARCH_FOUNDATION`이다. 이것은 수익성, 모델 승격, paper-forward, live broker 주문, 기본 UI 전환 또는 태그 릴리스를 뜻하지 않는다.

| 축 | 이전 | 이번 결과 | 판정 |
|---|---:|---:|---|
| 대시보드·증거 엔지니어링 | V5 문서 기준 `98/100` | V5.1 `99/100` | 구현 품질 거의 완료. 단, monolithic full pytest가 한 프로세스로 완료되지 않아 1점 보류 |
| 일봉 종가매매 RL 연구 기반 | 회고 rubric `29/100` | 회고 rubric `71/100` | 연구 실행 전 기반 강화. 모델 학습·fresh OOS 결과는 `0`점 |
| 실거래·수익 준비도 | `0/100` | `0/100` | `NOT_RUN / NO-GO / NO_CLAIM` |

중요한 경계:

- V3는 계속 기본 UI다.
- V5.1은 직접 `?ui=v5` 또는 관련 route로 확인하는 연구용 화면이다.
- 이전 `NO-GO`, `NOT_RUN`, `INCONCLUSIVE`, RULE baseline 판정은 완화하지 않는다.
- `ts_imb` 등 기존 우상향 RULE 근거는 RL 결과가 아니다.
- 새 PPO 학습, fresh OOS, paper-forward, live trading은 실행하지 않았다.
- 비용 표기는 사용자 문서와 화면에서 `%`로 유지한다. 예: `23bp = 0.23%`, `46bp = 0.46%`.

## 2. 원래 의도와 이번에 고정한 결정

### 2.1 원래 의도

`docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md`의 목적은 다음이었다.

1. D일 15:20 시점의 정보만 사용하는 일봉 종가매매 RL 연구 환경을 만든다.
2. 6,000만원 연구 계좌와 10개 slot 회계를 모든 계층에서 일치시킨다.
3. H1/H3/H5 보유기간 비교를 사전에 고정한다.
4. KOSPI·KOSDAQ·RL 경제 NAV를 동일 기간·동일 축에서 비교할 수 있게 한다.
5. 기존 연구 문서를 삭제하거나 의미를 바꾸지 않는 Wiki·HTML 보고 체계를 만든다.
6. Kronos 예측과 RL 정책 연구를 UI와 문서에서 분리한다.
7. 3,440×1,440 울트라와이드와 2,160×3,840 portrait 화면에서 가독성과 독립 rail 동작을 검증한다.

### 2.2 이번에 고정한 결정

| 결정 | 고정값 | 금지 또는 보류 |
|---|---|---|
| 의사결정 시각 | D일 `15:20:00 KST` | 15:30 공식 종가 주장 금지 |
| 가격 기준 | `15:20_bar_close_proxy`, `official_close=false` | nearest bar, full-day daily OHLCV 대체 금지 |
| source | `_database/Stock_Database_ohlcv_5min.db`의 exact `YYYYMMDD1520` row | 일봉 DB를 15:20 증거로 위장 금지 |
| 자본 | 60,000,000원 | 실거래 계좌 아님 |
| slot | 10개, slot당 5,000,000원, 최대 투자 50,000,000원, reserve 10,000,000원 | 공매도·레버리지·중복 slot 초기 금지 |
| 비용 | primary `0.23%`, control `0.00%`, stress `0.46%` | 신규 한글 UI/문서에서 bp 그대로 표시 금지 |
| 보유기간 | H1 primary, H3/H5 validation variant | untouched test 이후 retune 금지 |
| 지수 custody | PyKRX-derived offline artifact only | Naver fallback, live network fallback 금지 |
| API/report | GET-only, fail-closed, allowlisted report roots | mutation method, path traversal, symlink escape, XSS 금지 |
| UI | V5.1 opt-in, V3 default | V5.1 기본 전환 금지 |

## 3. 구현 결과

### 3.1 15:20 인과 source와 causal panel

V5.1은 `kronos_daily_1520_source.v1` source contract와 `kronos_daily_v51_causal_panel.v1` panel contract를 추가했다.

| 항목 | 결과 |
|---|---|
| causal cutoff | `15:20:00` KST |
| timestamp | JSON artifact에서 `YYYY-MM-DDT15:20:00+09:00` 및 `YYYYMMDD1520` suffix 강제 |
| symbol | `000250` 같은 6자리 문자열 보존, source table은 `A######` |
| source columns | `date/open/high/low/close/volume` exact set |
| amount | 현재 5분봉 DB에 검증된 amount column 없음. `price × volume` 근사 금지 |
| volume | `bar_volume_1520`은 5분봉 단일 bar volume. `volume_to_1520`/`cumulative_volume_to_1520`은 검증 source 전까지 unavailable |
| fallback | nearest fallback, full-day daily fallback, zero-fill 금지 |
| labels | `future_return_h1_1520_proxy`, `future_return_h3_1520_proxy`, `future_return_h5_1520_proxy` |
| missing 처리 | `missing_entry`, `missing_exit`를 명시하고 synthetic return 생성 금지 |
| locks | promotion/model/paper/live/profit/go summary 관련 false locks 유지 |

이 구현은 대시보드 표시를 source of truth로 쓰지 않는다. evaluator는 검증된 panel 이후 단계에서만 NAV·비용·baseline/control metric을 계산할 수 있으며 source gap을 UI나 일봉 DB로 수리할 수 없다.

### 3.2 6,000만원 10-slot 회계

V5.1 회계는 Decimal 기반 ledger와 독립 oracle로 10-slot 제약을 고정했다.

| 항목 | 값 |
|---|---:|
| 총 연구 자본 | 60,000,000원 |
| slot 수 | 10 |
| slot당 주문 예산 | 5,000,000원 |
| 최대 투자 원금 | 50,000,000원 |
| reserve | 10,000,000원 |
| reserve 비율 | 16.6667% |
| 최대 목표 투자 비율 | 83.3333% |
| primary 왕복 비용 | 0.23% |
| no-cost control | 0.00% |
| stress control | 0.46% |

주문 금액은 비용 포함 slot 한도를 넘을 수 없다. 한 종목에 중복 slot을 배정하지 않고, 공매도와 레버리지는 초기 action space에서 금지한다. 경제 NAV와 shaped reward도 분리했다.

### 3.3 H1/H3/H5 freeze

Horizon 선택은 사전등록·검증 순서의 일부로 고정됐다.

| Horizon | 정의 | 역할 |
|---|---|---|
| H1 | D일 15:20 진입 → D+1 거래일 15:20 청산 | primary |
| H3 | D일 15:20 진입 → D+3 거래일 15:20 청산 | validation variant |
| H5 | D일 15:20 진입 → D+5 거래일 15:20 청산 | validation variant |

`future_return_1d` 같은 legacy label은 V5.1 causal boundary에서 금지된다. Horizon mixing, duplicate symbols, post-test retune, altered freeze manifest는 fail-closed다.

### 3.4 PyKRX-only offline custody와 Naver disabled

KOSPI/KOSDAQ overlay는 PyKRX-derived raw/normalized offline artifact만 입력으로 받는다.

- PyKRX collector는 명시적 optional collector다.
- network call은 panel/evaluator 실행 경로가 아니다.
- raw/normalized artifact는 content-addressed SHA-256 lineage를 가진다.
- Naver source, Naver fallback, live fallback은 금지다.
- PyKRX artifact가 없으면 overlay나 universe field는 ready가 아니라 `BLOCKED`/`MISSING`으로 남는다.
- KOSPI/KOSDAQ/RL series는 exact common dates에서만 normalized-100과 누적 수익률 `%`를 계산한다.
- constituent 또는 point-in-time universe 완전성을 새로 주장하지 않는다.

### 3.5 일곱 개 read-only API와 report 보안

V5.1은 additive Flask blueprint로 일곱 개 GET-only route를 공식 앱에 등록했다.

| Route | 역할 | 보안·정직성 경계 |
|---|---|---|
| `/api/daily-close-v51/source-coverage` | exact 15:20 source coverage | source identity, SHA-256, missing row fail-closed |
| `/api/daily-close-v51/causal-panel` | causal panel summary | legacy daily/full-day source 금지 |
| `/api/daily-close-v51/accounting` | 60M/10-slot accounting | 비용 `%` 표시, false locks |
| `/api/daily-close-v51/evaluator` | H1/H3/H5 evaluator summary | no-retune, no claim |
| `/api/daily-close-v51/benchmark-overlay` | KOSPI/KOSDAQ/RL overlay | PyKRX offline only, Naver disabled |
| `/api/daily-close-v51/reports` | allowlisted report catalog | no path leak, no directory creation |
| `/api/daily-close-v51/reports/<report_id>` | sanitized report read | traversal/symlink/reparse/oversize/XSS fail-closed |

Non-GET method는 artifact나 report를 읽기 전에 `405`로 닫힌다. Query binding은 `run_id`, `artifact_id`, `revision`을 제한하고, duplicate/unknown/unsafe/mismatched query는 typed error 또는 conflict로 처리한다. 응답 envelope은 six false locks와 no-claim labels를 보존한다.

### 3.6 V5.1 IA와 독립 rails

V5.1 화면은 `Kronos / AI Quant Reinforcement Learning` 브랜드와 5개 navigation group을 적용했다.

```text
COMMAND
  Mission Control
KRONOS
  Forecast Workbench
  Prediction Diagnostics
REINFORCEMENT LEARNING
  Daily Close RL
  RL Trading Evidence
  RL Guide
OPERATIONS
  Live Training
  Runs & Reports
  Artifacts & Models
  System Health
KNOWLEDGE
  Research Reports
  Wiki
  Version History
  Settings
```

핵심 의도는 Kronos 예측과 RL 정책 연구의 판정을 합치지 않는 것이다. 두 rail은 독립적으로 동작한다.

- 좌측 navigation collapse와 우측 detail rail collapse가 서로 독립이다.
- 우측 rail을 접어도 `NO-GO`, `READ-ONLY`, six false locks, no-live/no-profit, `NOT_RUN` blocker 문구는 사라지지 않는다.
- report viewer는 read-only list/read API만 사용한다.
- 3,440×1,440 울트라와이드와 2,160×3,840 portrait에서 horizontal overflow가 없었다.

## 4. 점수 전후 비교

### 4.1 축 A — 대시보드·증거 엔지니어링: 98/100 → 99/100

이 점수는 트레이딩 성과 점수가 아니다. dashboard/evidence engineering rubric이다.

| 항목 | 배점 | V5 문서 기준 | V5.1 | 근거 |
|---|---:|---:|---:|---|
| 증거 source·계약 무결성 | 25 | 25 | 25 | 15:20 source/panel, SHA-256 identity, false locks, no fallback |
| 대시보드 IA·사용성·브라우저 | 25 | 24 | 25 | V5.1 IA, 독립 rails, 3440×1440/2160×3840 no overflow |
| API·보고서 보안 | 20 | 19 | 20 | 7 read-only routes, allowlisted report catalog, traversal/XSS/oversize/mutation fail-closed |
| 재현성·검증 | 20 | 20 | 19 | focused/backend/frontend/build/browser 증거는 강하지만 monolithic full pytest가 한 프로세스로 완료되지 않음 |
| 릴리스 경계·rollback 정직성 | 10 | 10 | 10 | V3 default 유지, no tag/push/merge/default, no live/profit claim |
| **합계** | **100** | **98** | **99** | 누락 1점은 full-suite 단일 프로세스 미완료 때문 |

V5.1이 100점이 아닌 이유는 기능 결함보다 검증 형식의 한계다. 전체 2,298-test monolithic command가 단일 프로세스로 clean completion을 남기지 못했으므로 full-suite evidence는 “분할 검증 + 집중 검증 + frontend/build/browser”로만 주장한다.

### 4.2 축 B — 일봉 종가매매 RL 연구 기반: 29/100 → 71/100

이 표는 **새로운 회고 rubric**이다. 과거에 기록된 역사적 metric을 덮어쓰는 것이 아니며, RL 성과 점수가 아니다. 결과 evidence 항목은 모델 학습과 fresh OOS가 실행되지 않았으므로 계속 `0`이다.

| 항목 | 배점 | 이전 기반 | V5.1 기반 | 근거 |
|---|---:|---:|---:|---|
| 인과 source·panel | 20 | 4 | 18 | exact 15:20, official_close=false, no fallback, H1/H3/H5 labels |
| 회계·경제 NAV | 15 | 6 | 14 | 60M/10-slot/reserve/비용 `%`/Decimal oracle |
| protocol·freeze·horizon | 20 | 5 | 16 | H1 primary, H3/H5 validation, no-retune, digest/claim closure |
| controls·custody·overlay | 15 | 5 | 13 | 0.00%/0.46% controls, PyKRX offline custody, Naver disabled, overlay blocked-safe |
| 결과 evidence | 20 | 0 | 0 | PPO 학습, fresh OOS, paper-forward 실행 없음 |
| no-claim·문서/API governance | 10 | 9 | 10 | Wiki/report/API 경계, prior NO-GO 보존, six false locks |
| **합계** | **100** | **29** | **71** | 연구 실행 전 기반 점수만 개선 |

따라서 “RL 연구 기반”은 크게 좋아졌지만, “RL이 수익을 냈다”는 증거는 여전히 없다.

### 4.3 축 C — 실거래·수익 준비도: 0/100 → 0/100

| 항목 | 배점 | 이전 | 이번 | 판정 |
|---|---:|---:|---:|---|
| fresh OOS 수익 결과 | 40 | 0 | 0 | `NOT_RUN` |
| live broker/order 준비 | 25 | 0 | 0 | 구현·승인 없음 |
| paper-forward | 15 | 0 | 0 | 실행·승인 없음 |
| 모델 승격 | 10 | 0 | 0 | prior `NO-GO`/`INCONCLUSIVE` 유지 |
| 운영 승인·tag·merge | 10 | 0 | 0 | tag/push/merge/default 전환 없음 |
| **합계** | **100** | **0** | **0** | `NO-GO / NOT_RUN / NO_CLAIM` |

## 5. 검증 명령과 결과

본 문서는 최초 문서 commit `1ec28bd` 이후 최종 blocker 보강 commit `bf6fce9`–`6a8fd02`와 현재 HEAD 기준 검증을 함께 기록한다.

### 5.1 집중 Python 검증

```text
py -3.11 -m pytest tests/test_kronos_v51_1520_source.py tests/test_kronos_v51_causal_panel.py tests/test_kronos_v51_contract_schema.py tests/test_stom_rl_daily_close_slot_dataset.py tests/test_kronos_v5_api_schema.py -q -W error
# G001 cumulative: 200 passed

py -3.11 -m pytest tests/test_kronos_v51_horizon_variants.py tests/test_kronos_v5_close_slot_accounting.py -q -W error
# G002 focused: 63 passed

py -3.11 -m pytest tests/test_kronos_v51_index_source.py tests/test_kronos_v51_index_overlay.py -q -W error
# G003 focused: 23 passed

py -3.11 -m pytest tests/test_kronos_v51_research_api.py tests/test_kronos_v51_research_api_schema.py tests/test_kronos_v51_app_integration.py tests/test_kronos_v5_app_integration.py -q -W error
# final API/schema focused: 71 passed
```

최종 V5.1 누적 배치는 다음 결과를 남겼다.

```text
py -3.11 -m pytest tests/test_kronos_v51_1520_source.py tests/test_kronos_v51_causal_panel.py tests/test_kronos_v51_contract_schema.py tests/test_kronos_v51_horizon_variants.py tests/test_kronos_v5_close_slot_accounting.py tests/test_kronos_v51_index_source.py tests/test_kronos_v51_index_overlay.py tests/test_kronos_v51_report_catalog.py tests/test_kronos_v51_research_api.py tests/test_kronos_v51_research_api_schema.py tests/test_kronos_v51_app_integration.py tests/test_kronos_v5_app_integration.py -q -W error
# 250 passed

py -3.11 -m pytest tests/test_kronos_v51_horizon_variants.py tests/test_kronos_v5_close_slot_accounting.py tests/test_kronos_v51_index_overlay.py tests/test_kronos_v51_index_source.py -q -W error
# runtime integration focused: 88 passed
```

### 5.2 Frontend, Svelte, build, audit

```text
bun test src
# 351 passed

npm run build
# Svelte check: 408 files, 0 errors, 0 warnings
# Vite build: passed

npm audit --audit-level=high
# 0 vulnerabilities
```

### 5.3 Dashboard regression

```text
py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_tab.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_route.py tests/test_v4_activation_shell.py tests/test_kronos_v51_app_integration.py -q -W error
# 33 passed
```

### 5.4 Browser 검증

```text
live Chromium: http://127.0.0.1:8122/?tab=rl&ui=v5
loaded bundle: index-jILoBmyy.js / index-wHVaqgPL.css
source revision: 6a8fd02ccdbd4d7cb28a4f283a865ad0f91454b3
viewports: 3440x1440 and 2160x3840
# horizontal overflow: false
# independent left/right rail collapse: passed
# version history: passed
# Research Reports & Wiki route: passed
```

증거:

- `artifacts/v51-browser-qa.json`
- `artifacts/v51-ultrawide-3440x1440.png`
- `artifacts/v51-portrait-2160x3840.png`

### 5.5 Monolithic full-suite 진실

전체 suite를 “모두 통과”했다고 주장하지 않는다.

| 시도 | 명령 | 관찰 결과 | 사용 가능한 주장 |
|---|---|---|---|
| 1 | `py -3.11 -m pytest tests -q -W error` | 900초 timeout, 진행률 81% | full-suite 단일 프로세스 완료 증거 아님 |
| 2 | `py -3.11 -m pytest tests -q -W error` | 진행률 84%에서 assertion output 없이 종료 | full-suite 단일 프로세스 완료 증거 아님 |
| tail partition | 남은 pytest partition | 342 passed + 의도적 V3 snapshot drift 1건 | partition 증거로만 사용 |
| snapshot 재생성 후 | V3 snapshot tests | 5 snapshot tests passed | commit `6cb5efd`의 승인 snapshot 증거 |

따라서 정확한 full-suite 문구는 다음이다.

> Monolithic 2,298-test command는 한 프로세스로 완료되지 않았다. 첫 실행은 900초 timeout으로 81%에서 중단됐고, 두 번째는 84%에서 assertion output 없이 종료됐다. Tail partition은 342 passed와 의도적 V3 snapshot drift를 남겼으며, 승인 snapshot 재생성 후 5개 snapshot test가 통과했다. 모든 2,298개가 통과했다고 주장하지 않는다.

## 6. 브라우저 증거와 사용자 확인 경로

### 6.1 확인 URL

최종 로컬 검증 포트는 `8122`이다.

| 목적 | URL |
|---|---|
| V3 기본 확인 | `http://127.0.0.1:8122/` |
| V5.1 opt-in shell | `http://127.0.0.1:8122/?ui=v5` |
| RL evidence 화면 | `http://127.0.0.1:8122/?tab=rl&ui=v5` |
| Research Reports & Wiki | `http://127.0.0.1:8122/?tab=docs&ui=v5` |
| source coverage API | `http://127.0.0.1:8122/api/daily-close-v51/source-coverage` |
| causal panel API | `http://127.0.0.1:8122/api/daily-close-v51/causal-panel` |
| accounting API | `http://127.0.0.1:8122/api/daily-close-v51/accounting` |
| evaluator API | `http://127.0.0.1:8122/api/daily-close-v51/evaluator` |
| benchmark overlay API | `http://127.0.0.1:8122/api/daily-close-v51/benchmark-overlay` |
| report list API | `http://127.0.0.1:8122/api/daily-close-v51/reports` |

### 6.2 사용자 확인 action

1. `/`가 V3 기본 화면인지 확인한다.
2. `?ui=v5`에서 V5.1 label과 version history가 보이는지 확인한다.
3. 좌측 navigation을 접고 펼친 뒤 우측 detail rail 상태가 독립인지 확인한다.
4. 우측 detail rail을 접었을 때 `NO-GO`, `READ-ONLY`, no-live/no-profit, six false locks, `NOT_RUN` blocker가 사라지지 않는지 확인한다.
5. `?tab=rl&ui=v5`에서 15:20 proxy, 60M/10-slot, H1/H3/H5, PyKRX offline/Naver disabled 문구가 보이는지 확인한다.
6. `?tab=docs&ui=v5`에서 Wiki와 Research Reports가 read-only로 열리는지 확인한다.
7. 위 API route에 GET으로 접근해 fail-closed payload가 나오더라도 mutation이나 path leak 없이 bounded JSON이 반환되는지 확인한다.
8. POST/PUT/PATCH/DELETE는 `405`로 거절되어야 하며 artifact/report를 읽기 전 닫혀야 한다.

## 7. 한계·blocker·금지 주장

### 7.1 한계와 blocker

| 항목 | 상태 | 의미 |
|---|---|---|
| Monolithic full pytest | incomplete | 2,298-test 전체 명령이 한 프로세스로 완료되지 않았으므로 100/100 엔지니어링 검증을 보류 |
| PPO 학습 | `NOT_RUN` | 새 모델 학습, seed/fold full run 없음 |
| fresh OOS | `NOT_RUN` | untouched test OOS 결과 없음 |
| live/paper | `NOT_RUN` | paper-forward와 live broker/order 실행 없음 |
| PyKRX offline artifact | 구현됨, 실행 artifact 의존 | 승인 artifact가 없으면 overlay는 blocked/missing으로 남아야 함 |
| 15:20 full-universe coverage | 구현 기반 있음, 전체 coverage claim 없음 | 전체 종목·전체 기간 coverage audit은 다음 연구 단계 |
| 공식 종가 | 주장 안 함 | 15:20 bar close proxy는 15:30 공식 종가가 아님 |

### 7.2 금지 주장

본 문서와 V5.1 구현은 다음을 주장하지 않는다.

- 수익성 또는 live profitability
- 실거래 준비도
- broker 주문 준비
- paper-forward 준비 또는 실행
- 모델 승격 또는 `GO`
- V5.1 기본 UI 전환
- tag/release/push/merge 완료
- 2,298개 전체 pytest가 한 프로세스로 모두 통과했다는 주장

### 7.3 기존 결과 보존

| 기존 증거 | 보존 판정 | 이번 문서의 처리 |
|---|---|---|
| `docs/stom_daily_close_slot_truthful_result_2026-07-12.md` | test OOS 무거래, `NO-GO` | 유지 |
| `docs/stom_daily_sb3_ppo_smoke_result_2026-07-12.md` | smoke/inconclusive, 미승격 | 유지 |
| `docs/stom_daily_sb3_ppo_result_2026-07-12.md` | full `NOT_RUN` | 유지 |
| RULE baseline 문서들 | RULE, RL 아님 | RL 성과로 재분류하지 않음 |

## 8. Rollback과 V3 기본 정책

Rollback의 기본값은 “V5.1을 기본으로 쓰지 않는 것”이다.

- root `/`는 V3 기본 유지.
- V5.1은 `?ui=v5` opt-in 확인용.
- V5.1 API/report viewer는 additive read-only surface다.
- source/panel/accounting/evaluator가 blocked를 반환해도 V3 기본 UX와 기존 연구 판정은 바뀌지 않는다.
- release default 전환은 별도 release gate, monolithic full-suite clean evidence, 현재 dist-bound browser evidence, 사용자 승인 없이는 불가하다.

## 9. 관련 문서·artifact

| 경로 | 역할 |
|---|---|
| `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` | V5.1 요구사항과 고정값 |
| `docs/kronos_v51_1520_causal_adr_2026-07-17.md` | 15:20 source/panel ADR |
| `docs/kronos_dashboard_v5_development_result_2026-07-16.md` | V5 baseline 98/100 기록 |
| `docs/wiki/13-research-ledger.md` | 연구 원장 |
| `docs/wiki/14-document-standard.md` | 문서 표준 |
| `docs/schemas/kronos_daily_1520_source.v1.schema.json` | 15:20 source schema |
| `docs/schemas/kronos_daily_v51_causal_panel.v1.schema.json` | V5.1 causal panel schema |
| `docs/schemas/kronos_v51_research_api.v1.schema.json` | V5.1 research API schema |
| `artifacts/v51-browser-qa.json` | browser automation transcript |
| `artifacts/v51-ultrawide-3440x1440.png` | ultrawide screenshot |
| `artifacts/v51-portrait-2160x3840.png` | portrait screenshot |

## 10. 관련 commit

### 10.1 기준과 범위

| 항목 | 값 |
|---|---|
| Branch | `feature/dashboard-v5-learning-evidence` |
| Baseline | `4c8ba1f` |
| V5.1 구현 범위 | `9d8e2ad` through `6a8fd02` |
| 최초 결과 문서 commit | `1ec28bd708fd19d61396af8cb3e7c0d8887c68a0` |
| 최종 브라우저 검증 대상 HEAD | `6a8fd02ccdbd4d7cb28a4f283a865ad0f91454b3` |
| tag/push/merge | 수행하지 않음 |

### 10.2 V5.1 commit 목록

| 순서 | commit | 제목 | 역할 |
|---:|---|---|---|
| 1 | `9d8e2ad6ff889339e2a614d6aca34b0486aa2dbe` | `feat(v5.1): 15시20분 인과 소스와 패널 계약 추가` | exact 15:20 source/panel 시작 |
| 2 | `b95f7337556dc24d9f4970412e9d583f81d91aa7` | `fix(v5.1): 인과 패널 계약을 폐쇄 검증` | panel fail-closed 보강 |
| 3 | `54331efb441045edfb79ab6ec876b30219d4f298` | `feat(v5.1): 6천만원 열 슬롯 회계 원장 추가` | 60M/10-slot accounting |
| 4 | `640a1a02db4c9d240aa9800b3a7ca079cb1cdfef` | `feat(v5.1): H1 H3 H5 동결 평가기 추가` | horizon freeze/evaluator |
| 5 | `660b9e8e0a46664456670e626b34d5053e4514a0` | `feat(v5.1): pykrx 오프라인 지수 보관과 오버레이 추가` | PyKRX offline custody, overlay |
| 6 | `f66420e2bb15cafb1af8f6464aac35b56eac2493` | `feat(v5.1): 읽기 전용 연구 API와 보고서 카탈로그 추가` | seven read-only routes/report security |
| 7 | `ec134dd2d6416a124b05f660bf7acdc5aec0dbae` | `feat(v5.1): AI 퀀트 강화학습 대시보드 UX 추가` | V5.1 IA, rails, report viewer |
| 8 | `e222c10ab510cc39558e52f5d30d8de4e0ca6d0b` | `chore(v5.1): 검증 이력에 프론트 커밋 기록` | version/history trace 보강 |
| 9 | `04cf086477aa061cb6305c029723e74acdcb6be7` | `build(v5.1): 공식 대시보드 번들 갱신` | official dist update |
| 10 | `e3e149b8a49659f27dea51780c82e74a473231a9` | `test(v5.1): 새 셸 내비게이션 회귀 계약 반영` | dashboard regression contract |
| 11 | `6cb5efd4bc66fe465e4a430c889662d0cafe3ed9` | `test(v5.1): V3 계약 스냅샷 재조정` | approved V3 snapshot drift 정리 |
| 12 | `1ec28bd708fd19d61396af8cb3e7c0d8887c68a0` | `docs(v5.1): 구현 결과와 연구 Wiki 원장 기록` | 최초 결과 보고서와 Wiki 원장 |
| 13 | `bf6fce9` | `fix(rl): close V5.1 evaluator integration gaps` | canonical accounting row와 overlay provenance closure |
| 14 | `18bc153` | `fix(api): fail closed V5.1 evidence contracts` | ERROR schema, identity, overlay, zero-cost ID closure |
| 15 | `2cf2371` | `fix(ui): make V5.1 research evidence fail closed` | label/cost/placeholder/IA truth closure |
| 16 | `6a8fd02ccdbd4d7cb28a4f283a865ad0f91454b3` | `build(dashboard): refresh V5.1 official assets` | 최종 browser 검증 bundle |

## 11. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-18 | 최초 결과 문서·Wiki commit `1ec28bd` 후 blocker를 보강하고, 최종 구현 HEAD `6a8fd02`의 bundle을 Chromium 3440×1440/2160×3840에서 재검증 | GJC | `1ec28bd`, `bf6fce9`, `18bc153`, `2cf2371`, `6a8fd02` |

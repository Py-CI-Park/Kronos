# Kronos Dashboard V5.1 UX·UI 전수 감사 — 2026-07-19

> 문서 ID: `KRONOS-DASHBOARD-V51-UX-AUDIT-2026-07-19`
> 작성일: `2026-07-19 KST`
> 상태: `COMPLETE / AUDIT_RECORDED`
> 범위: V5.1 대시보드 정보구조, 초보자 강화학습 여정, 시각·반응형 성숙도. 제품 코드 변경 없음(read-only 감사).
> 모델·실거래 판정: `NOT_RUN / NO-GO 유지 / LIVE_READY 아님 / PROFIT_CLAIM 없음`
> 브랜치: `feature/dashboard-v5-learning-evidence`
> 기준 commit: `23b0edb`
> 대체 문서: 없음. 후속 계획은 `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md`.

## 목차

1. [감사 목적](#1-감사-목적)
2. [감사 방법](#2-감사-방법)
3. [종합 점수](#3-종합-점수)
4. [핵심 결함](#4-핵심-결함)
5. [반응형 viewport 증거](#5-반응형-viewport-증거)
6. [잘 된 부분](#6-잘-된-부분)
7. [결론](#7-결론)
8. [한계](#8-한계)
9. [관련 문서·artifact](#9-관련-문서artifact)
10. [변경 히스토리](#10-변경-히스토리)

## 1. 감사 목적

사용자 요청은 다음이었다. "강화학습 초보자가 일봉 종가매매 또는 여러 강화학습을
진행하기 위해, 대시보드 전체 구조가 체계적이고 프로세스에 맞으며 사용자 친화적이고
초보자도 개발할 수 있고 깔끔하며 반응성 UX/UI로 잘 개발되었는지 냉정하게 전수 검사."

목적은 홍보가 아니라 냉정한 성숙도 판정이다. 기존 엔지니어링·증거 계약 점수(99/100)와
사용자 관점 UX 성숙도를 분리해서 평가한다.

## 2. 감사 방법

- 세 개의 독립 read-only 아키텍트 감사를 병렬 실행했다.
  - 초보자 강화학습 여정 감사
  - 정보구조(IA) 감사
  - 시각·반응형 성숙도 감사
- 실제 Chromium으로 12개 route를 전수 순회하며 heading/버튼/카드 수, `NOT_RUN`/`BLOCKED`/`NO-GO`
  출현 빈도, 스크롤 높이, 수평 overflow를 측정했다.
- viewport는 `3440×1440`, `1440×900`, `1080×1920`, `390×844`에서 확인했다.
- 실행 위치를 확인하기 위해 `stom_rl/daily_rl_train.py`, `daily_scenario_runner.py`,
  `daily_scenario_batch.py`, `daily_portfolio_sb3_runner.py`를 확인했다.

## 3. 종합 점수

| 평가 영역 | 점수 | 판정 |
|---|---:|---|
| 연구 정직성·가드레일 | 90/100 | 강함 |
| 엔지니어링·증거 계약 | 99/100 | 강함(별도 축) |
| 정보구조(IA) | 56/100 | USABLE_WITH_GAPS |
| 시각 완성도 | 55/100 | IMMATURE |
| 반응형 UX | 51/100 | IMMATURE |
| 초보자 강화학습 여정 | 41/100 | IMMATURE |
| 실험 설정·실행 가능성 | 30/100 | IMMATURE |
| 결과·효과 이해 용이성 | 45/100 | IMMATURE |
| **사용자 관점 UX 종합** | **51/100** | **IMMATURE** |

이전 99점은 엔지니어링·증거 계약 점수였고, 사용자 친화적 UX 성숙도는 별도 축이며
현재 약 51점이다.

## 4. 핵심 결함

### 4.1 실험을 어디서 정의·시작하는지 알 수 없음 (P1)

- 일봉 RL 실행은 대시보드가 아니라 `stom_rl/daily_rl_train.py`,
  `daily_scenario_runner.py`, `daily_scenario_batch.py` 등 Python 연구 모듈에서만 가능하다.
- 대시보드는 실행 플랫폼이 아니라 생성된 artifact를 읽는 증거 뷰어다.
- `configure / preregister / launch` 제품 흐름이 화면에 없다. 이는 데이터 누락이 아니라
  제품 흐름 부재다.

### 4.2 `Training & System`이 실제 RL 학습 화면이 아님 (P1)

- 현재 표시는 주로 Kronos predictor fine-tuning 상태·GPU·CPU·RAM이다.
- 일봉 RL run UID, 알고리즘, 환경 버전, state/action/reward 계약, seed/fold, episode,
  checkpoint, validation replay, H1/H3/H5 진행 상태가 연결되지 않았다.
- 초보자는 predictor 학습을 RL 학습으로 오인할 수 있다.

### 4.3 효과 판단용 단일 비교 화면 부재 (P1)

- 강화학습 효과 판단에는 H1/H3/H5 × KOSPI/KOSDAQ × RL/RULE/no-trade × 0.00%/0.23%/0.46%
  × train/validation/test × seed/fold 비교가 필요하다.
- 관련 컴포넌트는 분산돼 있고, PyKRX 지수 artifact가 없으면 비교가 `BLOCKED_INDEX_SERIES_SOURCE`로 남는다.
- 현재는 효과를 판단할 데이터도 없고, 판단하는 UX도 단일 흐름이 아니다.

### 4.4 정보 과밀과 반복 (P1/P2)

- RL Evidence 화면: 세로 약 5,879px, 카드 약 40개, `NOT_RUN` 약 80회, `BLOCKED` 약 19회, `NO-GO` 약 16회.
- Daily Close RL 화면: 세로 약 5,747px, 텍스트 약 19,725자, `BLOCKED` 약 15회, `NO-GO` 약 14회.
- 정직성은 좋으나 "현재 판정 → 원인 → 해결할 한 가지 → 위치 → 확인 지표" 구조가 아니라
  비슷한 무게의 계약·상태·경고가 반복된다.

### 4.5 Daily Close RL과 Intraday RL 재혼합 (P1)

- `RL Research & Evidence` 하나의 활성 메뉴가 `rl`, `daily-ohlcv`, `daily-rl-guide`를 모두 포함한다.
- 일봉과 인트라데이는 데이터 주기·환경·action·reward·평가 기준이 다르므로 분리해야 한다.

### 4.6 보고서·이력·artifact가 RL 여정과 분리됨 (P2)

- `Runs & Reports`와 `Research Reports & Wiki`가 분리돼 있고, 특정 run UID의 최종 보고서로
  이어지는 canonical 경로가 없다.

### 4.7 Mission Control이 초보자 중심이 아님 (P2)

- D0–D9, FACT, price_basis, universe, WF, lifecycle token 등 내부 개발 용어 중심이다.
- blocker 항목이 실제 해결 화면으로 이동하는 명확한 CTA가 부족하다.

### 4.8 우측 rail이 핵심 콘텐츠를 가림 (P1, 반응형)

- 가드레일 자체는 필요하다(RULE→RL 오인, NOT_RUN→결과 오인, live/profit 오인 방지).
- 그러나 공간 점유가 과도하다.

## 5. 반응형 viewport 증거

| viewport | 수평 overflow | 우측 rail | 문제 |
|---|---|---|---|
| 3440×1440 | 없음 | 폭 560px | 정보 밀도 낮고 글자 작음, 전 컬럼 증거 나열 |
| 1440×900 | 없음 | 폭 400px, 본문 약 830px | RL 페이지 약 7,161px, rail이 본문 폭 압박 |
| 1080×1920 portrait | 없음 | 폭 400px 고정 overlay | 화면 오른쪽 약 37% 점유, 본문 가림 |
| 390×844 mobile | 없음 | 폭 370px, 높이 약 608px | 첫 화면의 약 72%를 덮음, 핵심보다 가드레일 우선 |

수평 overflow는 모든 viewport에서 발생하지 않았다. 그러나 portrait/mobile에서 우측 rail이
콘텐츠를 덮는 것은 P1 사용성 문제다.

## 6. 잘 된 부분

- 오류를 성공처럼 꾸미지 않는다.
- `NO-GO`/`NOT_RUN`/`BLOCKED`를 숨기지 않는다.
- 좌우 rail 독립 접힘, Version History 접근성(focus/Escape) 개선.
- V3/V4 호환성과 deep link 보존.
- 기본 typography·색상·카드 스타일 일관성.
- 수평 overflow 없음.

## 7. 결론

현재 V5.1은 **정직한 연구 증거 뷰어로는 우수하지만, 강화학습 초보자가 실험을 정의·실행·평가하는
완성형 제품으로는 미성숙(IMMATURE)**하다. 사용자 관점 UX 종합은 약 `51/100`.

다음 단계는 카드·색상 미세 조정이 아니라 **강화학습 workflow 중심 전면 재설계(V6)**다. 표준 흐름은
`Overview → Data → Experiment → Training → Evaluation → Compare → Report`이며, 상세 계획은
`docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md`에 기록한다.

## 8. 한계

- 본 감사는 read-only이며 제품 코드를 변경하지 않았다.
- 실제 사용자 테스트(피험자 관찰)는 수행하지 않았다. 점수는 휴리스틱·전문가 감사 기준이다.
- 점수는 UX 성숙도 판정이며 수익성·모델 성과와 무관하다. 기존 `NO-GO/NOT_RUN`은 유지된다.

## 9. 관련 문서·artifact

| 경로 | 역할 |
|---|---|
| `docs/kronos_dashboard_v51_implementation_result_2026-07-18.md` | V5.1 구현·검증 결과 |
| `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` | V5.1 요구사항·고정값 |
| `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md` | V6 전면 재설계 계획 |
| `artifacts/ux-audit-mission-3440x1440.png` | Mission Control ultrawide 증거 |
| `artifacts/ux-audit-rl-1440x900.png` | RL 페이지 일반 데스크톱 증거 |
| `artifacts/ux-audit-rl-1080x1920.png` | RL 페이지 portrait 증거 |
| `artifacts/ux-audit-rl-390x844.png` | RL 페이지 mobile 증거 |

## 10. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-19 | 3개 독립 감사와 4개 viewport Chromium 측정을 종합한 V5.1 UX 전수 감사 최초 기록. 사용자 UX 종합 51/100, IMMATURE. | GJC | `23b0edb` 기준 |

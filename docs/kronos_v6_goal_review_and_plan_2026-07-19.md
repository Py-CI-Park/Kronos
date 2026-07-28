# Kronos V6 목표 적합성 검토와 통합 실행 계획 — 2026-07-19

> 문서 ID: `KRONOS-V6-GOAL-REVIEW-AND-PLAN-2026-07-19`
> 작성일: `2026-07-19 KST`
> 상태: `PLAN_RECORDED / IMPLEMENTATION_NOT_STARTED`
> 범위: 사용자 최종 목표(일봉 DB 기반 강화학습 모델 개발 + 직관적 인사이트 AI Quant 플랫폼) 대비 기존 V6 계획의 냉정한 적합성 검토와 보완 통합 계획.
> 정직성 경계: 수익성, 모델 승격, 실거래 준비, 브로커 주문, paper-forward, `GO`를 주장하지 않는다. 기존 `NO-GO`/`NOT_RUN` 판정을 완화하지 않는다.
> 브랜치: `feature/dashboard-v6-rl-platform`
> 기준 commit: `00b4ce4` (master 병합, tag `fork-v1.4.0-dashboard-v51-research-preview`)
> 대체 문서: 없음. `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md`를 보완·확장한다.

## 목차

1. [사용자 목표 분해](#1-사용자-목표-분해)
2. [사실 확인 — 보유 자산](#2-사실-확인--보유-자산)
3. [냉정한 적합성 판정](#3-냉정한-적합성-판정)
4. [부족한 것 — Gap 목록](#4-부족한-것--gap-목록)
5. [핵심 설계 결정 — 두 DB의 역할 분리](#5-핵심-설계-결정--두-db의-역할-분리)
6. [통합 실행 계획 — 3-Track](#6-통합-실행-계획--3-track)
7. [수용 기준](#7-수용-기준)
8. [승인 게이트](#8-승인-게이트)
9. [위험과 완화](#9-위험과-완화)
10. [검증](#10-검증)
11. [관련 문서](#11-관련-문서)
12. [변경 히스토리](#12-변경-히스토리)

## 1. 사용자 목표 분해

사용자 목표를 검증 가능한 하위 목표로 분해한다.

| ID | 하위 목표 | 성격 |
|---|---|---|
| G-A | 새 브랜치에서 V6 완전 개선 대시보드·프로세스 구축 | 플랫폼 |
| G-B | **제공된 일봉 DB를 우선 사용해 강화학습 모델을 실제로 개발** | 연구 실행 |
| G-C | 시각적으로 직관적이고 사용하기 쉬운 UX | 플랫폼 |
| G-D | 사용자에게 인사이트를 주는 화면(수급·시장·성과 해석) | 플랫폼+데이터 |
| G-E | AI Quant 플랫폼으로서 프로세스가 체계적일 것 | 프로세스 |

G-B가 명시적으로 "먼저"다. 즉 이 목표는 UX 재설계만으로 달성되지 않고,
**모델 개발 실행이 크리티컬 패스**다.

## 2. 사실 확인 — 보유 자산

### 2.1 일봉 DB (`_database/Stock_Database_ohlcv_1day.db`)

이번 검토에서 직접 확인한 사실:

| 항목 | 값 |
|---|---|
| 종목 테이블 수 | **4,727개** (`A######` 형식) |
| 표본 기간 (`A005930`) | **1986-04-15 ~ 2026-06-12**, 10,488행 |
| 컬럼 | `date, open, high, low, close, volume` + **`상장주식수, 외국인주문한도수량, 외국인현보유수량, 외국인현보유비율, 기관순매수, 기관누적순매수`** |
| 크기 | 962.3MB |

수급(외국인·기관) 컬럼은 5분봉 DB에 없는 **인사이트 자산**이다. G-D의 핵심 원천이 된다.

### 2.2 5분봉 DB (`_database/Stock_Database_ohlcv_5min.db`)

- 14.9GB. V5.1 exact 15:20 인과 계약의 유일 가격 소스.
- `A000250` 기준 15:20 행 1,739개(2019-05-09~2026-06-12).

### 2.3 기존 연구 코드 자산 (재사용 대상)

| 모듈 | 역할 | 상태 |
|---|---|---|
| `stom_rl/daily_ohlcv_db.py` | 일봉 DB 요약·검증 | 일봉 DB 사용 |
| `stom_rl/daily_close_slot_dataset.py / _env.py / _train.py / _gate.py` | 종가매매 slot 데이터셋·환경·학습·게이트 | 기존 `NO-GO` 증거 보유 |
| `stom_rl/daily_rl_train.py` | tabular-Q 일봉 포트폴리오 러너 | 연구용, live-events 스트림 지원 |
| `stom_rl/daily_portfolio_sb3_*` | SB3 PPO 프로토콜·prereg·상태·이벤트 | full run `NOT_RUN` |
| `stom_rl/daily_scenario_runner.py / _batch.py` | 시나리오 실행 CLI | 실행 진입점 존재 |
| `stom_rl/daily_1520_source.py`, `daily_v51_causal_panel.py`, `daily_v51_evaluator.py` | V5.1 15:20 인과 스택 | 구현 완료, 실데이터 실행 전 |
| `stom_rl/korean_index_source.py / _overlay.py` | PyKRX 오프라인 지수 custody | **artifact 미수집 → BLOCKED** |
| `scripts/collect_korean_index_artifact.py` | 지수 수집 CLI | 실행 전 |

**V6는 백지 재개발이 아니라 기존 자산 감사·재사용이 옳다.** 전면 재작성은 검증된
`NO-GO` 게이트·회계·계약 테스트 자산을 버리는 역행이다.

### 2.4 중요한 계약 충돌 (직접 확인)

`stom_rl/daily_v51_causal_panel.py`는 **일봉 DB를 가격 소스로 명시적으로 금지**한다
(`_FORBIDDEN_DAILY_SOURCE_SUFFIX = "_database/Stock_Database_ohlcv_1day.db"`).
이유: 15:20 의사결정 시점에 당일 공식 종가는 관측 불가능하므로 인과 위반.

즉 "일봉 DB로 강화학습"이라는 목표는 **그대로는 V5.1 인과 계약과 충돌**하며,
5장에서 역할 분리로 해소한다.

## 3. 냉정한 적합성 판정

기존 `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md`가 사용자 목표를 얼마나
반영하는지에 대한 판정:

| 하위 목표 | 기존 V6 계획 반영도 | 판정 |
|---|---:|---|
| G-A 새 브랜치·V6 프로세스 | 80% | 반영됨 (P0 scaffold, 커밋 경계) |
| G-B **일봉 DB로 모델 개발** | **25%** | **불충분** — P7/P8 "별도 승인 staging"으로 밀려 주변부. 일봉 DB 자체(4,727종목·수급 컬럼)는 계획에 등장하지 않음 |
| G-C 직관적 UX | 75% | 대체로 반영 (P1/P2/P5) |
| G-D 인사이트 제공 | **20%** | **불충분** — 수급·시장 regime·종목 drill-down·랭킹 등 인사이트 화면이 계획에 없음. Compare Matrix만으로는 부족 |
| G-E 체계적 프로세스 | 70% | 반영 (staging·prereg) 그러나 연구 실행 트랙이 UX 뒤에 직렬로 배치되어 목표 순서("먼저 모델")와 반대 |

**종합: 기존 V6 계획 단독으로는 목표의 약 45~55%만 달성한다.**

핵심 결함 세 가지:

1. **순서가 반대다.** 사용자는 "일봉 DB로 모델 먼저"인데 계획은 "UX 6단계 후 모델".
2. **일봉 DB가 계획에 없다.** 수급 컬럼·4,727종목·40년 이력이라는 실자산이 미반영.
3. **인사이트 레이어가 없다.** 정직성(무엇이 아닌지)은 강하지만 인사이트(무엇을 보라)는 빈약.

## 4. 부족한 것 — Gap 목록

| ID | 심각도 | Gap | 결과 |
|---|---|---|---|
| GAP-1 | P0 | 일봉 DB 기반 모델 개발 트랙이 크리티컬 패스에 없음 | 목표 G-B 미달 |
| GAP-2 | P0 | 일봉 DB(가격·수급)와 5분봉 DB(15:20 체결)의 역할 분리 미정의 | 인과 계약 충돌 방치 |
| GAP-3 | P1 | PyKRX 지수 artifact 수집이 계획에 task로 없음 | Compare가 영구 `BLOCKED` |
| GAP-4 | P1 | 로컬 연구 러너(승인 manifest→queue→학습→artifact) 설계 부재 | 대시보드에서 개발 불가 지속 |
| GAP-5 | P1 | 인사이트 화면(수급 흐름, 시장 regime, 종목 drill-down, 시그널 랭킹) 미계획 | 목표 G-D 미달 |
| GAP-6 | P2 | 수용 기준이 UX 점수 중심, 연구 실행 완료 기준 부재 | "모델 개발" 완료를 판정 불가 |
| GAP-7 | P2 | 데이터 스코프·컴퓨트 예산 미정 (4,727종목×40년 전량은 과대) | 실행 지연 위험 |
| GAP-8 | P2 | 기존 연구 자산 재사용 인벤토리 부재 | 중복 개발 위험 |
| GAP-9 | P3 | 수급 컬럼 품질 감사(0 채움 구간, point-in-time성) 미계획 | 인사이트 신뢰도 위험 |

## 5. 핵심 설계 결정 — 두 DB의 역할 분리

목표와 인과 계약을 모두 만족하는 유일한 구조:

| DB | 역할 | 허용 | 금지 |
|---|---|---|---|
| **일봉 DB (1day)** | **Feature·인사이트 권위** | D-1 이전 가격/거래량 feature, 수급(외국인·기관) feature, 유동성 필터, universe 통계, 인사이트 화면 | 당일 체결가격 소스로 사용(인과 위반) |
| **5분봉 DB (5min)** | **체결가격 권위** | D일 15:20 진입가, D+N 15:20 청산가(H1/H3/H5 라벨) | 누락 bar의 근사 대체 |

즉 "일봉 DB를 이용한 강화학습"은 다음으로 정확히 정의된다:

```text
state  = 일봉 DB의 D-1 이전 가격·거래량·수급 feature
action = 10-slot 종가매매 (매수/보유/청산)
체결   = 5분봉 DB exact 15:20 (official_close=false)
reward = 경제 NAV 로그수익 − 0.23% 비용 − 위험 벌점
검증   = H1 primary, H3/H5 validation, untouched test OOS
```

수급 컬럼은 point-in-time 공시 지연 감사(GAP-9)를 통과한 범위에서만 state에 넣는다.

## 6. 통합 실행 계획 — 3-Track

기존 8-Phase 직렬 계획을 폐기하지 않고 **3-Track 병행**으로 재구성한다.
Track R(연구)이 크리티컬 패스이고, Track U(UX)와 Track D(데이터)가 병행한다.

### Track D — 데이터 기반 (선행, 1~2 세션)

| 단계 | 내용 | 산출물 |
|---|---|---|
| D-1 | 일봉 DB 전수 감사: 종목 수, 기간, 수급 컬럼 채움율, 0-채움 구간, 상폐·신규상장 분포 | 감사 보고서 + coverage artifact |
| D-2 | 연구 universe 확정: 유동성 필터(예: 최근 N일 거래대금), 보통주만, Q-product 격리, 기간 스코프(권장: 2018-01~2026-06) | universe manifest + SHA-256 |
| D-3 | PyKRX 지수 artifact 수집 실행(`scripts/collect_korean_index_artifact.py`) → KOSPI/KOSDAQ overlay `BLOCKED` 해소 | offline index artifact + hash |
| D-4 | 일봉(feature) × 5분봉(15:20 체결) 결합 dataset 계약: leakage 테스트 포함 | dataset 계약 + 테스트 |

### Track R — 강화학습 모델 개발 (크리티컬 패스)

| 단계 | 내용 | 산출물 |
|---|---|---|
| R-1 | 기존 자산 감사·재사용 결정: `daily_close_slot_*`, `daily_rl_train`, `daily_portfolio_sb3_*` 중 V6 dataset 계약에 맞는 것 선별 | 재사용 인벤토리 |
| R-2 | 사전등록: 가설, state(수급 포함 여부), action, reward, seed/fold, 성공·실패·중단 기준 동결 | prereg 문서 + SHA-256 |
| R-3 | H1 smoke: 소규모 universe·짧은 기간으로 파이프라인 관통(학습→checkpoint→validation replay→artifact) | smoke 결과 문서 |
| R-4 | 본 학습: 다중 seed, H1 primary, 0.00%/0.23%/0.46% 비용, RULE·no-trade·shuffle control 동시 산출 | run artifacts |
| R-5 | 평가: validation → untouched test OOS 1회, H3/H5 variant, KOSPI/KOSDAQ 대비 경제 NAV | 평가 보고서 |
| R-6 | 판정 문서: `GO/NO-GO/INCONCLUSIVE` — **결과가 나빠도 그대로 기록** | RESULT 문서 |

Track R의 성공 정의는 "수익"이 아니라 **"판정 가능한 증거가 생산되는 것"**이다.

### Track U — 플랫폼·인사이트 UX (병행)

| 단계 | 내용 | 기존 계획 대응 |
|---|---|---|
| U-1 | V6 opt-in shell + Overview(RL Journey Home: 현재 단계·blocker 1개·다음 행동 1개) | P0+P1 |
| U-2 | Workflow IA: Data → Experiment → Training → Evaluation → Compare → Report, Daily/Intraday 분리 | P2 |
| U-3 | **인사이트 화면(신규)**: 종목 drill-down(가격+수급 오버레이), 외국인·기관 순매수 흐름, 시장 regime(KOSPI/KOSDAQ 추세·변동성), 시그널 랭킹(연구 산출물 기반, 추천 아님 명시) | GAP-5 해소 |
| U-4 | Training 화면을 Track R run lifecycle(run UID·episode·checkpoint·replay)과 직결 | P2 확장 |
| U-5 | Compare Matrix: H1/H3/H5 × KOSPI/KOSDAQ × RL/RULE/no-trade × 비용 | P3 |
| U-6 | Experiment Studio: manifest 생성·검증·실행 명령 미리보기(read-only-safe) → 승인 후 로컬 러너 queue 연동 | P6→P7 |
| U-7 | Reports & Provenance 통합 + rail drawer화 + mobile/portrait 재설계 | P4+P5 |

### 실행 순서 (권장)

```text
세션 1  D-1 → D-2 → D-3          (데이터 사실 확정, BLOCKED 해소)
세션 2  D-4 → R-1 → R-2          (dataset 계약, 재사용 결정, 사전등록)
세션 3  R-3 (H1 smoke) ∥ U-1     (파이프라인 관통 + Journey Home)
세션 4  R-4 (본 학습) ∥ U-2~U-4  (학습 진행 중 UX 병행)
세션 5  R-5 → R-6 ∥ U-5          (평가·판정 + Compare Matrix)
세션 6  U-6 → U-7                (Studio·러너 연동, 마감 재설계)
```

## 7. 수용 기준

### 연구 (G-B)

- 일봉 DB 감사 artifact와 universe manifest에 SHA-256이 존재한다.
- H1 smoke가 학습→checkpoint→validation replay→artifact를 관통했다.
- 본 학습이 다중 seed로 완료되고 RULE·no-trade·shuffle 대비표가 생산됐다.
- untouched test OOS 1회 실행과 `GO/NO-GO/INCONCLUSIVE` 판정 문서가 존재한다.
- **판정 결과와 무관하게** 위 증거가 모두 있으면 G-B는 달성이다.

### 플랫폼 (G-A/C/D/E)

- Overview에서 "현재 단계/막힌 이유/다음 행동"이 한 화면에 보인다.
- 인사이트 화면에서 임의 종목의 가격+수급 40년 이력을 열람할 수 있다.
- Compare Matrix가 실제 KOSPI/KOSDAQ artifact로 렌더링된다(`BLOCKED` 아님).
- 특정 run UID → 학습 상태 → 평가 → 보고서 → artifact hash로 끊김 없이 이동한다.
- mobile/portrait에서 안전 rail이 기본 닫힘이며 콘텐츠를 가리지 않는다.
- V3/V4 계약 테스트·프론트 테스트·Svelte check 0/0·build 통과.
- UX 재감사 목표: 초보자 여정 ≥ 75/100, 사용자 종합 ≥ 78/100.

## 8. 승인 게이트

| 게이트 | 시점 | 승인 대상 |
|---|---|---|
| A1 | Track D 완료 후 | universe·기간 스코프, 수급 feature 포함 여부 |
| A2 | R-2 사전등록 | 가설·중단 기준·seed matrix 동결 |
| A3 | R-3 smoke 통과 후 | 본 학습 컴퓨트 예산 |
| A4 | U-6 이전 | 대시보드→로컬 러너 실행 연동(read-only 계약 첫 완화) |
| — | 항상 금지 | push/PR/merge/tag 추가, 실거래·브로커·paper-forward, V6 기본 UI 전환 |

## 9. 위험과 완화

| 위험 | 완화 |
|---|---|
| 수급 컬럼의 사후 수정·지연 공시로 leakage | GAP-9 감사에서 채움 시점 검증, 불명확 구간은 feature 제외 |
| 4,727종목 전량 학습으로 컴퓨트 폭증 | D-2에서 유동성 상위 universe로 스코프, 기간 2018+ 권장 |
| 5분봉 15:20 누락으로 학습 표본 축소 | 누락은 거래불가 처리(계약 유지), coverage를 D-1 감사에서 정량화 |
| 나쁜 결과를 UX로 포장 | RESULT 문서와 six false locks 계약 테스트 유지, `NO-GO` 그대로 표기 |
| UX 병행이 연구를 지연 | Track R을 크리티컬 패스로 명시, U-트랙은 R 산출물 소비자로 설계 |
| 러너 도입으로 보안 경계 훼손 | A4 게이트, 허용 entrypoint allowlist, 브로커·주문 경로와 물리적 분리 |

## 10. 검증

이번 검토에서 실행한 사실 확인:

```text
read _database → 1day 962MB / 5min 14.9GB / tick 27.7GB
sqlite: 1day 테이블 4,727개
sqlite: A005930 = 1986-04-15~2026-06-12, 10,488행, 수급 컬럼 존재
search: daily_v51_causal_panel.py가 1day DB를 가격 소스로 금지함을 확인
search: daily_ohlcv_db.py가 1day DB를 사용함을 확인
```

구현 검증은 각 Track 단계에서 집중 pytest(`-W error`)·프론트 테스트·browser 증거로 수행한다.

## 11. 관련 문서

| 경로 | 역할 |
|---|---|
| `docs/kronos_dashboard_v6_remodel_plan_2026-07-19.md` | 기존 V6 UX 계획(본 문서가 보완) |
| `docs/kronos_dashboard_v51_ux_audit_2026-07-19.md` | UX 감사 근거 |
| `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` | 15:20·회계·비용 고정값 |
| `docs/kronos_v51_1520_causal_adr_2026-07-17.md` | 인과 계약 ADR |
| `docs/wiki/13-research-ledger.md` | 연구 원장 |

## 12. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-19 | 일봉 DB 사실 확인(4,727종목·1986~2026·수급 컬럼) 기반 목표 적합성 검토. 기존 V6 계획 반영도 45~55% 판정, 9개 Gap, 두 DB 역할 분리 결정, 3-Track 통합 계획 수립. | GJC | 본 문서 커밋 |

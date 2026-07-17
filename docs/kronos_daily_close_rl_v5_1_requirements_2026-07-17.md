# Kronos 일봉 종가매매 강화학습·대시보드 V5.1 요구사항 (2026-07-17)

> 상태: `REQUIREMENTS_RECORDED / IMPLEMENTATION_NOT_STARTED`
>
> 범위: 일봉 종가매매 강화학습 환경, 연구 결과 시각화, 연구 문서·Wiki 체계, 대시보드 정보구조와 울트라와이드 UX.
>
> 정직성 경계: 이 문서는 연구·구현 요구사항이다. 수익성, 모델 승격, 실거래 준비, 브로커 주문, paper-forward 또는 `GO`를 주장하지 않는다.

## 1. 목적

다음 개발의 기준값과 사용자 요구를 하나의 변경 불가 기준점으로 기록한다.

1. D일 15:20 시점의 가격을 연구용 종가 대용값으로 사용하는 일봉 종가매매 환경
2. 6,000만원 연구 계좌와 10개 slot 회계
3. KOSPI·KOSDAQ·RL 경제 NAV/수익률을 동일 기간과 동일 축에서 비교하는 실시간·최종 그래프
4. 기존 연구 문서를 삭제하거나 의미를 바꾸지 않는 Wiki·HTML 보고 체계
5. 울트라와이드 모니터에 적합한 V5.1 정보구조와 가독성 개선
6. Kronos 예측과 강화학습 연구를 명확히 분리한 Mission Control

## 2. 확정된 연구 환경

### 2.1 시간과 가격 가정

| 항목 | 확정값 | 의미 |
|---|---|---|
| 시간대 | `Asia/Seoul` | 한국 표준시 고정 |
| 의사결정 시각 | D일 `15:20:00` | 해당 시각까지 존재하는 정보만 관측 가능 |
| 매수 가격 | D일 15:20 봉의 종가 | 연구용 종가 대용값 |
| 가격 기준 식별자 제안 | `15:20_bar_close_proxy` | 공식 종가와 구분하기 위한 기계 식별자 |
| 공식 종가 여부 | `false` | 15:30 공식 종가로 주장하지 않음 |
| 청산 | D+N일 15:20 봉 종가 | 매수와 동일한 대용 가격 기준 사용 |

본 연구에서는 사용자 요청에 따라 **D일 15:20 봉 종가를 당일 종가로 가정**한다. 이는 연구 편의를 위한 대용값이며 한국거래소 15:30 공식 종가가 아니다. 모든 manifest, API, 그래프, 보고서에는 `15:20 종가 대용값`, `official_close=false` 또는 동등한 문구를 표시한다.

15:20 봉이 실제 데이터에 없으면 가장 가까운 값으로 자동 대체하지 않는다. 해당 일자·종목은 거래 불가 또는 `MISSING_1520_BAR`로 처리한다.

### 2.2 계좌와 slot 회계

| 항목 | 확정값 |
|---|---:|
| 초기 연구 자본 | 60,000,000원 |
| 총 slot 수 | 10 |
| slot당 주문 예산 | 5,000,000원 |
| 최대 투자 원금 | 50,000,000원 |
| 상시 여유 현금 | 10,000,000원 |
| 여유 현금 비율 | 16.6667% |
| 최대 목표 투자 비율 | 83.3333% |
| 공매도 | 초기 단계 금지 |
| 레버리지 | 초기 단계 금지 |

한 종목은 기본적으로 한 slot만 사용한다. 한 종목에 여러 slot을 중복 배정하는 기능은 초기 환경에서 금지하고 별도 ablation으로만 허용한다. 실제 주문 금액은 수수료를 포함해 5,000,000원을 초과할 수 없다.

### 2.3 비용 표기 원칙

사용자 화면과 신규 한글 문서에서는 `bp` 대신 `%`를 사용한다.

| 기존 의미 | 사용자 표시 |
|---|---:|
| 23bp | 0.23% |
| 46bp | 0.46% |
| 1.5bp | 0.015% |
| 20bp | 0.20% |

기존 artifact, JSON Schema, API field와 호환되는 `round_trip_cost_bp`, `base_23bp` 같은 내부 식별자는 즉시 이름을 바꾸지 않는다. 내부 정수값을 화면에서 100으로 나눠 정확한 `%`로 변환한다. 단순 문자열 치환은 금지한다.

초기 비용 계약:

- primary 왕복 비용: `0.23%`
- 비용 제거 control: `0.00%`
- 스트레스 control: `0.46%`
- 경제 NAV와 학습용 shaped reward는 분리

## 3. 추가로 동결해야 할 연구 선택값

다음 값은 구현 전에 사전등록에서 확정한다.

### 3.1 보유기간

권장 비교 집합은 H1·H3·H5다.

- H1: D일 15:20 매수 → D+1일 15:20 청산
- H3: D일 15:20 매수 → D+3일 15:20 청산
- H5: D일 15:20 매수 → D+5일 15:20 청산

보유기간은 validation에서 선택하고 untouched test OOS 확인 후 변경하지 않는다. 초기 기준 실험은 H1로 두고 H3/H5는 독립 variant로 관리하는 것을 권장한다.

### 3.2 universe

KOSPI·KOSDAQ 전체 종목의 point-in-time 소속 정보가 필요하다. 초기 권장 필터:

- 해당 거래일 당시 상장된 종목만 포함
- 거래정지, 관리종목, 상장폐지 절차 종목 제외
- 상장 후 60거래일 미만 제외
- 최근 20거래일 중위 거래대금 10억원 미만 제외
- 우선주·스팩·ETF·ETN 포함 여부를 명시적으로 고정
- `000250` 같은 6자리 종목코드를 문자열로 보존

현재 D1 universe authority가 완전히 닫히기 전에는 decision-grade 성과로 승격하지 않는다.

### 3.3 15:20 데이터 source

필수 필드:

- `session_date`
- `timestamp_kst`
- `symbol`
- `price_1520_close_proxy`
- `volume_to_1520`
- `amount_to_1520`
- 거래 가능 여부와 제외 사유
- 원본 DB/table/column 식별자
- source SHA-256 또는 SQLite snapshot identity

당일 최종 OHLCV만 있고 15:20 봉이 없으면 당일 완성 일봉을 15:20 값으로 위장하지 않는다.

### 3.4 로컬 DB 직접 점검 결과 (2026-07-17)

15:20 source 후보는 실제로 확인됐다.

| 항목 | 확인 결과 |
|---|---|
| DB | `_database/Stock_Database_ohlcv_5min.db` |
| 테이블 형식 | 종목별 `A######` |
| 컬럼 | `date`, `open`, `high`, `low`, `close`, `volume` |
| timestamp 형식 | `YYYYMMDDHHMM` 정수 |
| 표본 테이블 | `A000250` |
| 표본 15:20 행 수 | 1,739 |
| 표본 15:20 최초·최종 | `2019-05-09 15:20` ~ `2026-06-12 15:20` |

`A000250` 표본에서 15:20 행이 실제로 존재함을 확인했다. 다만 종목별 상장일·결측이 다르므로 전체 universe 기간은 별도 coverage audit으로 계산해야 한다. 5분봉 DB에는 거래대금 컬럼이 없으므로 `amount_to_1520`은 가격×거래량의 근사값으로 조용히 대체하지 않는다. 필요한 경우 검증된 별도 source를 연결하거나 필드를 `NOT_AVAILABLE`로 유지한다.

`_database/Stock_Database_ohlcv_1day.db`에는 `A` 및 `Q` 종목별 테이블만 확인됐고 KOSPI/KOSDAQ 공식 지수명 테이블은 발견되지 않았다. `_database/stock_tick_back.db`의 `stockinfo`는 종목의 KOSPI/KOSDAQ 구분에는 사용할 수 있지만 공식 지수 시계열을 제공한다는 증거는 아니다. 따라서 지수 overlay는 공식 지수 source 경로가 확인될 때까지 `BLOCKED_INDEX_SERIES_SOURCE`다. 임의의 종목 평균을 KOSPI/KOSDAQ으로 표시하지 않는다.

## 4. 강화학습 환경 권장 계약

### 4.1 observation

종목별 관측값:

- D일 15:20까지의 가격·거래량·거래대금
- 1/3/5/10/20일 과거 수익률
- 과거 변동성, 거래대금 순위, 유동성
- 이동평균 이격, 상대강도, 시장·업종 대비 상대수익률
- Kronos 예측값을 사용할 경우 모델·checkpoint·source hash를 별도 기록
- 결측 여부와 거래 가능 action mask

시장 관측값:

- KOSPI·KOSDAQ의 동일 시각 또는 과거 확정값
- 시장 변동성, breadth, 거래대금, regime

계좌 관측값:

- 현금, 사용 slot, 남은 slot
- 종목별 진입일, 보유일, 수량, 원가, 미실현 손익
- 누적 turnover와 drawdown

모든 feature는 날짜별 단면 정규화 또는 train-only robust normalization을 사용한다. validation/test 통계로 fit하지 않는다.

### 4.2 action

초기에는 수천 종목 전체에 직접 buy/sell을 부여하지 않는다. 다음 2단계 구조를 권장한다.

1. RULE 또는 supervised ranker가 거래 가능한 후보 30~50개 생성
2. PPO가 후보 중 최대 10개 slot, 현금 비중, 유지·교체 강도를 결정

초기 action 예시:

- 신규 매수 없음
- 1~10개 후보 선택
- 기존 보유 유지
- 만기 청산
- 위험 감소를 위한 일부 현금화

무효 action은 실행하지 않고 원인과 비율을 기록한다. 공매도·레버리지·중복 slot은 초기 action space에서 제외한다.

### 4.3 transition과 episode

- 하루에 한 번 15:20 의사결정
- H1/H3/H5 variant별 만기 청산
- 서로 다른 진입일의 포지션을 독립 lot로 추적
- episode 권장 길이 120거래일
- episode 종료 시 동일한 15:20 대용 가격으로 강제 청산
- train 시작일은 train 범위 안에서만 선택
- validation/test는 고정 시간순 replay

### 4.4 경제 NAV와 reward

경제 NAV:

```text
economic_nav = cash + marked_positions - accrued_costs
```

기본 학습 reward:

```text
reward_t = log(economic_nav_t / economic_nav_t-1)
         - turnover_penalty
         - drawdown_penalty
         - concentration_penalty
         - invalid_action_penalty
```

권장 시작 계수:

- turnover penalty: `0.05`
- drawdown penalty: `0.10`
- concentration penalty: `0.02`
- invalid action penalty: `1.00`

계수는 신규 사전등록에서 동결한다. 그래프와 성과 판정에는 shaped reward가 아니라 경제 NAV와 비용 차감 수익률을 사용한다.

## 5. KOSPI·KOSDAQ·RL 오버랩 그래프

### 5.1 목적

DB에 실제로 존재하는 평가 시작일부터 종료일까지 다음 세 series를 한 그래프에서 비교한다.

1. RL portfolio 경제 NAV
2. KOSPI 누적 수익률
3. KOSDAQ 누적 수익률

모든 series는 공통 시작일을 `100`으로 정규화하고 보조 표시에 누적 수익률 `%`를 제공한다. 원화 NAV와 지수 level을 그대로 같은 축에 혼합하지 않는다.

### 5.2 날짜 정렬

- 기본 범위: 세 series가 모두 존재하는 거래일의 교집합
- DB 최초·최종 날짜를 화면과 보고서에 명시
- 누락 날짜를 0% 수익률로 채우지 않음
- 휴장일은 제거하고 거래일 key로 join
- KOSPI/KOSDAQ 중 하나가 없으면 해당 series를 `MISSING`으로 표시
- train/validation/test 경계를 수직선 또는 배경 구간으로 표시

### 5.3 실시간과 최종 결과의 구분

학습 minibatch reward를 날짜별 수익률처럼 그리지 않는다.

- 학습 중: 최신 checkpoint를 고정된 validation 기간에 deterministic replay한 결과만 overlay 갱신
- 학습 진단: loss, raw reward, step은 별도 차트
- 최종 결과: 동결된 checkpoint로 validation 및 untouched test OOS를 재생한 경제 NAV
- 완료 후: 동일 run UID/revision의 final artifact를 표시

### 5.4 이벤트·API 권장 필드

- run UID와 revision
- phase, seed, fold, variant, checkpoint step
- `session_date`
- `economic_nav_krw`
- `portfolio_index_100`
- `portfolio_cumulative_return_pct`
- `kospi_index_100`, `kospi_cumulative_return_pct`
- `kosdaq_index_100`, `kosdaq_cumulative_return_pct`
- 비용 `0.23%`/`0.00%`/`0.46%`
- split, evaluation status, source hashes
- `price_basis=15:20_bar_close_proxy`
- `official_close=false`

## 6. 연구 문서·Wiki·HTML 보고 시스템

### 6.1 가능성 판정

현재 내용을 보존하면서 체계화할 수 있다. 기존 결과 문서를 일괄 재작성하지 않고 다음 방식으로 증분 관리한다.

1. 기존 `docs/` 문서는 불변 증거로 보존
2. `docs/wiki/`에 연구 원장과 문서 표준 추가
3. 원장에서 기존 문서를 상태·종류·날짜·관련 commit과 함께 연결
4. 새 문서부터 표준 양식 적용
5. 이전 문서는 의미를 바꾸지 않는 metadata/index만 추가

기존 `DocsTab.svelte`는 Markdown을 `marked`로 HTML 변환하고 DOMPurify로 정화해 표시한다. 따라서 Markdown을 원본으로 유지하고 HTML은 안전한 read-only view로 제공하는 구조가 적합하다.

### 6.2 문서 종류

- `PREREGISTRATION`: 가설·프로토콜·중단 기준을 실행 전에 동결
- `RESULT`: 실행 결과와 판정
- `INCIDENT`: 오류·원인·영향·수정·재발 방지
- `ADR`: 아키텍처 결정과 대안
- `HANDOFF`: 현재 상태와 재개 방법
- `RELEASE`: 변경점·검증·rollback·commit/tag
- `RUNBOOK`: 반복 운영 절차
- `RESEARCH_LEDGER`: 전체 연구 이력 색인

### 6.3 연구 결과 보고서 필수 항목

1. 제목
2. 문서 metadata
3. 목차
4. 연구 목적
5. 실행 일자와 데이터 기간
6. 사전등록 가설과 성공·실패 기준
7. 입력 데이터·universe·가격 기준·source hash
8. 환경·상태·행동·보상·알고리즘
9. 비용·자본·slot·체결 가정
10. train/validation/test 및 purge/embargo
11. baseline·control·ablation
12. 실행 결과
13. 원인 분석
14. 리스크·한계·blocker
15. 결론과 `GO/NO-GO/INCONCLUSIVE/NOT_RUN`
16. artifact와 SHA-256
17. 관련 문서
18. 관련 commit·branch·tag
19. 변경 히스토리

## 7. 대시보드 V5.1 UX·정보구조 요구

### 7.1 브랜드와 버전

내부 `v2_src`·`/static/v2/dist/` 경로는 변경하지 않는다. 사용자 표시 권장안:

```text
Kronos
AI Quant Reinforcement Learning
v5.1 · Updated 2026-07-17
```

`Kronos`를 제품·예측 기반 브랜드로 유지하고, `AI Quant Reinforcement Learning`을 연구 플랫폼 설명으로 사용한다. 정확한 영문 이름은 구현 전 사용자 확인 항목이다.

버전 버튼을 누르면 다음 이력이 표시되어야 한다.

- version
- 업데이트 날짜
- commit SHA
- release tag
- 주요 변경점
- 검증 결과
- 기본 UI 여부
- rollback 대상

### 7.2 좌측 navigation 권장 구조

기존 route id와 bookmark는 유지하고 label과 그룹만 재구성한다.

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

기존 `트레이딩 리서치` 아래 Daily OHLCV, RL 설명서, Trading Command Center의 혼합 구조는 Kronos와 RL 경계를 흐린다. Daily OHLCV 중 데이터 준비·예측 진단은 Kronos 쪽, 정책·환경·성과 증거는 Reinforcement Learning 쪽으로 화면 내부 section을 구분한다.

### 7.3 Mission Control

연구 라인을 다음 두 개의 1급 section으로 분리한다.

- `Kronos`: 예측 워크벤치, 예측 진단, 데이터·모델 계보
- `Reinforcement Learning`: 일봉 종가매매, 포트폴리오 RL, 인트라데이 RL, baseline/control, 학습 상태

두 section이 데이터를 공유해도 판정은 합치지 않는다. Kronos 예측 성능과 RL 정책 성과를 별도 score와 별도 verdict로 표시한다.

### 7.4 울트라와이드와 가독성

현재 content 최대폭은 1,480px이다. V5.1은 다음 breakpoint를 권장한다.

- 1,920px 미만: 기존 1,480px 중심 레이아웃 유지
- 1,920~2,559px: 최대 1,760~1,920px
- 2,560px 이상: 최대 2,240px, 12-column grid
- 긴 표·그래프는 가로폭을 우선 사용하되 본문 문장은 80ch 안팎 유지
- 좌측 brand 제목과 주요 nav 글자 크기 확대
- sidebar 접힘 상태에서도 tooltip과 접근 가능한 label 유지
- 우측 상세 rail은 독립적으로 접을 수 있게 하되 핵심 blocker를 숨기지 않음

현재 좌측 sidebar는 이미 collapse store와 header toggle을 갖고 있다. 사용자 요청의 “우측 탭 접힘”은 우측 상세 rail을 의미하는지 좌측 navigation을 의미하는지 구현 전 확인한다.

## 8. 구현 단계와 커밋 경계

### 단계 A — 문서 기준점

- 본 요구사항
- Wiki 연구 원장
- 문서 표준
- 별도 문서 commit

### 단계 B — 표시·정보구조

- `%` 비용 formatter
- V5.1 brand/version history
- sidebar 그룹 재배치와 가독성
- Mission Control의 Kronos/RL 분리
- 울트라와이드 layout
- frontend test, check, build, Chrome 검증

### 단계 C — 연구 환경

- 15:20 source adapter와 fail-closed 검증
- 6,000만원/10-slot/5백만원/1천만원 reserve 회계
- H1/H3/H5 variant
- observation/action/reward와 deterministic evaluator
- accounting oracle와 focused tests

### 단계 D — 오버랩 그래프와 보고서

- KOSPI/KOSDAQ point-in-time adapter
- checkpoint evaluation event/API
- live/final overlay chart
- 연구 report catalog/API/HTML view
- 날짜·split·비용·source hash 검증

### 단계 E — 사전등록과 실행

- 새 사전등록 승인
- 작은 smoke
- signal gate
- multi-seed full PPO
- untouched test OOS

## 9. 구현 전 사용자 확인 항목

| ID | 질문 | 권장 기본값 |
|---|---|---|
| U1 | 화면 영문 이름 | `Kronos / AI Quant Reinforcement Learning` |
| U2 | “우측 탭 접힘”의 대상 | 우측 상세 rail, 좌측 sidebar는 기존 접힘 유지 |
| U3 | 최초 공식 보유기간 | H1, H3/H5는 validation variant |
| U4 | ETF·ETN·스팩·우선주 포함 여부 | 모두 제외 후 보통주부터 시작 |
| U5 | 15:20 봉 source | `_database/Stock_Database_ohlcv_5min.db`; 전체 종목 coverage audit 필요 |
| U6 | KOSPI/KOSDAQ 공식 지수 source | 현재 로컬 DB에서 미발견; 경로 또는 공급 source 확인 필요 |
| U7 | 동시 보유 종목 중복 slot | 종목당 1 slot 고정 |
| U8 | 울트라와이드 기준 해상도 | 3,440×1,440 또는 실제 모니터 해상도 확인 |

## 10. 완료 기준

- 확정값이 protocol, environment, event, API, UI, report에서 동일하다.
- 15:20 대용값이 공식 종가로 표시되지 않는다.
- 사용자 표시에서 비용이 정확한 `%`로 변환된다.
- 초기 NAV 60,000,000원, 최대 투자 50,000,000원, reserve 10,000,000원이 모든 ledger에서 reconciliation된다.
- KOSPI·KOSDAQ·RL overlay가 같은 거래일과 같은 정규화 기준을 사용한다.
- train reward와 OOS 경제 NAV가 시각적으로 분리된다.
- 기존 `NO-GO`, `NOT_RUN`, blocker와 원본 문서가 보존된다.
- V3 기본 및 기존 route/bookmark는 별도 승인 전까지 유지된다.

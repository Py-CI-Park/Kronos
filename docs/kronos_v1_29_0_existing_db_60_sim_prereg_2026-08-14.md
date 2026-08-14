# Kronos v1.29.0-dev 기존 DB 60거래일 역사 시뮬레이션 사전등록

- 등록일: 2026-08-14 KST
- 연구 ID: `DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001`
- 브랜치: `codex/v1.29.0-dev-existing-db-60-sim`
- 연구 등급: `POST_HOC_EXISTING_DB_HISTORICAL_SIMULATION`
- 공식 Fresh OOS·미래 성과 검증: 아님
- promotion·paper/live·broker: 금지

## 1. 정직성 경계

현재 기존 DB의 마지막 날짜는 2026-06-12이고 등록된 미래 holdout cutoff 2026-08-14 이후 행은 0개다. 따라서 “미래 60거래일이 존재한다”고 가정해 미래/OOS 결과를 만들 수 없다.

이번 실행은 사용자의 기존 DB-only 요구를 최대한 수행하되, 실제로 존재하는 등록 score day 중 마지막 60개를 **역사 시뮬레이션**으로 재생한다. 결과가 좋아도 future, Fresh OOS, independent OOS, KRX-authoritative 또는 profitability verified로 부르지 않는다. 기존 `LOCAL_DB_FRESH_HOLDOUT`의 0/60 상태는 변하지 않는다.

## 2. 고정 window

| 항목 | 고정 값 |
|---|---|
| window 선택 | 등록 score dataset을 decision date 오름차순 정렬한 마지막 60일 |
| 시작 decision date | 2026-03-09 |
| 종료 decision date | 2026-06-11 |
| 원본 split 구성 | VALIDATION 14일 + TEST 46일 |
| reward 가용성 | 기존 DB에서 exact next-two-open을 읽되 누락일은 blocker로 공개 |
| 실제 거래 결정 | position overlap 방지를 위해 exit 이후 다음 decision만 선택 |

VALIDATION은 이미 정책 선택에 소비됐고 historical TEST feature와 기존 binary-CQL reward도 이미 소비됐다. 그러므로 window 전체가 경제적 독립 증거로는 오염됐다.

## 3. 고정 정책

Candidate는 allocation 002의 4행동 CQL checkpoint 5개다.

- CQL seed 0..4
- checkpoint SHA-256은 allocation 002 receipt와 실제 파일을 모두 검산

Controls:

- NO_TRADE/CASH
- RULE_ALWAYS_TOP5
- UNIFORM_RANDOM seed 0..4
- 각 CQL seed action histogram을 보존하는 paired action shuffle seed 0..4

행동:

- CASH
- INVEST_TOP3_EQUAL_SLOT
- INVEST_TOP5_EQUAL_SLOT
- INVEST_TOP10_EQUAL_SLOT

비용:

- 기본 왕복 23bp
- stress 왕복 46bp

## 4. 평가 계약

각 비용 시나리오에서 다음을 기록한다.

- 날짜별 action
- final NAV
- net return
- MDD
- 비용
- turnover
- action count
- filled slots
- reward log NAV

기술 gate:

1. CQL 5-seed 중앙값이 0%와 최고 no-trade/RULE/random control을 초과
2. 최소 4/5 CQL seed가 최고 control 초과
3. stress CQL 중앙값이 0% 초과
4. 모든 CQL seed MDD가 -20% 이상
5. CQL 중앙값이 paired shuffle 중앙값을 초과

기술 gate가 모두 통과해도 최종 판정은 `HISTORICAL_SIMULATION_ONLY_NO_PROMOTION`이다.

## 5. 금지 사항

- 결과 확인 후 checkpoint·seed·threshold·window 변경
- 60개 score day를 다른 기간으로 교체
- blocked day를 유리한 날로 대체
- seed 하나만 사후 선택
- 결과를 Local DB Fresh Holdout 60일로 소급 포장
- 경제 점수·live readiness 상향
- main 병합·정식 태그·paper/live 승격

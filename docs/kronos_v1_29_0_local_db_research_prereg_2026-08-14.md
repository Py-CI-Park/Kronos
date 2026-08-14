# Kronos v1.29.0-dev 기존 DB 전용 연구 사전등록

- 등록일: 2026-08-14 KST
- 브랜치: `codex/v1.29.0-dev-db-only-research`
- 데이터 범위: 기존 `_database`와 이미 생성된 immutable 연구 receipt만 사용
- 성격: 로컬 연구·반증·미래 holdout 준비
- 공식 PIT/OOS·수익성·paper/live 주장: 금지

## 1. 목적

외부 KRX 권위 구축 전에 기존 DB에서 모델·비용·대조군·데이터 품질을 먼저 반증한다. 기존 일봉 DB와 stockinfo를 버리거나 재작성하지 않고 read-only로 감사한다. Historical TEST 결과는 이미 알려졌으므로 새 성능 검증이 아니라 `POST_HOC_LOCAL_DB_BASELINE_ADJUDICATION`으로만 재분류한다.

## 2. 고정 실행 ID

| 단계 | ID | 허용 동작 |
|---|---|---|
| DB custody | `DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001` | DB hash·schema·날짜·중복 read-only 감사 |
| 기존 경제 증거 재판정 | `DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001` | 기존 CQL receipt만 검산, DB reward 재열람·재학습 금지 |
| 미래 holdout 등록 | `DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001` | payload 경로 없는 descriptor·no-read registration 작성 |

각 output은 create-exclusive이며 기존 경로를 덮어쓰지 않는다.

## 3. DB custody 계약

대상은 canonical root의 다음 파일이다.

- `_database/Stock_Database_ohlcv_1day.db`
- `_database/stock_tick_back.db:stockinfo`

감사 항목:

- whole-file SHA-256과 stable file descriptor
- canonical stockinfo query SHA-256
- 전체 일봉 table count와 row count
- `date/open/high/low/close/volume` schema coverage
- nonempty table coverage
- 중복 date table count
- 전체 최소·최대 date
- stockinfo row count
- leading-zero code 보존

가격 기준은 `UNKNOWN_LOCAL_DB_BASIS`, universe는 `CURRENT_SNAPSHOT_NOT_PIT`로 고정한다. 품질 검사가 PASS해도 독립 OOS·수익성·승격은 false다.

## 4. 경제 baseline 계약

기존 `DAILY_MARKET_CQL_2026_08_09_001` receipt를 그대로 검산한다.

- DQN seed 0..4
- CQL seed 0..4
- reward shuffle seed 0..4
- action shuffle seed 0..4
- no-trade
- cost-aware momentum RULE
- 기본 23bp, stress 46bp

기존 결과와 gate를 변경하지 않는다. Random policy control이 기존 historical receipt에 없으면 `RANDOM_POLICY_CONTROL_NOT_EVALUATED`를 명시하고 새 historical TEST 실행으로 보충하지 않는다. 판정은 `NO_GO_LOCAL_DB_BASELINE`이다.

## 5. Local DB Holdout 계약

- cutoff: `20260814`
- 첫 session: DB에 cutoff 이후 처음 추가되는 local trading session
- 정확한 길이: 60 trading days
- 행동: CASH, Top-3, Top-5, Top-10
- candidate: allocation 002의 CQL seed 0..4 checkpoint hash
- controls: no-trade 1, deterministic Top-5 RULE 1, uniform random seed 0..4, paired shuffle seed 0..4
- 비용: 23bp/46bp
- 기간 완료 전 feature/action/reward read 금지
- 결과 확인 후 retune·seed 선택·window 변경·retry 금지

이 holdout의 공식 명칭은 `LOCAL_DB_FRESH_HOLDOUT`이다. `official OOS`, `KRX-authoritative`, `profitability verified` 또는 `live ready`로 부르지 않는다.

초기 blocker:

- `FUTURE_60_TRADING_DAY_WINDOW_NOT_ACCUMULATED`
- `RANDOM_CONTROL_NOT_EVALUATED`
- `HUMAN_ONE_READ_APPROVAL_MISSING`
- `LOCAL_DB_NOT_OFFICIAL_PIT_AUTHORITY`

## 6. 분기 규칙

- 기존 baseline은 이미 NO-GO이며 재튜닝 근거로 사용하지 않는다.
- Local DB Holdout도 실패하면 새 가설 사전등록 전 연구를 종료한다.
- Local DB Holdout이 통과한 경우에만 Kiwoom provenance·KRX PIT·signed reviewer receipt 비용을 투입한다.
- D0/D1 및 공식 Fresh OOS PASS 전에는 main/tag/paper/live/broker를 금지한다.

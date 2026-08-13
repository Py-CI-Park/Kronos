# Kronos v1.29.0-dev D0/D1 권위 감사 및 다중 행동 RL 사전등록

- 사전등록일: 2026-08-10 KST
- 기준 커밋: `38b4270`
- 개발 브랜치: `codex/v1.29.0-dev-market-authority`
- 권위 감사 ID: `DAILY_MARKET_AUTHORITY_2026_08_10_001`
- 행동 선별 ID: `DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001`
- 연구 범위: 로컬 회고 연구, TRAIN/VALIDATION 진단 전용
- historical TEST: 읽지 않음
- Fresh OOS: `NOT_RUN_NO_READ`
- paper/live/broker/order: 차단

## 1. 목적

이 단계는 이전 CQL historical TEST의 `-10.191550%` 결과에 맞춰 재튜닝하지 않는다. 먼저 현재 일봉 DB가 가격 기준과 날짜별 투자 가능 종목군을 증명할 수 있는지 다시 감사하고, 동시에 기존 이진 행동의 한계를 TRAIN/VALIDATION 안에서만 분리한다.

기술적 질문은 세 가지다.

1. DB의 OHLC가 원주가·수정주가·total-return 중 무엇인지 독립적으로 증명할 수 있는가?
2. 각 의사결정일에 실제로 투자 가능했던 보통주 universe를 증명할 수 있는가?
3. `CASH`와 고정 Top-10만 선택하던 정책보다 다중 노출 행동이 validation에서 비용 후 손실을 줄이는가?

## 2. D0 가격 기준 감사 계약

| 항목 | 사전등록 기준 |
|---|---|
| 로컬 원천 | `_database/Stock_Database_ohlcv_1day.db`, 읽기 전용 |
| DB 필수 검사 | 파일 identity, SQLite table/column, 기업행사·분할계수·배당·수정주가 선언 필드 존재 여부 |
| 외부 설명 원천 | Kiwoom OpenAPI+ 공식 개발가이드 |
| 공식 가이드 관측 | 차트 TR 출력에는 `수정주가구분` 항목이 존재 |
| PASS 조건 | 로컬 DB 생성 계보가 가격·수정주가구분을 함께 보존하고, 분할·배당 처리 정책 및 dated source hash가 있음 |
| FAIL 조건 | 로컬 DB가 가격만 보존하거나 수집 옵션·기업행사 정책을 역추적할 수 없음 |

공식 가이드 URL:

- `https://download.kiwoom.com/web/openapi/kiwoom_openapi_plus_devguide_ver_1.1.pdf`

공식 가이드에 필드가 있다는 사실은 현재 DB가 그 필드를 보존했다는 증거가 아니다. DB에서 필드와 수집 계보가 발견되지 않으면 `D0_PRICE_BASIS_NOT_VERIFIED`를 유지한다.

## 3. D1 PIT universe 감사 계약

| 항목 | 사전등록 기준 |
|---|---|
| 로컬 원천 | 일봉 DB table 목록 + `stock_tick_back.db:stockinfo` |
| 기대 공식 원천 | KRX 상장회사/전종목 공식 다운로드 또는 검토된 동등 원천 |
| 현재 snapshot의 역할 | 현재 종목명·시장구분·instrument type 대조 |
| PIT 필수 필드 | `code`, `name`, `market`, `instrument_type`, `effective_from`, `effective_to`, `available_at`, `source_hash` |
| PASS 조건 | 모든 연구 의사결정일의 종목 membership을 당시 사용 가능 정보로 재구성 가능 |
| FAIL 조건 | 현재 snapshot만 있거나 상장폐지·시장 이전·종류주·ETF/ETN 이력을 복원할 수 없음 |

공식 KRX 원천:

- `https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT015`
- `https://global.krx.co.kr/contents/GLB/03/0308/0308010000/GLB0308010000.jsp`

현재 KRX snapshot을 확보하더라도 과거 모든 날짜의 PIT membership 증거가 되지는 않는다. 이 경우 D1은 부분 증거이며 `D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED`를 유지한다.

## 4. 다중 행동 RL 계약

| 항목 | 고정값 |
|---|---|
| 의사결정 | D 종가 이후 |
| 체결 | D+1 정확한 시가 진입, 다음 정확한 시가 청산 |
| 상태 | 기존 인과 상태 172차원 |
| 행동 0 | `CASH` — 전액 현금 |
| 행동 1 | `INVEST_TOP3_EQUAL_SLOT` — 최대 1,500만원 노출 |
| 행동 2 | `INVEST_TOP5_EQUAL_SLOT` — 최대 2,500만원 노출 |
| 행동 3 | `INVEST_TOP10_EQUAL_SLOT` — 최대 5,000만원 노출 |
| 초기 NAV | 6,000만원 |
| 현금 하한 | 1,000만원 |
| 슬롯 예산 | 종목당 최대 500만원 |
| 기본 비용 | 왕복 0.230% |
| 스트레스 비용 | 왕복 0.460% |
| 알고리즘 | DQN, CQL |
| 시드 | 0, 1, 2, 3, 4 |
| 모델 수 | 10개 |
| 은닉층 | 128, 64 |
| 학습률 | 0.0003 |
| discount | 0.95 |
| CQL alpha | DQN 0.0, CQL 1.0 |
| gradient steps | 600 |
| batch size | 256 |

Top-3과 Top-5는 남은 슬롯 예산을 다른 종목에 재분배하지 않는다. 따라서 행동이 작은 종목 수를 고르면 총 시장 노출도 함께 줄어든다. 이것이 이번 abstention/노출 제어 가설의 핵심이다.

## 5. 데이터 개봉 경계

| split | reward 읽기 | 용도 |
|---|---|---|
| TRAIN | 허용 | 4행동 탐색 궤적과 Q 학습 |
| VALIDATION | 허용 | 고정 정책 선별 gate |
| historical TEST | **금지** | 이전 연구에서 이미 소비됨 |
| Fresh OOS | **금지** | 권위·사전등록·사람 승인 전 봉인 |

이 실행은 새로운 경제성 TEST가 아니다. 결과가 양수여도 `VALIDATION_CANDIDATE_ONLY`이며 수익성·일반화·실전 가능성을 주장하지 않는다.

## 6. Validation 선별 gate

CQL 5시드 집계에 다음 기준을 적용한다.

| gate | PASS 조건 |
|---|---|
| `CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE` | 기본 비용 중앙값 > 0% |
| `CQL_VALIDATION_FOUR_OF_FIVE_POSITIVE` | 최소 4/5 시드 기본 비용 수익률 > 0% |
| `CQL_VALIDATION_STRESS_MEDIAN_POSITIVE` | 스트레스 비용 중앙값 > 0% |
| `CQL_VALIDATION_ACTION_DIVERSITY` | 최소 4/5 시드가 3개 이상의 행동을 사용 |
| `CQL_VALIDATION_BEATS_DQN_MEDIAN` | CQL 기본 비용 중앙값 > DQN 중앙값 |
| `CQL_VALIDATION_MDD_WITHIN_20_PERCENT` | 모든 CQL 시드 MDD >= -20% |

모든 기준을 통과해도 다음 단계 후보 자격만 얻는다. D0/D1가 차단이면 새 TEST 생성·개봉과 promotion은 계속 금지한다.

## 7. 산출물

| 산출물 | 위치 |
|---|---|
| 권위 요약 | `webui/rl_runs/daily_market_authority/DAILY_MARKET_AUTHORITY_2026_08_10_001/summary.json` |
| 권위 receipt | 같은 디렉터리 `authority_receipt.json` |
| 행동 선별 요약 | `webui/rl_runs/daily_market_allocation/DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001/summary.json` |
| 행동 선별 receipt | 같은 디렉터리 `validation_receipt.json` |
| 모델 | 같은 디렉터리 `models/{DQN,CQL}/seed-*.kq` |
| 행동 ledger | 같은 디렉터리 `validation_action_ledger.jsonl` |

모델과 실행 산출물은 immutable evidence로 보존하지만 Git에는 커밋하지 않는다. Git에는 소스·테스트·사전등록·결과 문서만 기록한다.

## 8. 중단 조건

- DB 또는 산출물 경로가 symlink/junction 경계를 벗어나면 fail-closed.
- 가격 기준 또는 PIT universe를 추정으로 `VERIFIED` 처리하지 않음.
- historical TEST/Fresh OOS 접근 시 실행 실패.
- 손상·비유한 모델 가중치, 잘못된 action index, 현금 하한 위반 시 실행 실패.
- 단일 시드 양수를 사후 선택하지 않음.

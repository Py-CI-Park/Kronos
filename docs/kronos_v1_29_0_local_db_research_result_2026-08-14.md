# Kronos v1.29.0-dev 기존 DB 전용 연구 실행 결과

- 완료일: 2026-08-14 KST
- 브랜치: `codex/v1.29.0-dev-db-only-research`
- 기준 develop: `9218e47`
- 데이터: 기존 canonical `_database`만 사용
- 판정: `NO_GO_LOCAL_DB_BASELINE`
- Local DB Holdout: `REGISTERED_SEALED_NO_READ`
- 공식 OOS·수익성·paper/live: 차단

## 1. 계획 대비 실행 결과

| 우선순위 | 계획 | 실제 실행 | 결과 | 계획 대비 |
|---:|---|---|---|---:|
| P0 | 기존 DB SHA·schema custody | 1GB 일봉 DB whole-file SHA, 4,727 table 전체 schema/date/duplicate scan, stockinfo canonical query | PASS, local research 허용 | 100% |
| P0 | 가격·universe 한계 명시 | price basis unknown, current stockinfo snapshot not PIT를 typed blocker로 고정 | PASS | 100% |
| P0 | 기존 비용·baseline·seed 검산 | historical receipt만 재검산, DB reward·가격 재열람 및 재학습 없음 | `NO_GO_LOCAL_DB_BASELINE` | 100% |
| P0 | 23bp/46bp 비용 | 기존 20모델 전 시나리오 검산 | PASS | 100% |
| P0 | no-trade·RULE·shuffle·5 seed | 기존 receipt의 no-trade/RULE 및 두 shuffle 5시드 확인 | PASS | 100% |
| P0 | random control | 기존 historical receipt에 없음 | historical 재실행 금지, holdout용 seed 0..4 commitment만 고정 | 준비 100%, 평가 0% |
| P0 | Local DB Fresh Holdout | cutoff 이후 정확히 60 trading days, 4행동, CQL 5개, controls 고정 | `REGISTERED_SEALED_NO_READ` | 등록 100%, 축적 0/60 |
| P1 | KRX/Kiwoom 권위 | Local holdout 결과 전까지 연기 | 미실행 | 계획 일치 |
| 금지 | main/tag/paper/live | 실행하지 않음 | 차단 유지 | 100% |

## 2. 실제 DB custody 결과

연구 ID: `DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001`

| 항목 | 실제 값 |
|---|---:|
| 일봉 DB 크기 | 1,009,057,792 bytes |
| 일봉 DB SHA-256 | `9a363b33a9c2d125f3df7010e54efcec9d53fd6a40dbf16a39b538c20247a09c` |
| 일봉 table | 4,727 |
| nonempty table | 4,727 |
| 필수 schema 충족 | 4,727/4,727 |
| 전체 row | 14,691,020 |
| 중복 date table | 0 |
| 최초 date | 1986-04-15 |
| 마지막 date | 2026-06-12 |
| 명시적 `수정주가구분` table | 0 |
| stockinfo row | 4,229 |
| stockinfo canonical SHA-256 | `ce76f768eae993d910eeb66d8b1cdd58748cd35127f3e2c2b3efb6524105f144` |
| leading-zero code | 보존 |

품질 검사는 PASS했지만 다음 blocker는 유지한다.

- `D0_PRICE_BASIS_UNKNOWN_LOCAL_DB`
- `D1_CURRENT_SNAPSHOT_NOT_PIT`

따라서 `local_research_allowed=true`이지만 independent OOS·profitability·promotion·paper/live는 모두 false다.

## 3. 기존 DB 경제 baseline 재판정

연구 ID: `DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001`

| 항목 | 결과 |
|---|---:|
| 원본 experiment SHA-256 | `1b3210ab5e488d615bc8bae02742bd30c265106824835d3a0fd79a2dff239859` |
| DQN | seed 0..4 |
| CQL | seed 0..4 |
| reward shuffle | seed 0..4 |
| action shuffle | seed 0..4 |
| 기본 비용 | 23bp |
| stress 비용 | 46bp |
| 최고 control | no-trade 0.0% |
| CQL 기본 중앙값 | -10.1915504852% |
| CQL stress 중앙값 | -12.3911378390% |
| 판정 | `NO_GO_LOCAL_DB_BASELINE` |

실패 항목:

- CQL 중앙값이 0%와 최고 control을 넘지 못함
- 4/5 seed가 control을 넘지 못함
- bootstrap 하한이 양수가 아님
- stress 중앙값이 양수가 아님
- 최악 MDD가 -20% 경계를 위반
- random policy historical control이 없음
- historical TEST가 이미 오염됨

Random control을 보충하기 위해 같은 historical TEST를 다시 실행하지 않았다. 결과 확인 후 control·seed·threshold를 추가하면 새로운 독립 검증이 아니기 때문이다.

## 4. Local DB Holdout 등록

연구 ID: `DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001`

| 항목 | 고정 값 |
|---|---|
| 상태 | `REGISTERED_SEALED_NO_READ` |
| cutoff | `20260814` |
| 첫 session 규칙 | cutoff 이후 DB에 처음 추가되는 local session |
| 요구 기간 | 정확히 60 trading days |
| 현재 축적 | 0/60 |
| 행동 | CASH, Top-3, Top-5, Top-10 |
| candidate | allocation 002 CQL seed 0..4 |
| controls | no-trade, Top-5 RULE, random 0..4, paired shuffle 0..4 |
| 비용 | 23bp, 46bp |
| descriptor SHA-256 | `db68efe62f6675bb51de8957eb7a9aa0af0b4b580ad7cd9e97a5784f5e3783aa` |
| feature/action/reward read | 모두 false |
| one-read authorization | false |

현재 DB 마지막 날짜가 2026-06-12이므로 cutoff 2026-08-14보다 이전이다. DB가 정상 갱신되어 cutoff 이후 60개 session이 쌓이기 전에는 holdout 평가를 시작할 수 없다.

초기 blocker:

- `FUTURE_60_TRADING_DAY_WINDOW_NOT_ACCUMULATED`
- `RANDOM_CONTROL_NOT_EVALUATED`
- `HUMAN_ONE_READ_APPROVAL_MISSING`
- `LOCAL_DB_NOT_OFFICIAL_PIT_AUTHORITY`

## 5. 산출물 identity

| 파일 | bytes | SHA-256 |
|---|---:|---|
| custody receipt | 1,664 | `f8e56c86a46dddd82cc5bff81eebad3837f590755cb36bce1e7bb4db31dd74ed` |
| economic gate | 2,215 | `b1d423041a75047781786e480d4c66b46e55e9b483e5dd3c43d09cbac2282d47` |
| holdout descriptor | 5,235 | `db68efe62f6675bb51de8957eb7a9aa0af0b4b580ad7cd9e97a5784f5e3783aa` |
| holdout registration | 621 | `db0a1ba834141132282f0a2f858ab0766d29e7da3f329b12ef4aacb4e3804271` |

생성 산출물은 canonical `webui/rl_runs/daily_market_local_db/`에 보존하고 Git에는 넣지 않는다.

## 6. 검증

| 검증 | 결과 |
|---|---:|
| 신규 DB-only 집중 테스트 | 14 passed |
| 확장 daily-market/V6/security 회귀 | 198 passed |
| bundle/route | 18 passed |
| Bun frontend | 473 passed, 0 failed |
| Svelte check | 620 files, 0 errors, 0 warnings |
| BasedPyright | 0 errors, 0 warnings |
| Ruff·format·diff-check | PASS |
| Chromium 공식 페이지 | 8/8 identity PASS |
| horizontal overflow | 0 |
| 화면 오류 | 0 |

Frontend dependency 설치 시 Node 22는 허용 범위였으나 npm 12는 package 권고 9~11 밖이라는 warning이 있었다. 검증 실패는 없었지만 release 환경은 npm 11 이하로 맞춘다.

## 7. 점수와 결론

| 점수 축 | 현재 |
|---|---:|
| 제품·UI 구현 | 94/100 |
| 프로그램 진행 | 71/100 |
| 경제 모델 증거 | 20/100 |
| live readiness | 0/100 |
| 이번 즉시 실행 가능한 DB-only 계획 | 100% |

기존 DB는 구조·중복·식별자 측면에서 로컬 연구에 사용할 수 있다. 그러나 기존 경제 결과는 여전히 NO-GO이고, 가격 기준·PIT universe는 미확정이다. KRX 작업을 지금 수행하지 않는 결정은 유지한다. Local DB Holdout 60일이 완료되고 사전 고정 정책이 비용·control gate를 통과한 경우에만 D0/D1 공식 권위 비용을 투입한다.

main 병합, 정식 태그, paper/live, broker 주문 및 수익성 주장은 계속 금지한다.

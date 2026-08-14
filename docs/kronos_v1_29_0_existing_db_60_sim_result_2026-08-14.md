# Kronos v1.29.0-dev 기존 DB 60거래일 역사 시뮬레이션 결과

- 실행일: 2026-08-14 KST
- 연구 ID: `DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001`
- 판정: `HISTORICAL_SIMULATION_ONLY_NO_PROMOTION`
- 기술 gate: FAIL
- 데이터: 기존 canonical DB와 기존 allocation 002 checkpoint만 사용
- Fresh OOS·미래 검증·수익성 검증: 아님

## 1. 요청 적용 방식

기존 DB 마지막 날짜는 2026-06-12이고 미래 holdout cutoff 2026-08-14 이후 행은 실제로 존재하지 않는다. 존재하지 않는 60일을 미래 데이터라고 가정해 생성하지 않았다.

대신 등록 score dataset에서 실제 존재하는 마지막 60개 decision day를 고정하고, 기존 DB exact-open 가격으로 한 번만 역사 재생했다. 이 window는 VALIDATION과 historical TEST가 이미 소비된 오염 구간이므로 모델 개발 파이프라인의 반증 결과로만 사용한다. 등록된 진짜 `LOCAL_DB_FRESH_HOLDOUT`은 계속 0/60이다.

| 요청·계획 | 실제 적용 | 결과 |
|---|---|---|
| 기존 DB만 사용 | DB·score/panel·allocation 002 checkpoint 외 입력 없음 | 완료 |
| 미래 60일 가정 | 존재하지 않는 행은 생성하지 않고 마지막 기존 60 score day로 대체 | 역사 시뮬레이션 |
| CQL 5 seed | seed 0..4 checkpoint hash 검산 후 평가 | 완료 |
| baseline·control | cash, Top5 RULE, random 5, paired shuffle 5 | 완료 |
| 비용 | 모든 정책에 23bp·46bp | 완료 |
| 1회 실행·immutable artifact | 사전등록 commit 후 create-exclusive 실행 | 완료 |
| 공식 OOS·수익성 승격 | 오염 window이므로 차단 | 계획대로 미수행 |

## 2. Window 실행 결과

| 항목 | 결과 |
|---|---:|
| score day | 60 |
| 시작 | 2026-03-09 |
| 종료 | 2026-06-11 |
| VALIDATION | 14 |
| TEST | 46 |
| reward 가용일 | 59 |
| blocked | 1 (`2026-06-11:002220:MISSING_EXIT_OPEN`) |
| non-overlapping 실제 decision | 30 |
| 정책 | 17 |
| 비용 시나리오 | 2 |
| 전체 trajectory | 34 |
| ledger row | 1,020 |

60 score day를 60번 모두 거래하지 않은 이유는 D+1 open 진입, D+2 open 청산 포지션이 서로 겹치지 않게 했기 때문이다.

## 3. CQL 5-seed 결과

| Seed | 23bp 순수익률 | 23bp MDD | 46bp 순수익률 | 46bp MDD |
|---:|---:|---:|---:|---:|
| 0 | -10.844286% | -15.420345% | -13.559467% | -16.638313% |
| 1 | -6.840827% | -9.172571% | -8.327837% | -9.616417% |
| 2 | -8.002465% | -8.233106% | -10.513600% | -10.645264% |
| 3 | -7.572390% | -13.353420% | -9.948595% | -14.135626% |
| 4 | -6.241003% | -10.776608% | -8.464841% | -11.894291% |
| **중앙값** | **-7.572390%** | — | **-9.948595%** | — |

5개 CQL seed 모두 기본 비용과 stress 비용에서 손실이었다.

## 4. Baseline과 control

### 기본 23bp

| 정책 | 순수익률 | MDD |
|---|---:|---:|
| NO_TRADE | 0.000000% | 0.000000% |
| RULE_ALWAYS_TOP5 | -11.356049% | -19.331429% |
| 최고 random (`seed 1`) | +0.005106% | -8.823060% |
| Random 5-seed 중앙값 | -7.060540% | — |
| Paired shuffle 5-seed 중앙값 | -3.807412% | — |
| 최고 paired shuffle (`seed 1`) | +2.246462% | -4.536548% |
| CQL 5-seed 중앙값 | **-7.572390%** | — |

### Stress 46bp

| 정책 | 순수익률 |
|---|---:|
| NO_TRADE | 0.000000% |
| RULE_ALWAYS_TOP5 | -14.154221% |
| 최고 random (`seed 1`) | -1.592357% |
| 최고 paired shuffle (`seed 1`) | +0.720936% |
| CQL 5-seed 중앙값 | **-9.948595%** |

CQL 중앙값은 no-trade, 최고 random, paired shuffle 중앙값을 모두 이기지 못했다. 이는 정책의 시간 순서가 학습된 유효 신호라는 근거도 만들지 못한다.

## 5. Gate 결과

| Gate | 결과 | 관측값 |
|---|---|---|
| CQL 중앙값 > 0 및 최고 control | FAIL | -7.572390% vs +0.005106% |
| 4/5 CQL seed가 최고 control 초과 | FAIL | 0/5 |
| stress 중앙값 > 0 | FAIL | -9.948595% |
| CQL MDD -20% 이내 | PASS | 최악 -15.420345% |
| CQL 중앙값 > paired shuffle 중앙값 | FAIL | -7.572390% vs -3.807412% |

기술 gate는 1/5만 통과했다.

## 6. Artifact identity

| 파일 | bytes | SHA-256 |
|---|---:|---|
| `summary.json` | 987 | `475e791d78686f5e3205e32f2a022a3de79487343cc4d12b9e04a877ca689169` |
| `simulation_receipt.json` | 24,485 | `c55aecd917ea2d8213f778ae8cce04fe981f78a4fb7f7bbdc79999fb8ba274d2` |
| `action_ledger.jsonl` | 370,000 | `997ecc1e5932fb5d2ba01feafb2119adbcc0a026a30d553f8aa5f30b76631adb` |
| `bundle_manifest.json` | 704 | `ca8f837bc4b8148405f2e576a12326a91c6c800479c3390efea559bacd41b6b6` |

산출물은 canonical `webui/rl_runs/daily_market_existing_db_sim/DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001/`에 create-exclusive로 보존하며 Git에는 커밋하지 않는다.

## 7. 검증

| 검증 | 결과 |
|---|---:|
| 신규 simulation 집중 테스트 | 5 passed |
| 확장 daily-market/V6/security | 204 passed |
| Bun frontend | 473 passed, 0 failed |
| Svelte check | 620 files, 0 errors, 0 warnings |
| BasedPyright | 0 errors, 0 warnings |
| Ruff·format·bundle·diff check | PASS |
| Strict publication bundle | pinned manifest SHA 검증, VALID |
| receipt·summary 재작성 후 manifest 재hash 공격 | INVALID |
| 현재 writer로 artifact 재생성 | 4/4 byte-exact |
| V6 research catalog | CQL·dataset·NO_PROMOTION 상태 노출 PASS |
| Chromium 공식 페이지 | 8/8 identity PASS |
| horizontal overflow | 0 |
| 화면/API 오류 | 0 |

Artifact를 생성한 source commit은 `e92c568`이며 receipt에 고정됐다. 이후 source 변경은 기존 artifact를 덮어쓰지 않고 publication 검증과 dashboard metadata 경계를 강화하는 데만 사용했다. 동일 연구 ID 재실행은 `HISTORICAL_SIMULATION_OUTPUT_UNTRUSTED`로 거부됨을 확인했다.

Node 22는 허용 범위였으나 npm 12는 프로젝트 권고 9~11 밖이라는 warning이 있었다. 테스트 실패는 없었다.

## 8. 결론

기존 DB만으로 수행 가능한 60 score-day CQL·baseline·random·shuffle·비용 stress 역사 시뮬레이션은 완료했다. 결과는 명확한 `NO-GO`다.

- 경제적으로 성공한 강화학습 모델: 없음
- 특정 seed 승격: 금지
- 추가 사후 튜닝: 금지
- 경제 증거 점수: 20/100 유지
- live readiness: 0/100 유지
- KRX/Kiwoom 권위 비용 투입: 보류
- Local DB Fresh Holdout: 여전히 0/60

새로운 미래 데이터가 없는 상태에서 기존 DB로 더 반복 실행하면 검증이 아니라 동일 오염 구간에 대한 사후 최적화가 된다. 새 가설은 별도 사전등록 없이는 진행하지 않는다.

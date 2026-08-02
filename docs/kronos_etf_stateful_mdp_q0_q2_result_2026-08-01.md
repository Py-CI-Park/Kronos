# Kronos ETF Stateful MDP Q0~Q2 개발·연구 결과

- 실행일: 2026-08-01 KST
- 부모 연구 브랜치: `codex/rl-etf-stateful-mdp-v1`
- 실행 브랜치: `codex/rl-etf-q0-q2-foundation-v1`
- 사전등록: `kronos_etf_stateful_mdp_q0_prereg_2026-08-01.json`
- 로컬 receipt: `.omx/artifacts/etf_stateful_q0_q2/foundation_receipt.json`
- receipt SHA-256: `5547b7379ccd9b82e1fb55fa56bcaebc77a8b51f4fb7f7a20a8921fb796e669c`
- 전체 판정: **`BLOCKED_Q1_DATA_CUSTODY`**
- Q3 PPO: **`NOT_RUN / LOCKED`**
- live·paper·broker: **모두 금지**

## 1. 한 줄 성과

강화학습 모델의 상태 전이와 23bp 회계를 검증할 수 있는 Q2-B 환경은 3/3 seed에서 통과했지만, 로컬 ETF 데이터 custody가 불완전하고 20일 momentum canary가 23bp에서 실패했으므로 실제 PPO 모델 학습은 시작하지 않았다.

## 2. 전체 결과표

| 단계 | 목적 | 실행 결과 | 판정 | 다음 행동 |
|---:|---|---|---|---|
| Q0 | 가설·비용·split·seed·잠금 사전등록 | 문서와 JSON 커밋 | `PASS_PREREG` | 기준 변경 금지 |
| Q1 | point-in-time/as-of/total-return 데이터 감사 | 구조 7개 통과, custody 4개 실패 | `BLOCKED_DATA_CUSTODY` | 공식 과거 metadata 확보 |
| Q2-A | 20일 momentum supervised floor | 23bp -9.23bp, delta -2.33bp, 1/5 fold | `NO_GO_SIGNAL_FLOOR` | 새 데이터에서 재검증 또는 가설 종료 |
| Q2-B | action-dependent stateful 환경 | known policy 3/3 seed 통과 | `PASS_SYNTHETIC_STATEFUL_MDP` | Q3 전까지 환경만 보존 |
| Q3 | Residual MLP PPO pilot | 실행하지 않음 | `LOCKED_NOT_RUN` | Q1·Q2-A 모두 통과 필요 |
| D7 | 기존 top-5 Fresh OOS | 읽지 않음 | `LOCKED_NOT_RUN_NO_READ` | 기존 계보와 분리 유지 |

## 3. 개발 완료 범위

| 모듈 | 책임 | 상태 |
|---|---|---|
| `stom_rl/etf_research/data.py` | SQLite `mode=ro`, 6자리 코드, OHLC·날짜·custody gate | 완료 |
| `stom_rl/etf_research/signal_floor.py` | 20일 momentum, 5일 horizon, 5-fold, 3 shuffle seed | 완료 |
| `stom_rl/etf_research/environment.py` | cash·units·target position·open fill·close mark·비용 | 완료 |
| `stom_rl/etf_research/synthetic_gate.py` | 알려진 정책·always-long·no-trade 비교 | 완료 |
| `stom_rl/etf_research/runner.py` | Q1/Q2 실행, overall fail-closed, JSON receipt | 완료 |
| `programPages.ts` | 전체 12페이지 ETF lane 상태 | 완료 |
| `programCapabilities.ts` | Q0~Q3 가능/부분/차단 역량 | 완료 |
| `programExecution.ts` | 실행 브랜치·stage·receipt SHA·다음 행동 | 완료 |

이 구현은 학습 버튼이나 주문 기능을 추가하지 않는다. 연구 runner와 대시보드는 증거를 생성·조회하는 범위에 한정한다.

## 4. Q1 데이터 감사 상세

### 4.1 실제 DB 범위

| 항목 | 값 |
|---|---|
| DB | `_database/Stock_Database_ohlcv_1day.db` |
| 모드 | SQLite URI `mode=ro` |
| 전체 테이블 | 4,727 |
| canary code | `069500`, `102110`, `091160`, `091170` |
| 공통 최신 일자 | 2026-06-12 |
| 확인된 장기 row | 각 4,485~5,840 |
| 최종 cross-section 평가일 | 4,461 |
| 생성 signal sample | 20,071 |

canary 네 코드는 파이프라인 검증 대상이며 최종 64개 TIGER ETF universe가 아니다.

### 4.2 Gate 결과

| Gate | 결과 | 증거·해석 |
|---|---|---|
| `READ_ONLY_SOURCE` | PASS | SQLite `mode=ro` |
| `LEADING_ZERO_PRESERVED` | PASS | 코드 문자열 6자리 유지 |
| `NONEMPTY_SERIES` | PASS | 네 테이블 모두 장기 OHLCV 존재 |
| `STRICT_DATE_ORDER` | PASS | 중복·역순 없음 |
| `VALID_OHLC` | PASS | 양수 가격·low/high envelope |
| `NO_BACKFILL` | PASS | 신규 코드에서 미래 bfill 사용 없음 |
| `FOLD_LOCAL_SCALER` | PASS | canary에는 scaler 없음; 후속 train-only 강제 |
| `POINT_IN_TIME_UNIVERSE` | FAIL | 당시 ETF 구성 snapshot 없음 |
| `OFFICIAL_INSTRUMENT_IDENTITY` | FAIL | 공식 상품유형·이름 snapshot 없음 |
| `AVAILABLE_AT_CUTOFF` | FAIL | 외부 피처 발표시각 custody 없음 |
| `TOTAL_RETURN_CONTRACT` | FAIL | 분배금·수정주가 계약 없음 |

OHLCV 무결성이 좋아도 마지막 네 항목을 추정으로 채우지 않았다. 따라서 Q1은 fail-closed다.

## 5. Q2-A 실제 canary 결과

### 5.1 실험 계약

| 축 | 값 |
|---|---|
| Feature | 전일 종가까지의 20일 momentum |
| Entry | 다음 거래일 시가 |
| Exit | 5거래일째 종가 |
| Selection | 완전한 4-code cross-section에서 top-1 |
| Primary cost | 왕복 23bp |
| Diagnostic cost | 왕복 9bp |
| Split | chronological 5-fold |
| Controls | shuffle seed 0·1·2, equal-weight, no-trade |

평가일에 네 코드가 모두 존재하지 않으면 cross-sectional ranking에서 제외했다. 과거에 한 ETF만 존재했던 날짜가 native 성과로 섞이는 문제를 차단한 결과다.

### 5.2 핵심 지표

| 지표 | 결과 | Gate | 판정 |
|---|---:|---:|---|
| Native 23bp 평균 | **-9.2271bp** | `>0` | FAIL |
| Native 9bp 평균 | **+4.7729bp** | 진단 전용 | 승격 불가 |
| Shuffle 23bp 평균 | **-6.8930bp** | 비교 | native가 더 나쁨 |
| Native−shuffle | **-2.3341bp** | `≥10bp` | FAIL |
| Equal-weight 23bp | **-5.7508bp** | baseline | native가 더 나쁨 |
| Positive folds | **1/5** | `≥4/5` | FAIL |
| Positive seed comparisons | **0/3** | `≥2/3` | FAIL |
| Non-overlap diagnostic MDD | **94.79%** | `≤25%` | FAIL |

### 5.3 Fold 결과

| Fold | 평가일 | 23bp 평균 | 판정 |
|---:|---:|---:|---|
| 0 | 893 | -56.04bp | FAIL |
| 1 | 892 | -29.10bp | FAIL |
| 2 | 892 | -28.83bp | FAIL |
| 3 | 892 | -9.59bp | FAIL |
| 4 | 892 | +77.48bp | PASS |

마지막 fold 하나만 매우 강하다. 이는 최근 regime 가설을 만들 수 있는 관찰이지만 전체 기간 alpha 증거는 아니다. 마지막 fold를 본 뒤 horizon·feature를 맞추면 사후 과적합이 되므로 별도 amendment 없이는 재튜닝하지 않는다.

### 5.4 9bp가 양수인데도 NO-GO인 이유

| 이유 | 설명 |
|---|---|
| Primary 기준 | 사전등록에서 23bp를 primary로 고정함 |
| Control 실패 | native가 shuffle과 equal-weight보다 낮음 |
| 시간 안정성 | 양수 fold가 1/5뿐임 |
| Drawdown | 25% 제한을 크게 초과함 |
| 데이터 custody | 공식 point-in-time·total-return 증거가 없음 |

따라서 +4.77bp는 비용 민감도 진단일 뿐 PPO를 시작할 근거가 아니다.

## 6. Q2-B stateful 환경 결과

### 6.1 확인한 전이

1. 목표 포지션 `[0,1]` 행동이 다음 cash와 units를 변경한다.
2. 매매는 bar open에 처리하고 portfolio는 bar close에 평가한다.
3. 거래 notional에 편도 11.5bp를 적용한다.
4. 동일 가격에서 전량 진입·청산하면 약 22.99bp가 차감된다.
5. no-trade는 turnover와 비용이 0이다.
6. 다음 state는 cumulative return, drawdown, position ratio를 제공한다.

### 6.2 합성 결과

| Seed | Known policy | Always long | No trade | 판정 |
|---:|---:|---:|---:|---|
| 0 | 1,261,351.61 | 880,443.99 | 1,000,000 | PASS |
| 1 | 1,250,298.87 | 881,925.71 | 1,000,000 | PASS |
| 2 | 1,253,808.72 | 884,595.78 | 1,000,000 | PASS |

이는 환경이 action-dependent하고 알려진 상태 신호를 학습할 수 있다는 구현 증거다. 실제 시장 예측 성과나 수익성 증거는 아니다.

## 7. 현재 점수

| 평가 대상 | 점수 | 이전 대비 | 의미 |
|---|---:|---:|---|
| 기존 D6R2 모델 성과 | **18/100** | 0 | 기존 NO-GO 유지 |
| ETF lane 설계 준비도 | **44/100** | 0 | 외부 설계 검토 기반, 성능점수 아님 |
| ETF Q0~Q2 실행 완성도 | **72/100** | 신규 | 사전등록·runner·테스트·UI 완료, Q1/Q2-A 실패 |
| Kronos 연구 플랫폼 | **90/100** | 0 | 실패를 숨기지 않는 gate·artifact·Git 구조 |
| 실거래 준비도 | **0~5/100** | 0 | Q3·paper·broker 모두 차단 |

Q0~Q2 실행 완성도 72점은 다음처럼 계산한다.

| 축 | 점수 | 가중치 | 근거 |
|---|---:|---:|---|
| 사전등록·거버넌스 | 95 | 20% | 기준·잠금·브랜치 확정 |
| 데이터 안전 구현 | 80 | 20% | fail-closed 구현, 실제 custody는 미확보 |
| Signal floor 실행 | 85 | 20% | 실제 DB·5fold·controls 완료, 성과는 NO-GO |
| Stateful 환경 | 90 | 20% | 23bp invariant·3/3 synthetic PASS |
| 실제 PPO 성과 | 0 | 15% | 의도적으로 NOT_RUN |
| live/paper 운영 | 0 | 5% | 미실행 |
| **가중 합계** | **72** | **100%** | 개발·연구 실행 완성도 |

## 8. 전체 12페이지 반영

| 페이지 | 표시 상태 | 핵심 수치·경계 | 다음 행동 |
|---|---|---|---|
| Home | `ETF_Q0_Q2_BLOCKED_Q1_Q2A` | 기존 18·ETF 44·Q3 lock | Q1 custody |
| Program Scorecard | 세 점수 분리 | 18 / 44 / 90 | 점수 의미 유지 |
| Discovery Lab | Q0 done·Q1 block·Q2A no-go·Q2B pass | D7 no-read | Q1 재실행 |
| Data | `FOUR_CUSTODY_GATES` | PIT·identity·available_at·total return | 공식 metadata |
| Experiment | Q0 prereg executed | 5fold·3shuffle·9/23bp | amendment 없이는 기준 변경 금지 |
| Training | `ETF_Q3_LOCKED_NOT_RUN` | PPO model 0개 | Q1·Q2-A 통과 필요 |
| Evaluation | `23BP_NO_GO_1_OF_5` | -9.23bp·MDD 94.79% | 공식 universe 재검증 |
| Compare | `NATIVE_MINUS_SHUFFLE_NEG_2_334BP` | 9bp +4.77은 진단 | 비용 민감도만 표시 |
| Report | receipt SHA | `5547b737…` | 부모 PR 계보 |
| Insights | diagnostic only | 마지막 fold +77.48bp | 사후 alpha 주장 금지 |
| Other Lanes | external reference only | Quantylab 성과 합산 금지 | lane 분리 |
| Settings | DB read-only | 학습·broker 실행 없음 | artifact/cutoff 표시만 |

## 9. 테스트와 품질 결과

| 검증 | 결과 |
|---|---|
| Python Q1/Q2+대시보드 대상 회귀 | 41 passed |
| Ruff | passed |
| Python no-excuse audit | 0 violations |
| Scorecard focused tests | 5 passed |
| Frontend 전체 tests | 402 passed, 0 failed |
| Svelte check | passed |
| Vite production build | passed; 신규 hashed bundle 생성 |
| Pure LOC | 모든 신규 Python/TS 파일 250 이하 |

빌드 결과는 `index-jG0UP3Go.js`와 `LearningNowTab-pOL3IyGV.js` hashed bundle로 갱신됐다. dist는 소스와 분리된 생성 산출물 커밋으로 관리한다.

## 10. Git 계보와 커밋

| 순서 | 커밋 | 책임 |
|---:|---|---|
| 1 | `b4a94ef` | Q0 plan·prereg |
| 2 | `1c98799` | red-first Python contracts |
| 3 | `8ede5a8` | Q1/Q2 foundation implementation |
| 4 | `56d86d0` | scorecard capability extraction |
| 5 | `b9d9b36` | 12페이지 gate 결과 |
| 6 | `c0976b0` | execution lineage·lock tests |

부모 브랜치는 `codex/rl-etf-stateful-mdp-v1`, 실행 브랜치는 `codex/rl-etf-q0-q2-foundation-v1`이다. 실행 브랜치는 부모로 PR하고, 부모는 별도 integration 검토 후 master로 이동한다.

## 11. 남은 단계와 예상 시간

| 우선 | 작업 | 예상 | 완료 조건 |
|---:|---|---:|---|
| 1 | 공식 point-in-time ETF universe 확보 | 0.5~1일 | 거래일별 membership snapshot |
| 2 | instrument identity·available_at·total-return adapter | 1~2일 | Q1 11 gate 전체 PASS |
| 3 | 새 supervised feature/horizon prereg | 4~8시간 | 기존 결과를 본 사후 튜닝과 분리 |
| 4 | Q2-A 재실행 | 1~2일 | 23bp 양수·delta≥10bp·4/5·2/3·DD≤25% |
| 5 | Q3 Residual MLP PPO prereg | 4~8시간 | Q1·Q2-A PASS 뒤 독립 브랜치 |
| 6 | Q3 5fold×3seed pilot | 1~3일+연산 | net-return arm부터 통과 |
| 7 | reward ablation·LSTM/Mamba | 2~4일 | baseline 통과 뒤에만 |
| 8 | 새 sealed ETF OOS | 0.5~1일 | 사전등록한 1회 평가 |
| 9 | paper-forward | 수주 | 체결·지연·분배금 운영 증거 |

현재 데이터 문제를 해결하지 않고 20일 momentum PPO를 돌리는 예상 시간은 짧지만 연구가치는 거의 없다. 다음 유효한 작업은 모델 학습이 아니라 Q1 custody 확보다.

## 12. 최종 결정

| 질문 | 답 |
|---|---|
| 실제 강화학습 환경을 만들었는가 | 예. cash·units·position이 행동으로 변하는 Q2-B 환경을 만들었다. |
| 실제 PPO 모델을 만들었는가 | 아니다. Q1·Q2-A 실패로 의도적으로 잠갔다. |
| 기존 18점 모델 성과가 개선됐는가 | 아니다. 18/100 유지다. |
| 새 ETF 신호 성과가 있는가 | 9bp에서만 +4.77bp이나 controls·fold·23bp·DD가 실패했다. |
| 연구를 계속할 의미가 있는가 | 데이터 custody와 새 supervised signal 가설을 검증하는 범위에서는 있다. |
| 다음 즉시 행동 | point-in-time ETF metadata·분배금·available_at 확보다. |

이번 성과는 실패 원인을 더 빨리 차단하고 실제 강화학습 문제를 테스트할 환경을 만든 것이다. 수익 모델 생성 성공은 아니다.

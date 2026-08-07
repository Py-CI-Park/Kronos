# Kronos v1.29.0-dev 95점·실제 일봉 RL 마스터 계획

- 작성일: 2026-08-07 KST
- 부모 개발선: `develop/v1.29.0-dev`
- 계획 브랜치: `codex/v1.29.0-dev-95-baseline-plan`
- 직전 릴리즈: `v1.28.0`
- 현재 통합 성숙도: **73/100**
- 제품 구현·UX: **94/100**
- 실제 시장 경제 모델: **20/100 · NO-GO**
- Fresh OOS: **`NOT_RUN_NO_READ`**
- 실거래: **`BLOCKED`**

## 1. 목표와 판정 원칙

목표는 현재 DB를 사용해 **한국 개별주식 일봉 종가 정보로 다음 거래일 시가에 체결하는 6천만원·최대 10종목 강화학습 모델**을 실제로 학습·평가하고, 연구 플랫폼 전체 성숙도를 95점 이상으로 만드는 것이다.

95점은 코드·페이지·커밋 수로 만들지 않는다. 다음 조건을 모두 만족해야 한다.

1. 통합 점수 95점 이상.
2. 데이터·실행, RL 시스템, 경제 검증, UX, 재현성의 카테고리 최저점 통과.
3. 실제 시장 데이터로 학습한 모델 artifact와 동일 run ID의 telemetry·평가·manifest 존재.
4. 0.230% 비용 후 등록된 기준선·random·shuffle control을 통과.
5. 튜닝에 사용하지 않은 검증 구간에서 여러 seed 결과와 불확실성 기록.
6. Fresh OOS는 사전등록 hash와 사람 승인 전까지 열지 않음.
7. 모델이 실패하면 95점이나 성공을 주장하지 않고 새 가설을 별도 사전등록.

외부 KRX·DART 증거가 없더라도 `LOCAL_RETROSPECTIVE_RESEARCH` 범위의 학습은 계속한다. 외부 권위 부족은 연구 중단 사유가 아니라 **승격·수익성·paper·실거래 주장 차단 사유**다.

## 2. 현재 실패의 확인된 원인

| 원인 | 실행 증거 | 영향 | 대책 |
|---|---|---|---|
| 실제 시장 CQL/DQN 경로가 없음 | `runner.py`는 실제 DB를 ridge 신호 진단에만 쓰고 `train_offline_q()`에는 `synthetic_market_dataset()`만 전달 | 반복 실행해도 합성 2상태·2행동 모델만 생성 | 실제 시장 transition builder와 별도 market runner 구현 |
| 목표 MDP와 보정 MDP 불일치 | 보정 상태는 `(signal, position)`, 행동은 cash/invest 2개; 목표는 6천만원·10슬롯·복수 행동 | 합성 학습 성공이 종가 포트폴리오 성공으로 전이되지 않음 | 1단계 binary risk controller → 2단계 masked 6-action controller |
| 실제 daily-close telemetry 0개 | `/api/v6/telemetry-runs`: 21개 중 orderbook 5, intraday 13, portfolio 3, daily_close 0 | 모델 실행과 대시보드 성과를 같은 run으로 추적 불가 | 표준 event writer·manifest·catalog binding |
| daily-close catalog 식별 부족 | daily_close 52건 중 algorithm `MISSING` 37건 | 비교·검색·모델 계보 불명확 | algorithm/model_scope/split/cost/seed 필수 계약 |
| 고정 현재 20종목 편향 | 2017 앵커에서 19 stable, `068270` 1 excluded | 생존편향과 universe 상승 편향 가능 | 로컬 연구에는 명시적 제한, 승격 전 날짜별 PIT 원천 필요 |
| 가격·기업행사 의미 미확정 | official price, adjustment, available-at 4 gate false | 수익률 왜곡 가능 | 원본/조정 정의와 수신시각 receipt 확보 전 승격 차단 |

## 3. 냉정한 100점 기준선

각 기준은 5점이다. 구성은 계약·구현, 정상 테스트, 실패 테스트, 실제 실행 증거, 독립 검토·hash의 다섯 1점 항목이다. 없는 증거는 0점이며 부분 반올림은 없다.

| ID | 카테고리·기준 | 현재 | 확인된 증거 | 5점 조건 |
|---|---|---:|---|---|
| A1 | DB 불변성·읽기 전용 custody | 4/5 | 1GB SQLite SHA-256, mode=ro, query_only, 변경 감지 | 독립 검토 hash 추가 |
| A2 | 날짜별 PIT universe | 2/5 | 단일 2017 앵커와 제외 반례 | 모든 거래일 membership 원본·테스트·실행·검토 |
| A3 | available-at·feature cutoff | 2/5 | 미래시각 차단 계약·실패 테스트 | 실제 필드 공표/수신시각과 fold 실행 증거 |
| A4 | 가격 동일성·기업행사·체결 | 3/5 | POST_CLOSE_NEXT_OPEN·비용 계약 | 공식/조정 가격·분할·합병·배당 원본 결속 |
|  | **A 데이터·실행 권위** | **11/20** |  | 목표 19+ |
| B1 | 6천만원·10슬롯 MDP | 4/5 | 정수주·5천만원 노출·1천만원 예비금 invariant | 실제 market episode 실행·독립 검토 |
| B2 | 실제 시장 offline dataset·model | 0/5 | 존재하지 않음 | 시장 transition·split·학습·model·검토 |
| B3 | 알고리즘·seed·통제군 | 5/5 | 합성 DQN/CQL 3 seed, shuffle, random | 현재는 학습기 보정 점수이며 경제성 점수 아님 |
| B4 | daily-close telemetry·lineage | 3/5 | 일반 telemetry API와 실패 처리 | daily_close runtime·manifest·독립 검토 |
|  | **B RL 시스템** | **12/20** |  | 목표 19+ |
| C1 | 비용·다음 시가 체결 | 5/5 | 0.230%, KRX/NXT/ETF 분리, next-open | 유지 |
| C2 | 시장 모델 시간순 검증 | 2/5 | ridge 4-fold만 존재 | RL seed×fold 결과·CI·실패 테스트·검토 |
| C3 | 실제 시장 baseline·control | 3/5 | ridge shuffle와 합성 controls 분리 | always-cash/invest/rule/random/shuffle 동일 조건 비교 |
| C4 | Fresh OOS·paper-forward | 2/5 | 잠금·no-read 회귀만 존재 | 승인된 1회 OOS·봉인 결과·paper ledger |
|  | **C 경제 검증** | **12/20** |  | 목표 19+ |
| D1 | 8페이지 정보 구조·일관성 | 5/5 | 공통 셸·토큰·페이지 진행표 | 유지 |
| D2 | 반응형·접근성 | 5/5 | 375/768/1280 × 8페이지, overflow 0 | 유지 |
| D3 | 연구·학습 시각화 | 5/5 | 98 run, telemetry 차트, 행동 표 | daily_close 실제 run 연결 유지 |
| D4 | 평가·거버넌스 UX | 5/5 | 9단계, 430px 비교 차트, NO-GO·MISSING | 유지 |
|  | **D UX·관찰성** | **20/20** |  | 목표 18+ |
| E1 | 타입·테스트·빌드 | 5/5 | Python 173, frontend 454, Svelte 0/0, build | 유지 |
| E2 | 재현성·artifact hash | 4/5 | DB·모델·보고서 일부 hash | market run 전체 manifest·source/model/event hash |
| E3 | 성능·보안·fail-closed | 4/5 | read-only API, 경로 방어, browser console clean | 장기 `/api/v6/runs` 병목 또는 대체 계약 종결 |
| E4 | 브랜치·릴리즈·독립 QA | 5/5 | v1.28.0 tag/Release, 비FF 계보, 독립 리뷰 | 유지 |
|  | **E 엔지니어링·릴리즈** | **18/20** |  | 목표 19+ |
|  | **현재 합계** | **73/100** | Gate 95 FAIL | 목표 95+ |

### 3.1 95점 hard cap

다음 중 하나라도 존재하면 총점과 관계없이 95점 판정을 금지한다.

- 실제 시장 model artifact 없음.
- 동일 조건의 no-trade·rule·random·shuffle 비교 누락.
- 비용 0.230% 또는 체결 방향이 실행 artifact에 결속되지 않음.
- train/validation/Fresh OOS가 섞이거나 split hash가 없음.
- Fresh OOS를 사전등록·사람 승인 전에 읽음.
- 데이터 누수·조정가격 모순·실패한 테스트·dirty release tree.
- 단일 seed나 단일 종목의 유리한 결과만 선택.

## 4. 1차 실제 모델: 해석 가능한 종가 위험배분 RL

처음부터 종목 선택과 주문 크기를 모두 신경망에 맡기지 않는다. 현재 20종목의 cross-sectional ridge 순위는 해석 가능한 후보 생성기로 유지하고, RL은 **현금 또는 상위 10종목 동일 슬롯 투자**를 결정한다.

| 항목 | 1차 계약 |
|---|---|
| 결정 시각 | D일 공식 장 종료 후 |
| 체결 | D+1 시가 |
| 평가 가격 | 등록 holding horizon의 다음 시가 |
| 자금 | 초기 60,000,000원 |
| 주식 노출 | 최대 50,000,000원 |
| 현금 | 최소 10,000,000원 |
| 종목 | D일 관측값으로 순위화한 최대 10종목 |
| 행동 0 | `CASH` · 신규 진입 없음 |
| 행동 1 | `INVEST_TOP10_EQUAL_SLOT` · 종목당 약 5,000,000원 정수주 |
| 상태 | 5·10·20일 수익, volume ratio, cross-sectional breadth/spread, 변동성, 이전 exposure, drawdown |
| 주 보상 | `log(net_NAV_t / net_NAV_t-1)`; 비용이 NAV에 이미 반영되므로 이중 비용 페널티 금지 |
| 비용 | KRX 주식 왕복 0.230%; 0.330%·0.460% stress 병행 |
| 후보 알고리즘 | CQL primary, DQN diagnostic |
| 통제군 | always cash, always invest, ridge threshold, random action, shuffled reward |
| 범위 | `LOCAL_RETROSPECTIVE_RESEARCH`; 승격 증거 아님 |

이 2행동 모델이 비용 후 기준선을 안정적으로 넘지 못하면 6행동 모델로 복잡도를 늘리지 않는다. 통과할 때만 기존 `HOLD_CASH/HOLD/ADD_ONE/EXIT_ONE/REPLACE_ONE/REDUCE_RISK` 포트폴리오 환경에 action masking을 추가한다.

## 5. 데이터·분할·평가 설계

| 구분 | 정책 |
|---|---|
| TRAIN | 가장 오래된 기간부터 순차 학습, transform은 fold 내부 TRAIN에서만 fit |
| Validation | 4개 expanding-window fold, 알고리즘·보상·threshold 선택에 사용 |
| Fresh OOS | 최신 미사용 기간, prereg hash·사람 승인 전 `NOT_RUN_NO_READ` |
| seed | 최소 5개 primary + 5개 shuffled-reward |
| 통계 | IQM, 95% bootstrap CI, seed별 결과, fold별 결과 모두 보존 |
| 지표 | 비용 후 누적수익, 연환산수익, max drawdown, Calmar, turnover, 거래수, 현금 비율 |
| 비교 | best simple baseline보다 net IQM 우월, shuffle/random보다 우월 |
| 집중도 | 종목·시기·regime 기여도를 분해하고 한 종목 제거 민감도 수행 |

### 5.1 사전등록 경제 gate

- primary 0.230% 비용에서 최소 4/5 seed 순수익 양수.
- primary net IQM의 95% bootstrap 하한이 0 초과.
- best simple baseline 대비 delta IQM 양수.
- shuffled-reward와 random의 IQM보다 primary가 높음.
- max drawdown 15% 이하 또는 best baseline보다 악화되지 않음.
- 0.460% stress에서 파산·회계 invariant 위반 없음.
- 최소 거래수와 turnover가 사전등록 하한/상한 안에 존재.

## 6. 실행 계획과 브랜치

| 순서 | 작업 브랜치 | 작업 | 핵심 산출물 | 예상 점수 | 예상 작업시간 |
|---:|---|---|---|---:|---:|
| 1 | `codex/v1.29.0-dev-95-baseline-plan` | 현재 감사·점수·계획 고정 | 본 문서, 실패 원인 receipt | 73 | 현재 |
| 2 | `codex/v1.29.0-dev-market-transition` | 실제 DB state/action/reward transition | typed dataset, split hash, tests | 78 | 4~8시간 |
| 3 | `codex/v1.29.0-dev-market-cql` | 5-seed CQL/DQN·controls 실행 | model, metrics, bootstrap receipt | 83~88 | 계산 포함 4~12시간 |
| 4 | `codex/v1.29.0-dev-daily-telemetry` | event·cost·NAV·action·manifest 결속 | daily_close telemetry/API/UI | 88~90 | 3~6시간 |
| 5 | `codex/v1.29.0-dev-robust-validation` | regime·leave-one-symbol·cost stress | robustness report | 90~93 | 4~8시간 |
| 6 | `codex/v1.29.0-dev-data-authority` | PIT·available-at·가격·기업행사 원천 | G2 5/5 receipt | 95 후보 | 외부 승인 후 1~3일 |
| 7 | `codex/v1.29.0-dev-fresh-oos` | 승인된 Fresh OOS 1회 | sealed verdict | 95+ 확정 또는 NO-GO | 승인 후 1~2시간 |
| 8 | `codex/v1.29.0-dev-95-release` | 전 페이지·연구·보안·릴리즈 gate | 최종 scorecard·handoff·tag 후보 | 95+ | 3~6시간 |

각 브랜치는 최신 `develop/v1.29.0-dev`에서 생성하고, 기능·테스트·문서·생성 번들을 논리 커밋으로 나눈 뒤 `--no-ff` 병합한다. 병합 브랜치는 삭제하거나 재사용하지 않는다.

## 7. UX 연결 완료 조건

| 페이지 | 실제 연구 연결 조건 |
|---|---|
| 통합 현황 | 현재 연구 세대, 정확한 점수, hard cap, 다음 실행을 표시 |
| 연구 라이브러리 | algorithm·model scope·split·seed·cost·verdict 검색 가능 |
| 실시간 학습 | daily_close loss/reward/NAV/drawdown/action과 파일 freshness 표시 |
| 평가·비교 | RL과 동일 조건 baseline·control·cost scenario를 큰 차트로 비교 |
| 데이터·증거 | DB hash, split hash, PIT/available-at/price/corporate-action gate 표시 |
| 모델·산출물 | calibration 모델과 market policy를 명확히 분리 |
| 보고서·거버넌스 | prereg → run → model → metrics → verdict → Git SHA 연결 |
| 설정 | 비용·단위·테마는 표시 설정만 제공하고 연구 계약을 변경하지 않음 |

## 8. 완료 정의

개발 완료는 다음 두 판정을 모두 따로 보고한다.

- **플랫폼 95+**: 코드·UX·증거·재현성 scorecard와 모든 hard cap 통과.
- **모델 성공**: 사전등록된 비용 후 validation/Fresh OOS 경제 gate 통과.

플랫폼이 95점이어도 모델이 실패하면 결과는 `PLATFORM_GO / MODEL_NO_GO`다. 모델을 학습했다는 사실이나 그래프가 상승했다는 사실만으로 성공이라고 보고하지 않는다.

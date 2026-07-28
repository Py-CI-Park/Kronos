# Kronos 종가매매 10-slot RL 연구 재개 계획 — 2026-07-21

> 문서 ID: `KRONOS-V8-CLOSING-RL-CONTINUATION-2026-07-21`
> 상태: `PLAN / NEXT_PREREG_DRAFTED / EXECUTION_NOT_STARTED`
> 기존 결과: M1 `INCONCLUSIVE`, M2 `NO_GO`, M3 `INCONCLUSIVE`, M4 `NOT_RUN_DEFERRED`
> untouched test: `NOT_RUN`

## 1. 먼저 바로잡을 표현

| 표현 | 정확한 의미 |
|---|---|
| 60,000,000원 | 실제 투입 운영금이 아니라 연구 성과를 환산하기 위한 fixed-notional accounting scale |
| 10 slots | 매일 사용할 수 있는 최대 용량이며 반드시 10종목을 선택·보유한다는 뜻이 아님 |
| slot당 5,000,000원 | 고정 연구 notional, 실제 주식 수량·현금 차감·브로커 체결이 아님 |
| 최대 투자 50,000,000원 | 10개 slot을 모두 썼을 때의 연구상 최대 notional exposure |
| reserve 10,000,000원 | 연구상 미사용 notional이며 실제 예치금·증거금이 아님 |
| NAV | `60M + Σ 5M × (15:20 proxy return - cost)` 연구 원장 값, 계좌 잔고가 아님 |

따라서 현재 시스템은 실제 운영금으로 10종목을 매매하는 시스템이 아닙니다. 매일 0~10개 서로 다른 종목을 선택할 수 있는 연구 회계 환경입니다.

## 2. 기존 연구 재검토

| 모델 | 장점 | blocker | 판정 |
|---|---|---|---|
| M1 Tabular-Q | 대조군 교정, seed0 validation 우위 | 1/5 seed만 통과, 경로 민감성 | `INCONCLUSIVE` |
| M2 PPO | gym/SB3 실행 체인 확보 | 학습은 symbol-order MDP인데 평가는 neutral-context top-k로 정책 불일치 | `NO_GO` |
| M3 LinUCB | 계수 방향 해석 가능, 1 seed 우위 | 1/3 seed만 통과, online order 민감성 | `INCONCLUSIVE` |
| M4 best-policy+filter | 품질 필터 아이디어 | GO 후보가 없어 best-policy 선택이 post-hoc | `NOT_RUN_DEFERRED` |

M2는 결과를 완화하지 않으며 다음 trainer의 기준으로 재사용하지 않습니다. 새로운 cycle은 train/evaluation에서 동일한 policy contract를 사용해야 합니다.

## 3. 다음 cycle: M3E fixed-seed consensus

분류는 full sequential RL이 아니라 **contextual-bandit research experiment**입니다.

### 가설

train-only에서 처음부터 학습한 LinUCB 5개 member를 seed 선택 없이 평균하면 경로 분산이 줄어들어, 고정 full ensemble과 5개 leave-one-seed-out ensemble 중 최소 4개가 reused validation screen에서 0.23% 비용 기준 no-trade와 최선 frozen baseline을 모두 초과합니다.

### 고정 계약

| 항목 | 값 |
|---|---|
| seeds | `[0,1,2,3,4]` |
| train pass | 1회 |
| feature | D-1 frozen feature, NaN→0, 새 feature 사후 추가 금지 |
| label | exact `future_return_h1_1520_proxy`, 공식 종가 아님, fallback 없음 |
| action | member score 5개 평균 > 0인 종목 중 score 내림차순·symbol 오름차순 tie-break로 최대 10개 |
| zero action | 허용, 선택 0종목 가능 |
| reward | 진입 slot별 `future_return_h1_1520_proxy - 0.0023` |
| primary cost | 0.23% |
| display controls | 0.00%, 0.46%; 판정에는 0.23%만 사용 |
| accounting | 60M fixed notional, optional 10×5M slots, max 50M, reserve 10M |
| checkpoint | validation 선택 없음, 각 seed 최종 1-pass member 고정 |

### baseline과 controls

- no-trade 60M
- frozen RULE: ret5, low-vol, institutional-flow top-10
- seeded random top-10
- 실제 ensemble과 같은 session별 pick count를 쓰는 exposure-matched random 20회
- predeclared shuffled-label ensemble control 5개

### validation gate

1. shuffled control 하나라도 `max(60M, exposure-matched mean+2σ)`를 넘으면 `NO_GO`입니다.
2. full 5-member ensemble이 no-trade와 최선 frozen baseline을 모두 넘어야 합니다.
3. 5개 jackknife 중 4개 이상이 같은 기준을 넘어야 `OOS_OPEN_ELIGIBLE_REUSED_VALIDATION_SCREEN`입니다.
4. 1~3개면 `INCONCLUSIVE`, 0개 또는 full ensemble 실패는 `NO_GO`입니다.
5. 이 상태는 GO나 승격이 아니라 OOS 개봉 자격 후보입니다.

## 4. OOS custody 선행 조건

현재 코드의 `NOT_RUN`은 평가 미실행을 의미하지만 test label이 combined dataset에서 deserialize되지 않았음을 기술적으로 증명하지 못합니다. 다음 실행 전 아래가 필요합니다.

1. train/validation과 test label artifact를 물리적으로 분리합니다.
2. test artifact SHA-256과 split `2025-07-01~2026-06-12`를 고정합니다.
3. 일반 train/validation 명령은 test artifact를 읽을 수 없어야 합니다.
4. independent gate receipt가 있어야 test loader가 열립니다.
5. 최초 read를 access ledger에 기록하고 두 번째 read를 거부합니다.
6. 기존 test custody를 입증할 수 없으면 confirmatory claim에는 새 exact-15:20 OOS window를 사용합니다.

## 5. Quant-Insight 데이터 사용 판단

현재 M3E prereg·구현·train/reused-validation에는 `D:\Chanil_Park\Project\Programming\Quant-Insight\`의 추가 데이터가 필요하지 않습니다. 현재 frozen dataset과 수급 feature로 가설을 검증할 수 있습니다.

다음 경우에만 Quant-Insight를 사용합니다.

- 기존 test label custody를 입증하지 못해 새로운 fresh OOS를 축적할 때
- 새 데이터 feature를 소비하는 별도 preregistration을 먼저 동결했을 때
- KRX credential을 쓰는 수집이 source timestamp, point-in-time, hash, rate-limit, credential 비노출 조건을 충족할 때

KRX ID/PW는 코드·문서·manifest·로그에 기록하지 않습니다.

## 6. 실행 순서

1. M3E DRAFT의 source/protocol hash를 구현 후 채우고 FROZEN으로 전환
2. policy/accounting 단일 함수와 synthetic tests 작성
3. sealed test custody와 gate receipt 구현
4. train-only fit
5. reused validation screen 및 controls 1회
6. independent gate audit
7. 자격 충족 시에만 sealed OOS 1회
8. 결과가 무엇이든 immutable result/report/ledger 기록

## 7. 금지 사항

- 과거 M1 seed0 또는 M3 seed2를 winner로 선택
- 결과를 본 뒤 seed/member/threshold/feature/checkpoint 제거·변경
- 10 slots를 항상 10종목 보유라고 표현
- 60M을 실제 투입금·필요자금·계좌 NAV라고 표현
- 공식 종가 체결, 실현 수익, alpha, GO, promotion, live/broker/order readiness 주장
- gate 이전 test OOS 접근

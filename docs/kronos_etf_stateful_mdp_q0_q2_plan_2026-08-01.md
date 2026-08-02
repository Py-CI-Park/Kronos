# Kronos ETF Stateful MDP Q0~Q2 개발·연구 실행 계획

- 작성일: 2026-08-01 KST
- 부모 브랜치: `codex/rl-etf-stateful-mdp-v1`
- 실행 브랜치: `codex/rl-etf-q0-q2-foundation-v1`
- 기존 기준점: D6R2 모델 성과 18/100, `NO-GO`, D7 `LOCKED`
- 신규 lane: `ETF_STATEFUL_MDP_Q0_Q2`
- 현재 판정: `PREREGISTERED_NOT_RUN`
- 전략 종류: `RL experiment candidate`; RULE 또는 검증된 수익 모델이 아님

## 1. 목적

기존 일봉 top-5 lane은 행동이 다음 날의 보유 상태나 현금을 바꾸지 않아 contextual selection에 가까웠고, 23bp 비용 후 supervised signal floor도 확인되지 않았다. 같은 환경에서 DQN/PPO 설정만 반복하지 않고 다음 두 질문을 독립적으로 검증한다.

1. 국내 주식형 ETF의 수일 horizon에 왕복 23bp 이후에도 chronological fold에서 유지되는 선택 신호가 있는가?
2. 목표 보유비율 행동이 현금·수량·포트폴리오 상태를 실제로 바꾸는 환경을 회계적으로 검증할 수 있는가?

두 질문 중 하나라도 실패하면 실제 시장 PPO 단계 Q3은 실행하지 않는다.

## 2. 브랜치와 병합 계보

| 계층 | 브랜치 | 책임 | 병합 대상 |
|---|---|---|---|
| 기준 | `master` | D6R2까지 병합된 공식 기준선 | 없음 |
| 의사결정 | `codex/rl-continuation-decision-review-v1` | 18점 모델 중단·외부 자료 검토 | 부모 연구 브랜치 |
| 부모 연구 | `codex/rl-etf-stateful-mdp-v1` | ETF Q0~Q7 장기 계보 | 향후 integration PR |
| 실행 | `codex/rl-etf-q0-q2-foundation-v1` | Q0·Q1·Q2-A·Q2-B·대시보드 | 부모 연구 브랜치 |
| 후속 예정 | `codex/rl-etf-q3-ppo-pilot-v1` | gate 통과 시 Residual MLP PPO | 부모 연구 브랜치 |

병합 순서는 `Q0~Q2 실행 브랜치 → 부모 연구 브랜치 → 별도 integration → master`다. Q3 브랜치는 Q1, Q2-A, Q2-B가 모두 통과하기 전 만들지 않는다.

## 3. 연구 범위와 비범위

| 구분 | 포함 | 제외 |
|---|---|---|
| Q0 | 사전등록, 비용·split·seed·gate·잠금 계약 | 성과 사후 기준 변경 |
| Q1 | DB read-only 감사, 날짜·OHLC·중복·custody·point-in-time 확인 | 현재 ETF 목록을 과거에 소급 적용 |
| Q2-A | momentum canary, 5 chronological folds, 3 shuffle seeds, 9/23bp | 신경망·PPO·Mamba |
| Q2-B | cash/units/position state, open fill, close mark, 비용 invariant | 다중 ETF 동시 포트폴리오 |
| Dashboard | 후보·차단·gate·점수·증거 표시 | 학습 버튼·브로커 주문 |
| 운영 | artifact·receipt·문서·Git 계보 | live/paper 수익 주장 |

## 4. 데이터 계약

### 4.1 현재 확인된 로컬 데이터

| 항목 | 관측값 |
|---|---|
| DB | `_database/Stock_Database_ohlcv_1day.db` |
| 접근 | SQLite `mode=ro` |
| 전체 테이블 | 4,727 |
| canary ETF 테이블 | `A069500`, `A102110`, `A091160`, `A091170` |
| 공통 필드 | `date`, `open`, `high`, `low`, `close`, `volume` |
| 최신 일자 | 2026-06-12 |
| 최소 관측 수 | 4,485 rows |

이 네 종목은 파이프라인 검증용 canary다. Quantylab의 64개 TIGER ETF universe나 최종 연구 universe로 간주하지 않는다.

### 4.2 Q1 필수 gate

| Gate | PASS 조건 | 현재 예상 |
|---|---|---|
| Read-only source | SQLite URI `mode=ro` | 가능 |
| Leading zero | 6자리 코드 문자열 유지 | 가능 |
| 날짜 단조성 | 중복 0, strictly increasing | 실행 확인 필요 |
| OHLC 유효성 | `low≤open/close≤high`, 양수 가격 | 실행 확인 필요 |
| Point-in-time universe | 각 거래일 당시 상품 구성 증거 | 현재 없음 |
| Instrument identity | 공식 ETF 상품유형·이름 snapshot | 현재 없음 |
| Availability | 피처별 `available_at≤decision_at` | 현재 없음 |
| Total return | 분배금/수정주가 처리 계약 | 현재 없음 |
| Imputation | 미래 `bfill` 0건 | 새 코드에서 강제 |
| Scaling | fold train-only fit, evaluation row 0 | 새 코드에서 강제 |

마지막 네 항목 중 하나라도 미확인이면 Q1 verdict는 `BLOCKED_DATA_CUSTODY`다. OHLCV 자체가 깨끗해도 이 판정을 완화하지 않는다.

## 5. Q2-A supervised signal floor

### 5.1 canary 가설

- 전일 종가 기준 20일 momentum으로 ETF를 순위화한다.
- `t-1`까지의 값만 사용한다.
- `t` 시가 진입, `t+4` 종가 청산의 5거래일 gross return을 계산한다.
- 날짜별 최고 score ETF 하나를 선택한다.
- 23bp를 primary round-trip 비용으로 차감한다.
- 9bp 결과는 ETF 진단값으로만 병기한다.

### 5.2 split과 control

| 축 | 계약 |
|---|---|
| Split | 날짜 기준 expanding chronological 5-fold evaluation block |
| Native | 20일 momentum 순위 |
| Shuffle | 같은 날짜의 ETF score를 seed 0·1·2로 섞음 |
| Baseline | no-trade 0, equal-weight, 단순 momentum |
| Primary cost | 23bp round trip |
| Diagnostic cost | 9bp round trip |

### 5.3 승격 gate

| Gate | 기준 |
|---|---:|
| Native 23bp mean | `>0` |
| Native−shuffle | `≥10bp` |
| Positive folds | `≥4/5` |
| Positive shuffle-seed 비교 | `≥2/3` |
| Maximum drawdown | `≤25%` |

현재 canary는 point-in-time universe가 아니므로 수치가 좋아도 `DIAGNOSTIC_ONLY`다. Q1 PASS 이후 같은 코드를 공식 universe snapshot에 재실행해야 Q2-A PASS가 가능하다.

## 6. Q2-B stateful 환경

### 6.1 전이 계약

| 시점 | 처리 |
|---|---|
| `t-1` close 이후 | feature와 포트폴리오 state 관측 |
| `t` open | 목표 비율 `[0,1]`로 리밸런싱 |
| 체결 | 매수·매도 notional에 편도 비용 반영 |
| `t` close | portfolio value·return·drawdown 계산 |
| 다음 state | cash·units·position ratio·peak value 반영 |

왕복 23bp는 편도 11.5bp로 나눈다. 거래하지 않으면 비용이 0이어야 하고, 동일 가격에서 전량 진입 후 청산하면 약 23bp 손실이 발생해야 한다.

### 6.2 합성 gate

| 검증 | PASS 조건 |
|---|---|
| No-trade | cash와 value 불변 |
| Flat round-trip | 비용과 손실이 회계식과 일치 |
| Position transition | 행동 후 다음 state 비율 변화 |
| Rising regime | long 정책이 no-trade보다 높음 |
| Falling regime | cash 정책이 always-long보다 높음 |
| Seeds | 알려진 정책 관계가 3/3 seed에서 유지 |

합성 환경 gate는 alpha 증명이 아니라 MDP와 회계 구현이 학습 가능한지 확인하는 테스트다.

## 7. 대시보드 UX/UI 계약

디자인 방향은 `industrial research control room`이다. 성공처럼 보이는 장식보다 판정·잠금·다음 행동을 먼저 읽게 한다.

| 페이지 | 신규 표시 | 금지할 오해 |
|---|---|---|
| Home | `ETF STATEFUL MDP · PREREGISTERED` | 모델이 이미 학습됨 |
| Program Scorecard | 기존 모델 18점과 lane 준비도 분리 | 44점을 수익 성능으로 해석 |
| Discovery | Q0~Q7 사다리와 현재 Q gate | 기존 D7 재사용 |
| Data | DB 범위·PIT·as-of·dividend·bfill | OHLCV 존재=데이터 PASS |
| Experiment | 5-fold·3-seed·9/23bp·controls | best-of-many 선택 |
| Training | `LOCKED_BY_Q1_Q2` | PPO 실행 가능 표시 |
| Evaluation | native/shuffle/fold/MDD | 9bp만 통과한 결과 승격 |
| Compare | D6R2와 ETF lane 별도 카드 | 다른 universe cross-rank |
| Report | prereg SHA·artifact SHA·verdict | 외부 글을 성과 근거로 합산 |
| Insights | canary regime 관찰 | 사후 설명을 신호로 주장 |
| Other Lanes | external design reference | 제3자 성과를 Kronos 성과로 표시 |
| Settings | read-only DB·artifact root | API key·broker credential 노출 |

## 8. 커밋 단위

| 순서 | 커밋 | 내용 |
|---:|---|---|
| 1 | `docs(rl): preregister ETF stateful Q0-Q2` | 본 계획·machine-readable prereg |
| 2 | `test(rl): specify ETF data and state transitions` | 실패 우선 계약 테스트 |
| 3 | `feat(rl): implement ETF Q1-Q2 research foundation` | 데이터 audit·signal probe·환경·runner |
| 4 | `feat(dashboard): surface ETF research gates` | API·scorecard·12페이지 상태 |
| 5 | `docs(rl): publish ETF Q0-Q2 result` | 실행 수치·NO-GO/GO·남은 단계 |

각 커밋 후 대상 테스트를 실행한다. 생성 artifact와 소스·문서는 같은 커밋에 섞지 않는다.

## 9. 완료 정의

- Q0 prereg가 커밋되고 이후 gate 기준이 바뀌지 않는다.
- Q1은 확인되지 않은 custody를 PASS로 만들지 않는다.
- Q2-A는 실제 로컬 DB canary를 읽어 5-fold·3-shuffle 결과를 낸다.
- Q2-B는 action-dependent transition과 23bp 회계를 테스트한다.
- API와 UI가 `candidate`, `blocked`, `not run`, `no live`를 구분한다.
- 전체 대상 pytest, Svelte check/test/build가 통과한다.
- 결과 문서에 실패도 그대로 남긴다.

## 10. Q3 이후 잠금

Q3 Residual MLP PPO는 다음을 모두 만족할 때만 시작한다.

1. 공식 point-in-time ETF universe 확보
2. `available_at`과 total-return 처리 확인
3. Q2-A primary 23bp gate 통과
4. Q2-B synthetic gate 3/3 통과
5. 새 Q3 prereg와 독립 브랜치 생성

그 전에는 PPO 모델 파일을 만들 수 있어도 연구 성과로 인정하지 않는다.

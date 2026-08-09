# Kronos v1.29.0-dev 실제 일봉 CQL/DQN 사전등록

- 사전등록일: 2026-08-09 KST
- 연구 ID: `DAILY_MARKET_CQL_2026_08_09_001`
- 기준 커밋: `eede235`
- 작업 브랜치: `codex/v1.29.0-dev-market-cql`
- 목적: 실제 한국 주식 일봉의 인과 상태와 D+1·D+2 시가 전이를 사용해 이진 종가 의사결정 CQL/DQN 체크포인트를 만들고, 비용 차감 후 대조군보다 나은지 historical TEST에서 한 번만 판정한다.
- 범위: 로컬 회고 연구 전용. Fresh OOS, paper-forward, 실계좌, 수익성 보장, 승격을 포함하지 않는다.

## 1. 고정된 문제 정의

| 항목 | 사전등록 값 |
|---|---|
| 시장 | 한국 개별주식 일봉, 기존 읽기 전용 SQLite DB |
| 의사결정 | 거래일 D 종가 이후 |
| 행동 0 | `CASH` |
| 행동 1 | `INVEST_TOP10_EQUAL_SLOT` |
| 체결 | D+1 시가 진입, 그다음 정확한 거래일 시가 청산 |
| 초기 NAV | 60,000,000원 |
| 주식 노출 상한 | 50,000,000원 |
| 현금 하한 | 10,000,000원 |
| 슬롯 | 최대 10종목, 동일 슬롯 예산, 정수 주식 |
| 기본 비용 | 매수 0.015% + 매도 0.015% + 매도세 0.200% = 왕복 0.230% |
| 스트레스 비용 | 기본 비용 + 양방향 슬리피지 각 0.115% = 왕복 0.460% |
| 경제 보상 | `log(비용 차감 후 NAV / 직전 NAV)` |
| Fresh OOS | `NOT_RUN_NO_READ`, 봉인 유지 |

가격 기준은 `unknown`, 의사결정 등급은 `BLOCKED_UNTIL_PRICE_BASIS_VERIFIED`이다. 따라서 역사적 결과가 좋아도 연구 체크포인트만 생성하며 승격 판정은 계속 `NO-GO`다.

## 2. 데이터·누출 방지 경계

| 증거 | 고정 값 |
|---|---|
| 인과 score dataset | 244일, SHA-256 `3b42c21e0533389c7d41fcb3c345781e29fb485455efc73cafb0f422e7a8a314` |
| 인과 state dataset | 160차원, SHA-256 `986098337cfd733760876e82a724a9052000fa43ef0b2fe72089ac199808d03b` |
| split | TRAIN 151일 / VALIDATION 47일 / historical TEST 46일 |
| 보상 가용성 | 243 PASS / TEST 마지막 1일 right-censored BLOCKED |
| 전처리 | TRAIN Top-10만으로 평균·표준편차·결측 대체값 적합 |
| TEST 사용 | 구현·단위/통합 테스트·사전등록 커밋 뒤 최종 실행에서 한 번만 경제 성과를 읽음 |

기존 160차원 인과 특성에 다음 값만 추가하여 모델 입력을 172차원으로 고정한다.

1. TRAIN Top-10 score만으로 표준화한 당일 상위 10개 score 10차원
2. 직전 실행 노출 비율 1차원
3. 직전 실행 후 drawdown 1차원

미래 진입·청산 가격, 미래 수익률, future rank/direction, TEST 통계는 입력과 전처리에 사용하지 않는다.

## 3. 시간 중첩 방지

D 결정의 포지션은 D+2 시가까지 존재하므로 D+1 종가에 새 포지션을 순차 NAV로 연결하면 미래 NAV를 먼저 사용하게 된다. 이를 막기 위해 각 split에서 다음 규칙으로 비중첩 궤적을 만든다.

1. 가장 이른 가용 결정일을 선택한다.
2. 선택한 전이의 청산일 시가 이후에 오는 결정만 다음 상태가 될 수 있다.
3. 다음 결정일은 `decision_date >= previous_exit_date`를 만족하는 가장 이른 날로 고정한다.
4. split 경계를 넘지 않고 각 split 시작 시 NAV를 60,000,000원으로 초기화한다.
5. right-censored 일자는 삭제로 숨기지 않고 차단 감사에는 유지하되 학습·평가 궤적에는 넣지 않는다.

## 4. 학습 사전등록

| 항목 | DQN | CQL |
|---|---:|---:|
| 모델 seed | 0, 1, 2, 3, 4 | 0, 1, 2, 3, 4 |
| 행동 데이터 | TRAIN 비중첩 궤적, 32개 고정 50:50 탐색 seed | 동일 |
| 네트워크 | 172 → 128 → 64 → 2, ReLU | 동일 |
| optimizer | Adam, learning rate 0.0003 | 동일 |
| discount | 0.95 | 0.95 |
| batch | 256 | 256 |
| gradient steps | 600 | 600 |
| target 갱신 | 25 step hard update | 동일 |
| CQL alpha | 0 | 1.0 |
| 장치 | CPU, 단일 thread, deterministic algorithms |
| 모델 선택 | 고정 마지막 step; TEST 기반 재학습·조기종료 없음 | 동일 |

학습 보상은 기본 비용 0.230%만 사용한다. 같은 고정 정책을 기본 비용과 스트레스 비용에서 각각 재생해 비용 강건성을 본다.

## 5. 필수 대조군

| 종류 | 정의 | 목적 |
|---|---|---|
| No-trade | 항상 `CASH` | 위험 없는 0% 기준 |
| Always-invest | 항상 행동 1 | 단순 시장 노출 기준 |
| Cost-aware momentum RULE | 당일 Top-10의 인과 5일 수익률 평균이 0.230%보다 클 때만 투자 | RL이 단순 규칙보다 나은지 확인 |
| Reward-shuffled CQL | TRAIN 보상만 고정 seed로 섞음 | 미래 경제 구조가 사라져도 성과가 나오는지 확인 |
| Action-shuffled CQL | TRAIN 행동만 고정 seed로 섞고 보상·상태는 유지 | 행동-보상 연결이 깨져도 성과가 나오는지 확인 |

RULE 성과를 RL 성과로 부르지 않는다. 무작위 대조군이 본 모델과 비슷하면 학습 성공이 아니라 선택 편향 또는 약한 신호로 판정한다.

## 6. 고정 평가 지표와 판정

각 split·알고리즘·seed·비용 시나리오에 대해 최종 NAV, 순수익률(%), 최대 낙폭(%), 투자 행동 수/비율, 진입 원금 합계, 총비용(원), turnover, 일별 행동·보상 ledger를 남긴다. 5개 seed의 중앙값과 95% seed bootstrap 구간을 보고한다.

historical TEST의 CQL 연구 성과는 아래를 모두 만족할 때만 `PASS_HISTORICAL_RESEARCH_ONLY`다.

1. 기본 비용 5-seed 수익률 중앙값이 0%와 세 규칙 대조군 중 최고 수익률을 모두 초과한다.
2. 최소 4/5 seed가 최고 규칙 대조군을 초과한다.
3. 기본 비용 seed-bootstrap 95% 하한이 0%보다 크다.
4. 스트레스 비용 수익률 중앙값이 0%보다 크다.
5. 모든 seed의 최대 낙폭이 -20%보다 크거나 같다.
6. 최소 4/5 seed가 10% 이상 90% 이하의 투자 행동 비율을 보여 전액 현금/항상 투자 붕괴가 아니다.
7. 정상 CQL 중앙값이 reward-shuffled와 action-shuffled CQL 중앙값을 모두 초과한다.

하나라도 실패하면 결과는 `NO_GO_HISTORICAL_ECONOMIC_GATE`다. 결과를 본 뒤 이번 TEST에 맞춰 threshold, alpha, 네트워크, seed, step 수를 바꾸지 않는다.

## 7. 산출물·Git 경계

- 생성 연구 산출물: `webui/rl_runs/daily_market_offline_rl/DAILY_MARKET_CQL_2026_08_09_001/`
- 커밋 대상: 소스, 테스트, 사전등록, 결과·한계 문서
- 비커밋 대상: 모델 `.pt`, 거래 ledger CSV/JSON, 실행 중간 산출물
- 기능 브랜치는 삭제하지 않는다.
- 전체 검증 뒤 `develop/v1.29.0-dev`에 `--no-ff` 병합 후보로 올리며, `main` 병합과 `v1.29.0` 태그는 가격 기준·universe 권위·Fresh OOS·사람 승인 전에는 만들지 않는다.


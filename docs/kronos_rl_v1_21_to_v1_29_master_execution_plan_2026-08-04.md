# Kronos 강화학습 v1.21~v1.29 전체 실행 계획

- 계획 ID: `KRONOS-RL-MASTER-PLAN-V1.21-V1.29`
- 작성일: 2026-08-04 KST
- 계획 브랜치: `codex/rl-research-governance-v1-21`
- 현재 프로그램 기준선: master `30297a0`
- 현재 모델 판정: 모델 생성 `SUCCESS`, 경제성 `NO_GO`, Fresh OOS `NOT_RUN_NO_READ`
- 목표: 일봉 기반 종가 의사결정에서 일정 자금·최대 10종목을 관리하는 인과적·비용 인식·상태연결 강화학습 후보를 생성하고 정직하게 검증한다.

## 1. 성공 정의

| 성공 단계 | 정의 | 현재 |
|---|---|---|
| Build success | 환경·학습기·모델 artifact 생성 | 완료 |
| Calibration success | 알려진 최적 합성정책을 3/3 seed에서 학습 | 부분 완료, 계약 확대 필요 |
| Research candidate | 올바른 비용·데이터의 nested validation에서 baseline과 control 초과 | 미달 |
| Economic evidence | sealed OOS에서 사전등록 기준 통과 | 미실행 |
| Operational evidence | paper-forward에서 실제 체결비용·지연·위험 확인 | 미실행 |
| Live readiness | broker·risk·monitoring·human approval | 범위 밖·0점 |

이 계획은 모델 생성과 연구 후보 도출을 완료할 수 있지만 수익을 보장하지 않는다. 신호 floor가 실패하면 해당 가설의 정직한 성공은 빠른 종료와 실패 증거 보존이다.

## 2. 실행 순서와 계획 버전

| 단계 | 계획 버전 | 목적 | 핵심 산출물 | 예상 | 진입 조건 |
|---:|---|---|---|---:|---|
| G0 | `v1.21.0` | 연구 원리·비용·버전 기준선 | 본 검토·정책·계획·프롬프트 | 완료 목표 | 없음 |
| G1 | `v1.22.0` | 상품·시장·계좌별 비용 계약 | cost schema/API/UI/tests | 1~2일 | G0 문서 승인 |
| G2 | `v1.23.0` | 인과적 종가와 PIT 데이터 | timing contract, universe, identity, available_at, total return | 2~5일+데이터 | G1 |
| G3 | `v1.24.0` | 새 feature·horizon 신호 바닥 | 5-fold native/shuffle/baseline 결과 | 1~3일 | G2 custody PASS |
| G4 | `v1.25.0` | stateful MDP calibration | synthetic oracle, accounting invariants, 3 seeds | 1~3일 | G1·G2 |
| G5 | `v1.26.0` | 최소 offline RL pilot | DQN+CQL 후보, train/inner-val artifacts | 2~5일 | G3·G4 PASS |
| G6 | `v1.27.0` | nested validation | 5 folds×3+ seeds, IQM/CI, controls | 2~4 계산일 | G5 후보 동결 |
| G7 | `v1.28.0` | sealed OOS | one-time receipt와 최종 판정 | 0.5~1일 | G6 PASS+별도 승인 |
| G8 | `v1.29.0` | paper-forward | 실제 체결·비용·지연 dashboard | 8~12주 | G7 PASS+별도 승인 |

## 3. 단계별 상세 계획

### G0 — 문서·거버넌스 기준선

| 작업 | 완료 조건 |
|---|---|
| 강화학습 원리·환경·보상 문서 | MDP/POMDP, 비용, 보상, 검증 경계 포함 |
| 비용 재검토 | 개별주식 0.23%, 국내주식형 ETF 0.03% 분리 |
| 버전 정책 | `vMAJOR.MINOR.PATCH`, minor 무제한 증가, patch fix |
| UX 연결 | 13페이지별 상태·다음 행동 정의 |
| 실행 프롬프트 | 다음 단계가 재개 가능한 단일 문서 |
| Git | 문서 전용 브랜치·한글 커밋·clean status |

### G1 — 비용 계약과 UX

작업 브랜치 예시: `codex/cost-contract-v1-22`

| 작업 | 수용 기준 |
|---|---|
| 상품 분류 | `EQUITY`, `DOMESTIC_EQUITY_ETF`, `OTHER_ETF`를 혼합하지 않음 |
| 거래소 | KRX·NXT·SOR execution venue 기록 |
| 계좌 tier | 기본·이벤트·사용자 계약, 유효기간 기록 |
| 비용 구성 | buy commission, sell commission, tax, spread, slippage, impact 분리 |
| 화면 표시 | `%` primary, 원화 환산, bp 보조 |
| legacy | `base_23bp` artifact 호환성 보존 |
| 검사 | 500만원·5천만원 예시와 Decimal oracle 일치 |

### G2 — 인과적 데이터와 종가 계약

작업 브랜치 예시: `codex/causal-close-data-v1-23`

| 데이터 gate | 필수 증거 |
|---|---|
| Universe | 거래일별 point-in-time membership |
| Identity | 종목코드·종목명·시장·상품종류의 유효기간 |
| Available-at | 재무·수급·지수·feature가 알려진 시각 |
| Total return | 배당·분할·병합·상장폐지 현금흐름 |
| Execution timing | `CLOSE_AUCTION_CAUSAL` 또는 `NEXT_SESSION_AFTER_DAILY_CLOSE` |
| Missing policy | 결측을 미래값으로 보간하지 않음 |

G2가 실패하면 G3~G7을 실행하지 않는다. 데이터 custody 미완료 상태의 대규모 RL은 더 정교한 과적합을 만들 수 있다.

### G3 — 값싼 신호 바닥

작업 브랜치 예시: `codex/signal-floor-v1-24`

사전등록 후보는 제한한다.

| 축 | 고정 후보 |
|---|---|
| 보유 horizon | 5일, 10일, 20일 |
| 모델 | ridge/logistic ranker, 작은 tree 1종 |
| fold | chronological expanding 5-fold, purge/embargo |
| 비용 | 상품별 actual explicit + realized 추정 + stress |
| controls | label/reward shuffle, no-trade, equal-weight, 기존 RULE |

최소 통과 조건:

- 비용 후 native median reward `> 0`
- native-shuffled delta `>= 0.10%` 또는 사전등록된 경제적 최소차이
- positive fold `>= 4/5`
- MDD `<= 25%`
- 하나의 전역 후보 선택 규칙
- evaluation row로 scaler·threshold·early-stop을 fit하지 않음

모든 horizon이 실패하면 실제 시장 RL을 실행하지 않고 feature hypothesis를 종료한다.

### G4 — 합성 stateful MDP

작업 브랜치 예시: `codex/stateful-calibration-v1-25`

| 환경 요소 | 검사 |
|---|---|
| 상태 | 현금·수량·보유종목·보유일수·평균단가가 다음 step에 유지 |
| 행동 | HOLD/CASH/ADD/EXIT/REPLACE/REDUCE_RISK가 상태를 실제 변경 |
| 비용 | 거래가 발생한 side와 notional에만 적용 |
| 제약 | 최대 10종목, 5천만원 노출, 1천만원 reserve |
| 강제청산 | terminal에서 사전등록된 회계 적용 |
| oracle | 알려진 최적 정책이 random/shuffle을 안정적으로 초과 |
| seed | 3/3 seed 성공, ledger exact match |

의도적 train 과적합은 G4에서 허용한다. 이는 학습기·환경 calibration 증거이며 시장 수익성으로 집계하지 않는다.

### G5 — 최소 offline RL pilot

작업 브랜치 예시: `codex/offline-rl-pilot-v1-26`

| arm | 역할 |
|---|---|
| supervised-only | 종목 ranker만 사용하는 비-RL ceiling/baseline |
| DQN | 작은 discrete action 기준선 |
| CQL | offline 데이터 밖 행동의 Q 과대평가를 억제하는 primary 후보 |
| shuffled CQL/DQN | negative control |

PPO는 G5 primary가 아니다. 신뢰할 수 있는 다양한 trajectory simulator가 생긴 뒤 별도 ablation으로만 추가한다.

모델 구조:

```text
causal features
  → compact ranker top-20
  → stateful RL controller
  → cash/hold/add/exit/replace
  → self-financing NAV after costs
```

### G6 — nested validation

작업 브랜치 예시: `codex/nested-validation-v1-27`

| 평가 | 필수 출력 |
|---|---|
| seed | 개별 값과 최악 seed |
| fold | 개별 값과 최악 fold |
| aggregate | IQM, median, bootstrap 95% CI |
| economics | net return, Sharpe/Sortino/Calmar, MDD, turnover, cost drag |
| control | native-shuffle, no-trade, RULE, supervised-only delta |
| behavior | action histogram, cash rate, holding age, replacement rate |
| custody | code/data/prereg/model/report SHA와 source commit |

G6를 본 뒤 같은 validation에 threshold·seed·feature를 재선택하지 않는다. 실패하면 새 연구 가설과 새 기간으로 돌아간다.

### G7 — sealed OOS

G7은 자동 다음 단계가 아니다. G6를 통과한 단 하나의 preregistered candidate와 별도 사용자 승인이 있어야 한다.

| 원칙 | 요구사항 |
|---|---|
| read-once | 최초 접근 receipt와 데이터 cutoff 기록 |
| immutable | candidate hash와 evaluator hash 동결 |
| no selection | 여러 seed 중 OOS best 선택 금지 |
| terminal verdict | GO/NO_GO를 append-only 기록 |
| no retry | 실패 후 같은 OOS 재튜닝 금지 |

### G8 — paper-forward

paper 단계도 live broker가 아니다. 실제 주문을 전송하지 않는 paper 또는 shadow 방식으로 다음을 측정한다.

- 주문 결정 지연
- 종가 경매 대비 모델 체결가격 차이
- 주문 미체결·부분체결
- KRX/NXT/SOR 선택
- 실제 계좌 수수료 계약
- spread·slippage·시장충격
- corporate action·휴장·거래정지 처리
- 일일 risk limit과 human stop

## 4. 전체 13페이지 진행표

| 번호 | 페이지 | 현재 | G0 문서 반영 | 다음 구현 | 목표 버전 | 완료 기준 |
|---:|---|---|---|---|---|---|
| 1 | Home | BUILT | 모델 생성/경제성/연구계속/OOS 4상태 정의 | 다음 허용 단계와 비용상품 표시 | v1.22 | 사용자가 10초 안에 현재 상태와 다음 행동 이해 |
| 2 | Program Scorecard | BUILT | 플랫폼·환경·비용·일반화 점수 분리 | version/branch/PR/tag와 모델 점수 분리 | v1.21 | 버전 상승이 모델 GO로 합산되지 않음 |
| 3 | Discovery Lab | BUILT / lane NO-GO | 기존 후보 종료와 새 pivot 분리 | G1~G6 연구 사다리와 kill gate | v1.24 | 실패 lane과 허용 lane이 동시에 보임 |
| 4 | Data | BUILT / PARTIAL | PIT·timing 계약 정의 | universe·identity·available_at·total return audit | v1.23 | 4 custody gate와 종가 계약 PASS |
| 5 | Experiment | BUILT / FROZEN | 비용·horizon·algorithm prereg 필드 정의 | G3/G4/G5 manifest 생성·동결 | v1.24 | 결과 보기 전 모든 선택 고정 |
| 6 | Training | BUILT / COMPLETE | 오래 학습과 일반화 실패 구분 | DQN/CQL curve, global checkpoint, OOD 지표 | v1.26 | native/shuffle/seed 상태와 종료 이유 표시 |
| 7 | Evaluation | BUILT / NO-GO | 상품별 실제 비용과 stress 분리 | nested fold, IQM/CI, MDD, turnover | v1.27 | 실제 비용 primary와 통계 불확실성 표시 |
| 8 | Compare | BUILT | RL·supervised·RULE·control 역할 정의 | 동일 split·cost·family만 비교 | v1.27 | 호환되지 않는 run cross-rank 금지 |
| 9 | Report | BUILT | 새 문서·버전·판정 계약 | packet/receipt/SHA/version/PR 표준 보고 | v1.21 | append-only 및 source link 완전성 |
| 10 | Insights | BUILT / DIAGNOSTIC | 관찰과 정책 입력의 경계 정의 | 선택 종목 전체의 causal feature provenance | v1.23 | 한 종목 고정 오해와 추천 오해 제거 |
| 11 | Other Lanes | BUILT | 주식/ETF/인트라데이 계보 분리 | 비용·horizon·evidence compatibility 표시 | v1.22 | 서로 다른 lane 성과 합산 금지 |
| 12 | Kronos | AVAILABLE_NOT_LOADED | foundation model과 RL policy 역할 분리 | Kronos embedding의 supervised floor ablation | v1.24+ | Kronos 사용이 RL 성과로 자동 합산되지 않음 |
| 13 | Settings | BUILT / READ_ONLY | 버전·비용 contract source 정의 | 상품·venue·account fee를 읽기 전용 미리보기 | v1.22 | 설정 변경이 과거 artifact를 변조하지 않음 |

## 5. 페이지 공통 UX 계약

모든 화면은 다음 순서로 정보를 보여준다.

1. 사용자의 질문: “모델이 만들어졌나, 수익성이 있나, 다음에 무엇을 하나?”
2. 한글 상태 요약.
3. 근거 수치와 원본 token.
4. 실패 이유.
5. 다음 허용 행동과 잠긴 행동.
6. source artifact·commit·prereg 링크.

상태 색만으로 의미를 전달하지 않는다. 긴 token은 한글 label과 tooltip을 제공하고 모바일에서 줄바꿈한다.

## 6. Git 실행 매트릭스

| 단계 | 작업 브랜치 | 부모 | 예상 커밋 묶음 | PR |
|---|---|---|---|---|
| G0 | `codex/rl-research-governance-v1-21` | `master` | docs + index | master 또는 새 research parent 결정 |
| G1 | `codex/cost-contract-v1-22` | `research/daily-close-offline-rl-v2` | test → feat → ui → docs → build | parent research |
| G2 | `codex/causal-close-data-v1-23` | 동일 | data contract → audit → ui → docs | parent research |
| G3 | `codex/signal-floor-v1-24` | 동일 | prereg → runner → result → dashboard | parent research |
| G4 | `codex/stateful-calibration-v1-25` | 동일 | red tests → env → oracle → result | parent research |
| G5 | `codex/offline-rl-pilot-v1-26` | 동일 | prereg → CQL/DQN → controls → result | parent research |
| G6 | `codex/nested-validation-v1-27` | 동일 | evaluator → stats → report → UI | parent research |
| G7 | 별도 승인 후 생성 | frozen candidate | one-time runner → receipt → result | release review |

## 7. 중단·계속 규칙

| 결과 | 다음 행동 |
|---|---|
| G1 비용 계약 실패 | 회계부터 수정, 학습 금지 |
| G2 custody 실패 | 데이터 확보, G3 이후 금지 |
| G3 signal floor 실패 | 해당 feature/horizon 종료, RL 금지 |
| G4 synthetic 실패 | 환경/학습기 수정은 1회 재사전등록, 반복 실패 시 환경 lane 종료 |
| G5 train 실패 | algorithm 또는 action contract 가설 종료 |
| G6 validation 실패 | 현재 candidate NO-GO, 동일 validation 튜닝 금지 |
| G6 통과 | G7 실행 승인 요청 |
| G7 실패 | 최종 NO-GO, paper/live 금지 |
| G7 통과 | paper-forward 별도 승인 요청 |

`NO-GO`는 현재 후보의 terminal verdict다. 연구 프로그램은 새 가설의 정보가치가 있고 새 사전등록·새 데이터 경계가 있을 때 계속된다.

## 8. 기대 효과

| 효과 | 가능한 변화 | 보장 여부 |
|---|---|---|
| 비용 정확성 | ETF를 0.23%로 과대평가하는 오류 제거 | 구현 가능 |
| 인과성 | 당일 종가 미래정보 누출 제거 | 구현 가능 |
| 학습 안정성 | 상태·행동·보상 오류와 alpha 부재 분리 | 구현 가능 |
| 과적합 감소 | nested folds, shuffle, sealed OOS, review gate | 감소 가능, 제거 보장 아님 |
| 거래비용 감소 | 보유 유지·현금·한 종목 교체 행동 | 정책이 학습하면 가능 |
| 모델 성공 가능성 | 낮은 회전율·offline pessimism·올바른 비용으로 개선 | 수익 보장 아님 |
| UX 직관성 | 모델 생성·경제성·다음 행동 분리 | 구현 가능 |
| Git 추적성 | 버전·브랜치·PR·tag와 연구 판정 분리 | 구현 가능 |

## 9. 완료 정의

G0는 문서가 커밋됐을 때 완료다. 전체 프로그램은 G6까지 실행해 candidate 판정을 만들었을 때 1차 연구가 완료된다. G7과 G8은 데이터와 승인이 필요한 독립 단계다.

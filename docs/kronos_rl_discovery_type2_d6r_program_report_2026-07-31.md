# Kronos RL D6R 프로그램 완료 보고서

- 작성일: 2026-07-31 KST
- 검토 run: `type2-d6r-primary-20260731-001`
- 판정: `D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED`
- 실행: 실제 SB3 DQN 60개 모델, 3,000,000 학습 step, 60개 outcome
- 연구 경계: 로컬 TRAIN_ONLY 반증 evidence. 수익성·promotion·paper·live·broker 준비도 주장이 아니다.
- Fresh OOS: `NOT_RUN_NO_READ`; D7은 계속 봉인한다.

## 1. 결론

실제 강화학습 모델은 생성·학습·평가됐다. 그러나 10bp 추가 거래 페널티는 거래율을 낮추지 못했고, 23bp 보상·5-fold·3-seed·drawdown gate를 통과하지 못했다. 10개 gate 중 invalid action 하나만 통과했으므로 모델 사용 판정은 **NO-GO**다.

| 핵심 지표 | 실측 | 기준 | 판정 |
|---|---:|---:|---|
| Native accuracy | 0.160000 | ≥ 0.200000 | FAIL |
| Native 23bp reward ratio | -0.106835 | ≥ 0 | FAIL |
| Native 23bp total reward | -0.348605 | ≥ 0 | FAIL |
| Native − Shuffled | +0.016968 | ≥ +0.100000 | FAIL |
| Positive folds | 1/5 | ≥ 4/5 | FAIL |
| Positive seeds | 0/3 | ≥ 2/3 | FAIL |
| Native trade rate | 0.880000 | ≤ 0.650000 | FAIL |
| Trade-rate reduction | 0.000000 | ≥ 0.150000 | FAIL |
| Drawdown | 0.486807 | ≤ 0.250000 | FAIL |
| Invalid actions | 0 | 0 | PASS |

## 2. 전체 프로그램 점수

| 영역 | 점수 | 가중치 | 가중 점수 | 근거 |
|---|---:|---:|---:|---|
| Platform | 98 | 30% | 29.4 | 12개 페이지, D6R API, fail-closed 60-unit viewer |
| RL Evidence | 80 | 30% | 24.0 | 실제 DQN·shuffle·5 folds·3 seeds; 성능 gate는 실패 |
| Engineering | 100 | 20% | 20.0 | exact matrix, terminal receipt, tests, typed verifier |
| Governance | 100 | 10% | 10.0 | prereg-first, D6/D7 no-read, custody, NO-GO 공개 |
| Live Readiness | 0 | 10% | 0.0 | Fresh OOS·paper·broker·운영 리스크 미충족 |
| **종합** | **83 / 100** | **100%** | **83.4 → 83** | 플랫폼 연구 완성도이며 모델 수익성 점수가 아님 |

모델 연구 gate 자체는 **1/10**이다. 프로그램 품질 83점과 모델 성과 1/10을 혼동하지 않는다.

## 3. 전체 페이지 상태

| 페이지 | 진행 | D6R 표시 상태 | 이번 반영 | 다음 액션 | 예상 시간 |
|---|---:|---|---|---|---:|
| Home | 100% | `D6R_TRAIN_NO_GO_VISIBLE` | 공통 D6R/1-of-10 배너 | D6R2 MDP 재설계 연결 | 설계 후 30분 |
| Program Scorecard | 100% | `D6R_AUDITED_83` | 5영역·12페이지 재채점 | 새 연구마다 rubric 갱신 | 15분 |
| Discovery Lab | 100% | `D6R_PRIMARY_60_OF_60_NO_GO` | 10 gates·15 Native fold×seed·custody | gamma=0/bandit/MDP 비교 | 2~4시간 설계 |
| Data | 100% | `D6R_TRAIN_573_FIVE_FOLDS` | expanding fold와 D6/D7 no-read | fold-local scaler | 1~2시간 |
| Experiment | 100% | `D6R_PREREG_EXECUTED` | 고정 profile/control/seed/gate | D6R2 prereg | 2~4시간 |
| Training | 100% | `D6R_PRIMARY_60_MODELS_3M_STEPS` | 실제 60모델·3M steps | 동일 penalty 반복 금지 | 완료 |
| Evaluation | 100% | `D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED` | 23bp primary·0bp 진단 | MDP 오지정 반증 | 1~3시간 실행 |
| Compare | 100% | `D6R_NATIVE_DELTA_POS_0_017_BELOW_GATE` | Native/Shuffled·cost/turnover 비교 | gamma=0·bandit·ceiling | 1~2시간 |
| Report | 100% | `D6R_RECEIPT_CUSTODY` | manifest·summary·receipt SHA | release 계보 보존 | 완료 |
| Insights | 76% | `OBSERVATION_ONLY` | RL 성과 합산 금지 유지 | 검증 입력 경계 강화 | 30~60분 |
| Other Lanes | 73% | `INELIGIBLE_FOR_RL_RANK` | RULE/RL 분리 유지 | RL 점수 제외 유지 | 30분 |
| Settings | 84% | `LOCAL_ONLY` | 실행 권한 추가 없음 | 읽기 전용 유지 | 15분 |

Insights·Other Lanes·Settings의 낮은 점수는 D6R 실행 완료율을 뜻하지 않는다. 보조·관찰·로컬 설정 범위의 별도 성숙도다.

## 4. UX/UI 변경

| 화면 요소 | 목적 | 실패 시 표시 |
|---|---|---|
| Verdict banner | `NOT_CONFIRMED`, 1/10, D7 lock 즉시 인지 | danger 강조 |
| 6개 KPI | reward·accuracy·control·trade·stability·drawdown 요약 | 임계값 미달 수치 그대로 표시 |
| 10 gate grid | 사전등록 기준과 실측 분리 | PASS/FAIL 개별 표시 |
| 15 Native fold×seed matrix | 평균 하나로 시간/seed 실패를 숨기지 않음 | 음수 row danger 표시 |
| Interpretation boundary | 후보·확인·실거래 주장 분리 | D6/D7 no-read 명시 |
| Custody block | run·prereg·manifest·normalizer 추적 | 누락/변조 시 전체 BLOCK |

## 5. QA·재현성

| 검증 | 결과 |
|---|---|
| D6R 구현 TDD | 16 passed |
| D6R/dashboard/STOM 통합 회귀 | 121 passed, 2 environment-dependent skipped |
| Dashboard backend actual-run verification | exact 60 outcomes·60 models·custody·gate 재계산 |
| 전체 frontend tests | 402 passed |
| Svelte static check | 0 errors, 0 warnings |
| TypeScript no-excuse audit | 0 violations |
| Python Ruff | 통과 |
| Python basedpyright | 0 errors, 0 warnings |
| Production build | 974 modules transformed, 성공 |
| Browser QA | 실제 API D6R panel·83점 scorecard 렌더링, console warning/error 0 |
| Responsive QA | desktop 1265px·mobile 375px document horizontal overflow 0 |
| UX 개선 | 1400px 이하 execution meta 2열, 상태 chip 한 줄 표시 |
| 관찰된 성능 부채 | `/api/rl/runs?limit=100` cold 응답 29.08초; 후속 index/cache 대상 |

## 6. 증거와 개발 계보

| 항목 | 값 |
|---|---|
| Base release | `fork-v1.18.0-kronos-rl-d6-reused-validation` |
| Research branch | `codex/rl-d6r-train-falsification-v1` |
| Prereg commit | `91d88ce6d2dfbab7b388bca32b85e552c4ec0150` |
| Producer commit | `bbbdf5a3d5553126337b24f11d831ee879673b9b` |
| Artifact manifest | `83e71bc3bf9d5bfae66c7af3ac76521e1e1a6f700ec81fb6eb90d0ffe53aeee4` |
| Summary SHA-256 | `2d492a295066d8e29beb8b1d4f04af6986fc625a3512b63fe78ec0ee6dc23a92` |
| Receipt SHA-256 | `ab159550c080c88f545e2e16d0936bb7346f37fa61b65cb3b74b8e5547d205b4` |
| Release candidate | `fork-v1.19.0-kronos-rl-d6r-train-falsification` |

## 7. 다음 단계

| 순서 | 단계 | 이유 | 예상 시간 | D7 영향 |
|---:|---|---|---:|---|
| 1 | D6R2 질문·stop rule 사전등록 | 동일 penalty 반복 방지 | 2~4시간 | 잠금 유지 |
| 2 | fold-local normalizer | 현재 full-TRAIN scaler의 temporal limitation 제거 | 1~2시간 | 잠금 유지 |
| 3 | gamma=0 DQN vs contextual bandit vs supervised ceiling | MDP 오지정과 신호 부재 분리 | 1~3시간 | 잠금 유지 |
| 4 | stateful portfolio MDP env unit tests | action이 다음 position/state에 실제 영향 | 2~4시간 | 잠금 유지 |
| 5 | 새 train-only matrix | ≥5 folds·≥3 seeds·shuffle·23bp | 1~3시간 | 통과해도 후보만 |
| 6 | 새 봉인 기간 결정 | 후보가 있을 때만 별도 승인 | 30~60분 | 별도 prereg 후 검토 |

현재 D7을 실행할 수 있는 근거는 없다. 같은 D6 validation을 다시 사용하거나 penalty·seed를 결과에 맞춰 선택하지 않는다.

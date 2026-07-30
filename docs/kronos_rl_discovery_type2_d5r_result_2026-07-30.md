# Type2-D5R 용량·목적함수 연구 결과

## 최종 판정

| 항목 | 결과 | 등록 기준 | 판정 |
|---|---:|---:|---|
| Verdict | `D5R_CAPACITY_NOT_CONFIRMED` | 5개 gate 모두 통과 | **NO-GO** |
| 실제 강화학습 | SB3 DQN, 6개 연속 lineage | Native/Shuffle × 3 seeds | 완료 |
| 신규 학습량 | 총 4,800,000 step | 400k·800k checkpoint | 완료 |
| Native accuracy lift | -0.176265 | ≥ +0.030 | 실패 |
| Native reward-ratio lift | -0.233700 | ≥ +0.020 | 실패 |
| Native − Shuffle reward | +0.694599 | ≥ +0.200 | 통과 |
| 동시 개선 seed | 0/3 (0%) | ≥ 2/3 | 실패 |
| Invalid action | 0 | 0 | 통과 |
| D5 verdict | `D5_FULL_TRAIN_COST_NOT_CONFIRMED` | 변경 금지 | 유지 |
| Reused validation / Fresh OOS | `NOT_RUN_NO_READ` / `NOT_RUN_NO_READ` | 봉인 | 유지 |

D5R은 강화학습 모델을 실제로 생성하고 총 4.8M step을 학습하는 데 성공했다. 그러나 200k에서 800k로 학습량을 늘리면 성능이 개선되지 않고 모든 Native seed에서 악화됐다. 따라서 “모델 생성 실패”가 아니라 “단순 장기학습 가설의 실험적 기각”이다.

## D5R-1 진단 성과

| 지표 | Native 중앙값/범위 | 해석 |
|---|---:|---|
| exact accuracy | seed별 0.6614~0.7400 | D5 행동 복원은 불완전 |
| near-optimal 25bp 중앙값 | 0.766143 | 사전등록 0.85 미만, capacity 실행 조건 충족 |
| median regret | 0bp | 절반 이상 에피소드의 regret가 0에 가까움 |
| mean regret | 57.15~92.16bp | 소수의 큰 손실 꼬리가 평균을 악화 |
| Shuffle mean regret | 656.59~691.19bp | Native 신호와 control 분리가 큼 |

## D5R-2 checkpoint 결과

| Arm | Seed | 400k accuracy | 400k reward | 800k accuracy | 800k reward | 800k 추세 |
|---|---:|---:|---:|---:|---:|---|
| Native | 0 | 0.541012 | 0.682285 | 0.429319 | 0.575516 | 악화 |
| Native | 1 | 0.661431 | 0.830500 | 0.497382 | 0.616686 | 악화 |
| Native | 2 | 0.685864 | 0.850378 | 0.551483 | 0.713745 | 악화 |
| Shuffle | 0 | 0.162304 | -0.110886 | 0.158813 | -0.029010 | Native replay 0 이하 |
| Shuffle | 1 | 0.188482 | -0.050150 | 0.188482 | -0.082648 | Native replay 0 이하 |
| Shuffle | 2 | 0.172775 | -0.135101 | 0.171030 | -0.077913 | Native replay 0 이하 |

Shuffle의 자체 fit reward ratio도 400k에서 0.7932~0.8466이었지만 800k에서 0.5942~0.6741로 세 seed 모두 하락했다. 그러므로 실패를 단순 데이터 과적합으로만 부르기보다 DQN 장기 최적화 불안정, catastrophic forgetting, 고정 learning-rate·탐색 스케줄의 후반부 붕괴 가능성으로 분리해야 한다.

## 실패 원인과 다음 연구 대책

| 우선순위 | 확인된 문제 | 다음 사전등록 실험 | 성공 기준 | 목적 |
|---|---|---|---|---|
| P0 | 200k 이후 세 Native seed 모두 악화 | 100k 간격 checkpoint + TRAIN_ONLY purged internal early-stop | 3 seed 중 2개 이상 200k 성능 보존 | 최적 step 식별 |
| P0 | reward는 배우지만 exact action과 tail regret가 불안정 | cost-aware regret/advantage auxiliary objective | mean regret 25bp 이하 + reward lift 양수 | 큰 손실 꼬리 억제 |
| P1 | 고정 LR·탐색 후반 붕괴 가능성 | LR decay, target update, exploration schedule ablation | 400k→800k 성능 비하 없음 | 최적화 안정화 |
| P1 | 용량만 늘리는 가설 기각 | Double/Dueling/QR-DQN 또는 offline CQL 비교 | Native 우위 유지 + 3 seed 반복 | 알고리즘 변경 검증 |
| P2 | 행동 표현의 학습 가능성 상한 미확인 | oracle 행동 supervised pretrain 후 RL fine-tune (`HYBRID_RL`) | supervised ceiling과 RL 기여를 별도 표시 | 표현/탐색 원인 분리 |
| HOLD | D6/D7 데이터 누출 위험 | 위 TRAIN_ONLY gate 통과 전 validation/OOS 금지 | 별도 승인 | 과적합 주장 차단 |

일봉 종가 매매 모델 연구는 가능하지만, 이 D5R 결과만으로 수익성·실거래 준비를 주장할 수 없다. 다음 성공 경로는 “더 오래 학습”이 아니라 내부 purged early-stop과 regret 목적을 먼저 검증한 후, 통과한 단 하나의 preregistered 후보만 D6 reused validation과 D7 Fresh OOS로 보내는 것이다.

## 증거·계보

| 증거 | 값 |
|---|---|
| Diagnostic run | `type2-d5r-diagnostic-20260730-001` |
| Diagnostic manifest | `8f346a80421d413bfa02eb3ab6bbf036630ca7d290acd5061b872f319fa0e78e` |
| Primary run | `type2-d5r-primary-20260730-001` |
| Prereg SHA-256 | `bd5e771b10c9e3551030848675b57afa9db9f3f9b71cfd7e898e1acdc9f6176f` |
| Primary manifest | `a2d71046a9636fc66c272fb95474c0529f39a5fe02367c8349efc35739742747` |
| Summary SHA-256 | `add2faea6ad64cb16d817ea661d01ab29a66b5db1bff0660d8e16f26981c6921` |
| Receipt SHA-256 | `3d78ca3d80b091671328d618723322c74cf84ada906a939334e9dfdcba23c6c6` |
| Model / outcome | 12 / 12 |
| Producer commit / tree | `6423fcdd4a7a48bad0a555c94dd56ed20589a8c6` / `43f49fb2d3ba8f914414ee792219de625823d379` |
| Base release | `fork-v1.15.0-kronos-rl-d5-full-train-cost` |

## 전체 페이지 상태

| 페이지 | 진행률 | D5R 반영 결과 | 현재 점수/상태 | 다음 액션 |
|---|---:|---|---|---|
| Home | 100% | D5R NO-GO·OOS 봉인 공통 배너 | 연구 상태 강함 | 다음 prereg 연결 |
| Program Scorecard | 100% | 12/12·게이트·프로그램 86점 | 86/100 | release 계보 반영 |
| Discovery Lab | 100% | D5R 전용 capacity·control 패널 | AVAILABLE | D5S 가설 사전등록 |
| Data | 100% | 573 TRAIN_ONLY·23bp·hash 경계 | BOUND | D6 봉인 유지 |
| Experiment | 100% | D5R prereg·amendment 실행 완료 | COMPLETE | early-stop/regret prereg |
| Training | 100% | 실제 DQN 4.8M step·12 checkpoint | COMPLETE | 안정화 ablation |
| Evaluation | 100% | 3 fail / 2 pass gate 공개 | NO-GO | 원인 분해 |
| Compare | 100% | 200k·400k·800k·shuffle 비교 | COMPLETE | 알고리즘 비교 |
| Report | 100% | receipt·custody·SHA·결과 문서 | COMPLETE | PR·tag |
| Insights | 76% | 관찰 전용 유지 | PARTIAL | 정식 입력 경계 강화 |
| Other Lanes | 73% | RULE·intraday와 RL 성과 분리 | PARTIAL | 분리 유지 |
| Settings | 84% | read-only/local 연구 설정 | PARTIAL | 실행 권한은 보류 |

프로그램 종합 점수는 연구 플랫폼 기준 **86/100**, live readiness는 **0/100**이다. 실제 모델·negative control·비용·custody·실패 공개는 강하지만 Fresh OOS, paper gate, broker/risk operation이 없으므로 실거래 점수는 올리지 않는다.

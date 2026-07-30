# Type2-D5S 전역 조기종료·안정성 연구 결과

## 최종 판정

| 항목 | 실제 결과 | 사전등록 기준 | 판정 |
|---|---:|---:|---|
| Verdict | `D5S_STABILITY_CONFIRMED` | 7개 gate 모두 통과 | **TRAIN_ONLY CONFIRMED** |
| 실제 강화학습 | SB3 DQN, 6개 독립 lineage | Native/Shuffle × 3 seeds | 완료 |
| 신규 학습량 | 2,400,000 step | lineage당 400k | 완료 |
| 모델 / outcome | 36 / 36 | 2 arms × 3 seeds × 6 checkpoints | 완료 |
| 전역 선택 checkpoint | 100,000 step | 모든 arm·seed에 하나만 적용 | 통과 |
| Selected Native accuracy | 0.827225 | ≥ 0.712042 | 통과 |
| Selected Native reward ratio | 0.971076 | ≥ 0.872779 | 통과 |
| Native − Shuffle reward | +1.085154 | ≥ +0.200000 | 통과 |
| 400k accuracy 열화 | 0.019197 | ≤ 0.050000 | 통과 |
| 400k reward 열화 | 0.011771 | ≤ 0.050000 | 통과 |
| D5 기준 보존 seed | 3/3 (100%) | ≥ 2/3 | 통과 |
| Invalid action | 0 | 0 | 통과 |
| Reused validation / Fresh OOS | `NOT_RUN_NO_READ` / `NOT_RUN_NO_READ` | 봉인 | 유지 |

Kronos는 이번 연구에서 **실제 일봉 종가 매매 DQN 모델을 생성하고 TRAIN_ONLY 안정성 gate를 처음으로 통과**했다. 이는 모델 생성·학습·negative control 분리·전역 checkpoint 선택에 성공했다는 뜻이다. 다만 재사용 validation(D6), Fresh OOS(D7), paper forward, 실거래를 통과했다는 뜻은 아니며 수익성·promotion·브로커 준비 주장은 계속 금지된다.

## 왜 이전 NO-GO와 이번 CONFIRMED가 모순이 아닌가

| 단계 | 질문 | 결과 | 이번 연구가 바꾼 점 |
|---|---|---|---|
| D5 | 200k 비용 포함 학습이 seed 다수에서 절대 gate를 통과하는가 | `NOT_CONFIRMED` | 기준선으로만 유지 |
| D5R | 1e-3 LR로 400k·800k까지 더 오래 학습하면 개선되는가 | `NOT_CONFIRMED` | 장기학습 가설 기각 |
| D5S | 3e-4 LR와 하나의 전역 조기종료 지점이 Native 신호와 안정성을 보존하는가 | `CONFIRMED` | 100k 전역 checkpoint 발견 |

D5R의 실패는 200k 이후 성능 붕괴와 고정된 높은 learning rate·탐색 스케줄의 불안정 가능성을 드러냈다. D5S는 learning rate를 `1e-3 → 3e-4`로 낮추고 50k~400k 곡선에서 하나의 전역 checkpoint만 선택했다. seed별·arm별 cherry-pick이나 사후 재학습 없이 100k가 선택됐고, 400k에서도 허용 열화 범위 안에 남았다.

## 23bp checkpoint 중앙값 곡선

| Reward arm | Steps | Native accuracy 중앙값 | Native reward 중앙값 | Fit reward 중앙값 | 해석 |
|---|---:|---:|---:|---:|---|
| Native | 50k | 0.809773 | 0.953359 | 0.953359 | 빠른 학습 |
| Native | **100k** | **0.827225** | **0.971076** | **0.971076** | **전역 선택** |
| Native | 150k | 0.858639 | 0.970347 | 0.970347 | accuracy 상승, reward는 근소 하락 |
| Native | 200k | 0.837696 | 0.969516 | 0.969516 | 안정 범위 |
| Native | 300k | 0.835951 | 0.966574 | 0.966574 | 완만한 열화 |
| Native | 400k | 0.808028 | 0.959305 | 0.959305 | gate 허용 열화 내 |
| Shuffled | 50k | 0.181501 | -0.103967 | 0.935074 | control fit은 높지만 Native 전이는 실패 |
| Shuffled | **100k** | **0.167539** | **-0.114078** | **0.964236** | **선택 지점 negative control** |
| Shuffled | 150k | 0.184991 | -0.087397 | 0.963576 | Native 전이는 계속 음수 |
| Shuffled | 200k | 0.178010 | -0.095390 | 0.972528 | control 분리 유지 |
| Shuffled | 300k | 0.171030 | -0.065834 | 0.970360 | control 분리 유지 |
| Shuffled | 400k | 0.171030 | -0.092017 | 0.967713 | control 분리 유지 |

Shuffled 모델도 자기 데이터 fit reward는 0.96 수준까지 학습하지만 Native replay reward는 음수다. 따라서 D5S 결과는 단순한 행동 빈도 암기보다 Native 구조에 의존하는 신호가 있음을 지지한다. 이것은 TRAIN_ONLY 인과·수익성 증명이 아니라 negative control 분리 증거다.

## 선택 checkpoint의 seed별 결과

| Arm | Seed | 100k accuracy | 100k reward ratio | D5 200k 기준 보존 | 판정 |
|---|---:|---:|---:|---|---|
| Native | 0 | 0.801047 | 0.952027 | accuracy·reward 모두 상회 | 통과 |
| Native | 1 | 0.827225 | 0.971076 | accuracy·reward 모두 상회 | 통과 |
| Native | 2 | 0.853403 | 0.973218 | accuracy·reward 모두 상회 | 통과 |
| Shuffled | 0 | 0.167539 | -0.114078 | negative control | 분리 |
| Shuffled | 1 | 0.171030 | -0.097243 | negative control | 분리 |
| Shuffled | 2 | 0.143106 | -0.158814 | negative control | 분리 |

## 다음 연구 단계

| 순서 | 단계 | 실행 전 조건 | 핵심 질문 | 성공 기준 | 현재 상태 |
|---:|---|---|---|---|---|
| 1 | D6 preregistration | D5S release·custody 고정 | 선택된 100k 정책이 재사용 validation에서 유지되는가 | 사전등록 비용·drawdown·baseline gate | **다음 액션** |
| 2 | D6 reused validation | D6 prereg commit 이후에만 데이터 read | TRAIN_ONLY 선택이 기존 validation에 과적합됐는가 | control 포함 gate 통과 | 봉인 |
| 3 | D7 Fresh OOS | D6 통과와 별도 외부 승인 | 한 번도 읽지 않은 기간에서 신호가 유지되는가 | 비용·drawdown·baseline·negative control | 봉인 |
| 4 | Paper forward | D7 통과 | 실제 시간 순서·지연·체결에서 재현되는가 | 운영 리스크 gate | 금지 |
| 5 | Broker/live | 별도 권한·kill switch·감사 체계 | 운영 가능한가 | 별도 제품 승인 | 금지 |

다음 연구는 새로운 모델을 다시 고르는 단계가 아니다. `D_DQN_STABLE_LR`, 100k checkpoint, 23bp 비용, 하나의 전역 선택을 고정한 뒤 D6 사전등록부터 해야 한다. D6를 읽기 전에 기준을 문서와 커밋으로 동결해야 이번 TRAIN_ONLY 성공을 과적합으로 오염시키지 않는다.

## 증거·계보

| 증거 | 값 |
|---|---|
| Smoke run | `type2-d5s-smoke-20260730-001` |
| Primary run | `type2-d5s-primary-20260730-001` |
| Prereg SHA-256 | `cecaf4b70fb437db1b7b4aacecb3113e6f80e14b9d0d204faa68afed62c77a6a` |
| Primary manifest | `c9f7f0a35c16491b02a78fe2932f9b006891d62e5318b731d696893e788387f9` |
| Summary SHA-256 | `4f0e9803e181425dfd0780c49d15ec7b2f0783119f6f4e0fb71f9abdb563832a` |
| Receipt SHA-256 | `8a03a4b8d646090a4b3674f6dbe2eaf09abad579f1b067882a985820cf5b9984` |
| Model / outcome | 36 / 36 |
| Producer commit / tree | `0203e068e8dda89c994d8f940618677882499540` / `330de1cf4b52c8a0666de592b3d1e665b304be33` |
| Base release | `fork-v1.16.0-kronos-rl-d5r-capacity-objective` |

## 전체 페이지 상태와 프로그램 점수

| 페이지 | 진행률 | D5S 반영 결과 | 현재 점수/상태 | 다음 액션 |
|---|---:|---|---|---|
| Home | 100% | D5S CONFIRMED·OOS 봉인 공통 상태 | STRONG | D6 prereg 연결 |
| Program Scorecard | 100% | 36/36·7/7 gate·프로그램 86점 | 86/100 | D6 상태 추적 |
| Discovery Lab | 100% | D5S 안정성 곡선·gate 표·exact matrix | AVAILABLE | D6 고정 후보 표시 |
| Data | 100% | 573 TRAIN_ONLY·23bp·hash 경계 | BOUND | D6 입력 봉인 유지 |
| Experiment | 100% | D5S prereg·Smoke·Primary 완료 | COMPLETE | D6 preregistration |
| Training | 100% | 실제 DQN 2.4M step·36 checkpoints | COMPLETE | 100k 모델 고정 |
| Evaluation | 100% | D5S gate 7/7 통과 공개 | TRAIN_ONLY CONFIRMED | D6 validation |
| Compare | 100% | 6 checkpoints·3 seeds·shuffle 비교 | COMPLETE | D5/D5R/D5S 비교 유지 |
| Report | 100% | receipt·custody·SHA·결과 문서 | COMPLETE | PR·tag 계보 |
| Insights | 76% | 관찰 전용 유지 | PARTIAL | 정식 입력 경계 강화 |
| Other Lanes | 73% | `ts_imb` RULE과 RL 성과 분리 | PARTIAL | 분리 유지 |
| Settings | 84% | read-only/local 연구 설정 | PARTIAL | 실행 권한 보류 |

프로그램 종합 점수는 연구 플랫폼 기준 **86/100**, live readiness는 **0/100**이다. D5S는 RL evidence의 완성도를 높였지만 Fresh OOS, paper gate, broker·risk operation을 추가하지 않았으므로 live 점수와 수익성 주장은 올리지 않는다.

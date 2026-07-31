# Kronos RL D6 프로그램 완료 보고서

- 작성일: 2026-07-31 KST
- 검토 run: `type2-d6-primary-20260731-002`
- 판정: `D6_REUSED_VALIDATION_NOT_CONFIRMED`
- 연구 경계: 로컬 연구·백테스트 evidence 전용. 수익성, promotion, paper, live 또는 브로커 준비도 주장이 아니다.
- Fresh OOS: `NOT_RUN_NO_READ`; D7은 계속 봉인한다.

## 1. 결론

D5S에서 선택한 실제 DQN 100K 정책은 TRAIN_ONLY 안정성 gate를 통과했지만, 사전등록된 128-session reused validation에서 일반화되지 않았다. D6는 7개 gate 중 invalid action gate 하나만 통과했으므로 `NO-GO`다. 이미 읽은 validation에 맞춘 재튜닝은 금지하며, 다음 연구는 train-only 범위의 D6R 반증 실험으로 제한한다.

## 2. D6 성과와 실패 지표

| 항목 | 기준 | 실측 | 판정 |
|---|---:|---:|---|
| Native median accuracy | ≥ 0.200 | 0.179688 | FAIL |
| Native median reward ratio, 23bp | ≥ 0 | -0.037396 | FAIL |
| Native median total reward | ≥ 0 | -0.302731 | FAIL |
| Native − shuffled reward delta | ≥ 0.100 | -0.039216 | FAIL |
| Native passing seed fraction | ≥ 2/3 | 0/3 | FAIL |
| Native median max drawdown | ≤ 0.250 | 0.810130 | FAIL |
| Invalid actions | 0 | 0 | PASS |
| Native median reward ratio, 0bp 진단 | 진단 전용 | -0.003198 | 음수; 비용만의 실패가 아님 |

추가 진단:

- D5S train accuracy 0.827225가 D6 validation 0.179688로 하락해 6-action 무작위 기준 0.166667에 가까워졌다.
- Native가 shuffled control보다 0.039216 낮아 negative-control separation이 역전됐다.
- Native trade rate가 0.882813~0.937500으로 높지만, 0bp 진단도 음수여서 거래비용만으로 설명할 수 없다.
- 가장 타당한 현재 가설은 train-only 과적합, regime 변화, candidate-rank 분포 변화다. 이는 확정 원인이 아니라 다음 train-only 반증 대상이다.

## 3. 재현성·custody

| 증거 | 값 |
|---|---|
| validation episodes | 128 |
| validation snapshot SHA-256 | `31134cd5307174b6530031990d4580f1ff45360b6d6df2dbdc3cd2e14ae1e1c7` |
| validation read count | 1 |
| recovery source | `type2-d6-primary-20260731-001`의 `FAILED_RUN_SNAPSHOT` |
| recovered run | `type2-d6-primary-20260731-002` |
| artifact manifest SHA-256 | `4e72f8bf7ef0e52fbe7e7e093a9991980c1aa2806e0d993adb869bc97b676a63` |
| summary SHA-256 | `a0828b1006734ba40c5838bb09edfab28d87035b9b4d42e0e0a210c8b9bbe21f` |
| receipt SHA-256 | `b47f74a44af33b27df803d0d71c372517b5dd9ed4011471bcc57427490d89049` |
| source models | Native 3 + Shuffled 3, 총 6개 |

첫 run의 정책 로드 실패는 결과로 덮어쓰지 않고 terminal `FAILED/NO_GO`로 보존했다. 두 번째 run은 동일 typed snapshot을 복구했으며 validation 원본을 다시 읽지 않았다.

## 4. 프로그램 점수

| 영역 | 점수 | 가중치 | 가중 점수 | 근거 |
|---|---:|---:|---:|---|
| Platform | 98 | 30% | 29.4 | 12개 페이지, D6 API, custody viewer |
| RL Evidence | 75 | 30% | 22.5 | 실제 DQN·control은 있으나 D6 validation 실패, D7 미실행 |
| Engineering | 100 | 20% | 20.0 | 실패 보존, snapshot 복구, exact matrix, 테스트·빌드 |
| Governance | 100 | 10% | 10.0 | read-before-prereg 차단, hashes, NO-GO 공개 |
| Live Readiness | 0 | 10% | 0.0 | Fresh OOS·paper·broker·운영 리스크 모두 미충족 |
| **종합** | **82 / 100** | **100%** | **81.9 → 82** | 연구 플랫폼 완성도이며 모델 성능 점수가 아님 |

## 5. 전체 페이지 상태

| 페이지 | 진행 | D6 표시 상태 | 다음 액션 | 예상 시간 |
|---|---:|---|---|---:|
| Home | 100% | `D6_VALIDATION_NO_GO_VISIBLE` | D6R 계획 연결 | 완료 |
| Program Scorecard | 100% | `D6_AUDITED_82` | D6R 상태 추적 | 완료 |
| Discovery Lab | 100% | `D6_PRIMARY_6_OF_6_NO_GO` | D6R train-only falsification | 완료 |
| Data | 100% | `D6_VALIDATION_128_BOUND` | 새 확인 기간 봉인 유지 | 완료 |
| Experiment | 100% | `D6_PREREG_EXECUTED` | D6R 사전등록 | 1~2시간 |
| Training | 100% | `D5S_PRIMARY_36_OF_36` | 기존 모델 동결; validation 재튜닝 금지 | 완료 |
| Evaluation | 100% | `D6_REUSED_VALIDATION_NOT_CONFIRMED` | 새 가설을 train-only에서 반증 | 완료 |
| Compare | 100% | `D6_NATIVE_DELTA_NEG_0_039` | train/validation 격차 추적 | 완료 |
| Report | 100% | `D6_RECEIPT_CUSTODY` | PR·merge·tag 계보 연결 | 완료 |
| Insights | 76% | `OBSERVATION_ONLY` | 검증 입력 경계 강화 | 30~60분 |
| Other Lanes | 73% | `INELIGIBLE_FOR_RL_RANK` | RL 점수 제외 유지 | 30분 |
| Settings | 84% | `LOCAL_ONLY` | 실행 권한 추가 보류 | 15분 |

Insights, Other Lanes, Settings의 미완료율은 D6 연구 판정을 막지 않는다. 해당 항목은 관찰·보조·로컬 설정 범위이며 RL 성과에 합산하지 않는다.

## 6. UX/UI 및 QA

| 검증 | 결과 |
|---|---|
| D6 fail-closed parser | exact 6 evaluations, 128 episodes, D7 seal, read count 검증 |
| Discovery UI | D5S train 성공 → D6 validation 실패 비교, 7개 gate, 6개 평가, 실패 원인 표시 |
| 공통 연구 배너 | `D6 / VALIDATION · NO-GO / 1 of 7 / D7 LOCKED` |
| Scorecard | 82점, 5개 영역, 전체 12개 페이지, capability boundary 표시 |
| Svelte static check | 0 errors, 0 warnings |
| frontend regression | 399 passed |
| production build | 969 modules transformed, 성공 |
| browser QA | Discovery·Scorecard 실제 API 렌더링 확인; console warning/error 0 |
| mobile QA | 390px viewport, document horizontal overflow 0 |

## 7. 다음 단계: D6R

| 순서 | 작업 | 허용 데이터 | 완료 기준 | 예상 시간 |
|---:|---|---|---|---:|
| 1 | D6R 사전등록 | train-only | 가설·fold·seed·비용·중단 기준 commit | 1~2시간 |
| 2 | 무거래/HOLD 및 turnover penalty baseline | train-only | 기존 D5S와 동일 seed/control 비교 | 1~2시간 |
| 3 | chronological walk-forward train folds | train-only | fold 간 방향·seed 안정성 표 | 1~2시간 |
| 4 | 실패 원인 분리 | train-only | 과적합/분포변화/행동붕괴 중 반증 가능한 결론 | 1시간 |
| 5 | 새 확인 가설 결정 | 새로 봉인할 기간만 | 통과 가설이 없으면 종료; 있으면 별도 prereg | 30분 |

D6R이 train-only에서 안정적인 새 가설을 만들지 못하면 연구를 종료하거나 환경·행동 공간을 재설계한다. D6 validation 수치에 맞춘 threshold, reward, seed 선택은 하지 않는다. D7은 D6 실패 상태에서 열지 않는다.

## 8. Git 전달 원칙

1. 연구 구현·실행 결과·backend·frontend source·generated dist·보고서를 논리 커밋으로 분리한다.
2. `codex/rl-d6-reused-validation-v1` → `research/type1-closing-rl-v1` PR 후 통합 branch를 통해 `master` PR로 연결한다.
3. 두 PR의 CI/회귀가 통과한 뒤 annotated tag `fork-v1.18.0-kronos-rl-d6-reused-validation`을 생성한다.
4. 태그는 연구 플랫폼 release 표식이며 모델 GO 또는 live readiness를 의미하지 않는다.

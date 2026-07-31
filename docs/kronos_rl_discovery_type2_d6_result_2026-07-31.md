# Type2-D6 reused-validation 연구 결과

## 최종 판정

| 항목 | 결과 | 사전등록 기준 | 판정 |
|---|---:|---:|---|
| Verdict | `D6_REUSED_VALIDATION_NOT_CONFIRMED` | 7개 gate 모두 통과 | **NO-GO** |
| Validation episodes | 128 | 최초 chronological eligible 128개 | 완료 |
| 평가 모델 | 6 | Native/Shuffle × seed 0/1/2, 고정 100K | 완료 |
| Native median accuracy | 0.179688 | ≥ 0.200000 | 실패 |
| Native median 23bp reward ratio | -0.037396 | ≥ 0 | 실패 |
| Native median 23bp total reward | -0.302731 | ≥ 0 | 실패 |
| Native − Shuffle reward ratio | -0.039216 | ≥ +0.100000 | 실패 |
| Native passing seeds | 0/3 | ≥ 2/3 | 실패 |
| Native median drawdown | 0.810130 | ≤ 0.250000 | 실패 |
| Invalid actions | 0 | 0 | 통과 |
| Fresh OOS | `NOT_RUN_NO_READ` | 봉인 | 유지 |

D5S에서 선택한 100K DQN 정책은 TRAIN_ONLY 안정성은 보였지만 reused validation에서 재현되지 않았다. 사전등록된 7개 gate 중 invalid-action gate만 통과했으며, D7 Fresh OOS 진입 조건은 충족되지 않았다.

## Seed별 23bp 결과

| Arm | Seed | Accuracy | Reward ratio | Total reward | Trade rate | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Native | 0 | 0.179688 | -0.037396 | -0.302731 | 0.937500 | 0.591866 |
| Native | 1 | 0.148438 | -0.032627 | -0.264129 | 0.898438 | 0.810130 |
| Native | 2 | 0.179688 | -0.105328 | -0.852663 | 0.882812 | 1.102873 |
| Shuffled | 0 | 0.140625 | -0.101667 | -0.823026 | 0.945312 | 1.055642 |
| Shuffled | 1 | 0.148438 | +0.001820 | +0.014733 | 0.937500 | 0.305350 |
| Shuffled | 2 | 0.210938 | +0.054725 | +0.443015 | 0.945312 | 0.683464 |

## 왜 D5S 성공이 D6에서 실패했는가

| 관찰 | 근거 | 해석 |
|---|---|---|
| Accuracy 붕괴 | D5S 0.827225 → D6 0.179688 | 6-action 무작위 기준 0.166667에 근접해 train 구조를 일반화하지 못함 |
| 0bp에서도 약함 | Native median 0bp reward ratio -0.003198 | 23bp 비용만이 실패 원인은 아님 |
| 높은 거래 빈도 | Native trade rate 0.883~0.938 | 약한 신호에서도 거의 매일 거래해 비용과 오판 손실을 누적 |
| Control 분리 역전 | Native−Shuffle -0.039216 | Native 정책이 Shuffled median보다도 낮아 학습 신호의 validation 보존 실패 |
| 큰 경로 손실 | Native median drawdown 0.810130 | 단순 평균뿐 아니라 시계열 경로 안정성도 실패 |

가장 강한 설명은 D5S가 573개 TRAIN_ONLY episode의 행동·보상 구조에 과적합됐고 validation 기간의 분포 또는 후보 순위 관계가 달라졌다는 것이다. D6 결과를 본 뒤 현재 validation에 맞추어 임계값이나 모델을 수정하면 confirmatory evidence가 아니라 추가 과적합이 되므로 허용하지 않는다.

## 운영 실패와 복구

첫 실행 `type2-d6-primary-20260731-001`은 validation snapshot을 한 번 생성한 뒤 SB3 loader의 Pydantic Protocol schema 오류로 terminal `NO_GO`가 됐다. 실패 run은 수정하지 않았다. 복구 실행 `type2-d6-primary-20260731-002`는 실패 run의 frozen snapshot SHA `31134cd5...`를 검증해 재사용했고 public rows를 다시 읽지 않았다.

| 항목 | 결과 |
|---|---|
| Validation read count | 1 |
| Failed run 보존 | 완료 |
| Recovery snapshot typed validation | 완료 |
| Recovery run terminalization | `COMPLETE` |
| Research verdict | `D6_REUSED_VALIDATION_NOT_CONFIRMED` |

## 다음 연구 대책

1. D7 Fresh OOS는 열지 않는다. D6 통과가 선행 조건이다.
2. 현재 validation은 이미 읽었으므로 모델 선택이나 성공 주장에 다시 사용할 수 없다.
3. 후속 단계는 D6R train-only falsification으로 제한한다. no-trade action 강화, trade-rate penalty, walk-forward train fold, seed 안정성을 사전등록해 원인을 분리한다.
4. D6R에서 새 후보를 만들더라도 현재 validation 결과는 진단 참고값일 뿐 승인 gate가 아니다.
5. 최종 검증에는 별도로 봉인된 새로운 기간과 새로운 prereg가 필요하다.

## 증거 계보

| 증거 | 값 |
|---|---|
| Prereg commit | `094cae71fbdfd23af88b37e32ee0e53df73698fc` |
| Producer commit | `e47ffc88b07c9f0d34cdaaa7f07cfdf1c6460997` |
| Primary run | `type2-d6-primary-20260731-002` |
| Artifact manifest | `4e72f8bf7ef0e52fbe7e7e093a9991980c1aa2806e0d993adb869bc97b676a63` |
| Summary SHA-256 | `a0828b1006734ba40c5838bb09edfab28d87035b9b4d42e0e0a210c8b9bbe21f` |
| Receipt SHA-256 | `b47f74a44af33b27df803d0d71c372517b5dd9ed4011471bcc57427490d89049` |
| Validation snapshot | `31134cd5307174b6530031990d4580f1ff45360b6d6df2dbdc3cd2e14ae1e1c7` |

본 결과는 로컬 연구 backtest 증거다. 수익성, promotion, paper-forward, broker 또는 live readiness를 주장하지 않는다.

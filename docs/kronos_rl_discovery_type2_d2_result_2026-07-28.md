# Kronos RL Discovery Type2-D2 결과 및 다음 연구 계획

> 실행일: 2026-07-28~29 KST  
> 최종 상태: `COMPLETE`  
> 판정: `D2_PARTIAL_CAPACITY_CONFIRMED`  
> 범위: 실제 일봉 공개 데이터의 `TRAIN_ONLY / RESEARCH_ONLY`

## 1. 결론

D2는 실제 일봉 데이터로 MaskablePPO 모델 24개를 생성하고 학습·저장·재평가하는 데 성공했다.
행동은 `STOP`과 `BUY_OBSERVABLE_TOP_RET_1D_PREV` 두 개이며, 행동 후보는 의사결정 시점에
관측 가능한 값으로만 정했다. 미래 수익률은 보상과 사후 oracle에만 사용했다.

다만 성공 범위는 8개 일봉 episode까지다. 1/8/32/128 episode 중 사전등록된 90% 적합
게이트를 3개 seed의 2/3 이상에서 native와 shuffled arm이 함께 통과한 최대 규모는 8이다.
32와 128에서는 과적합조차 충분히 하지 못했다. 따라서 “강화학습 모델 생성과 소규모 실제
데이터 학습”은 가능하지만, 일반화·수익성·실거래 준비를 확인한 것은 아니다.

## 2. 실제 실행 행렬

| Profile | 규모 | Arm | Seed | 모델 수 | 결과 |
|---|---|---|---|---:|---|
| Smoke | 1, 8 | native, shuffled | 0 | 4/4 | 완료 |
| Primary | 1, 8, 32, 128 | native, shuffled | 0, 1, 2 | 24/24 | 완료 |
| 합계 | 4개 규모 | 2개 arm | 3개 seed | 28개 실행 | 실패 run 1개는 저장 경로 계약 위반 증거로 별도 보존 |

Primary 평균:

| Episodes | Arm | Fit 정확도 | Fit 보상비 | 원래 수익률 보상비 | 23bp 진단 보상비 | 해석 |
|---:|---|---:|---:|---:|---:|---|
| 1 | Native | 1.000 | 1.000 | 1.000 | 1.000 | 단일 표본 과적합 가능 |
| 1 | Shuffled | 1.000 | 1.000 | 1.000 | 1.000 | 단일 표본이라 control 분리 불가 |
| 8 | Native | 0.958 | 0.747 | 0.747 | 0.745 | seed 0·2 통과, seed 1 불안정 |
| 8 | Shuffled | 0.917 | 0.667 | -0.047 | -0.062 | 자체 fit과 원래 수익률이 분리됨 |
| 32 | Native | 0.875 | 0.832 | 0.832 | 0.823 | 90% gate 미달 |
| 32 | Shuffled | 0.844 | 0.745 | -0.299 | -0.362 | 원래 수익률에서 음수 |
| 128 | Native | 0.672 | 0.440 | 0.440 | 0.428 | 과적합 능력 부족 |
| 128 | Shuffled | 0.703 | 0.507 | -0.095 | -0.132 | 원래 수익률에서 음수 |

128 episode에서 native와 shuffled의 원래 수익률 보상비 차이는 `+0.535502`다. 이는 현재
관측 표현에 무정보만 있는 것은 아니라는 train-only 단서다. 그러나 native 자체 보상비가
0.440에 불과하므로 alpha 또는 수익성 증거로 사용할 수 없다.

## 3. 기존 실패가 계속된 이유

| 원인 | 과거 증거 | D2에서 분리된 사실 | 판단 |
|---|---|---|---|
| 행동공간 과대 | 기존 Type1은 501행동 | 2행동에서는 8 episode까지 적합 | 유력한 원인 후보; 단독 인과 미확정 |
| 관측 차원 과대 | 기존 Type1은 8,514차원 | D2는 29차원 | 축소 효과 확인 |
| 비용 장벽 | 기존 Primary는 23bp | D2 0bp 학습과 23bp 진단 분리 | 비용만이 유일한 원인은 아님 |
| PPO seed 불안정 | D0 PPO-only seed 분산 큼 | D2 8 episode seed 1만 크게 실패 | 재현된 원인 |
| 표본 증가 대비 학습예산 부족 | 큰 데이터에서도 고정 예산 | 32/128에서 fit 하락 | 관찰된 병목 후보; D3에서 분리 필요 |
| 표현력/후보 선택 제약 | top-1 ret_1d_prev 규칙 후보 | @128 native가 shuffle보다 우수하나 절대 fit 낮음 | D3 핵심 질문 |
| 비용 후 신호 약화 | 기존 23bp NO-GO | 23bp에서도 native 평균은 소폭 하락 | D4에서 정식 비용 사다리 필요 |
| 일반화 미검증 | Fresh OOS 봉인 | 계속 `NOT_RUN_NO_READ` | 의도된 안전 경계 |

## 4. 증거와 재현성

| 항목 | 값 |
|---|---|
| Prereg | `docs/kronos_rl_discovery_type2_d2_prereg_2026-07-28.json` |
| Primary run | `webui/rl_runs/rl_discovery/type2-d2-primary-20260728-v1` |
| Dataset | `type1-close-20260803-005`, 919,500 rows |
| Source rows SHA-256 | `a0fbeb1b54e59e3c1e83c66c8ca5aa85caa7063b7cbb382efeb716e86ae915cf` |
| Episode snapshot SHA-256 | `e971517a10a3c3953f9ba02fd7b2ce4e901e82bfda2f9c3c6c716ff130b1929e` |
| Prereg SHA-256 | `2e995923bfeebde5559eedbbb27ff209bd883da8dbe09ea17a5f421fe33d794a` |
| Artifact manifest SHA-256 | `f1d9f60c7ed5fba78044fef8772eb2e24e866ca87a8db53cc5051ac9f0fd6c44` |
| Summary file SHA-256 | `b8f0cb66e0943a34f32c1fbe1f0e7e1481dc55ef92abb2398474d2efc7125fdb` |
| Terminal receipt file SHA-256 | `bd9871edcae89b4fd71ee861b4bbbef95209b3227e5088ada0c38975f267c1e9` |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Promotion / 수익성 주장 | `BLOCKED / BLOCKED` |

## 5. 전체 프로그램 및 페이지 상태

프로그램 점수는 연구 플랫폼 완성도 점수이며 모델 수익률 점수가 아니다.

| 영역 | 점수 | 가중치 | 상태 | 다음 액션 |
|---|---:|---:|---|---|
| Platform | 96 | 30% | STRONG | D3 증거 연결 |
| RL Evidence | 78 | 30% | PARTIAL | D3 representation/action ablation |
| Engineering | 94 | 20% | STRONG | scale/arm/seed resume 강화 |
| Governance | 86 | 10% | PARTIAL | research→master PR 계보 정리 |
| Live Readiness | 0 | 10% | BLOCKED | D6 전까지 유지 |
| **전체** | **80/100** | **100%** | **RESEARCH PLATFORM** | **수익성 점수가 아님** |

| 페이지 | 진행률 | D2 반영 상태 | 다음 단계 | 예상 시간 |
|---|---:|---|---|---:|
| Home | 99% | D2 partial capacity | D3 안전 상태 연결 | 20분 |
| Program Scorecard | 99% | 80/100 재채점 | D3 후 재채점 | 15분 |
| Discovery Lab | 100% | 24/24 모델·gate | D3 prereg | 2~4시간 |
| Data | 96% | 128 train episodes·SHA | 표현 후보 고정 | 2~3시간 |
| Experiment | 100% | D2 prereg 완료 | D3 prereg | 2~3시간 |
| Training | 99% | Smoke/Primary 완료 | D3 실행 | 2~4시간 |
| Evaluation | 99% | fit/native/23bp 분리 | 32/128 실패 원인 분리 | 2~4시간 |
| Compare | 98% | native/shuffle 비교 | 표현별 @128 비교 | 1~2시간 |
| Report | 99% | receipt·결과 문서 | D3 문서 연결 | 30~60분 |
| Insights | 72% | 관찰 전용 | 정책 증거와 경계 강화 | 30~60분 |
| Other Lanes | 70% | RL 점수 제외 | 현 상태 유지 | 30분 |
| Settings | 80% | 읽기 전용 | 실행 권한 보류 | 15분 |

## 6. 다음 단계: D3

D3의 목표는 128 episode에서 과적합 게이트를 통과하지 못한 이유를 표현과 행동 후보 수로
분리하는 것이다. Fresh OOS를 열지 않고 같은 128개 train episode만 사용한다.

| 순서 | 연구 arm | 질문 | 실행 규모 | 예상 시간 |
|---:|---|---|---|---:|
| 1 | 현재 top-1 / 29차원 | D2 재현 기준선 | 2 arms × 3 seeds | 1~2시간 |
| 2 | top-5 후보 / 약 71차원 | 후보 선택 자유도가 fit을 높이는가 | native+shuffle × 3 seeds | 2~3시간 |
| 3 | 날짜/시장 regime embedding | 동일 특징의 표현력이 병목인가 | native+shuffle × 3 seeds | 2~3시간 |
| 4 | 학습예산 1×/4× | 단순 under-training인가 | 통과 가능성이 높은 arm만 | 2~4시간 |
| 5 | 판정 | 128 episode에서 2/3 seed가 정확도·보상비 0.90 이상인가 | prereg gate | 30분 |

D3가 128 episode 과적합에 성공하면 D4에서 0/5/10/23/46bp 비용 사다리로 이동한다. D3가
실패하면 모델을 수익성 평가로 보내지 않고 표현·학습예산 병목을 `NO-GO`로 기록한다.

## 7. Git 전달 계획

| 단계 | 브랜치/태그 | 작업 |
|---:|---|---|
| 1 | `codex/rl-d2-historical-scale-v1` | 소스·테스트·UI·문서 커밋 |
| 2 | PR → `research/type1-closing-rl-v1` | D2 연구선 병합 |
| 3 | `fork-v1.11.0-kronos-rl-d2-historical-scale` | research 병합 commit annotated tag |
| 4 | 통합 PR → `master` | 기존 `origin/master` 고유 commit과 research 계보 병합·검증 |
| 5 | 최종 release tag | master 통합 commit에만 생성 |

`ts_imb`는 계속 RULE 전략이며 D2 결과를 RL 수익 곡선으로 표현하지 않는다.

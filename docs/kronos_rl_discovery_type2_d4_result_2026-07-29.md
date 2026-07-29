# Kronos RL Discovery Type2-D4 결과 및 전체 페이지 진행 보고

> 실행일: 2026-07-29 KST
> 상태: `COMPLETE`
> 판정: `D4_ALGORITHM_OBJECTIVE_CONFIRMED`
> 범위: 실제 일봉 `TRAIN_ONLY / RESEARCH_ONLY`; Fresh OOS `NOT_RUN_NO_READ`

## 1. 결론

D4는 D3와 동일한 실제 일봉 train-only 128개 세션에서 supervised ceiling, MaskablePPO, DQN, 지도 사전학습 후 PPO를 native/shuffled × seed 0·1·2로 비교해 24개 모델을 생성했다. 비-RL supervised ceiling은 1.000을 기록했고 실제 RL인 DQN은 native 평균 0.988, shuffled 자기-fit 0.991, shuffled→native -0.111로 사전등록 gate를 통과했다.

이는 현재 표현에서 DQN이 train-only reward를 실제 강화학습으로 학습하고 대조군과 분리했다는 뜻이다. 일반화, 수익성, 실거래 성공을 의미하지 않는다. Fresh OOS와 reused validation은 열지 않았다.

## 2. 알고리즘 결과

| Arm | 유형 | Native fit | Native 23bp | Shuffled fit | Shuffled→native | Fit accuracy | 판정 |
|---|---|---:|---:|---:|---:|---:|---|
| A Supervised ceiling | 비-RL 진단 | 1.000 | 1.000 | 1.000 | -0.124 | 1.000 | 표현 상한 확인 |
| B PPO baseline | 실제 RL | 0.533 | 0.512 | 0.527 | -0.227 | 0.430 | gate 실패 |
| C DQN discrete | 실제 RL | **0.988** | **0.985** | **0.991** | **-0.111** | **0.906** | **native 2/3·shuffled 2/3 seed 통과** |
| D Auxiliary PPO | 실제 RL + 지도 사전학습 | 0.525 | 0.508 | 0.465 | -0.109 | 0.438 | gate 실패 |

| 실행 항목 | 값 |
|---|---:|
| Smoke | 8/8 완료 |
| Primary | 24/24 완료 |
| 모델 / outcome | 24 / 24 |
| 전체 artifact | 52 files / 26,195,383 bytes |
| Supervised−best RL gap | 0.0124 |
| 확인된 실제 RL arm | `C_DQN_DISCRETE` |
| Fresh OOS | `NOT_RUN_NO_READ` |

## 3. 실패 원인에 대한 답

| 가설 | D4 관찰 | 결론 |
|---|---|---|
| 표현에 학습 가능한 정보가 없음 | supervised 1.000 | 기각; train-only 표현 용량 충분 |
| PPO 예산만 부족 | PPO 65,536 step 평균 0.533 재현 | 예산 단독 문제가 아님 |
| PPO 목적함수·온폴리시 경로 병목 | DQN 0.988, PPO 0.533 | 강하게 지지 |
| 지도 사전학습이면 PPO가 해결 | Aux-PPO 0.525 | 기각; 단순 warm start 불충분 |
| DQN이 상수 행동으로 우연히 통과 | accuracy 0.906, shuffle→native 음수 | 기각; 행동 분포·control 분리 |
| 23bp 비용이 train fit을 제거 | DQN 0bp 0.988 → 23bp 0.985 | 이 train 구간의 주원인 아님 |

## 4. 프로그램 점수

| 영역 | 점수 | 가중치 | 근거 | 남은 액션 |
|---|---:|---:|---|---|
| Platform | 98 | 30% | D4 API·전체 페이지·24-model snapshot | D5 증거 연결 |
| RL Evidence | 92 | 30% | 실제 DQN native 2/3 + shuffled 2/3 + PPO 비교 | 전체 train·5 seed |
| Engineering | 97 | 20% | HMAC·held snapshot·exact matrix·다중 알고리즘 | seed resume |
| Governance | 100 | 10% | prereg amendment 선행·실패 run 보존·custody·research→master→tag | D5 동일 계보 유지 |
| Live Readiness | 0 | 10% | Fresh OOS·broker·운영 리스크 미검증 | D5/D6 전 금지 |
| **전체** | **86/100** | **100%** | 85.6 반올림 | 수익성 점수가 아님 |

## 5. 전체 페이지 단일 진행표

| 페이지 | 목적 | 구현 | D4 성숙도 | D4 반영 | 다음 액션 | 예상시간 |
|---|---|---:|---:|---|---|---:|
| Home | 전체 상태·안전 경계 | 완료 | 100% | DQN train-only confirmation | D5 상태 연결 | 20분 |
| Program Scorecard | 점수·진행 감사 | 완료 | 100% | 86점 루브릭 | D5 후 재채점 | 15분 |
| Discovery Lab | D0~D7 연구 관리 | 완료 | 100% | D4 24/24·DQN 확인 | D5 prereg | 2~4시간 |
| Data | split·SHA·OOS 경계 | 완료 | 98% | 동일 128 episode | 전체 train registry | 2~4시간 |
| Experiment | arm·seed·gate 사전등록 | 완료 | 100% | D4 prereg+amendment | D5 5+5 seed 등록 | 2~4시간 |
| Training | 모델·진행·receipt | 완료 | 100% | PPO/DQN/Aux 24 models | seed resume | 4~8시간 |
| Evaluation | 비용·control·gate | 완료 | 100% | DQN 0/23bp·shuffle 분리 | 23bp train | 3~6시간 |
| Compare | 알고리즘·RULE·control | 완료 | 100% | supervised/PPO/DQN/Aux | 전체 train 비교 | 2~4시간 |
| Report | 판정·artifact·custody | 완료 | 100% | 52 artifacts 연결 | D5 문서 연결 | 30~60분 |
| Insights | 관찰·시장 구간 | 완료 | 76% | alpha 주장과 분리 | 구간별 실패 분석 | 1~2시간 |
| Other Lanes | 보조 연구 | 완료 | 73% | RULE/RL 분리 유지 | DQN만 RL로 표기 | 30분 |
| Settings | 로컬 연구 환경 | 완료 | 84% | 읽기 전용·키 비저장 | 실행 권한 보류 | 15분 |

## 6. 증거

| 항목 | SHA-256 / 값 |
|---|---|
| Producer commit | `e5e6d7536506692382a3253e07df37cd8ed34894` |
| Producer tree | `8d1223f23c344c3afaafc28e085735c0ae93ebd1` |
| Prereg | `fc8d095c065f2eb91847a114499baaa06986fbd7392b469b827046467eca95ac` |
| Episode snapshot | `50170682d245f4c85ca9a93dc0704d8417d6d852ee66a98e063ee9979dccda52` |
| Artifact manifest | `8515ebb3cc93234b4694889f5240abe00e7095274864a555bf30e9e77a033504` |
| Summary | `26a15747c2498637dcce64898b4159381fec7bf4744c78e2d94002aa72fc78bb` |
| Terminal receipt | `e9b9b519fcbd86ba5da425b50da4cad33d9dce612673cdfbaced68cccaaeb625` |
| Custody | `docs/evidence/type2-d4-primary-20260729-v2.custody.json` |

첫 `type2-d4-smoke-20260729-v1`은 승인 키가 없어 학습 전 `PermissionError`로 실패했고 `FAILED/NO_GO` receipt로 보존했다. `v2`만 승인된 Primary의 부모다.

## 7. 다음 D5

D5는 DQN 설정을 동결하고 실제 train 전체 범위, native 5 seeds + shuffled 5 seeds, 23bp primary reward로 확장한다. D5를 통과해야 D6 reused validation을 단 한 번 열 수 있다. 현재 D4 결과만으로 Fresh OOS, 수익성, paper/live 승격을 허용하지 않는다.

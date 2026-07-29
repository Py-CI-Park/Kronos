# Kronos RL Discovery Type2-D3 결과 및 전체 페이지 진행 보고

> 실행일: 2026-07-29 KST
> 최종 상태: `COMPLETE`
> 판정: `D3_REPRESENTATION_ACTION_NOT_CONFIRMED`
> 범위: 실제 일봉 `TRAIN_ONLY / RESEARCH_ONLY`; Fresh OOS `NOT_RUN_NO_READ`

## 1. 결론

D3는 실제 일봉 데이터에서 4개 표현·행동·예산 단계, native/shuffled reward, seed 0·1·2를 조합한 PPO 모델 24개를 모두 생성했다. top-5 시장문맥과 4배 학습예산은 일관된 개선을 만들었지만 사전등록한 fit 정확도·보상비 0.90 게이트를 통과한 정책 arm은 0/4이다. 모델 생성과 연구 플랫폼 실행은 성공했지만 종가매매 정책 성공은 아니다.

## 2. 실제 실행 결과

| Policy arm | 설명 | Native fit reward | Native 23bp | Shuffled native replay | Native−shuffle | 판정 |
|---|---|---:|---:|---:|---:|---|
| A | top-1 + context, 1× | 0.418 | 0.400 | -0.038 | +0.455 | 게이트 실패 |
| B | top-5 plain, 1× | 0.385 | 0.361 | -0.163 | +0.548 | 게이트 실패 |
| C | top-5 + context, 1× | 0.465 | 0.442 | -0.189 | +0.654 | 게이트 실패 |
| D | top-5 + context, 4× | **0.533** | **0.512** | -0.227 | **+0.760** | 게이트 실패 |

| 실행 항목 | 값 |
|---|---:|
| Smoke | 4/4 PPO 모델 |
| Primary | 24/24 PPO 모델 |
| 모델 / normalizer / outcome | 24 / 24 / 24 |
| 전체 artifact | 76 files / 31,607,903 bytes |
| 4× budget native lift | +0.067865 |
| 확인된 policy arm | 0/4 |
| 최선 arm | `D_TOP5_CONTEXT_4X` |
| 최종 판정 | `D3_REPRESENTATION_ACTION_NOT_CONFIRMED` |

## 3. 반복 실패 원인 분리

| 가설 | D3 관찰 | 판정 |
|---|---|---|
| 후보가 top-1이라 실패 | top-5 plain은 0.385로 top-1 0.418보다 낮음 | 단독 원인 아님 |
| 시장문맥 부족 | context가 plain보다 약 +0.080 개선 | 기여는 있으나 해결책 아님 |
| 학습예산 부족 | 4×가 1×보다 +0.068 개선 | 부분 원인, 단독 해결 불가 |
| 데이터에 학습 신호가 없음 | 최선 native−shuffle +0.760 | train-only 신호는 존재 |
| 23bp 비용 때문에 실패 | 0bp 0.533 → 23bp 0.512 | D3 과적합 실패의 주원인 아님 |
| PPO 목적함수·모델 부적합 | 표현·예산 개선 후에도 0.90에서 멂 | 다음 우선 가설 |

이 결과는 인과를 확정하지 않는다. 다만 행동 수, 문맥, 학습량을 단계적으로 분리했으므로 다음 연구를 무작정 비용 사다리로 확장하지 않고 알고리즘·목적함수 상한을 먼저 측정해야 한다.

## 4. 100점 프로그램 평가

| 영역 | 점수 | 가중치 | 상태 | 근거 | 남은 핵심 액션 |
|---|---:|---:|---|---|---|
| Platform | 97 | 30% | STRONG | D3 API·전체 페이지·24-model snapshot | D4 증거 연결 |
| RL Evidence | 80 | 30% | PARTIAL | 24/24, 4개 ablation, shuffle control | 알고리즘/목적함수 분리 |
| Engineering | 95 | 20% | STRONG | held streaming, custody, interrupt receipt | resume 범위 유지 |
| Governance | 88 | 10% | PARTIAL | 실행 전 prereg commit, SHA, PR 계보 | D3 태그·master 병합 |
| Live Readiness | 0 | 10% | BLOCKED | Fresh OOS·주문 권한 없음 | D4~D6 전 진행 금지 |
| **전체** | **81/100** | **100%** | **RESEARCH PLATFORM** | 반올림 가중합 | 수익성 점수가 아님 |

점수는 UI와 동일한 고정 100점 루브릭에서 `achieved=true`인 항목만 합산한다. 각 영역의 최대점은 정확히 100점이며, 가중치는 위 표와 같다.

| 영역 | 획득 항목 | 미획득 항목 | 산식 |
|---|---|---|---:|
| Platform | 12페이지 25 + D3 API 20 + snapshot 20 + 실패 UX 17 + evidence viewer 15 | 브로커 운영 UI 3 | 97/100 |
| RL Evidence | 실제 PPO 25 + shuffle control 20 + 4-arm ablation 15 + 비용 진단 10 + prereg gate 10 | Fresh OOS 10 + confirmed arm 10 | 80/100 |
| Engineering | held input 20 + atomic artifact 20 + terminal receipt 15 + 24-unit gate 15 + test/build 15 + HMAC snapshot 10 | seed 자동 resume 5 | 95/100 |
| Governance | prereg-first 25 + custody 20 + 실패 공개 15 + control 15 + RULE/RL 분리 13 | D3 main PR·tag 12 | 88/100 |
| Live Readiness | 없음 | Fresh OOS 30 + paper gate 20 + broker 30 + 운영 리스크 20 | 0/100 |

따라서 D3의 0/4 gate 실패에도 점수가 오른 이유는 alpha 성공이 아니라 실제 RL 모델·대조군·custody·실패 공개 체계가 추가됐기 때문이다. 미완료인 D3 main PR·tag는 Governance 점수에 포함하지 않았다.

## 5. 전체 페이지 단일 진행표

| 페이지 | 목적 | 진행률 | D3 반영 상태 | 성과 | 다음 액션 | 예상 시간 |
|---|---|---:|---|---|---|---:|
| Home | 전체 상태·안전 경계 | 100% | D3 NO-GO 공통 strip | 최신 판정 즉시 확인 | D4 질문 연결 | 20분 |
| Program Scorecard | 100점 평가·진행 감사 | 100% | 81/100 | 가중치·근거 공개 | D4 후 재채점 | 15분 |
| Discovery Lab | 연구 사다리·arm/seed | 100% | D3 24/24 | 전체 모델·control 비교 | D4 prereg | 2~4시간 |
| Data | split·SHA·OOS 경계 | 97% | top-5 128 episode | 동일 데이터 비교 | D4 입력 고정 | 1~2시간 |
| Experiment | 가설·arm·gate | 100% | D3 prereg 완료 | 사후 기준 변경 차단 | D4 prereg | 2~4시간 |
| Training | 학습·모델·receipt | 100% | Primary complete | 24 모델·중단 receipt | D4 Smoke→Primary | 4~8시간 |
| Evaluation | fit/native/23bp | 100% | D3 NO-GO explained | 비용과 학습 실패 분리 | 알고리즘 비교 | 3~6시간 |
| Compare | 표현·control 비교 | 100% | 4 policy arms 비교 | top-5/context/4× 효과 | PPO 대안 비교 | 2~4시간 |
| Report | 결과·custody·한계 | 100% | D3 receipt 연결 | 76 artifacts 결속 | D4 문서 연결 | 30~60분 |
| Insights | 종목·시장 관찰 | 74% | observation only | 정책 증거와 분리 | 입력 경계 강화 | 30~60분 |
| Other Lanes | 보조 연구 | 72% | RL 점수 제외 | RULE/RL 혼합 방지 | 제외 사유 유지 | 30분 |
| Settings | 로컬 연구 환경 | 82% | read-only 유지 | 실수로 실행 권한 확대 방지 | 제어 권한 보류 | 15분 |

## 6. 증거와 재현성

검토 후 실행 경계를 강화했다. 새 D3 실행은 32바이트 이상 운영자 키를 `KRONOS_D3_APPROVAL_KEY_HEX`에 16진수로 제공해야 하며, Smoke receipt HMAC, 4개 outcome, 4개 model/normalizer 묶음, 전체 manifest를 동일 held-handle snapshot에서 검증한 뒤에만 Primary를 허용한다. 기존 `type2-d3-primary-20260729-v1`은 패치 전 완료된 역사적 실행이므로 HMAC을 소급 주장하지 않으며, 아래 custody/manifest로만 검증된다. 이후 실행부터 새 승인 경계를 적용한다.

| 항목 | SHA-256 / 값 |
|---|---|
| Prereg | `90d240882dc676f3539b53f96295b41eb08d7ce6d76f4abb2ce1976626386548` |
| Episode snapshot | `50170682d245f4c85ca9a93dc0704d8417d6d852ee66a98e063ee9979dccda52` |
| Artifact manifest | `4d5940b266bd241a0cee1d7d86f1ed365ecb4f09cf5eaf92bc253c2d66410479` |
| Summary | `ed43909c8864a7a6a55754e94057ca3fd0200e00442b8a1dd87905a7d8b245be` |
| Terminal receipt | `d0fd640cec0fc674722c2c43363809184c77b6385602fa6084d128fd827df963` |
| Committed custody | `docs/evidence/type2-d3-primary-20260729-v1.custody.json` |
| Local Primary | `webui/rl_runs/rl_discovery/type2-d3-primary-20260729-v1` |

## 7. 다음 D4 연구 제안

| 순서 | 연구 arm | 목적 | 진행 조건 |
|---:|---|---|---|
| 1 | supervised ceiling diagnostic | 현재 표현에서 0.90 자체가 가능한지 측정; RL로 주장하지 않음 | train-only·shuffle 동일 적용 |
| 2 | PPO baseline 재현 | D3 최선 arm 기준점 | exact D3 snapshot |
| 3 | DQN 또는 discrete Q baseline | 6개 행동에서 PPO 목적함수 병목 여부 | 동일 seed·budget |
| 4 | auxiliary prediction + PPO | 표현 학습 보조가 정책 fit을 높이는지 | 별도 prereg |
| 5 | 판정 | 2/3 seed가 0.90 fit·control separation 통과하는지 | Fresh OOS 계속 봉인 |

D4에서도 통과하지 못하면 현재 128일 train representation에서 강화학습 확대를 중단하고, 데이터 표현 또는 비-RL 기준선 연구로 돌아간다. `ts_imb`는 계속 RULE이며 D3 결과를 수익 곡선으로 부르지 않는다.

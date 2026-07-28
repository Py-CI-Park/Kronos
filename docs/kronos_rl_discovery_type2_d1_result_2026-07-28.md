# Kronos RL Discovery Type2-D1 결과

> 실행일: 2026-07-28 KST
> 상태: `PRIMARY_COMPLETE`
> 판정: `D1_ACTION_REWARD_CONFIRMED`
> 연구 범위: 합성 fixture 기반 `TRAIN_ONLY / RESEARCH_ONLY`

## 결론

D1은 501-way 행동 공간을 `STOP`과 `SELECT_TOP_OBSERVED`의 2개 행동으로 줄이고,
경제 보상·첫 결정 진단 보상·shuffled 보상을 분리했다. Smoke 3/3과 Primary
9/9를 실제 SB3 MaskablePPO 모델로 실행했다. native와 diagnostic arm은 세 seed
모두 목표를 학습했고, shuffled 음성 대조군은 실패했다. 따라서 제한된 합성
train-only 환경에서 행동·보상 메커니즘은 확인됐다.

모든 native economic reward와 비교 지표는 Type1 frozen accounting의 주 비용
가정인 왕복 23bp(0.23%)를 사용한다. 0bp/46bp 민감도는 D1 범위가 아니며 이후
cost-sensitivity 단계에서 별도 사전등록한다.

이 판정은 시장 일반화, 비용 후 수익성, Fresh OOS 성능, paper/live trading
준비도를 뜻하지 않는다. Promotion과 profitability claim은 계속 차단한다.
`ts_imb`는 RL이 아닌 RULE baseline이다.

## 실행 결과

| 단계 | Run | Matrix | 결과 | 판정 |
|---|---|---:|---|---|
| Smoke | `type2-d1-smoke-v3-20260728` | 3 arms × 1 seed = 3/3 | native 1.0, diagnostic 1.0, shuffled 0.0 | digest-bound gate 통과, Primary 승인 |
| Primary | `type2-d1-primary-v3-20260728` | 3 arms × 3 seeds = 9/9 | 아래 표 참조 | `D1_ACTION_REWARD_CONFIRMED` |

| Arm | 목적 | Seeds | 평균 economic reward ratio | 평균 initial accuracy | 평균 dominant action | 해석 |
|---|---|---:|---:|---:|---:|---|
| `A_BINARY_NATIVE` | 실제 경제 보상 학습 | 0,1,2 | 1.000 | 1.000 | 0.750 | train-only 메커니즘 통과 |
| `B_BINARY_DIAGNOSTIC` | 첫 결정 진단 보상 | 0,1,2 | 1.000 | 1.000 | 0.750 | 학습 가능성 진단 통과 |
| `C_BINARY_SHUFFLED` | 음성 대조군 | 0,1,2 | 0.000 | 0.250 | 1.000 | 의도대로 실패 |

모든 단위의 invalid action, block, no-fill count는 0이다. Primary 각 모델은
16,384 timestep을 학습했다.

## 증거·재현성

| 항목 | 값 |
|---|---|
| Producer commit | `24e79cd6453c73fe56265a6c336a790a99dc1e35` |
| Producer tree | `c898058cd35fa0cd08e612caace36367df75f0d3` |
| Prereg SHA-256 | `58de192fe007d0a976bd4a364dd8085e47935f50ead263382560de6bf2b33100` |
| Fixture SHA-256 | `1fd8543967cc48d3daa48ec5dfa4c4755b5327730c7db6f392f10677f12c80a6` |
| Primary round-trip cost | 23bp (0.23%) |
| Custody binding | `RECEIPT_BOUND` |
| Artifact inventory | 51 files / 1,796,873 bytes |
| Pre-terminal artifact manifest SHA-256 | `2920dd72303a7bef412fe8639d1086e3eeaed38e470b0f56a1bc9e01cf2faa99` |
| Terminal receipt file SHA-256 | `52f7225071364d42586e44b7b31d3a6da95d1194ba6a42455d10930042039e04` |
| Evidence manifest SHA-256 | `ef4403f2e7926008e2e58f1c83d04ccb5191ff43fba245479a80cbae4c117ede` |
| Fresh OOS | `NOT_RUN_NO_READ` |

권위 파일:

- 사전등록: `docs/kronos_rl_discovery_type2_d1_prereg_2026-07-28.json`
- custody: `docs/evidence/type2-d1-primary-v3-20260728.custody.json`
- 로컬 실행물: `webui/rl_runs/rl_discovery/type2-d1-primary-v3-20260728/`
- reviewed snapshot: `webui/v2_src/src/v6shell/discovery/reviewedDiscoverySnapshot.ts`

## 프로그램 점수

| 영역 | 점수 | 가중치 | 가중 기여 | 근거 |
|---|---:|---:|---:|---|
| Platform | 95 | 30% | 28.5 | 전체 페이지와 evidence viewer |
| RL Evidence | 72 | 30% | 21.6 | D1 9/9와 음성 대조군, 아직 합성 train-only |
| Engineering | 93 | 20% | 18.6 | runner, receipt, custody, 회귀 테스트 |
| Governance | 82 | 10% | 8.2 | prereg·SHA·브랜치·릴리스 흐름 |
| Live Readiness | 0 | 10% | 0.0 | Fresh OOS·브로커·실거래 미준비 |
| **전체** |  | **100%** | **76.9 → 77/100** | 연구 플랫폼 기준 |

## 한계와 다음 단계

| 순서 | 단계 | 작업 | 예상 시간 | 시작 조건 |
|---:|---|---|---:|---|
| 1 | D2 prereg | 1/8/32/128 train-only episode scale, arm·seed·중단 gate 동결 | 2~4시간 | D1 결과/코드 merge |
| 2 | D2 Smoke | 최소 episode에서 파이프라인·대조군 확인 | 30~60분 | prereg SHA 고정 |
| 3 | D2 Primary | 승인된 Smoke와 동일 입력으로 multi-seed 실행 | 1~3시간 | Smoke receipt 통과 |
| 4 | D2 review | episode scale별 학습 안정성·붕괴·대조군 비교 | 1~2시간 | Primary terminal receipt |
| 5 | D3 이후 | representation·cost·full control → D6 reused validation | 단계별 별도 산정 | 각 단계 신규 prereg |
| 6 | D7 Fresh OOS | 외부 승인 뒤에만 접근 | 미정 | D6 통과 + 별도 권한 |

Fresh OOS는 D2에서 열지 않는다. D2가 실패하면 `NO-GO`로 기록하고, 성공해도
다음 단계 연구 증거일 뿐 수익성이나 실거래 승격 근거로 사용하지 않는다.

## 브랜치·PR·릴리스 흐름

| 단계 | 값 | 규칙 |
|---|---|---|
| 작업 브랜치 | `codex/rl-d1-reward-action-v1` | D1 구현·증거·UI만 포함 |
| PR 대상 | `research/type1-closing-rl-v1` | 직접 push가 아니라 PR review 후 merge |
| 핵심 생산자 커밋 | `24e79cd` | v3 Smoke/Primary artifact의 source identity |
| 릴리스 후보 태그 | `fork-v1.10.0-kronos-rl-d1-action-reward` | PR merge commit에 annotated tag 생성 |
| 다음 개발 브랜치 | `codex/rl-d2-episode-scale-v1` | D2 prereg 승인 뒤 별도 생성 |

권장 명령 흐름은 `git push -u origin codex/rl-d1-reward-action-v1` → PR 생성 →
검증 통과 후 merge → merge commit에서 annotated tag 생성·push 순서다. 태그는
feature commit이 아니라 `research/type1-closing-rl-v1`의 merge 결과를 가리켜야 한다.

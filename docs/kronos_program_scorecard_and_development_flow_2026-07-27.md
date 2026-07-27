# Kronos 프로그램 점수판 및 개발 흐름 v1

**기준일:** 2026-07-27 KST

**기준 계보:** `73c4c1bd4885ae5cfb33595d3973ce289cd4daf9`

**작업 브랜치:** `codex/rl-discovery-governance-v1`

**릴리스 태그:** `fork-v1.8.0-kronos-rl-discovery-scorecard`

## 1. 프로그램 점수

점수는 모델 수익률이 아니라 현재 저장소가 제공하는 연구 플랫폼, 증거, 엔지니어링, 거버넌스와 라이브 경계를 측정한다. 라이브 준비도 0은 숨겨야 할 실패가 아니라 연구 전용 상태를 정확히 나타낸다.

| 영역 | 점수 | 가중치 | 가중 기여 | 상태 | 근거 | 다음 작업 |
|---|---:|---:|---:|---|---|---|
| 플랫폼 | 88 | 30% | 26.4 | STRONG | V6 shell, read-only API, artifact scanner, 모바일 UI | Primary 재개 체크포인트 |
| 강화학습 증거 | 38 | 30% | 11.4 | PARTIAL | D0 smoke 완료, Type1 NO_GO, Primary 미완료 | D0 Primary 완결 |
| 엔지니어링 | 86 | 20% | 17.2 | STRONG | Python/TS 테스트, 타입 검사, 빌드, Chromium QA | 장시간 실행 E2E |
| 개발 거버넌스 | 70 | 10% | 7.0 | PARTIAL | prereg SHA, receipt, 브랜치·태그 규칙 | CI 보호 규칙 |
| 라이브 준비도 | 0 | 10% | 0.0 | BLOCKED | Fresh OOS 봉인, 브로커 권한 없음 | 연구 gate 이전 진행 금지 |
| **종합** | **62** | **100%** | **62.0** | **RESEARCH PLATFORM** | 구현 강점과 증거 부족을 함께 반영 | Primary와 D1~D6 |

## 2. 전체 페이지 안내

| 그룹 | 페이지 | 목적 | 구현 | 현재 증거 상태 |
|---|---|---|---|---|
| COMMAND | Home | 연구 상태와 안전 경계 요약 | BUILT | READ_ONLY |
| COMMAND | Program Scorecard | 점수, 역량, 페이지, 개발 계보 | BUILT | AUDITED |
| RL | Discovery Lab | D0~D6 연구 사다리와 arm 귀속성 | BUILT | SMOKE_COMPLETE |
| RL | Data | 데이터, split, Fresh OOS 경계 | BUILT | MIXED |
| RL | Experiment | 사전등록과 실험 잠금 | BUILT | PREREGISTERED |
| RL | Training | 학습, seed, step과 실행 상태 | BUILT | PRIMARY_INCOMPLETE |
| RL | Evaluation | 비용, baseline과 control 평가 | BUILT | NO_GO |
| RL | Compare | 정책, rule, negative control 비교 | BUILT | RESEARCH_ONLY |
| RL | Report | 판정, 아티팩트와 계보 보고 | BUILT | HAS_REPORTS |
| RESEARCH | Insights | 종목, 수급과 시장 국면 관찰 | BUILT | OBSERVATION |
| PLATFORM | Other Lanes | 인트라데이와 Kronos 보조 연구 | BUILT | INELIGIBLE_FOR_RL_RANK |
| ADVANCED | Settings | 테마, 화면과 로컬 연구 환경 | BUILT | LOCAL_ONLY |

## 3. 현재 가능한 것과 금지된 것

| 역량 | 상태 | 경계 |
|---|---|---|
| Type1 NO_GO 증거 조회 | AVAILABLE | 기존 판정을 변경하지 않음 |
| D0 4-arm smoke 실행 및 비교 | AVAILABLE | 수익성·일반화 판정 아님 |
| prereg SHA, receipt와 artifact 감사 | AVAILABLE | read-only evidence |
| D0 Primary 104k × 3 seed | PARTIAL | arm/seed 체크포인트와 재개 기능 필요 |
| D1~D6 연구 사다리 | PARTIAL | 이전 단계 gate 뒤 순차 실행 |
| Fresh OOS 조회 | BLOCKED | `NOT_RUN_NO_READ` |
| 브로커 주문·라이브 운용 | BLOCKED | 권한·검증·제품화 없음 |

## 4. 브랜치 전략

| 브랜치 | 수명 | 용도 | 병합 대상 | 예시 |
|---|---|---|---|---|
| `main` | 장기 | 검증된 릴리스 기준선 | 없음 | `main` |
| `research/<lane>-<hypothesis>-vN` | 장기 연구 계보 | 사전등록된 실험군과 공식 판정 | `main` 또는 다음 연구 계보 | `research/type1-closing-rl-v1` |
| `codex/<work-package>` | 단기 | 구현·테스트·문서 작업 패키지 | 해당 `research/*` | `codex/rl-discovery-governance-v1` |
| `feat/<surface>-<capability>` | 단기 | 제품 기능 단위 | `main` 또는 release | `feat/v6-program-scorecard` |
| `fix/<scope>-<defect>` | 단기 | 재현 가능한 결함 수정 | 원 결함이 있는 기준 브랜치 | `fix/v6-mobile-sidebar-isolation` |
| `release/vX.Y` | 단기 안정화 | 태그 직전 회귀·빌드·문서 | `main` | `release/v1.8` |

규칙:

1. 연구 결과와 UI 구현을 같은 의미의 브랜치로 취급하지 않는다.
2. `codex/*`는 작업 패키지이고 공식 연구 판정 계보는 `research/*`가 소유한다.
3. Fresh OOS 접근 여부나 GO/NO_GO를 바꾸는 변경은 별도 preregistration과 `research/*` 브랜치가 필요하다.
4. 생성된 dist는 source 커밋과 분리한다.
5. 커밋은 되돌릴 수 있는 한 가지 목적만 가진다.

## 5. 커밋 전략

| 순서 | 커밋 유형 | 포함 | 제외 |
|---:|---|---|---|
| 1 | `perf(type1)` | authority content cache와 테스트 | Discovery/UI |
| 2 | `feat(discovery)` | prereg, runner, gates, artifacts, 테스트 | V6 화면과 dist |
| 3 | `feat(v6)` | Discovery/Scorecard source와 UI 테스트 | 생성 dist |
| 4 | `docs(governance)` | 결과·점수·브랜치·태그 문서 | 코드와 dist |
| 5 | `build(v6)` | production dist 갱신 | source와 연구 문서 |

## 6. 태그 전략

기존 `fork-v1.7.0-kronos-dashboard-v6-type1` 계보를 이어 다음 형식을 사용한다.

`fork-v<major>.<minor>.<patch>-<product>-<milestone>`

| 부분 | 의미 | 이번 값 |
|---|---|---|
| `major` | 호환성 또는 연구 플랫폼 세대 | `1` |
| `minor` | 사용자에게 보이는 기능 묶음 | `8` |
| `patch` | 동일 기능 묶음의 수정 릴리스 | `0` |
| `product` | 대상 제품/플랫폼 | `kronos` |
| `milestone` | 검증된 기능 이정표 | `rl-discovery-scorecard` |

이번 태그는 **플랫폼 기능 릴리스**를 뜻한다. PPO GO, 수익성, Fresh OOS 또는 라이브 준비도를 뜻하지 않는다.

## 7. 표준 개발 흐름

```text
research 기준선
  -> codex 작업 브랜치
  -> Red test
  -> 구현
  -> 타입/테스트/build/browser QA
  -> 목적별 커밋
  -> research review
  -> annotated release tag
  -> 다음 research gate
```

릴리스 전 필수 확인:

| Gate | 필수 결과 |
|---|---|
| Python | pytest, Ruff, Basedpyright 통과 |
| Frontend | Bun tests, Svelte check, Vite build 통과 |
| Browser | desktop/mobile 실제 렌더링과 overflow 확인 |
| Evidence | Type1 NO_GO, Fresh OOS 봉인, promotion 금지 유지 |
| Git | 목적별 커밋, 작업 트리 확인, 주석 태그 |

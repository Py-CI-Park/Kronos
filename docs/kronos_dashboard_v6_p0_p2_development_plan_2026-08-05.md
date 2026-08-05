# Kronos V6 통합 강화학습 플랫폼 P0-P2 개발 계획

- 문서 ID: `KRONOS-V6-P0-P2-DEVELOPMENT-PLAN-2026-08-05`
- 부모 브랜치: `develop/v1.28.0-dev`
- 개발 버전: `v1.28.0-dev`
- 목표 UX 성숙도: 90점 이상, stretch 95점
- 경제 모델·실거래 경계: UX 목표와 별도. 기존 NO-GO·Fresh OOS sealed·read-only 계약 유지
- 선행 감사: `docs/kronos_dashboard_v6_unified_platform_audit_2026-08-05.md`

## 1. 제품 목표

Kronos V6를 여러 연구 결과를 보여주는 페이지 모음에서 실험을 설계하고, 진행을 관찰하고, 결과를 비교하고, 모델·증거·보고서를 추적하는 통합 강화학습 연구 플랫폼으로 재구축한다.

사용자의 대표 작업은 다음 하나의 흐름으로 통일한다.

`연구 찾기 -> run 선택 -> 학습 진행 확인 -> 경제 성과 평가 -> 행동·비용 분석 -> 증거·모델 확인 -> 판정·보고서 확인`

## 2. 디자인 방향

### 2.1 콘셉트

- 이름: `Evidence-first Quant Research Command Center`
- 톤: 산업적·정밀·통제된 연구실
- 기억 요소: 실제 run event와 연결되는 `Close -> Next Open` 연구 흐름 rail
- 우선 가치: 탐색성, 비교 가능성, 증거 정직성, 시각적 위계, 반응형

### 2.2 공통 화면 문법

모든 페이지는 다음 순서를 사용한다.

1. `PageHeader`: 제목, 한 문장 목적, 현재 상태
2. `ResearchFilterBar`: lane, experiment, run, split, seed, cost, 기간
3. `KpiStrip`: 최대 5개 핵심 숫자
4. `PrimaryVisualization`: 페이지 질문에 답하는 주 그래프
5. `EvidenceGrid`: 보조 지표·표·경고
6. `ContextDrawer`: 원본 hash, artifact, 문서, 상세 blocker

기존 3단 상단 상태는 `SystemStatusRail` 하나로 축약하고 상세 내용은 drawer로 이동한다.

## 3. 목표 정보구조

| 새 페이지 | 사용자 질문 | 기존 페이지 처리 |
|---|---|---|
| Command Center | 지금 무엇이 실행 중이고 다음 행동은 무엇인가 | Home+Scorecard 요약 통합 |
| Research Library | 지금까지 어떤 연구를 했는가 | Report+Other Lanes 기록 통합 |
| Run Detail | 이 run은 무엇을 했고 어떤 결과를 냈는가 | RL 7단계 결과를 run 중심으로 통합 |
| Live Training | 학습이 실제 진행 중인가 | Training 재구축 |
| Evaluation | 비용 후 기준선을 이겼는가 | Evaluation+Compare 통합 |
| Data & Evidence | 이 결과를 신뢰할 데이터 증거가 있는가 | Data+Insights 일부 통합 |
| Models & Artifacts | 어떤 모델·checkpoint·파일이 생성됐는가 | Kronos+RL 모델 통합 |
| Reports & Governance | 왜 GO/NO-GO이고 무엇이 승인됐는가 | Report+Scorecard 상세 통합 |
| Settings | 표시·단위·refresh·접근성을 어떻게 설정하나 | 기능 축소·정리 |

Other Lanes는 독립 페이지가 아니라 Research Library의 lane filter로 전환한다. Kronos Model은 Models & Artifacts의 model family로 관리한다.

## 4. 공통 도메인 계약

### 4.1 식별자

- `experiment_id`: 사전등록된 연구 묶음
- `run_id`: 단일 실행의 영구 식별자
- `dataset_id`: 데이터 snapshot 식별자
- `model_id`: checkpoint/model 식별자
- `artifact_id`: 산출물 식별자
- `event_seq`: run 안에서 단조 증가하는 event 순번

### 4.2 상태

허용 상태는 다음으로 제한한다.

| 상태 | 의미 |
|---|---|
| `DRAFT` | 사전등록·설정 작성 중 |
| `READY` | 실행 가능하지만 시작 전 |
| `RUNNING` | 최근 event가 있고 step이 증가함 |
| `STALE` | 실행 표시 후 정해진 시간 동안 event 없음 |
| `COMPLETE` | 구현·실행 완료 |
| `NO_GO` | acceptance gate 실패 |
| `BLOCKED` | 외부 권위·데이터·승인 조건 차단 |
| `OOS_SEALED` | Fresh OOS 미개봉 |
| `FAILED` | 실행 오류로 종료 |

row 존재만으로 RUNNING을 표시하지 않는다.

### 4.3 metric point

모든 시계열은 최소 다음 metadata를 가진다.

- run id
- event step 또는 timestamp
- metric name
- value
- unit
- split
- seed
- cost assumption
- source artifact

### 4.4 run event

append-only event는 다음 종류를 지원한다.

- lifecycle
- progress
- metric
- action
- checkpoint
- artifact
- gate
- warning
- error

## 5. API 구조

| API | SLA 목표 | 역할 |
|---|---:|---|
| `GET /api/v6/summary` | P95 0.5초 | 전역 경량 snapshot |
| `GET /api/v6/research-runs` | P95 1.5초 | filter·pagination run catalog |
| `GET /api/v6/research-runs/{run_id}` | P95 2초 | 단일 run 상세 |
| `GET /api/v6/research-runs/{run_id}/metrics` | P95 2초 | chart series |
| `GET /api/v6/research-runs/{run_id}/events` | P95 1초 | bounded event tail |
| `GET /api/v6/research-runs/{run_id}/artifacts` | P95 2초 | artifact/evidence 목록 |
| `GET /api/v6/research-stream` | 지속 연결 | SSE event stream |

무거운 report catalog hash 검증은 summary 요청에서 제거하고 별도 evidence detail에서 수행한다. SSE가 실패하면 5~15초 polling fallback을 사용한다.

## 6. 시각화 표준

### 6.1 Simple mode

| 그래프 | 기본 비교선 |
|---|---|
| Reward | raw + EMA |
| NAV | policy + no-trade + rule + random |
| Drawdown/Cost | drawdown area + cumulative cost |

### 6.2 Expert mode

- actor/critic loss
- entropy/exploration
- Q-value distribution
- action distribution
- position heatmap
- cash/exposure/turnover
- seed distribution
- fold heatmap
- cost sensitivity
- data coverage와 authority gate

### 6.3 차트 공통 계약

모든 차트는 제목, 답하는 질문, 단위, run id, 기간, split, seed, cost, baseline, data source, tooltip, empty/error/loading 상태를 가진다. 실패 episode·0 trade·negative result를 숨기지 않는다.

## 7. 종가매매 프로세스 rail

공식 기본 모드는 `POST_CLOSE_NEXT_OPEN`이다.

| 순서 | 단계 | 화면 표현 |
|---:|---|---|
| 1 | D일 공식 종가 확인 | close snapshot token |
| 2 | PIT·available-at gate | pass/block gate |
| 3 | feature freeze | feature count와 hash |
| 4 | policy inference | model id·action score |
| 5 | 6천만원·10 slot 배분 | 현금·종목 slot animation |
| 6 | D+1 시가 체결 | fill price·수량 |
| 7 | 비용 반영 | 0.230% 기본 비용 차감 |
| 8 | reward·NAV 계산 | NAV delta와 drawdown |
| 9 | event·artifact 저장 | run detail로 연결 |

animation은 event-driven으로 동작하고 `prefers-reduced-motion`에서는 정적 단계 rail로 대체한다. 장식용 가짜 진행률은 금지한다.

## 8. P0 개발 범위

### P0-1 공통 Shell·디자인 시스템

산출물:

- `UnifiedV6Shell`
- `SystemStatusRail`
- `PageHeader`
- `ResearchFilterBar`
- `KpiStrip`
- `ResearchPanel`
- `ChartFrame`
- `ContextDrawer`
- responsive layout token

완료 기준:

- 같은 역할의 카드·panel·table이 페이지별로 재정의되지 않는다.
- 첫 viewport 안에 page title, filter, KPI, primary visualization 시작점이 보인다.
- 360, 390, 768, 1280, 1920px에서 page-level horizontal overflow가 없다.
- light/dark와 reduced-motion을 지원한다.

### P0-2 Research Library

기능:

- lane, status, algorithm, split, cost, 기간 검색
- latest, active, failed, blocked quick filter
- list/table view
- run마다 permanent URL
- 실패·NO-GO·sealed 결과도 같은 비중으로 보존

완료 기준:

- 최신 완료 연구를 2클릭·10초 안에 찾는다.
- 각 row에 algorithm, dataset, status, cost, seed, period, updated time이 보인다.
- 한 종목·한 run만 보이는 경우 filter·source scope를 명시한다.

### P0-3 Run Detail

탭:

- Summary
- Learning
- Performance
- Actions
- Evidence
- Artifacts
- Logs

완료 기준:

- 모든 탭이 같은 run id를 공유한다.
- model·dataset·document·artifact lineage가 끊기지 않는다.
- missing evidence를 `MISSING`으로 표시하고 합성하지 않는다.

### P0-4 경량 summary API

- 화면용 snapshot과 authority verification 분리
- response 생성 시간 기록
- stale timestamp 포함
- 느린 하위 source가 있어도 다른 card는 렌더링

## 9. P1 개발 범위

### P1-1 Simple RL Dashboard

- reward, NAV, drawdown/cost 3개 핵심 chart
- Simple/Expert 전환
- run selector와 chart context 고정
- empty/loading/error/stale 상태 분리

### P1-2 Live Training

- REST snapshot + SSE delta
- step·episode·throughput·ETA
- reward/loss/entropy/action mix
- checkpoint·artifact event
- bounded log tail
- LIVE/STALE/COMPLETE 판정

### P1-3 Evaluation/Compare 통합

- 동일 contract run만 직접 비교
- 조건 차이는 warning과 normalize option 제공
- seed box plot, fold heatmap, cost sensitivity
- no-trade/rule/random/shuffle control 유지

### P1-4 Close-to-Next-Open Flow

- 실제 run event 또는 replay event와 연결
- fill timing·cost·reward 시각화
- proxy/next-open contract를 색과 label로 구분

## 10. P2 개발 범위

### P2-1 Data & Evidence

- dataset coverage timeline
- symbol count·기간·missing
- point-in-time universe
- available-at
- official price identity
- corporate action contract
- source hash·exclusion·limitations

### P2-2 Models & Artifacts

- synthetic calibration, market RL, supervised forecast, rule baseline 분리
- checkpoint registry
- model size·algorithm·training scope·dataset lineage
- validation status와 promotion boundary
- Kronos available/missing/loaded 상태 정리

### P2-3 Reports & Governance

- preregistration
- result verdict
- evidence receipt
- branch·commit·tag
- approval state
- Fresh OOS sealed state
- direct document link와 download

### P2-4 Settings·Help

- light/dark
- simple/expert default
- refresh interval
- won/percent/bp 단위 표시
- reduced motion
- 용어 도움말

### P2-5 기존 페이지 마이그레이션

- Home+Scorecard -> Command Center
- RL 단계 결과 -> Library/Run Detail/Live/Evaluation
- Insights -> Data & Evidence의 market context
- Kronos -> Models & Artifacts
- Other Lanes -> Research Library filter
- Report -> Reports & Governance

기능 parity와 browser QA가 끝나기 전 기존 URL은 compatibility redirect 또는 mapping으로 유지한다.

## 11. 테스트 전략

### 11.1 TDD

모든 API·상태 판정·filter·chart model·routing behavior는 실패 테스트를 먼저 작성한다. CSS-only polish는 기존 behavior test를 유지한 뒤 visual QA로 검증한다.

### 11.2 Python/API

- summary가 무거운 report verification을 호출하지 않음
- filter·pagination deterministic
- invalid run id fail-closed
- path traversal 차단
- missing/corrupt artifact typed response
- event order·bounded tail
- stale 판정

### 11.3 TypeScript/Svelte

- route resolution
- filter state와 URL 동기화
- run selection
- simple/expert mode
- metric normalization
- empty/loading/error/stale variant
- reduced-motion marker
- common component source contract

### 11.4 Browser E2E

| 시나리오 | 기대 결과 |
|---|---|
| 최신 연구 찾기 | Library에서 2클릭 이내 run detail |
| 진행 중 run 보기 | Live status와 마지막 event 확인 |
| 실패 run 보기 | NO-GO와 blocker가 숨겨지지 않음 |
| mobile 390px | page-level horizontal overflow 0 |
| keyboard | nav, filter, tab, drawer 접근 가능 |
| reduced motion | process rail이 정적 단계로 표시 |
| API 지연 | 부분 card error, 전체 화면 유지 |

## 12. 성능·접근성 목표

| 항목 | 목표 |
|---|---:|
| summary P95 | 0.5초 이하 |
| run catalog P95 | 1.5초 이하 |
| run detail P95 | 2초 이하 |
| first useful content | 첫 viewport 안 |
| page horizontal overflow | 0건 |
| Lighthouse Accessibility | 95 이상 |
| Lighthouse Performance | 85 이상 |
| Svelte check | 0 error, 0 warning |
| console error | 0 |

## 13. 코드 구조 계획

새 파일은 한 책임·순수 코드 250줄 이하로 유지한다.

```text
webui/v2_src/src/v6shell/
  api/
    statusApi.ts
    runsApi.ts
    metricsApi.ts
    evidenceApi.ts
    schemas.ts
  components/
    shell/
    research/
    charts/
    feedback/
  pages/
    command/
    library/
    run/
    live/
    evaluation/
    evidence/
    models/
    governance/
  stores/
    researchContext.ts
    runTelemetry.ts
```

Flask backend은 기존 구조를 존중하되 경량 research API를 독립 모듈로 두고 `webui/app.py`에는 blueprint 등록만 추가한다.

## 14. 브랜치·커밋·병합 전략

버전은 모든 단계에서 `v1.28.0-dev`를 유지한다. 병합 브랜치는 삭제하지 않는다.

| 순서 | 브랜치 | 목적 |
|---:|---|---|
| 1 | `codex/v1.28.0-dev-dashboard-audit-plan` | 감사·계획 문서 |
| 2 | `codex/v1.28.0-dev-dashboard-foundation` | P0 Shell·design system |
| 3 | `codex/v1.28.0-dev-research-library` | P0 Library·Run Detail·summary API |
| 4 | `codex/v1.28.0-dev-live-training` | P1 charts·telemetry |
| 5 | `codex/v1.28.0-dev-evaluation-flow` | P1 compare·process rail |
| 6 | `codex/v1.28.0-dev-evidence-models-reports` | P2 pages |
| 7 | `codex/v1.28.0-dev-dashboard-hardening` | migration·responsive·a11y·performance |

각 브랜치는 최신 `develop/v1.28.0-dev`에서 생성하고 검증 후 다음 형식으로 병합한다.

```powershell
git switch develop/v1.28.0-dev
git merge --no-ff <feature-branch> -m "merge(dev): <단계>를 v1.28 개발선에 통합하다"
```

커밋 예시:

- `docs(ui): V6 통합 플랫폼 전수 감사를 기록하다`
- `docs(ui): V6 P0-P2 개발 계획을 고정하다`
- `feat(ui): 공통 연구 셸과 탐색 체계를 구축하다`
- `feat(api): 경량 연구 실행 카탈로그를 제공하다`
- `feat(ui): 강화학습 실시간 관측 화면을 구축하다`
- `feat(ui): 종가매매 연구 흐름을 시각화하다`
- `test(ui): 전체 연구 플랫폼 브라우저 회귀를 고정하다`

## 15. 점수 상승 계획

| 단계 | UX 목표 | 상승 근거 |
|---|---:|---|
| 현재 | 42 | 기능 분산·일관성·실시간 결함 |
| P0 foundation | 60 | 공통 Shell·상태·responsive 기반 |
| P0 Library/Run | 72 | 연구 탐색성과 lineage 확보 |
| P1 charts/live | 82 | 학습·경제 성과·실시간 관측 |
| P1 evaluation/flow | 87 | 비교 가능성과 종가 프로세스 이해 |
| P2 pages | 91 | 데이터·모델·보고서 통합 |
| hardening | 95 목표 | 전 해상도·접근성·성능·browser 증거 |

95점은 automated test와 실제 browser acceptance가 모두 통과할 때만 선언한다. UI 점수는 경제 모델·수익성·실거래 GO와 합산하지 않는다.

## 16. 완료 정의

P0-P2 완료는 다음을 모두 만족해야 한다.

1. 사용자가 최신 연구를 2클릭 안에 찾는다.
2. 모든 run에 영구 URL이 있다.
3. 학습·경제 성과·행동·비용·증거가 같은 run context를 공유한다.
4. 실제 event 기반 LIVE/STALE/COMPLETE가 보인다.
5. 종가 결정에서 D+1 시가 체결까지 흐름을 재생할 수 있다.
6. 모든 최상위 페이지가 공통 design grammar를 사용한다.
7. 360~1920px에서 page overflow가 없다.
8. missing·failed·NO-GO·sealed 결과가 숨겨지지 않는다.
9. API·Svelte·build·browser 회귀가 통과한다.
10. exact commit 기준 최종 score report와 handoff가 작성된다.

## 17. 예상 일정

| 범위 | 예상 작업일 |
|---|---:|
| 감사·계획·기준선 | 1~2 |
| P0 foundation | 2~4 |
| P0 Library·Run·API | 3~5 |
| P1 charts·live | 3~5 |
| P1 evaluation·flow | 2~4 |
| P2 pages | 4~6 |
| migration·hardening·QA | 4~6 |
| 합계 | 19~32 |

외부 KRX/OpenDART 권위 승인, Fresh OOS 개봉 승인, paper-forward 기간은 포함하지 않는다.

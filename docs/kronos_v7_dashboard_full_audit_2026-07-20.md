# Kronos 대시보드 전수검사 보고서 — 2026-07-20

> 문서 ID: `KRONOS-V7-DASHBOARD-FULL-AUDIT-2026-07-20`  
> 작성일: 2026-07-20 KST  
> 상태: `COMPLETE_AUDIT / REQUEST_CHANGES`  
> 범위: 공식 대시보드 전체 세대, V6 opt-in 연구 워크플로, Flask API, 연구·실행·보고서 증거 체인  
> 브랜치: `review/dashboard-v7-full-audit`  
> 기준 commit: `46345fd`  
> 기본 경로 정책: `/`는 V3 유지, V6는 `/?ui=v6&tab=home` 명시 진입  
> 실행 정책: 연구 전용, read-only dashboard, live/broker/profit claim 없음

## 1. 결론

현재 대시보드는 **보이는 화면만 평가하면 80점대 중반**이지만, 처음부터 다시 설계한다고 가정해 데이터 소유권·증거 일관성·오류 상태·수명주기·보고서 custody까지 포함하면 **58/100**이다. 즉, 시각적 프로토타입 단계를 넘었고 실제 연구 실행 결과를 볼 수 있으나, **권위 있는 연구 증거 시스템으로 승인하기에는 구조적 blocker가 남아 있다.**

가장 큰 문제는 화면의 미려함이 아니라 다음 네 가지다.

1. V6 고정 사전등록 정보와 V7 실행이 한 화면에서 섞일 수 있다.
2. 학습 실행이 존재하기만 하면 untouched test가 `NOT_RUN`이어도 평가 단계가 완료처럼 보일 수 있다.
3. 보고서 무결성 `OK`가 HTML 자체 해시만 확인하며 run→dataset→prereg 증거 체인을 재검증하지 않는다.
4. 하나의 연구 안에서 여러 cycle/run을 관리하고 비교하는 프로젝트 단위 HTML 보고서가 없다.

따라서 현재 상태 판정은 `BLOCK / REQUEST_CHANGES`다. 이는 모델 성능 판정과 별개이며 기존 `NO_GO`, `INCONCLUSIVE`, `NOT_RUN`을 완화하지 않는다.

## 2. 평가 방법과 점수

| 평가축 | 가중치 | 점수 | 가중 점수 | 판정 |
|---|---:|---:|---:|---|
| 프론트엔드 구조·상태 소유권 | 20% | 43 | 8.6 | BLOCK |
| 백엔드 API·artifact custody | 20% | 52 | 10.4 | BLOCK |
| UX/UI·프로세스 완결성 | 25% | 58 | 14.5 | BLOCK |
| HTML 보고서·연구 수명주기 | 20% | 57 | 11.4 | BLOCK |
| 연구 정직성·안전 표시 | 15% | 88 | 13.2 | CLEAR |
| **전체** | **100%** |  | **58.1 → 58/100** | **BLOCK** |

기존 85/100 평가는 레이아웃·시각 계층·반응형 스윕 중심의 UX 점수였다. 이번 58/100은 코드, API, provenance, failure semantics, 보고서 수명주기를 포함하므로 이를 대체한다.

### 핵심 페이지 점수

| 페이지 | 점수 | 핵심 이유 |
|---|---:|---|
| Home | 66 | 안전 토큰과 여정은 명확하나 API 실패를 `MISSING`과 구분하지 못하고 prereg SHA가 고정 누락됨 |
| Data | 60 | 데이터 기초 정보는 있으나 custody·freshness·가격 기준·manifest 해시 시각화가 부족함 |
| Experiment | 54 | 일부 자본/명령이 API 계약이 아니라 프론트 상수이며 V7 run 계약과 분리될 수 있음 |
| Training | 44 | tail 50개 이벤트를 seed 구분 없이 연결해 학습 곡선을 오해시킬 수 있음 |
| Report | 70 | 단일 run HTML/SHA/viewer는 좋으나 선택 run과 상단 provenance가 불일치할 수 있고 project/cycle 보고서가 없음 |

## 3. 잘 개발된 부분

- `NO_GO`, `INCONCLUSIVE`, `NOT_RUN`, read-only, no-live/no-profit를 시각적으로 숨기지 않는다.
- validation 결과와 untouched test custody를 문구상 구분하며 테스트 개봉을 자동화하지 않는다.
- 보고서 HTML은 self-contained이고 외부 리소스가 없으며 SVG 기반 차트, 비용 민감도, baseline, shuffled control, index overlay를 포함한다.
- 보고서 다운로드와 SHA 표시, sandbox iframe, CSP, 경로 traversal 방어가 존재한다.
- V6 연구 여정은 Data→Experiment→Training→Evaluation→Compare→Report로 탐색 가능하다.
- V3 기본/V6 opt-in 정책과 내부 `v2` 경로 호환성을 유지한다.
- 테마, 줌, 키보드 stepper, wide/mobile overflow 점검이 이미 존재한다.

## 4. 덕지덕지 누적된 구조와 greenfield 관점의 문제

### 4.1 세대별 shell/route 분기 격자

`App.svelte`와 Sidebar/routes가 V3/V4/V5/V6 분류·라벨·렌더링을 여러 위치에서 중복 관리한다. greenfield라면 하나의 typed route manifest가 alias, label, workspace, component loader, shell 정책을 소유해야 한다. 현재 구조는 새 버전을 붙일 때 분기와 예외가 증가하는 형태다.

### 4.2 혼합 API barrel과 서로 다른 오류 계약

`src/lib/api.ts`는 legacy nullable API, generated V5 validator, RL facade를 함께 노출한다. 호출자는 `null`, throw, validated result를 혼용한다. greenfield라면 feature-scoped typed client와 `ready | empty | unavailable | error` 결과 계약을 표준화한다.

### 4.3 거대·압축형 페이지 컴포넌트

V6 page 일부는 script/markup/style이 사실상 한 줄로 압축되어 있고 ReportPage는 catalog, registry, markdown viewer, report iframe, provenance chain을 한 파일이 소유한다. 기능 추가 때 기존 상태와 시각 규칙을 건드릴 위험이 높다. greenfield라면 ProjectCatalog, CycleTimeline, ReportViewer, DocumentViewer, EvidenceChain으로 분리한다.

### 4.4 request ownership 분산

legacy RL 화면의 접힌 disclosure도 mount 즉시 self-fetch하고 같은 lane API를 여러 카드가 반복 호출한다. App polling도 초기 실행 중복과 teardown 누락 가능성이 있다. greenfield라면 shell-level query snapshot과 lazy disclosure를 사용한다.

### 4.5 import-time Flask 거대 앱

`webui/app.py`는 import fallback, 전역 app 생성, route, model singleton을 함께 소유한다. 광범위 `except Exception`이 코드 결함을 optional dependency 부재처럼 숨길 수 있다. greenfield라면 app factory + blueprint/service 단위로 분리한다.

## 5. 정확성·증거 custody blocker

| 심각도 | 문제 | 사용자 영향 | 요구 수정 |
|---|---|---|---|
| HIGH | 선택 run과 hard-coded V6 prereg 혼합 | V7 결과 옆에 다른 계약 SHA가 표시될 수 있음 | run prereg ID/SHA로 계약을 resolve |
| HIGH | evaluation state가 training 존재 여부를 복제 | `test=NOT_RUN`인데 평가 완료처럼 보임 | train/validation/test/report 상태 독립 산출 |
| HIGH | report integrity가 HTML self-hash만 검증 | 원본 run/dataset/prereg 변경을 놓침 | source hash, schema, six false locks 재검증 |
| HIGH | run-detail가 일부 ID에 `train_`를 임의 추가 | catalog→detail round trip 실패 | catalog ID를 opaque exact name으로 처리 |
| HIGH | Training curve가 seed를 섞고 tail만 표시 | 학습 안정성·실패 episode 오해 | per_seed 전체 curve를 별도 series로 표시 |
| HIGH | 보고서/API 실패를 빈 목록으로 표시 | 증거 없음과 시스템 장애가 구분되지 않음 | 독립 error/empty/loading + retry |
| HIGH | 하나의 연구에 여러 cycle 보고서 없음 | 반복 연구의 가설 변화·비교·결론 추적 불가 | project→cycle→run sidecar와 project HTML |

## 6. UX/UI·시각화 누락

### Home
- `MISSING`과 API 장애를 구분하는 상태 패널이 없다.
- 실제 prereg ID/SHA와 최신 run lineage가 요약 카드에 연결되지 않는다.
- 브랜드 영역이 272px sidebar에서 여러 줄로 잘려 정보 밀도가 불안정하다.

### Data
- decorative progress bar가 실제 readiness 비율과 무관하다.
- DB freshness, audit population/filter, price-basis decision grade, manifest SHA, index coverage가 한눈에 보이는 matrix가 없다.
- 320~390px에서 420px minimum grid가 clipping 위험을 만든다.

### Experiment
- validation horizon, execution basis, official close 여부, control/stress 비용, constraints/locks가 충분히 노출되지 않는다.
- 실행 명령은 화면 상수가 아니라 표시 중인 FROZEN prereg SHA와 결합된 allowlist여야 한다.

### Training
- model family, trainer version, prereg, seed 수, 비용, MDD, trades, verdict reason을 포함한 filterable run ledger가 없다.
- seed별 curve, no-trade baseline, tail/full 구분이 필요하다.

### Report
- flat run card 8개와 prereg card 4개가 세로로 길게 이어져 연구 단위 문맥이 약하다.
- 선택한 역사 보고서와 최신 run provenance chain이 서로 다른 상태로 보일 수 있다.
- project summary, cycle timeline, cross-cycle comparison, integrity 탭이 없다.
- HTML 보고서는 긴 목차형 문서이고 사용자 요청의 내부 탭 양식이 없다.

### 접근성·반응형
- loading은 `role=status`, error는 `role=alert`, copy feedback은 `aria-live` 표준화가 필요하다.
- 표 caption/scope, 좁은 화면 shrink-safe grid, action wrapping이 일관되지 않다.
- 상태 색상은 텍스트 토큰을 유지하는 점은 양호하다.

## 7. 연구·보고서 성숙도 판정

| 능력 | 현재 판정 | 근거 |
|---|---|---|
| 실제 RL 연구 실행 | 가능 | Tabular-Q, PPO, LinUCB full run과 seed/control/verdict artifact 존재 |
| 단일 run 결과 보고 | 가능 | 16-section self-contained HTML, SVG, SHA, viewer/download |
| 과거 prereg/run/doc 탐색 | 부분 가능 | registry와 markdown viewer 존재 |
| 한 연구의 다중 cycle 관리 | 불가 | project/cycle schema·order·delta·aggregate verdict 없음 |
| cross-cycle 비교 보고 | 불가 | 호환성 검사와 project-level matrix 없음 |
| 증거 체인 무결성 보증 | 불충분 | report self-hash만 정상 여부에 반영 |
| promotion/live readiness | 불가 | 현재 모델은 NO_GO/INCONCLUSIVE, untouched test 미개봉 |

현재 시스템은 **실제 연구를 실행하고 실패를 기록할 수 있는 수준**이지만, **여러 cycle을 공식 프로젝트로 묶어 장기 관리하고 승격 판단에 쓰는 수준은 아니다.**

## 8. 검토 범위와 증거

- Git 기준: `feature/dashboard-v7-rl-reports`의 P1~P11 merge 및 구현 commit
- 코드: Flask app/V6 platform/insight API, Svelte shell/pages/legacy RL, report builder/tests
- 브라우저: `/?ui=v6&tab=home`, `/?ui=v6&tab=rl&step=report`, 1440×1000
- 관찰: horizontal overflow 없음, report page scroll height 약 3932px, report catalog 8건, prereg registry 4건
- 연구 결과: M1 `INCONCLUSIVE`, M2 `NO_GO`, M3 `INCONCLUSIVE`, untouched test `NOT_RUN`

## 9. 관련 문서

- `docs/kronos_v7_dashboard_full_audit_improvement_plan_2026-07-20.md`
- `docs/kronos_v7_model_series_result_2026-07-20.md`
- `docs/kronos_v7_paged_execution_plan_2026-07-20.md`
- `docs/wiki/14-document-standard.md`

## 10. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-20 | 최초 전수검사, greenfield 재평가, 58/100 판정 | GJC | 이 문서 commit |

# Kronos 대시보드 전수검사 개선 완료 보고서 — 2026-07-20

> 문서 ID: `KRONOS-V7-DASHBOARD-FULL-AUDIT-COMPLETION-2026-07-20`
> 작성일: 2026-07-20 KST
> 상태: `IMPLEMENTED_AND_VERIFIED`
> 브랜치: `review/dashboard-v7-full-audit`
> 감사·계획 commit: `9670896`
> 구현 commit: `99280e5`
> 기준 정책: V3 기본 유지, V6 `/?ui=v6&tab=home` opt-in, research-only/read-only

## 1. 완료 판정

전수검사에서 확인한 correctness blocker와 사용자가 요청한 다중-cycle HTML 연구 보고서 시스템을 구현하고 검증했다. 심층 성숙도는 **58/100 → 76/100**으로 상승했다.

모델 연구 판정은 변경하지 않았다.

- M1 Tabular-Q: `INCONCLUSIVE`
- M2 PPO: `NO_GO`
- M3 LinUCB: `INCONCLUSIVE`
- untouched test OOS: 모든 cycle `NOT_RUN`
- live/broker/order/profit/promotion: 잠금 유지

## 2. 구현 결과

| 영역 | 변경 전 | 변경 후 |
|---|---|---|
| run 조회 | 일부 ID에 `train_` 임의 prefix | catalog ID를 opaque exact name으로 round trip |
| 평가 상태 | training run 존재 시 `HAS_RUNS` | 최신 run test가 `NOT_RUN`이면 `TEST_NOT_RUN` |
| 단일 보고서 무결성 | HTML self-hash 중심 | run/dataset/prereg source SHA, schema, six false locks까지 chain 검증 |
| 프로젝트 연구 | flat run/prereg 목록 | project→ordered cycle→run sidecar와 catalog |
| 프로젝트 HTML | 없음 | self-contained CSS-only 5-tab HTML |
| 보고서 dashboard | run card·registry 중심 | project summary, cycle timeline, verdict/test/comparison/integrity, CHAIN_OK viewer |
| Training chart | tail 50 이벤트·seed 혼합 가능 | manifest의 seed별 전체 `val_nav_curve`, 독립 series와 no-trade baseline |
| Home/Data/Experiment | 일부 상수·decorative bar·MISSING/장애 혼용 | API fact 기반 readiness/계약, UNAVAILABLE/MISSING/EMPTY 구분, retry |
| legacy lifecycle | stale cost gate, subscription/polling 누적 위험 | run state 초기화, teardown, shell별 single polling owner |
| 반응형 | 일부 420px minimum clipping 위험 | shrink-safe grid, 390px 주요 5페이지 overflow 0 |

## 3. 다중-cycle 연구 보고서

권위 원본 sidecar:

- `docs/kronos_v7_project_daily_model_series_2026-07-20.json`
- schema: `kronos_v7_project_report_sidecar.v2`
- project: `kronos-v7-daily-model-series-2026-07-20`
- cycles: M1 Tabular-Q, M2 PPO, M3 LinUCB
- runs: full validation 3건

생성 명령:

```powershell
py -3.11 -m stom_rl.v7_report_builder --project-sidecar docs/kronos_v7_project_daily_model_series_2026-07-20.json --project-output-dir webui/rl_runs/v6_daily_h1/_projects/kronos-v7-daily-model-series-2026-07-20
```

생성물은 session/generated artifact로 유지한다.

- `project_report.html`
- `project_report_manifest.json`
- 최신 검증 시 report SHA-256: `115b7220697f94df58404333afbc334f1e428fbf7d9b6a06f445b22d276f81a8`
- API integrity: `CHAIN_OK`
- 내부 탭: Summary / Cycles / Comparison / Traceability / Integrity
- script: 0
- 외부 resource: 0
- source verdict: `INCONCLUSIVE`, `NO_GO`, `INCONCLUSIVE`
- OOS: `NOT_RUN`, `NOT_RUN`, `NOT_RUN`

## 4. 점수 재평가

| 평가축 | 전 | 후 | 근거 |
|---|---:|---:|---|
| 프론트엔드 구조·상태 소유권 | 43 | 58 | lifecycle leak/stale state 제거, Training/Report 가독성·선택 context 개선 |
| 백엔드 API·artifact custody | 52 | 72 | exact ID, 독립 test state, single/project report chain 검증 |
| UX/UI·프로세스 완결성 | 58 | 78 | 오류 상태, API-fact readiness, seed chart, project timeline, responsive 개선 |
| HTML 보고서·연구 수명주기 | 57 | 86 | 3-cycle sidecar, 5-tab export, 비교·traceability·integrity, dashboard viewer |
| 연구 정직성·안전 표시 | 88 | 90 | 판정/OOS 원문 보존과 fail-closed 강화 |
| **가중 전체** | **58** | **76** | 목표 76 달성 |

이 점수는 화면 미관만이 아니라 코드 구조, custody, 오류 의미, 보고서 수명주기를 포함한다.

## 5. 검증 증거

### Python dashboard/report regression

```text
py -3.11 -m pytest \
  tests/test_v6_platform_api.py tests/test_v6_insight_api.py \
  tests/test_v7_report_builder.py tests/test_stom_rl_dashboard_api.py \
  tests/test_stom_rl_dashboard_tab.py tests/test_stom_rl_orderbook_env.py \
  tests/test_stom_rl_orderbook_sb3.py tests/test_v2_route.py \
  tests/test_v2_dist_marker.py tests/test_kronos_v5_app_integration.py \
  tests/test_webui_local_security.py -q

100 passed in 75.56s
```

추가 custody/report 집중 검증:

```text
37 passed in 14.92s
```

### Frontend

```text
bun test src: 363 passed, 0 failed, 35 files
svelte-check: 436 files, 0 errors, 0 warnings
vite production build: 945 modules transformed, success
```

### Browser QA

- 390×844: Home, Data, Experiment, Training, Report 모두 `scrollWidth=clientWidth=390`
- 주요 5페이지 `role=alert` 오류 0
- live `/api/v6/status`: evaluation `TEST_NOT_RUN`
- project dashboard: 1 project, 3 cycles, 3 runs, `CHAIN_OK`
- project HTML: 5 tabs, script 0, external resource 0, 1280px overflow 0
- screenshot: `artifacts/v7-full-audit-project-report.png` (session evidence, 비추적)

## 6. 남은 구조 부채

이번 branch의 목표 blocker는 제거했지만 90점 수준을 위해 다음이 남는다.

1. `App.svelte`/Sidebar/routes의 세대별 branch lattice를 typed route manifest 하나로 통합
2. `webui/app.py`를 app factory와 domain blueprint로 단계 분리하고 broad import fallback 축소
3. legacy RL factory disclosure의 eager/self-fetch를 shared lazy snapshot으로 전환
4. artifact discovery 반복 glob/hash와 JSONL 전체 read를 bounded snapshot/tail reader로 전환
5. insight cache를 DB+manifest signature 기반 bounded cache로 변경
6. project report의 cycle 간 통계 시각화는 계약 호환 run에 한해 추가 가능하나 현재 판정을 미화하지 않아야 함

위 항목은 현재 연구 실행·보고서 열람의 correctness blocker가 아니라 장기 유지보수 부채다.

## 7. 사용자 확인 경로

- 최신 V6 Home: `http://127.0.0.1:8122/?ui=v6&tab=home`
- Training evidence: `http://127.0.0.1:8122/?ui=v6&tab=rl&step=training`
- Project report dashboard: `http://127.0.0.1:8122/?ui=v6&tab=rl&step=report`
- Project HTML direct: `http://127.0.0.1:8122/api/v6/project-report-html?project=kronos-v7-daily-model-series-2026-07-20`

## 8. 변경 히스토리

| 날짜 | 변경 | commit |
|---|---|---|
| 2026-07-20 | 전수검사·상세 개선 계획 | `9670896` |
| 2026-07-20 | custody·project report·UX·lifecycle 구현 | `99280e5` |
| 2026-07-20 | 검증·점수·잔여 부채 완료 기록 | 이 문서 commit |

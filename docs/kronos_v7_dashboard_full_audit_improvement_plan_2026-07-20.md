# Kronos 대시보드 전수검사 개선 실행 계획 — 2026-07-20

> 문서 ID: `KRONOS-V7-DASHBOARD-FULL-AUDIT-IMPROVEMENT-PLAN-2026-07-20`  
> 작성일: 2026-07-20 KST  
> 상태: `APPROVED_BY_USER_REQUEST / IN_EXECUTION`  
> 브랜치: `review/dashboard-v7-full-audit`  
> 기준 commit: `46345fd`  
> 관련 감사: `docs/kronos_v7_dashboard_full_audit_2026-07-20.md`

## 1. 목표와 완료 정의

기존 URL과 연구 판정을 보존하면서 대시보드를 다음 수준으로 올린다.

- 선택한 run의 prereg→dataset→run→report 체인이 하나의 권위 있는 context로 표시된다.
- `test=NOT_RUN`은 평가 완료로 절대 표시되지 않는다.
- 보고서 정상 판정은 HTML self-hash가 아니라 source custody까지 검증한다.
- 하나의 연구 프로젝트 안에 여러 cycle/run을 순서·가설 변화와 함께 관리한다.
- 프로젝트 단위 self-contained HTML 보고서는 내부 탭, cycle timeline, 비교, traceability, integrity를 포함한다.
- Training은 seed별 전체 validation curve와 lineage/decision metrics를 표시한다.
- 네트워크/API 장애, 정상 empty, artifact MISSING을 서로 구분한다.
- 320/390/768/1440px에서 clipping 없이 동작한다.
- V3 기본, V6 opt-in, 내부 `v2` 경로, 연구 전용·read-only 정책은 바꾸지 않는다.

완료는 문서 작성이 아니라 코드·테스트·build·브라우저 QA와 commit 증거로 판정한다.

## 2. 비목표

- 모델을 GO로 만들거나 untouched test를 개봉하지 않는다.
- live trading, broker/order, profitability claim을 추가하지 않는다.
- 내부 `webui/v2_src`, `/static/v2/dist` 경로를 rename하지 않는다.
- `app.py` 전체 rewrite나 모든 legacy generation 삭제를 한 번에 수행하지 않는다.
- 기존 NO_GO/INCONCLUSIVE 문서를 수정해 판정을 완화하지 않는다.

## 3. 페이지별 실행 계획

### Page 1 — 권위 있는 artifact catalog와 custody state

**대상**
- `webui/v6_platform_api.py`
- `tests/test_v6_platform_api.py`

**개발**
1. catalog run ID를 opaque exact name으로 처리한다.
2. 선택 run의 prereg ID/SHA를 allowlisted docs에서 resolve한다.
3. run manifest, dataset manifest, prereg, report manifest/source hash, six false locks를 검증한 chain state를 만든다.
4. training, validation, untouched test, report state를 독립적으로 산출한다.
5. `NOT_RUN` test는 `TEST_NOT_RUN`으로 유지하고 evaluation 완료를 금지한다.
6. report catalog에 `CHAIN_OK` 또는 정확한 blocker reasons를 노출하고 정상 viewer/download를 fail closed한다.

**완료 기준**
- V6/V7 valid chain, prereg mismatch, dataset mismatch, detached report, altered lock, malformed ID, `train-1` round trip, `NOT_RUN` 평가를 테스트한다.

### Page 2 — 다중 cycle 연구 프로젝트 보고서 v2

**대상**
- `stom_rl/v7_report_builder.py`
- `tests/test_v7_report_builder.py`
- `docs/wiki/14-document-standard.md`

**개발**
1. versioned project sidecar `project → ordered cycles → runs` 계약을 정의한다.
2. cycle은 ID/order/title/hypothesis delta/prereg doc/SHA/run refs를 가진다.
3. 기존 single-run report를 보존하면서 project report builder를 추가한다.
4. self-contained HTML에 접근 가능한 CSS-only tabs를 제공한다: Summary, Cycles, Comparison, Traceability, Integrity.
5. 호환되는 run만 비용/NAV/verdict/test 상태 비교 matrix에 넣고 나머지는 `INCOMPARABLE`로 표시한다.
6. NO_GO/INCONCLUSIVE/NOT_RUN은 원문 그대로 유지한다.
7. project report manifest에 모든 source hash와 chain state를 기록한다.

**완료 기준**
- 2 cycle/3 run deterministic fixture가 단일 HTML을 생성한다.
- 외부 리소스·실행 script·inline event는 0이다.
- 내부 탭, cycle order, verdict preservation, source tamper blocking을 테스트한다.

### Page 3 — 프로젝트·cycle 중심 Report Dashboard

**대상**
- `webui/v6_platform_api.py`
- `webui/v2_src/src/v6shell/v6Api.ts`
- `webui/v2_src/src/v6shell/pages/ReportPage.svelte`
- `tests/test_v6_platform_api.py`

**개발**
1. project report catalog/viewer API를 추가한다.
2. Report page를 연구 프로젝트 요약→cycle timeline→run/report→문서/무결성 순으로 재구성한다.
3. 보고서 선택 시 verdict, test state, prereg, hashes, iframe이 같은 선택 context를 사용한다.
4. report/registry/detail 요청의 독립 loading/error/empty 상태와 retry를 표시한다.
5. chain-invalid 보고서는 진단은 보이되 일반 열람/다운로드를 차단한다.

**완료 기준**
- 이전 flat reports도 그대로 탐색된다.
- 프로젝트가 없을 때 정상 empty, API 실패 때 `UNAVAILABLE`, tamper 때 `BLOCKED`가 구분된다.
- 390px와 desktop에서 overflow 없이 cycle/report를 탐색한다.

### Page 4 — Training evidence 정확성

**대상**
- `webui/v2_src/src/v6shell/pages/TrainingPage.svelte`
- `webui/v2_src/src/v6shell/v6Api.ts`
- `webui/v6_platform_api.py`

**개발**
1. `events_tail` 단일 선을 제거하고 run manifest의 `per_seed[*].val_nav_curve` 전체를 seed별 series로 표시한다.
2. trainer/model/prereg/timestamp/seeds/cost/verdict reasons/test state/MDD/trade count를 선택 run header에 표시한다.
3. run filter와 model family 표식을 추가한다.
4. tail event만 가능한 경우 seed와 truncation을 명시한다.

**완료 기준**
- seed 간 episode 선이 연결되지 않는다.
- baseline과 비용 단위가 명시되고 failure episode를 숨기지 않는다.

### Page 5 — 공통 UX state·responsive·접근성

**대상**
- V6 Home/Data/Experiment/Training/Report pages
- V6 Shell/ProcessStepper

**개발**
1. loading=`role=status`, error=`role=alert`, copy feedback=`aria-live`를 표준화한다.
2. `MISSING`, `EMPTY`, `UNAVAILABLE`, `BLOCKED`를 별도 상태로 표시한다.
3. fixed 420px grid를 `minmax(min(100%, ...), 1fr)`로 변경한다.
4. Data readiness matrix를 API 사실 기반으로 만들고 decorative 78%를 제거한다.
5. Experiment 상수/명령을 contract 기반 표시로 전환한다.

**완료 기준**
- 320/390/768/1440px에서 horizontal overflow 0.
- 키보드 focus, table caption/scope, status announcement가 확인된다.

### Page 6 — 누적 legacy debt의 안전한 절단

**대상**
- `webui/v2_src/src/tabs/RLTradingTab.svelte`
- `webui/v2_src/src/layout/Header.svelte`
- `webui/v2_src/src/layout/Sidebar.svelte`
- `webui/v2_src/src/lib/polling.ts`
- `webui/v2_src/src/App.svelte`

**개발**
1. run 선택 시작 시 cost gate를 포함한 모든 run-scoped 상태를 초기화하고 stale response token을 차단한다.
2. Header/Sidebar store subscription을 teardown한다.
3. polling은 shell owner가 한 번만 시작하고 teardown한다.
4. route manifest 통합과 lazy factory fetch는 후속 bounded refactor로 남기되 현재 오류를 만드는 lifecycle debt는 제거한다.

**완료 기준**
- run 전환 실패/지연 시 이전 cost gate가 표시되지 않는다.
- shell remount 후 subscription/polling 호출 수가 증가하지 않는다.

## 4. 구현 순서와 commit 전략

| 순서 | branch commit | 내용 | merge 조건 |
|---:|---|---|---|
| 1 | `audit(v7): ...` | 전수검사·계획 문서 | 문서 lint 불필요, git diff 검토 |
| 2 | `fix(v7-audit): custody catalog` | Page 1 | targeted pytest 통과 |
| 3 | `feat(v7-audit): project reports` | Page 2 | builder/API tests 통과 |
| 4 | `feat(v7-audit): project report dashboard` | Page 3 | frontend test/check 통과 |
| 5 | `fix(v7-audit): evidence UX correctness` | Page 4~5 | browser matrix 통과 |
| 6 | `fix(v7-audit): legacy lifecycle debt` | Page 6 | regression tests/build 통과 |
| 7 | `audit(v7): completion ledger` | 결과·점수·잔여 위험 | 모든 verification evidence 기록 |

현재 사용자가 동일 branch에서 계획에 이어 완료까지 요청했으므로 별도 승인 gate 없이 위 순서로 진행한다. master merge/tag/push는 이 계획 범위가 아니다.

## 5. 검증 계획

### Backend/report

```powershell
py -3.11 -m pytest tests/test_v6_platform_api.py tests/test_v7_report_builder.py -q -W error
py -3.11 -m pytest tests/test_v6_insight_api.py tests/test_kronos_v5_app_integration.py tests/test_webui_local_security.py -q
```

### Frontend

```powershell
cd webui/v2_src
bun test src
npm run check
npm run build
```

### Browser

- `/?ui=v6&tab=home`
- `/?ui=v6&tab=rl&step=data`
- `/?ui=v6&tab=rl&step=experiment`
- `/?ui=v6&tab=rl&step=training`
- `/?ui=v6&tab=rl&step=report`
- viewport: 320×800, 390×844, 768×1024, 1440×1000, 3440×1440
- horizontal overflow, console errors, unavailable/empty/error/tamper states, keyboard navigation, viewer integrity 확인

## 6. 목표 점수

| 축 | 현재 | 완료 목표 |
|---|---:|---:|
| 프론트엔드 구조·상태 소유권 | 43 | 62 |
| 백엔드 custody/API | 52 | 72 |
| UX/UI·프로세스 | 58 | 76 |
| 보고서·수명주기 | 57 | 82 |
| 연구 정직성 | 88 | 90 |
| **가중 전체** | **58** | **76 이상** |

90점 이상은 route manifest 단일화, Flask app factory 전환, lazy shared query layer, 전체 legacy shell retirement까지 완료해야 가능하다. 이번 branch는 correctness blocker와 project-report 요구를 우선 제거한다.

## 7. 위험과 rollback

- 기존 run artifact는 수정하지 않고 새 sidecar/report를 생성한다.
- API field는 additive로 확장하고 기존 field/route를 삭제하지 않는다.
- viewer 차단 강화로 기존 SHA-only `OK` 보고서가 `BLOCKED`가 될 수 있으며 이는 의도된 fail-closed 변경이다.
- frontend dist는 build 결과와 source commit을 함께 검토한다.
- rollback은 branch commit 단위 revert로 가능하며 master/V6 default는 변경하지 않는다.

## 8. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-20 | Page 1~6 개선 계획 확정 | GJC | 이 문서 commit |

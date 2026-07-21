# Kronos V8 대시보드 성숙도 95+ 실행 계획 — 2026-07-21

> 문서 ID: `KRONOS-V8-DASHBOARD-MATURITY-95-PLAN-2026-07-21`
> 상태: `IN_EXECUTION`
> 브랜치: `feature/dashboard-v8-maturity-95`
> 기준 release: `fork-v1.6.0-dashboard-v7-rl-reports`
> 시작 점수: 76/100
> 목표 점수: 95/100 이상

## 1. 목표

V6를 8122 기본 대시보드로 유지하면서 route 소유권, Flask 구성 경계, artifact custody 성능, cache freshness, lazy evidence, 오류 의미와 연구 연속성을 검증 가능한 수준으로 강화합니다.

95점은 미관 점수가 아니라 다음 가중 rubric의 합으로 판정합니다.

| 축 | 배점 | 현재 | 목표 |
|---|---:|---:|---:|
| 연구 정직성·custody·보안 | 25 | 22 | 25 |
| UX/UI·접근성·프로세스 완결성 | 20 | 16 | 19 |
| route·frontend 상태 소유권 | 20 | 11 | 19 |
| backend 경계·성능·freshness | 20 | 12 | 18 |
| 테스트·운영·rollback | 15 | 15 | 15 |
| **합계** | **100** | **76** | **96** |

## 2. 불변 조건

- V6는 `http://127.0.0.1:8122/` 기본 shell입니다.
- V3 `/?ui=v3`, V5 `/?ui=v5` rollback을 유지합니다.
- M1/M3 `INCONCLUSIVE`, M2 `NO_GO`, test `NOT_RUN`을 변경하지 않습니다.
- live trading, broker/order, profitability, promotion, paper-forward를 추가하지 않습니다.
- `ts_imb`는 RULE baseline이며 RL로 표기하지 않습니다.
- 생성 artifact 손상·부재를 유리한 `NOT_RUN`이나 빈 목록으로 완화하지 않습니다.

## 3. 페이지별 구현 계획

### Page 1 — Typed route ownership와 bookmark 호환

- `DASHBOARD_SHELLS`와 `DEFAULT_DASHBOARD_SHELL='v6'`를 단일 원본으로 만듭니다.
- legacy route ID를 `as const satisfies` manifest에서 파생합니다.
- route label, alias, shell availability, V5 workspace, component key, V6 compatibility target을 한 계약으로 묶습니다.
- `/training`, `/dashboard`가 V6 Training으로 연결되도록 pathname/query compatibility를 선언합니다.
- unknown route는 store/history를 변경하지 않고 명시적 unavailable 상태로 종료합니다.

**Gate:** 12개 legacy route inventory와 V3/V5 URL은 변하지 않고, V6 bookmark translation이 테스트됩니다.

### Page 2 — Flask app factory와 service boundary

- 기존 handler를 기능 변경 없이 legacy blueprint로 기계적으로 이동합니다.
- `create_app(config=None, *, blueprint_factories=...)`를 추가합니다.
- V2/V5/V5.1/V6 platform/V6 insight/legacy를 한 번씩 등록합니다.
- V6 blueprint는 path, reader, revision, cache를 소유한 service 주입을 지원합니다.
- optional dependency 실패는 subsystem별 구조화 진단으로 보존합니다.

**Gate:** 서로 다른 temp root/config를 가진 두 app이 reload/monkeypatch 없이 동시에 격리됩니다.

### Page 3 — Truthful artifact catalog와 bounded event tail

- request당 runs/docs root를 한 번만 스캔하는 artifact snapshot을 만듭니다.
- run/report/prereg를 ID·SHA index로 공유합니다.
- malformed manifest, missing report body, detached chain을 숨기지 않고 INVALID reason으로 반환합니다.
- events JSONL은 초기 크기 snapshot 기준으로 뒤에서 최대 1MiB/50개 object event만 읽습니다.
- missing/empty/partial/corrupt/truncated 상태를 구분합니다.

**Gate:** root scan count, 1MiB read ceiling, trailing corruption, concurrent append가 deterministic test로 고정됩니다.

### Page 4 — Content-based bounded cache freshness

- index custody cache는 검증한 bytes SHA-256을 key에 포함하고 symlink를 거부합니다.
- deleted path를 제거하고 cache cap을 둡니다.
- insight revision은 universe manifest SHA와 DB/WAL/SHM signature를 포함합니다.
- flow/regime cache는 generation 변경 시 원자적으로 purge하고 cap을 유지합니다.

**Gate:** 동일 size/mtime 변조, manifest-only 변경, WAL commit, eviction이 모두 재계산을 유발합니다.

### Page 5 — Lazy factory evidence와 명시적 오류

- `Disclosure`에 opt-in `lazy`를 추가하고 최초 open 때만 child를 mount합니다.
- 9개 factory disclosure는 닫힌 상태에서 optional request 0건이어야 합니다.
- lane-runs는 RL tab lifetime에서 successful non-null 결과만 공유하고 null/rejection은 재시도합니다.
- 모든 self-fetch card는 loading/error/empty/ready와 retry를 구분합니다.

**Gate:** 닫힌 상태 0 request, 4개 lane consumer 합계 1 request, close/reopen 추가 request 0을 browser transcript로 검증합니다.

### Page 6 — 운영·연구 UX와 95점 closure

- Home/Experiment에 60M/10-slot이 실제 운영금이 아닌 fixed-notional 연구 회계임을 명시합니다.
- 10 slots는 매일 0~10개의 선택 가능한 용량이며 항상 10종목 보유가 아님을 표시합니다.
- 다음 M3E cycle DRAFT, OOS custody blocker, reused-validation limitation을 registry에서 확인할 수 있게 합니다.
- 320/390/768/1440/3440 viewport와 V6/V3/V5 shell을 검사합니다.
- 점수는 테스트·browser·request transcript·custody tamper 증거가 없는 항목에는 부여하지 않습니다.

## 4. 구현 commit 전략

| 순서 | 내용 |
|---:|---|
| 1 | release baseline과 계획·연구 continuation 문서 |
| 2 | typed route ownership와 bookmark compatibility |
| 3 | app factory/service boundary |
| 4 | artifact tail/catalog와 cache freshness |
| 5 | lazy evidence와 explicit errors |
| 6 | research UX, browser matrix, 95점 closure |

## 5. 검증

```powershell
py -3.11 -m pytest tests/test_v6_platform_api.py tests/test_v6_insight_api.py tests/test_kronos_v5_app_integration.py tests/test_webui_local_security.py -q
py -3.11 -m pytest tests/test_stom_rl_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_stom_rl_dashboard_factory_tab.py tests/test_v2_route.py tests/test_v2_dist_marker.py -q
cd webui/v2_src
bun test src
npm run check
npm run build
```

Browser gate:

- `/`, `/?ui=v6&tab=home`, `/training`, `/dashboard`
- `/?ui=v3`, `/?ui=v5`
- V6 Data, Experiment, Training, Report
- 320×800, 390×844, 768×1024, 1440×1000, 3440×1440
- horizontal overflow 0, console error 0, blocked/error/empty semantics 확인

## 6. 완료 정의

- 가중 rubric 95점 이상
- V6 root default와 V3/V5 rollback 정상
- corrupt/missing evidence가 사라지지 않음
- event/cache resource bound가 테스트됨
- factory closed request 0 및 lane request dedup 확인
- research accounting과 실제 운영금이 명확히 분리됨
- 모델 판정과 OOS custody가 불변

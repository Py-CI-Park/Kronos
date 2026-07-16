# Kronos 대시보드 V5 개발·검증·커밋 결과 보고서 (2026-07-16)

> 상태: 개발 브랜치 커밋 완료, 공식 정적 자산 재생성 완료, V3 기본 유지, V5 기본 전환 및 릴리스는 미승인·미실행.
>
> 이 보고서는 대시보드·연구 엔지니어링 결과를 기록한다. 수익성, 알파, 실거래 준비, 브로커 주문 준비, 모델 승격 또는 `GO`를 주장하지 않는다.

## 1. 작업 식별 정보

| 항목 | 값 |
|---|---|
| 개발 브랜치 | `feature/dashboard-v5-learning-evidence` |
| 작업 시작 기준 | `dd5393b` |
| V5 소스·테스트 커밋 | `9707583` — `feat(v5): 학습 증거 대시보드와 연구 실행 체계 구축` |
| 공식 정적 자산 커밋 | `7ea9505` — `build(dashboard): V5 학습 증거 화면 정적 자산 갱신` |
| Ultragoal 범위 | G001~G010, 10개 목표 전체 완료 |
| 전체 기록 경과시간 | 2026-07-15 00:12:15 ~ 2026-07-16 00:55:52, 약 24시간 43분 37초 |
| 현재 기본 UI 정책 | V3 유지 |
| V5 사용 범위 | 직접 경로 및 명시적 `?ui=v5` 검증용 |
| publish/push/merge/tag | 수행하지 않음 |

## 2. 개발 결과 요약

### 2.1 사용자 화면 및 라우팅

- `/learning-now`와 `/v5/learning-now` 직접 경로를 추가했다.
- 공식 Flask 사용자 경로는 `/learning-now`와 `/v5/learning-now`이며, `/static/v2/dist/`는 JS/CSS 정적 자산 base로만 사용한다.
- Vite public base URL과 Flask shell route를 정렬해 잘못된 루트 접근 시 안내되는 정적 base URL 문제를 해소했다.
- 모바일 375px, 태블릿 768px, 데스크톱 1280px 레이아웃을 검증했다.
- Learning Now 화면에 불변 run UID/revision, phase/liveness/progress, 경제 NAV, 23bp 비용 구성, 평가 매트릭스, ledger reconciliation, governance 및 false-lock 상태를 표시한다.
- 데이터 부재, stale, retry, timeout, conflict, `NOT_RUN`, `BLOCKED`, `NO-GO`를 성공처럼 표시하지 않는다.
- V3는 기본값으로 유지하고 V5는 유효한 terminal release gate가 없으면 자동 기본값이 될 수 없도록 했다.

### 2.2 증거·권위·점수 체계

- RFC 8785/JCS canonical bytes와 tamper vector를 도입했다.
- 서명된 authority lifecycle, one-use authorization, terminal `CLOSED/BLOCKED/INVALID`를 구현했다.
- evidence DAG, score DAG, assurance, category floor, hard-cap, six-lock 계약을 기계 검증 가능하게 만들었다.
- 모델 판정 `GO/NO-GO`, D0/D1/OOS 가용성 및 `NOT_RUN`은 엔지니어링 점수를 임의로 변경하지 못한다.
- 다음 여섯 잠금은 모든 관련 표면에서 계속 `false`다.
  - `promotion_allowed`
  - `model_build_allowed`
  - `paper_forward_allowed`
  - `live_broker_order_allowed`
  - `profitability_claim_allowed`
  - `go_summary_allowed`

### 2.3 연구 실행 및 회계

- D0 가격 기준과 D1 universe authority reader를 추가했다.
- 실제 증거가 없으면 `VERIFIED`로 승격하지 않고 `NOT_RUN` 또는 `BLOCKED`로 남긴다.
- close-slot 및 stateful SB3 Decimal 회계와 독립 oracle을 추가했다.
- 0/23/46bp 비용 스케줄, side-specific 비용, terminal liquidation, horizon reconciliation을 검증한다.
- stochastic training과 deterministic evaluation을 분리했다.
- 50-cell seed/fold/variant matrix, controls, ablations, checkpoint/resume/stop 및 exact/non-exact resume를 구현했다.
- heavy PPO와 fresh OOS는 실행하지 않았다.

### 2.4 Registry/API/다운로드 보안

- canonical SQLite registry와 journal snapshot을 구현했다.
- run UID/revision 불변성, terminal snapshot 불변성, monotonic sequence/timestamp, cursor scope 및 concurrency를 검증한다.
- V5 API는 GET-only이고 broker/order side effect를 제공하지 않는다.
- JSON Schema에서 Python/TypeScript 타입 및 Ajv standalone validator를 생성한다.
- `V5SchemaValidationError`는 제한된 `instancePath`와 `keyword`만 보존하며 원본 오류 payload를 노출하지 않는다.
- artifact 확장자/MIME 계약을 다음과 같이 통일했다.
  - `.json` → `application/json`
  - `.csv` → `text/csv`
  - `.jsonl` → `application/jsonl`
  - `.md` → `text/markdown`
  - `.png` → `image/png`
- download URL에 run identity query가 있으면 payload의 `run_id`와 `run_revision`에 정확히 결합되어야 한다.
- path traversal, reserved filename, MIME mismatch 및 denied download를 fail-closed 처리한다.

### 2.5 V4/V3 호환성

- localStorage 접근 실패를 방어하고 V3 rollback 우선순위를 보존했다.
- lifecycle object/primitive 및 nested summary/strategy 정규화를 보강했다.
- list/detail의 run UID/revision 충돌을 `CONFLICT_BLOCKED`로 표시한다.
- 기존 `/`, `/training`, `/dashboard`, `/rl`, `/daily-ohlcv`, `/daily-rl-guide` 및 legacy redirect 계약을 보존했다.

## 3. 업데이트 전·후 전체 기능 점수 비교

### 3.1 점수 산정 원칙

아래 점수는 **트레이딩 성과 점수나 수익성 점수가 아니다.** `docs/kronos_dashboard_v5_scorecard_v2.json`의 100점 가중치(A 25, B 25, C 20, D 15, E 15)를 사용해 다음 증거를 감사 매핑한 개발 기능 커버리지 점수다.

- 업데이트 전: `docs/kronos_dashboard_v4_handoff_2026-07-14.md`의 V4 검증 결과와 당시 부재 기능
- 업데이트 후: G001~G010 구현, 전체 테스트, 브라우저 매트릭스, score replay 및 최종 리뷰
- release/default 여부는 엔지니어링 점수와 별도 gate로 평가한다.

### 3.2 비교표

| 분류 | 배점 | 업데이트 전 | 업데이트 후 | 개선 | 주요 근거 |
|---|---:|---:|---:|---:|---|
| A. 증거 및 계약 무결성 | 25 | 18 | 25 | +7 | V4 false-lock/provenance에서 JCS, signed authority, immutable terminal, DAG, source identity로 확장 |
| B. 대시보드 정확성 및 접근성 | 25 | 22 | 25 | +3 | V4 72개 브라우저 시나리오에서 V5 112개, Learning Now, error/stale/retry 및 모바일 보강 |
| C. 연구 엔지니어링 | 20 | 11 | 20 | +9 | D0/D1, Decimal oracle, 50-cell protocol, registry/API 및 deterministic evaluator 추가 |
| D. 재현성 및 통제 | 15 | 9 | 15 | +6 | canonical fixture, generated-byte check, custody denial, resume/stop, score replay 및 tamper matrix 추가 |
| E. 릴리스 및 운영 품질 | 15 | 8 | 13 | +5 | fail-closed release equation, rollback/security gate, 공식 dist 빌드; V5 기본/릴리스 미승인으로 2점 보류 |
| **합계** | **100** | **68** | **98** | **+30** | **44.1% 상대 개선, 30%p 절대 개선** |

### 3.3 점수 해석

- 업데이트 전 68점은 V4가 이미 12개 탭, 72개 브라우저 시나리오, 접근성 및 false-lock을 갖췄지만 V5의 canonical authority, registry, score DAG, OOS custody, 50-cell runner 및 release equation이 없었던 상태를 의미한다.
- 업데이트 후 98점은 V5 엔지니어링 기능과 검증 범위가 모두 category floor를 넘었음을 의미한다.
- E 분류의 2점은 의도적으로 보류했다. 현재 V5는 기본값이 아니며 clean non-dry-run closure와 현재 dist에 결합된 새 live-browser receipt가 없다.
- 내부 score replay의 `point_score_a_eq_b`, `engineering_90_pass`, category floor 및 six-lock 조건은 통과했다.
- 위 점수는 `NO-GO` 모델 판정을 숨기거나 수익성을 의미하지 않는다.

### 3.4 릴리스 gate 별도 평가

최종 dry-run terminal report의 18개 equation term 중 14개가 참이었고 4개가 거짓이었다.

| 구분 | 결과 |
|---|---|
| 엔지니어링 점수/동일 replay | 통과 |
| assurance/prior chain | 통과 |
| source/head/tree/dist/config identity | 해당 dry-run 기준 통과 |
| rollback/security/six locks | 통과 |
| worktree clean | 당시 실패 |
| live browser distinct from synthetic | 실패 |
| non-dry-run fixture | 실패 |
| release closed | 실패 |
| 최종 결정 | `RETAIN_V3`, `TERMINAL_BLOCKED` |

릴리스 gate 통과율은 단순 참고치로 `14/18 = 77.8%`이며, release equation은 AND 조건이므로 한 항목이라도 실패하면 V5 기본 전환은 불가능하다.

## 4. 검증 결과

### 4.1 전체 Python 회귀

```text
py -3.11 -m pytest tests -q -W error
2103 passed, 2 skipped in 1120.27s
```

- 두 skip은 Windows/Torch 환경 조건에 따른 명시적 environment-gated skip이다.
- 경고는 `-W error`로 실패 처리했다.

### 4.2 최종 release/API 집중 검증

```text
py -3.11 -m pytest \
  tests/test_kronos_v5_release_closure.py \
  tests/test_kronos_v5_release_gate.py \
  tests/test_kronos_v5_api_schema.py -q -W error
163 passed in 9.56s
```

### 4.3 Frontend 및 공급망

```text
npm test
328 passed, 0 failed

npm run check
400 files, 0 errors, 0 warnings

npm audit --audit-level=high
0 vulnerabilities
```

### 4.4 공식 dist 재생성 후 검증

```text
npm run build
895 modules transformed
build passed

py -3.11 -m pytest \
  tests/test_v2_route.py \
  tests/test_v2_dist_marker.py \
  tests/test_kronos_v5_app_integration.py \
  tests/test_kronos_v5_release_gate.py -q -W error
47 passed in 21.08s
```

공식 build output은 `webui/static/v2/dist/`에 생성했으며 별도 `build(dashboard)` 커밋으로 소스 변경과 분리했다.

### 4.5 브라우저 매트릭스

| 분류 | 시나리오 수 |
|---|---:|
| 기본 탭/테마/폭 | 72 |
| lifecycle | 18 |
| governance | 10 |
| async/security | 8 |
| keyboard | 4 |
| **합계** | **112** |

검증 당시 console/page/network/a11y 오류, overflow, focus, keyboard, chart/table semantics, V3 rollback, denied download 및 retry 상태를 검사했다.

주의: 112개 live headless-browser receipt는 최종 비시각적 TypeScript/release 계약 수정 및 최종 공식 dist 커밋 전에 생성됐다. 따라서 현재 V5 기본 전환의 release-bound 증거로 재사용하지 않는다.

## 5. 커밋 구성

### 5.1 소스·테스트·계약

```text
9707583 feat(v5): 학습 증거 대시보드와 연구 실행 체계 구축
```

- 179개 파일
- 53,035 insertions / 727 deletions
- 스키마, authority/evidence/score, 회계, protocol, registry/API, Learning Now, release gate 및 테스트 포함

### 5.2 공식 정적 자산

```text
7ea9505 build(dashboard): V5 학습 증거 화면 정적 자산 갱신
```

- 16개 dist 파일
- source commit에서 생성한 공식 정적 자산만 별도 기록

### 5.3 보고서

본 문서는 코드와 생성물 커밋 이후 별도 문서 커밋으로 기록한다. 문서 커밋 자체의 SHA는 커밋 후 `git log -3 --oneline`에서 확인한다.

## 6. 현재 제한 및 정직성 경계

- V3가 기본이다.
- V5 default/release eligibility는 `false`다.
- V5는 직접 경로 또는 명시적 query로만 확인한다.
- 모델 상태의 기존 `NO-GO`/`INCONCLUSIVE_NO_GO`를 변경하지 않는다.
- `ts_imb` gap-up baseline은 RULE이며 RL로 표현하지 않는다.
- 23bp는 명시된 round-trip 비용 가정이며 실제 체결 성과를 의미하지 않는다.
- fresh OOS, heavy PPO, broker order, paper-forward, publish, push, merge, tag는 수행하지 않았다.
- 실제 사용자 운영 승인, 수익성 및 실거래 준비를 주장하지 않는다.

## 7. 사용자가 직접 확인할 항목

### 7.1 Git 및 커밋

```powershell
git branch --show-current
git log -3 --oneline
git status --short
```

확인 기준:

- 브랜치가 `feature/dashboard-v5-learning-evidence`인지 확인한다.
- 소스, dist, 본 보고서의 3개 커밋이 순서대로 존재하는지 확인한다.
- `git status --short`가 비어 있는지 확인한다.

### 7.2 V3 기본 및 V5 직접 경로

대시보드 실행 포트는 `start_dashboard.bat` 기준 `8122`다. 실행 후 다음을 각각 확인한다.

```text
http://127.0.0.1:8122/
http://127.0.0.1:8122/?ui=v3
http://127.0.0.1:8122/learning-now?ui=v5
http://127.0.0.1:8122/v5/learning-now?ui=v5
```

`http://127.0.0.1:8122/static/v2/dist/learning-now?ui=v5`는 Flask 사용자 경로가 아니므로 사용하지 않는다. 해당 경로의 `404`는 정상이며, `/static/v2/dist/`는 빌드 자산 제공에만 사용한다.

Chrome 실기동 확인에서 실제 SQLite registry 연결 시 발견한 두 경계를 추가 수정했다.

- `/api/v5/rl/runs` 기본 page limit가 registry 최대값 100을 넘겨 101로 전달되던 문제를 100으로 수정했다.
- terminal registry snapshot의 `COMPLETED`가 API에서 `RUNNING`으로 변환되던 문제를 `SUCCEEDED`로 수정했다.
- 실제 Chrome 1280×900에서 V3/V5 shell, 4개 run selector, revision 선택, `SUCCEEDED`, 100/100 progress 및 문서 overflow 없음까지 확인했다.
- Chrome 375×812 모바일 에뮬레이션에서 카드 잘림은 없었고 브라우저 sub-pixel 반올림으로 document width가 1px 차이 나는 것을 관찰했다.

확인 기준:

1. `/`와 `/?ui=v3`는 V3 기본 화면을 유지한다.
2. V5 직접 경로에는 `Learning Now`가 표시된다.
3. 모바일 폭에서 가로 스크롤이나 잘린 카드가 없어야 한다.
4. registry 데이터가 없을 때 `UID_UNAVAILABLE`, `NOT_RUN`, `BLOCKED`처럼 정직한 빈 상태가 표시되어야 한다.
5. 모델 승격, 수익성, live-ready 또는 `GO` 표현이 없어야 한다.

### 7.3 API 및 다운로드 경계

확인 기준:

- V5 조회 API가 GET-only인지 확인한다.
- mutation POST는 `405` 또는 명시적 거부가 되어야 한다.
- artifact download에서 path traversal, 예약 파일명 및 MIME mismatch가 거부되어야 한다.
- run/revision이 다른 cursor 또는 download binding이 거부되어야 한다.

### 7.4 증거 화면

Learning Now에서 다음을 확인한다.

- Run UID와 revision이 함께 표시되는가
- source SHA-256와 registry revision을 혼동하지 않는가
- progress/liveness와 stale 상태가 구분되는가
- 경제 NAV와 23bp 비용 구성요소가 분리되는가
- matrix의 PASS/FAIL/BLOCKED/PENDING 합계가 보존되는가
- ledger와 artifact가 선택한 동일 run/revision에 결합되는가
- 여섯 개 lock이 모두 false인가

### 7.5 V5 기본 전환 전 필수 재검증

V5를 기본으로 바꾸려면 별도 승인 후 다음을 새로 수행해야 한다.

1. clean HEAD/tree/worktree 확인
2. 현재 공식 dist와 source manifest 재생성
3. 현재 dist를 대상으로 112개 live-browser matrix 재캡처
4. synthetic evidence와 다른 browser receipt 확인
5. security 및 V3 rollback 재검증
6. non-dry-run terminal closure 수행
7. `TERMINAL_CLOSED`, `SWITCH_TO_V5`, 빈 `blocking_codes` 확인

위 조건 전에는 V3 기본을 유지한다.

## 8. 최종 결론

이번 업데이트는 V4의 읽기 전용 증거 대시보드를 V5의 불변 권위·증거·회계·프로토콜·registry/API·Learning Now 체계로 확장했다. 감사 매핑 기능 점수는 68점에서 98점으로 30점 개선됐고, 전체 Python 2,103개 및 frontend 328개 테스트를 통과했다.

그러나 엔지니어링 완성도와 릴리스 승인은 별개다. 현재 V5는 수익성·실거래·승격을 주장할 수 없으며, 현재 공식 dist에 결합된 새 live-browser receipt와 non-dry-run terminal closure가 없으므로 V3 기본을 유지한다.

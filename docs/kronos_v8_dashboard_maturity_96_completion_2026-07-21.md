# Kronos V8 대시보드 성숙도 96/100 완료 보고 — 2026-07-21

> 문서 ID: `KRONOS-V8-DASHBOARD-MATURITY-96-COMPLETION-2026-07-21`
> 상태: `ENGINEERING_COMPLETE / RESEARCH_ONLY`
> 브랜치: `feature/dashboard-v8-maturity-95`
> 기준 release: `fork-v1.6.0-dashboard-v7-rl-reports`
> 서비스 URL: `http://127.0.0.1:8122/` → `/?ui=v6&tab=home`

## 1. 완료 요약

V6를 8122 기본 대시보드로 유지한 채 route 단일 소유권, legacy bookmark 변환, Flask app factory, bounded artifact/event 처리, content-based cache freshness, lazy evidence, 명시적 오류·재시도, M3E 연구 연속성 UX를 구현했습니다. V3/V5 rollback은 유지됩니다.

이 점수는 대시보드 엔지니어링 성숙도입니다. 모델 성과, 수익성, 실제 운영금, broker/live readiness 또는 GO 점수가 아닙니다. 기존 판정 M1/M3 `INCONCLUSIVE`, M2 `NO_GO`, untouched test `NOT_RUN`은 변경하지 않았습니다.

## 2. 페이지별 결과

| Page | 구현 | 핵심 결과 | 검증 | 상태 |
|---:|---|---|---|---|
| 1 | Typed route ownership | 12개 legacy route의 label, alias, component, shell, V5 workspace, V6 target을 manifest로 통합 | frontend 368 tests, `/training`·`/dashboard` → V6 Training | 완료 |
| 2 | Flask app factory | `create_app(config=None, *, blueprint_factories=None)`와 독립 app instance, 구조화 진단 | app integration 포함 backend 60 tests | 완료 |
| 3 | Artifact catalog/event tail | request snapshot 재사용, invalid chain 보존, 뒤에서 최대 1MiB·50 event read | corruption, append, scan-count tests | 완료 |
| 4 | Cache freshness | index content SHA, manifest SHA, DB/WAL/SHM revision, bounded purge/eviction | same-size/mtime tamper와 WAL tests | 완료 |
| 5 | Lazy evidence/error states | 9개 optional panel 최초 open mount, lane-runs dedup, loading/error/empty/ready/retry | 닫힘 optional request 0; open-close-reopen lane-runs 1회 | 완료 |
| 6 | Research/operations UX | M3E draft, OOS custody blocker, reused-validation 한계, 60M/0–10 slot 회계 의미 표시 | 45-case browser matrix, overflow·console error 0 | 완료 |

## 3. 기능별 변경 상세

| 영역 | 변경 전 문제 | 완료한 변경 | 사용자 효과 |
|---|---|---|---|
| 기본 실행 | 일부 launcher가 `/rl`을 운영 URL로 표시 | quiet launcher와 readiness를 `/`로 통일 | 8122 root가 V6 최신 화면의 단일 진입점 |
| Route | App/Sidebar에 route 정보 중복 | typed manifest + component registry | route 추가·변경 시 불일치 위험 감소 |
| Bookmark | V6에서 `/training`, `/dashboard` 의미 유실 | V6 `rl/training`으로 canonicalize | 기존 즐겨찾기 유지 |
| Backend 구성 | import-time singleton 결합 | app factory와 독립 instance | test/config 격리 강화 |
| Artifact 목록 | 반복 scan, invalid evidence 누락 위험 | request snapshot과 INVALID reason | 누락·손상을 빈 성공으로 오인하지 않음 |
| Event tail | 전체 파일 read 가능성 | 뒤쪽 bounded read와 diagnostics | 큰 run log의 메모리·latency 상한 |
| Index cache | size/mtime 충돌 가능 | content SHA 재검증, 삭제 prune, cap | 동일 stat 변조 fail-closed |
| Insight cache | DB 본체만으로 freshness 판단 | manifest + DB/WAL/SHM signature | WAL 변경도 즉시 반영 |
| Factory evidence | 닫힌 panel도 mount/fetch | opt-in lazy mount | 초기 네트워크·렌더 비용 감소 |
| Optional card | 실패와 빈 결과 혼동 | explicit loading/error/empty/ready + retry | 연구 증거 상태 해석 개선 |
| 종가 연구 UX | 60M/10 slots가 실제 운용처럼 보일 여지 | fixed-notional, 0–10 optional, no broker/live 문구 | 연구 회계와 실제 운영금 분리 |
| 연구 연속성 | 다음 cycle과 blocker가 UI에서 불명확 | registry 기반 M3E draft 및 OOS custody blocker | 과거 결과에서 다음 연구로 추적 가능 |

## 4. 성숙도 점수

| 평가 축 | 배점 | 점수 | 근거 |
|---|---:|---:|---|
| 연구 정직성·custody·보안 | 25 | 25 | 기존 verdict 불변, false locks, tamper fail-closed, KRX credential 비노출, fixed-notional 명시 |
| UX/UI·접근성·프로세스 완결성 | 20 | 19 | 5 viewport, V6/V3/V5, 명시적 상태·retry, 연구 단계/초안 시각화; 고급 시각 디자인 정량 사용자 시험은 미실시 |
| route·frontend 상태 소유권 | 20 | 19 | typed manifest와 bookmark compatibility; V3/V4/V5 legacy shell 자체는 호환을 위해 존치 |
| backend 경계·성능·freshness | 20 | 18 | app factory, bounded scans/tails/caches, WAL freshness; 완전한 DI service 분해는 후속 구조 개선 가능 |
| 테스트·운영·rollback | 15 | 15 | 368 frontend, 203 Python focused/regression, build, 45 browser checks, V3/V5 rollback |
| **합계** | **100** | **96** | **95점 gate 충족** |

## 5. 실행한 검증

| 검증 | 결과 |
|---|---:|
| `npm test` | 368 passed |
| `npm run check` | 437 files, 0 errors, 0 warnings |
| `npm run build` | 945 modules, success |
| V6 backend hardening set | 60 passed |
| core dashboard/orderbook set | 114 passed |
| STOM rule/gate set | 70 passed |
| security/route/dist set | 19 passed |
| Browser matrix | 45/45, horizontal overflow 0, console error 0 |
| Lazy closed-state transcript | optional factory request 0 |
| Lazy reopen transcript | `lane-runs` 1 request total |

Python은 각 명령에서 모두 통과했습니다. 60-test backend set은 114-test core set에 포함되므로 이를 합산한 고유 test 수를 주장하지 않습니다.

## 6. 종가매매 연구 재개 위치

다음 cycle은 full sequential RL이 아니라 `M3E fixed-seed consensus contextual-bandit research experiment`입니다. 실행 계약은 `docs/kronos_v8_prereg_m3e_2026-07-21.json`, 상세 순서는 `docs/kronos_v8_closing_rl_continuation_plan_2026-07-21.md`에 있습니다.

현재 바로 실행하지 않는 이유는 source/protocol hash가 아직 `TO_BE_FILLED_BEFORE_FREEZE`이고, untouched OOS의 물리 분리·SHA·gate receipt·one-time access ledger가 준비되지 않았기 때문입니다. Quant-Insight 추가 데이터와 KRX ID/PW는 현재 train/reused-validation 단계에 필요하지 않습니다. fresh OOS가 필요할 때만 credential을 코드·문서·manifest·로그에 남기지 않는 수집 경계를 사용합니다.

## 7. 잔여 작업

| 우선순위 | 잔여 작업 | 현재 blocker | 완료 조건 |
|---:|---|---|---|
| 1 | M3E policy/accounting 단일 함수와 synthetic tests | 구현 전 | train/eval 동일 contract와 source hash 확정 |
| 2 | OOS sealed custody | combined dataset가 test label을 기술적으로 읽을 수 있음 | 물리 분리, SHA, gate receipt, one-time ledger |
| 3 | M3E prereg freeze | source/protocol hash 미정 | draft를 결과 열람 전에 `FROZEN` 전환 |
| 4 | train-only + reused validation controls 1회 | 1~3 완료 필요 | 사전등록 gate 그대로 결과 기록 |
| 5 | 조건부 sealed OOS 1회 | eligibility와 independent audit 필요 | 결과와 무관하게 immutable report/ledger 생성 |

대시보드 95점 gate는 완료되었습니다. 남은 항목은 대시보드 결함이 아니라 다음 종가매매 연구 cycle의 실험·custody 작업입니다.

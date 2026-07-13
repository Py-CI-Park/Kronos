# Kronos 95점 완료 인계서 — 2026-07-13

## 1. 최종 판정

| 구분 | 결과 | 근거 |
|---|---:|---|
| 엔지니어링·연구 프로세스 점수 | **100 / 100** | 고정 v1 이진 점수표 재계산 |
| Gate-95 | **PASS** | 총점 ≥95, A~E 각 19점 이상, 활성 hard cap 없음 |
| 대시보드·릴리스 | **60 / 60** | A 20, B 20, E 20 |
| 연구 파이프라인 | **40 / 40** | C 20, D 20 |
| 모델·수익성 판정 | **INCONCLUSIVE / NO-GO** | 점수와 분리; 수익성·실거래 준비를 뜻하지 않음 |

이 문서의 100점은 **엔지니어링, 재현성, 안전 잠금, 증거 품질** 점수다. 수익성, 실거래, 브로커, 주문, 계좌, 페이퍼 포워드 또는 모델 승인을 의미하지 않는다.

## 2. 정확한 재개 지점

| 항목 | 값 |
|---|---|
| 로컬 브랜치 | `release/dashboard-v3-95` |
| 검증된 릴리스 후보 SHA | `095ef6d4919c7d048c7d0ca0a4f987490e4eef23` |
| 기준 통합 SHA | `044b5468be2baa11ef451da32ff3999c7c8ab83b` |
| 릴리스 커밋 제목 | `chore(release): assemble dashboard-v3 95-point candidate` |
| 최종 JS | `webui/static/v2/dist/assets/index-C7U88w1O.js` |
| 최종 CSS | `webui/static/v2/dist/assets/index-BfwbWl7b.css` |
| 외부 게시 상태 | **미실행 — 사용자 최종 승인 대기** |

인계 문서 커밋은 문서 자체에 자기 SHA를 고정할 수 없으므로, 재개 시 `git log -1 --oneline`으로 확인한다. 제품·런타임 검증 기준은 위 릴리스 후보 SHA다.

## 3. 점수표

| 범주 | 점수 | 핵심 성과 |
|---|---:|---|
| A · 증거 진실성 | 20/20 | RUNNING/STALE/REPLAY 진실성, 단위·행동 null 보존, 권위 있는 run/OOS 선택 |
| B · 사용성·성능 | 20/20 | 72개 반응형 화면, WCAG A/AA, 키보드, 카드별 Abort/RETRY, 지연 게이트 |
| C · 연구 실행 | 20/20 | close-slot 회계, SB3 adapter/smoke/정지 판정, R5 attribution, R6/R7 증거 |
| D · 거버넌스 | 20/20 | 사전등록, 23bp 및 0/46 통제, alias/seed 무결성, 잠금·승격 차단 |
| E · 릴리스 품질 | 20/20 | 전체 테스트, 보안·의존성, exact bundle/API/hash, clean tree, 독립 리뷰 |

공식 재계산 파일:

- `.omo/evidence/task-25-final-score/independent_score_evidence.json`
- `.omo/evidence/task-25-final-score/score_a.json`
- `.omo/evidence/task-25-final-score/score_b.json`
- `.omo/evidence/task-25-final-score/score_summary.json`
- `.omo/evidence/task-24-release-candidate/scorecard_evidence_map.json`
- `.omo/evidence/task-24-release-candidate/scorecard_evidence_resolution.json`

## 4. 현재 상태와 성과

| 영역 | 완료된 동작 | 사용자에게 보이는 개선 |
|---|---|---|
| Mission Control | 연구 라인, blocker, 잠금, 시스템 상태 통합 | 실패·NO-GO를 숨기지 않고 첫 화면에서 판단 가능 |
| Daily OHLCV | 권위 run/OOS/정책 선택, 카드별 독립 로딩·오류·재시도 | 느린 카드 하나가 전체 화면을 막지 않음 |
| RL 화면 | 상태·단위·행동 기록 여부·freshness 분리 | polling을 LIVE로 오인하거나 null을 HOLD/0으로 조작하지 않음 |
| 반응형·접근성 | 12 tabs × 2 themes × 3 widths, 키보드·WCAG·차트 대안 | 375/768/1280에서 가로 넘침 없이 검토 가능 |
| 보안 | loopback CORS, 경로 containment, 자원 상한, Markdown 정화 | trusted-local 범위를 유지하고 위험 입력은 fail-closed |
| 연구 추적 | 권위 registry, Aim localhost, rliable real-seed 보고 | smoke/alias/중복 seed를 독립 성과로 과대계상하지 않음 |

## 5. 검증 명령과 실제 결과

| 명령 | 결과 |
|---|---|
| `py -3.11 -m pytest -q` | **1219 passed, 2 skipped**, 353개 연구·환경 경고 유지 |
| `npm ci` | PASS |
| `npm run check` | **288 files, 0 errors, 0 warnings** |
| `npm run build` | PASS, 828 modules, exact bundle 생성 |
| `npm audit --audit-level=high` | **0 vulnerabilities** |
| TypeScript 6개 suite | **56 passed** |
| `scripts/verify_dashboard_v3_execution_boundaries.py` | `all_gates_pass=true` |
| exact HTTP/API 점검 | 12/12 HTTP 200, exact bundle 일치 |
| exact 화면 행렬 | 72/72 PASS, overflow/console/page/request 실패 0 |
| exact WCAG 점검 | 24/24 tab-theme, A/AA 위반 0 |
| exact 키보드 점검 | 12/12 sidebar Enter/focus-visible PASS; replay Enter/Space PASS |
| 지연 주입 | 20초 timeout, 해당 카드만 RETRY, progress/close-slot 유지, 정상 서버 복구 PASS |

## 6. 핵심 증거 목록

| 증거 | 역할 |
|---|---|
| `.omo/evidence/task-24-release-candidate/g024_gate_summary.json` | 릴리스 게이트 요약 |
| `.omo/evidence/task-24-release-candidate/runtime_http_api.json` | exact SHA HTTP/API·bundle |
| `.omo/evidence/task-24-release-candidate/artifact_hash_audit.json` | dist 및 증거 SHA-256 |
| `.omo/evidence/task-24-release-candidate/promotion_lock_audit.json` | 6개 승격·수익·실거래 잠금 |
| `.omo/evidence/task-24-release-candidate/execution_boundaries.json` | Gate-A, frozen path, route, clean tree |
| `.omo/evidence/task-24-release-candidate/source_generated_separation.json` | source/generated 분리 |
| `.omo/evidence/task-24-release-candidate/visual/exact_matrix_095ef6d.json` | 72개 실제 브라우저 캡처 |
| `.omo/evidence/task-24-release-candidate/visual/exact_wcag_aa_095ef6d.json` | WCAG A/AA |
| `.omo/evidence/task-24-release-candidate/visual/keyboard_all_tabs_exact_095ef6d.json` | 전 tab 키보드 |
| `.omo/evidence/task-24-release-candidate/visual/replay_keyboard_exact_095ef6d.json` | replay 키보드 |
| `.omo/evidence/task-24-release-candidate/async_card_injected_latency.json` | timeout 격리·복구 |
| `.omo/evidence/task-24-release-candidate/runtime_debug_hypotheses.json` | 3개 런타임 가설과 실제 증거 |

## 7. 독립 리뷰 영수증

| 검토 | 영수증 | 결과 |
|---|---|---|
| G024 목표 적합성 | `agent://132-132-G024ExactGoal` | PASS |
| 코드 품질 | `agent://128-128-G024ExactCode` | PASS |
| 보안·진실성 | `agent://129-129-G024ExactSecurity` | PASS |
| 런타임 hands-on | `agent://130-130-G024ExactHandsOn` | PASS |
| 범위·원문 제약 | `agent://131-131-G024ExactContext` | PASS |
| 시각 A | `agent://133-133-G025ExactVisualA` | PASS |
| 시각 B | `agent://134-134-G025ExactVisualB` | PASS |
| executor adversarial QA | `agent://135-135-G024ExecutorQa` | PASS |
| 독립 100-check scorer | `agent://136-136-G026IndependentScorer` | PASS · 100/100 |
| 독립 score critic | `agent://137-137-G026ScoreCritic` | PASS · 100/100 |

## 8. 남아 있는 NO-GO와 위험

| 항목 | 현재 판정 | 의미 |
|---|---|---|
| R5 attribution | `TUNING_HARMFUL` | F14 predictor 재학습은 잠금 유지 |
| close-slot 정책 | primary TEST OOS `NO-GO`, 체결 0 | train/aggregate 양수로 승격 금지 |
| R3b full | 사전등록 기준 미정으로 `NOT_RUN_NOT_PROMOTED` | 200k를 억지로 실행하지 않은 것이 정직한 완료 경로 |
| D4 stability | `SEED_NOISE_NO_GO` | seed 의존성과 never-trade 분화를 성과로 포장하지 않음 |
| D0/D1 | price basis·universe blocker 유지 | 조정가격·공식 universe 증거 전 의사결정 승격 금지 |
| 실거래 계층 | 모든 release lock false | live/broker/order/account/paper/model-build/profit GO 아님 |

기본 거래비용은 별도 문서가 명시하지 않는 한 **왕복 23bp**다. `ts_imb`는 계속 **RULE baseline**이며 RL 결과가 아니다. 종목 코드는 `000250`처럼 문자열로 유지한다.

## 9. 복구·롤백

1. 검증 기준으로 돌아가려면 `release/dashboard-v3-95`의 `095ef6d4919c7d048c7d0ca0a4f987490e4eef23`을 기준으로 diff를 확인한다.
2. 최종 문서 커밋만 되돌릴 때는 해당 문서 커밋을 `git revert`한다. 제품 릴리스 후보 커밋을 재작성하거나 강제 push하지 않는다.
3. dist 재생성이 필요하면 `webui/v2_src`에서 `npm ci`, `npm run check`, `npm run build` 후 exact asset 이름과 hash audit를 다시 만든다.
4. 제품 코드가 바뀌면 기존 exact-SHA 브라우저·API·리뷰 영수증은 모두 stale로 보고 G024/G026 게이트를 다시 수행한다.
5. `.omo/evidence/`는 gitignored 세션 증거다. 삭제 전에 필요한 인계 번들을 별도 보존한다.

## 10. master 병합·게시 절차 — 아직 실행 금지

사용자가 이 문서와 최종 영수증을 확인하고 **외부 게시를 명시적으로 승인한 뒤에만** 수행한다.

1. `git status --short`가 비어 있는지 확인한다.
2. `git rev-parse HEAD`와 `git log -2 --oneline`으로 릴리스·인계 커밋을 확인한다.
3. `release/dashboard-v3-95`를 `origin/dashboard-v3`에 게시한다.
4. base `master`, head `dashboard-v3`인 PR을 준비한다.
5. PR 본문에 이 문서, 100/100 엔지니어링 점수, 별도 `INCONCLUSIVE / NO-GO` 모델 판정, 23bp, 미해결 blocker를 그대로 기록한다.
6. merge, release tag, tag push는 별도 승인 없이는 수행하지 않는다.

현재 단계에서는 **push, PR 생성, merge, release tag, tag push를 수행하지 않았다**.

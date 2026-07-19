# Kronos 대시보드 V4 재설계 핸드오프 (2026-07-14)

> 상태: 릴리스 후보(검증 완료), 미발행/미머지/미태깅. 신규 최종 승인 없이는 publish/merge/tag 금지.
> 이 문서는 연구·읽기 전용 대시보드 재설계의 핸드오프이며, 수익성·실거래·모델 승격을 주장하지 않는다.

## 1. 브랜치 / SHA

- 브랜치: `feature/dashboard-v4-ux-rearchitecture`
- 브랜치 기준: `origin/master@7f31958299c42078e7a90946de2632314f5ce790`
- 커밋된 거버넌스 커밋: `860ecaacb0a4cd4ccecd3d67d751b5b911270889` (chore(governance): register dashboard v4 purpose branch)
- 제품/테스트/증거/재생성 dist는 작업 트리에 존재하며(의도적으로 미커밋), 리뷰 권위는 git status가 아니라 각 웨이브의 frozen manifest·verification 이다.
- 릴리스 dist(1회 재생성): `webui/static/v2/dist/assets/index-BVrQF9gJ.js`, `index-BVrQF9gJ.js.map`, `index-LZRQdlv3.css` (구 V3 dist 자산 삭제됨 — 단일 생성물).

## 2. IA / 탭 맵 (12 탭, V3 기본 · V4 opt-in)

| 탭 id | V3 (기본) | V4 (opt-in, `?ui=v4`) |
| --- | --- | --- |
| mission-control | MissionControl | V4MissionControl (Hybrid Mission Control, blocker strip + status locks + workflow map + 정확히 6 카드) |
| live-training | LiveTrainingTab | V4TrainingOps(children) |
| forecast | ForecastWorkbenchTab | V4ForecastStudio(children) |
| stom | StomDiagnosticsTab | V4LegacyDomainFrame surface=diagnostics(children) |
| daily-ohlcv | DailyOhlcvTab | V4DailyResearch(children) |
| daily-rl-guide | DailyRlGuideTab | V4LegacyDomainFrame surface=daily-guide(children) |
| rl | RLTradingTab | V4RLEvidenceConsole(children) |
| artifacts | ArtifactsModelsTab | V4ArtifactsWorkspace(children) |
| history | HistoryRunsTab | V4RunsWorkspace(children) |
| system-health | SystemHealthTab | V4SystemOps(children) |
| settings | SettingsTab | V4AdminWorkspace surface=settings(children) |
| docs | DocsTab | V4AdminWorkspace surface=docs(children) |

- 활성화 우선순위: `?ui=v3|v4`(현재 로드) → `ui_persist=1` 시 localStorage `kronos-dashboard-shell` 기록 → 미쿼리 시 localStorage → 기본 V3.
- DOM 마커: `data-kronos-shell="v3|v4"`, `data-v4-shell`, `data-v3-tab-host`, `data-v4-domain-host`, `data-v4-command-palette`.
- 레거시 라우트/별칭 보존: `/`, `/training`, `/dashboard`, `/rl`, `/daily-ohlcv`, `/daily-rl-guide`, `/daily-ohlcv/rl-guide`, `/v2*`, `/rl-lab` (별칭은 `routes.ts`로 이전되었으나 전부 보존).
- 명령 팔레트(V4): 읽기 전용 ARIA dialog+combobox, 탐색/조회 명령만, POST/mutation/action 비활성.

## 3. 안전 잠금 계약 (정확히 6종, 항상 fail-closed)

`promotion_allowed`, `model_build_allowed`, `paper_forward_allowed`, `live_broker_order_allowed`, `profitability_claim_allowed`, `go_summary_allowed` — 소스가 boolean true를 선언하지 않으면 항상 false. 낙관적 fallback 없음. 모든 V4 표면에서 `data-lock-key`로 렌더.

## 4. 실행 명령과 결과 (릴리스 게이트)

프론트엔드 (`webui/v2_src`):
```
bun test            # 258 passed / 0 failed (21 files)
npm run check       # 337 files, 0 errors, 0 warnings
npm run build       # 877 modules -> index-BVrQF9gJ.js + index-LZRQdlv3.css
npm audit --audit-level=high   # 0 vulnerabilities
```

파이썬 (V3/V4 계약·정직성·보안·경계 shard, 14 파일):
```
py -3.11 -m pytest tests/test_v4_all_tab_polish.py tests/test_v4_browser_matrix_harness.py \
  tests/test_v4_wave6_ops_admin.py tests/test_v4_wave5_daily_forecast.py tests/test_v4_wave3_mission_rl.py \
  tests/test_v4_evidence_system.py tests/test_v4_activation_shell.py tests/test_v3_contract_snapshot.py \
  tests/test_daily_ohlcv_dashboard_tab.py tests/test_stom_rl_dashboard_tab.py tests/test_stom_rl_dashboard_api.py \
  tests/test_v2_route.py tests/test_v2_dist_marker.py tests/test_webui_local_security.py \
  tests/test_dashboard_v3_execution_boundaries.py -q
# 154 passed
```

브라우저·성능·런타임:
```
browser matrix (12탭 x 2테마 x 375/768/1280 = 72) : 72/72 passed, GET-only, console/page/request 0, overflow 0, WCAG A/AA 0, keyboard/focus/chart-semantic passed
performance budgets : 9개 예산 + isolated-card RETRY 전부 통과(p95)
runtime HTTP : GET 읽기 엔드포인트 200, POST /api/training/status -> 405
```

## 5. V3 계약 스냅샷 재조정

`tests/_v3_contract_snapshot.json`는 브랜치 기준 이후 재생성되지 않아 drift가 누적되어 있었다. G009에서 `py -3.11 tests/_gen_v3_contract_snapshot.py`로 릴리스 소스에 맞춰 재조정. drift는 전부 benign: (1) 라우트 별칭이 `App.svelte`에서 `routes.ts`로 이전되었으나 보존, (2) 테스트 파일 제목에 대한 메타-단언 축소(하부 `cardRequest.ts`/`latencyGate.ts` 소스는 불변). 행위 가드 `test_verify_snapshot_passes_against_current_source`는 통과 — 필수 PRESENT/ABSENT 계약 문자열은 현재 소스에서 모두 유지.

## 6. 아티팩트 인벤토리

- 웨이브별 frozen manifest / verification:
  - Wave 0: `.omo/evidence/v4-wave-0/`
  - Wave 2(교체 체인 G010/G011): `.omo/evidence/v4-wave-2/`
  - Wave 3(G012, G005 대체): `.omo/evidence/v4-wave-3/frozen_change_set.json` (sha256 dfbd1edbb56615bcc325089bd68426343a52d356616d8182c450be62ed334aa1), `verification.json`
  - Wave 4/5(G006): `.omo/evidence/v4-wave-5/frozen_change_set.json`, `verification.json`
  - Wave 5(G007): `.omo/evidence/v4-wave-5/g007_frozen_change_set.json` (9767d6eb...), `g007_verification.json`
  - Wave 6(G008): `.omo/evidence/v4-wave-6/g008_frozen_change_set.json` (c8a89162...), `g008_verification.json`, browser_matrix_transcript.json, performance_capture.json
  - Wave 7(G009): `.omo/evidence/v4-wave-7/` (본 릴리스 게이트 로그·매니페스트·검증·시각 리시트)
- 브라우저 러너: `.omo/evidence/v4-wave-3/browser_qa_runner.cjs`, `browser_semantic_qa_runner.cjs`, `.omo/evidence/v4-wave-5/g007_browser_runner.cjs`, `.omo/evidence/v4-wave-6/browser_matrix_runner.cjs`, `performance_runner.cjs`.
- 검증 스크립트: `scripts/verify_dashboard_v4_browser_matrix.py`, `scripts/verify_dashboard_v4_performance.py`, `scripts/verify_dashboard_v3_execution_boundaries.py`.
- 릴리스 시각 리시트: `.omo/evidence/v4-wave-7/receipts/release-v3-default-home-1280.png`, `release-v4-home-1280.png`.

## 7. 알려진 NO-GO / 모델 리스크 (정직 고지)

- 대시보드 엔지니어링 품질은 수익성이나 승격을 의미하지 않는다.
- 모델 상태는 NO-GO: R5 `TUNING_HARMFUL`, close-slot TEST OOS `NO-GO`, R3b 전체 `NOT_RUN_NOT_PROMOTED`, D4 `SEED_NOISE_NO_GO`.
- 발행된 모델 판정은 `INCONCLUSIVE_NO_GO` 유지.
- RULE / supervised gate / RL 은 분리되어 표시되며, 누락 증거는 `MISSING`/`AGE_UNKNOWN`/`NOT_RECORDED`/무효 토큰으로 명시.
- 비용 가정 23bp는 명시 선언 시에만 사용. 6자리 종목코드는 문자열로 보존.
- 실거래/브로커/주문/계좌/페이퍼포워드/모델빌드/수익성/GO 주장 없음.

## 8. 롤백 / 복구

1. 즉시 롤백(런타임): `/?ui=v3&ui_persist=1` 방문 → V3 기본 복귀, localStorage `kronos-dashboard-shell=v3`.
2. 코드 롤백 필요 시: V4 셸/래퍼 관련 변경을 되돌리면 V3 탭은 그대로 동작(추가/opt-in 구조).
3. dist는 승인된 빌드 절차(`npm run build`)로만 재생성. dist 수기 편집 금지.
4. 롤백 후 활성화/라우트/브라우저 테스트 재실행.
5. frozen 백엔드/정적 라우트 파일(`webui/app.py`, `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py`, `stom_rl/rl_events.py`, `webui/v2_src/package.json`, `webui/v2_src/package-lock.json`)이 승인 없이 변경되면 즉시 중단·복구.

## 9. 발행 지침 (승인 필요)

- 본 릴리스 후보는 신규 최종 리시트 승인 없이는 publish/merge/tag 하지 않는다.
- 승인 시: 소스/생성물 분리 확인 → 단일 dist 재생성 → 본 문서의 게이트 재실행 → 태깅 → PR.
- 수익성·실거래·승격 문구를 발행물에 포함하지 않는다.

## 10. 게이트 요약 (전부 terminal PASS)

- Bun 258 / check 0-0 / build 877 / audit 0 / pytest 154(shard) — PASS.
- 브라우저 매트릭스 72/72, 성능 예산 전부 — PASS.
- 롤백·런타임 HTTP·DB 읽기전용·frozen 경계 — PASS.
- 각 웨이브 cleaner/architecture/executor QA 리시트 및 G008 독립 시각 리뷰어 2인 무조건 PASS.

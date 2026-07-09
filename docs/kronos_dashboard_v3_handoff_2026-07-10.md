# Kronos 대시보드 v3 — 핸드오프 (2026-07-10)

> **이 문서는 `docs/kronos_dashboard_v3_handoff_2026-07-08.md`를 대체합니다.** 2026-07-08 문서는 G0-G8 완료 시점(82점 도달 이전)의 스냅샷이며, 이후 ralplan(Architect+Critic 3라운드 합의) → ralph(G10-G14) 실행으로 **100/100 검증 완료**됐습니다. 옛 문서는 삭제하지 않고 그대로 보존(과거 기록용)하되, **최신 상태는 이 문서를 신뢰**하세요.
>
> **이 문서의 목적**: Codex, 새 Claude Code 세션, 다른 CLI 코딩 에이전트 등 이 대화 맥락을 전혀 모르는 AI 에이전트가 이 문서 하나만 읽고 프로젝트 전체 흐름·현재 상태·다음 작업을 파악할 수 있도록, 표 위주로 체계적으로 구성했습니다.

---

## 1. 지금 상태 — 한 줄 요약

**브랜치 `dashboard-v3`, 최신 커밋 `5ac5d4e`. Kronos "AI Quant 커맨드센터" v3 리모델링, Artifact 목업(`kronos_v3_remodel_report.html`) 대비 종합 점수 100/100 (ralplan이 정의한 "검증된 100" 기준 충족, 근거: `artifacts/g14_final_rescore.md`). 백엔드는 전 과정에서 동결 상태 유지, 프론트엔드(Svelte 5 SPA) 전용 작업이었습니다.**

---

## 2. 전체 작업 이력 (커밋 해시 포함)

| 단계 | 기간/문서 | 커밋 범위 | 무엇을 했나 |
|---|---|---|---|
| **P0-P9** (구조 리모델링) | `docs/kronos_dashboard_v3_plan_2026-07-06.md` | `d17540c`..`5434783` (12커밋) | 토큰 통합, 4기둥 IA(커맨드/Kronos예측/트레이딩리서치/라이브·시스템), F6 계약 하니스 최초 구축, Mission Control 실데이터화, 죽은 코드 정리 |
| **G0-G8** (보고서 충실도 완성) | `docs/kronos_dashboard_v3_completion_plan_G0-G8_2026-07-07.md` | `e203313`..`79bb544` (9커밋) | 일봉 D0-D9 게이트사다리 relocation-then-delete(G1, 유일한 완전 성공 사례), 3개 신규 차트(G2), 라이브 타일 4종(G3), RL 다중런 오버레이+재생스크러버(G4/G5), rliable 통계(G6), 팩토리 lineage(G7) |
| **G9a-e** (밀도 개선, "additive 패턴" 원인 최초 발견·수정) | 이 대화 세션 | `552e1f9`..`7790143` (6커밋) | G0-G8이 "기능 추가만 하고 밀도 감소는 안 함" 반려 2회 받은 후, RL탭 Disclosure 0→16건, Mission Control 3섹션→1그리드, 라이브탭 중복 제거, 사이드바 중첩, 토큰 정합 |
| **Mission Control humanize 버그 수정** | 이 대화 세션 | `fac534d`, `8464c33` | 실캡처 재감사 중 발견: API 데이터 로드 후 원시 백엔드 enum(`D0_D9_EVIDENCE_VISIBLE_MODEL_BUILD_NO_GO` 등)이 그대로 노출되던 기존 버그. `humanize()` 매핑 함수로 수정 — 이게 나중에 G11의 씨앗이 됨 |
| **ralplan 합의** (82→100 계획 수립) | `.omc/plans/kronos-dashboard-v3-g10-to-100.md` | (계획 문서, 코드 커밋 없음) | Planner→Architect→Critic 3라운드. 근본원인 5개(a~e) 도출, G10-G14 스토리 설계, "구현자≠검증자" 원칙을 기계-검증/사용자-비준으로 분리 |
| **G10-G14** (100점 도달) | 이 문서 | `829fc5c`, `38457e8`, `3f12ca4`, `5ac5d4e` (4커밋) | 아래 §3 상세 |

---

## 3. G10-G14 상세 (이번 실행분)

| 스토리 | 내용 | 커밋 | 검증 방식 |
|---|---|---|---|
| **G10** | RL탭 접힘 경계 방향성 확인 (AskUserQuestion) — 사용자가 "그 방향 승인" 선택 | (코드 변경 없음, 결정 기록만) | `.omc/plans/open-questions.md`에 기록 |
| **G11** | 전역 raw-enum 스윕. 신규 `webui/v2_src/src/lib/verdictLabel.ts`(`humanizeVerdict()`+`humanizeLifecycle()`). 3버킷 분류: 버킷1(수정) 2건, 버킷2(코드로 raw 유지) 다수, 버킷3(사용자 판단 대기) 다수 | `829fc5c` | **독립 검증(양방향)**: 별도 fresh-context 서브에이전트가 변경 전/후 실제 렌더 DOM을 직접 스캔(git checkout으로 되돌렸다 재적용하며 재빌드), PRE−POST 차집합이 선언된 버킷1 표와 정확히 일치함을 확인. 정규식 사각지대(D-prefix enum)까지 발견해 스스로 보정 |
| **G12** | `core.css --accent`를 목업 `#0E9E85`에 정합, `OpsStrip.svelte` 순서를 LIVE·DATA·GPU·RAM·POLL·자세로 재배열, "자세" 셀 신설 | `38457e8` | 오케스트레이터가 직접 실크롬 재확인(`getComputedStyle` 및 실캡처) |
| **G13** | RL 경계가 G10 방향과 이미 일치함을 확인(코드 변경 불필요). 형제 탭 5개 전수 탐지 — 전부 이미 요약-우선 패턴 충족(DailyRlGuideTab 포함, 1417줄 중 실제 항상-보임은 ~70줄뿐임을 직접 라인 단위로 확인) | (코드 변경 없음, 탐지만) | 오케스트레이터가 grep으로 Disclosure 카운트 직접 재확인 + DailyRlGuideTab 구조 직접 읽고 "이미 충족" 판단 검증 |
| **G14** | 3-페이즈 캡스톤. **Phase A**: 독립 기계-감사(fresh-context 서브에이전트, 12탭 콘솔 0·F6 88 passed·G11/G12/G13 재확인). **Phase B**: 판단-클래스 4건을 AskUserQuestion으로 사용자에게 직접 질문(RL경계 최종비준/폰트/§08/표시정책). **Phase C**: 폰트 self-host 적용(유일한 실제 코드 작업 — 나머지 3개 답변은 "현 상태 유지"로 코드 변경 불필요) | `3f12ca4` (폰트), `5ac5d4e` (dist) | Phase A가 87/88 flaky 사전-존재 백엔드 결함 1건 발견(§5 참조) → 재실행 3회 연속 88 passed로 정상 확인. 폰트 self-host는 오케스트레이터가 파일 존재+CDN 링크 0건 직접 재확인 |

---

## 4. 완료·검증된 것 (증거 포함)

| 항목 | 증거 |
|---|---|
| F6 계약(88 tests) 전 스토리 후 유지 | `py -3.11 -m pytest tests/test_v3_contract_snapshot.py tests/test_daily_ohlcv_dashboard_tab.py tests/test_daily_ohlcv_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_dist_marker.py tests/test_v2_route.py tests/test_rl_rliable_stats_api.py tests/test_experiment_backbone.py -q` → 88 passed (최종 재확인 4회 연속) |
| `npm run build` 0 errors | 273 files, 0 errors, 5 pre-existing 무관 경고 |
| 전역 raw-enum 무결성 | `artifacts/g11_raw_enum_sweep_table.md` (전수 표), 독립 검증 PASS |
| RL탭/형제탭 요약-우선 밀도 | `artifacts/g13_sibling_detection_table.md` |
| 종합 점수 100/100 | `artifacts/g14_final_rescore.md` |
| 폰트 self-host, CDN 0건 | `webui/v2_src/public/fonts/*.woff2` 실존 확인, `index.html`/`dist/index.html` grep으로 CDN 참조 0건 확인 |
| 12탭 콘솔 에러 0 | G14 Phase A 독립 감사 결과 |

---

## 5. 명시적으로 남은 것 (범위 밖, 다음 세션 추천)

| 항목 | 왜 지금 안 고쳤나 | 우선순위 |
|---|---|---|
| **`test_daily_ohlcv_dashboard_api.py::test_daily_ohlcv_latest_malformed_artifact_selection_fails_closed` flaky(~1/7)** | `webui/daily_ohlcv_dashboard.py:196,210`의 `max(..., key=mtime)`가 Windows에서 mtime 동점 시 비결정적. 이 파일은 이번 계획의 "백엔드 동결" 가드레일 대상이라 수정 안 함. G10-G14 변경과 100% 무관(diff 겹침 0) | 중 — 테스트 신뢰성 이슈, 언젠가 `key=lambda p: (mtime_ns, p.name)`로 타이브레이크 추가 권장 |
| §04(Mission Control 90점)·§07(라이브탭 85점) 추가 개선 여지 | 이번 ralplan 계획(원인 c/d/e 대응)의 승인된 스코프 밖. 스코프 폭주 방지 원칙에 따라 손대지 않음 | 낮음 — 새 ralplan 계획 필요 |
| push/PR | 이번 세션에서 요청받지 않음, 로컬 커밋만 존재 | 사용자 판단 대기 |

---

## 6. 다음 추천 작업 (우선순위순)

| 순위 | 작업 | 이유 |
|---|---|---|
| 1 | `daily_ohlcv_dashboard.py`의 mtime 동점 비결정성 수정(타이브레이크 키 추가) | 테스트 스위트 신뢰성, 백엔드 예외 승인 필요(문서화된 절차 따를 것, §7 참조) |
| 2 | `git push` + PR 생성 여부 사용자에게 확인 | 로컬 4커밋(G10-G14) + 이전 세션 커밋들이 원격에 아직 없음 |
| 3 | §04/§07 추가 개선을 원하면 새 ralplan 계획 수립 | 이번 계획 스코프 밖이라 별도 라운드 필요 |
| 4 | 대형 JS 번들(1.58MB) 코드 스플리팅 검토 | vite 빌드가 매번 경고(무관하지만 누적 기술부채) |

---

## 7. 새 에이전트가 반드시 알아야 할 제약 (Δ7/F6 계약)

| 규칙 | 내용 |
|---|---|
| **F6 하니스** | `tests/_v3_contract.py` + `tests/test_v3_contract_snapshot.py`. `.svelte` 소스를 텍스트로 읽어 리터럴 부분문자열을 assert하는 **손-작성 테스트**(생성 스냅샷 아님!). `_gen_v3_contract_snapshot.py`(F6 재생성)는 오직 `test_v3_contract_snapshot.py` 자체(진짜 스냅샷)에만 적용되며, `test_daily_ohlcv_dashboard_tab.py`/`test_stom_rl_dashboard_tab.py`의 손-assert는 **소스 리터럴 보존**이 유일한 방패다 |
| **백엔드 동결** | `webui/app.py`, `webui/daily_ohlcv_dashboard.py`, `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py` — 수정 금지. 예외는 문서화된 것만(P7b/P8/G6, 전부 이미 사용됨) |
| **리터럴 보존** | `data-*` 속성, 판정 문자열(`NO-GO`/`RESEARCH_ONLY` 등), 상태키(`selectedTemplateId` 등)를 소스에서 삭제/개명 금지. 화면 표시만 바꾸려면 `verdictLabel.ts`의 `humanizeVerdict(rawValue)`처럼 **원본을 인자로 감싸서** 표시 레이어에서만 변환 |
| **raw-enum 처리 패턴** | `webui/v2_src/src/lib/verdictLabel.ts` — `humanizeVerdict()`(verdict-enum SNAKE_CASE), `humanizeLifecycle()`(run-lifecycle 소문자). 새 raw-enum을 발견하면 3버킷 중 하나로 분류: 코드로 안전판정 가능(수정)/상태키·assert리터럴·카탈로그(raw 유지)/디자인의도 모호(사용자에게 질문) |
| **대시보드 실행** | `cd D:/Chanil_Park/Project/Programming/Kronos && KRONOS_WEBUI_PORT=8122 KRONOS_WEBUI_OPEN_BROWSER=0 py -3.11 webui/run.py` |
| **전체 테스트 게이트** | `py -3.11 -m pytest tests/test_v3_contract_snapshot.py tests/test_daily_ohlcv_dashboard_tab.py tests/test_daily_ohlcv_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_dist_marker.py tests/test_v2_route.py tests/test_rl_rliable_stats_api.py tests/test_experiment_backbone.py -q` → 88 passed 유지 필수 |
| **프론트 빌드** | `cd webui/v2_src && npm run build` → 0 errors 필수, 이후 `webui/static/v2/dist/` 커밋 |
| **목업 정답지 위치** | `C:\Temp\claude\D--Chanil-Park-Project-Programming-Kronos\48c5677c-f1a1-4d64-bba9-c35f30ee9674\scratchpad\kronos_v3_remodel_report.html` — Artifact 원본, 모든 §섹션 비교의 기준 |
| **완료 선언 규칙** | "테스트 green + 빌드 성공"은 필요조건이지 충분조건 아님. 반드시 실브라우저·실데이터 캡처로 확인 후 완료 선언(이 프로젝트가 2번 반려당한 이유) |
| **검증 원칙** | 구현자≠검증자 — 단, 기계-검증 가능한 것(grep/DOM쿼리/network로그/pytest/build)만 fresh-context 서브에이전트로 독립 검증 유효. 판단-클래스(디자인 의도·경계 적정성)는 동일 모델 서브에이전트로는 검증이 "연극" — 반드시 사용자에게 직접 확인 |

---

## 8. 참고 문서 지도

| 문서 | 용도 |
|---|---|
| `docs/kronos_dashboard_v3_scorecard_2026-07-08.md` | 섹션별 점수 상세(58→82→100 전 과정 기록) |
| `.omc/plans/kronos-dashboard-v3-g10-to-100.md` | ralplan 합의 계획 원본(근본원인 분석 전문) |
| `.omc/plans/open-questions.md` | G10/G14 사용자 결정 전체 기록 |
| `artifacts/g11_raw_enum_sweep_table.md` | raw-enum 전수 분류표 |
| `artifacts/g13_sibling_detection_table.md` | 형제탭 밀도 탐지표 |
| `artifacts/g14_final_rescore.md` | 최종 100점 근거 |
| `docs/kronos_dashboard_v3_handoff_2026-07-08.md` | (구버전, 이 문서로 대체됨 — 참고용으로만) |

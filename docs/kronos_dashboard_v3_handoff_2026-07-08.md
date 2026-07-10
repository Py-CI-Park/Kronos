# Kronos 대시보드 v3 — 핸드오프 (2026-07-08, 갱신됨)

**다음 세션에서 이 문서부터 읽을 것.** `/compact` 이후 컨텍스트가 초기화되므로, 아래 내용이 유일한 진실 소스입니다.

---

## 0. 2026-07-08 갱신 — G9a-e 밀도 개선 5개 항목 전부 완료

우선순위 1~5(아래 §2 원본 목록)를 Workflow로 병렬 구현(각 항목 소스 편집 + scoped pytest) → 통합 에이전트가 전체 게이트+build 실행 → **제가 직접** 크롬 실캡처(라이트+다크)로 재검증 + pytest 전체 게이트 독립 재실행(88 passed 재확인) → 5개 개별 커밋 + dist 커밋.

**커밋**: `552e1f9`(RL Disclosure) → `a063c2f`(MC 그리드) → `6a578c3`(라이브탭 중복제거) → `f61de25`(사이드바 중첩) → `d2736d6`(토큰) → `7790143`(dist 리빌드). 브랜치 `dashboard-v3` 최신 커밋 = `7790143`.

**점수**: 종합 58 → **82/100** (상세: `docs/kronos_dashboard_v3_scorecard_2026-07-08.md`, "갱신 결과" 블록 참조).

**남은 것**:
- CDN 폰트(jsdelivr Pretendard/JetBrains) self-host 여부 — 목업은 "웹폰트 미링크" 원칙을 명시했지만 실행 편의상 CDN 유지 중. **사용자 결정 필요.**
- RL탭의 "always-visible 경계"(posture strip/RunSelector/라이브 클러스터만 유지, 나머지 16개 Disclosure)는 이번 세션에서 합리적으로 추정한 것 — 목업에 명시적 스펙은 없었으므로 사용자가 실제로 보고 판단 필요.
- push/PR은 아직 안 함 — 사용자가 요청 시 진행.

---

## 1. 지금 상태 (한 줄 요약, 원본 — 위 §0의 갱신 반영 전 스냅샷)

**브랜치 `dashboard-v3`, 커밋 `79bb544`까지 완료. 백엔드 계약·테스트는 완벽(957 passed)하지만, Artifact 목업이 요구한 "요약 우선·밀도 감소"는 일봉(D0-D9 게이트사다리) 딱 한 곳에서만 실현됐고 나머지(Mission Control·라이브탭·RL탭)는 새 기능을 옛 밀도 위에 얹기만 해서 사용자가 두 번 "반영 안 됨"으로 반려함.**

- 상세 채점: `docs/kronos_dashboard_v3_scorecard_2026-07-08.md` (종합 58/100 → 갱신 후 82/100, 섹션별 상세)
- 원본 목업: `C:\Temp\claude\D--Chanil-Park-Project-Programming-Kronos\48c5677c-f1a1-4d64-bba9-c35f30ee9674\scratchpad\kronos_v3_remodel_report.html` (이게 "정답지")
- 원본 목업 Artifact 링크: https://claude.ai/code/artifact/63f888aa-b7b1-4a3d-8d35-bac3ab29faff

## 2. 다음에 할 일 — 우선순위 순서 (원본 목록, 전부 완료됨 — §0 참조)

1. ✅ **완료** RL탭(`RLTradingTab.svelte`)에 Disclosure 적용 — 16건 래핑, 커밋 `552e1f9`.
2. ✅ **완료** Mission Control(`MissionControl.svelte`) 6카드 단일 그리드 통합 — 커밋 `a063c2f`.
3. ✅ **완료** 라이브탭(`LiveTrainingTab.svelte`) 중복 제거 + 압축 — 커밋 `6a578c3`.
4. ✅ **완료** 사이드바(`Sidebar.svelte`) 부모-자식 중첩 — 커밋 `f61de25`.
5. ✅ **완료** 토큰 수치 정합 — 커밋 `d2736d6`.

**다음 세션에서 실제로 남은 일**: §0의 "남은 것" 3가지(CDN 폰트 결정, RL탭 경계 사용자 확인, push/PR 여부) + 사용자가 직접 크롬으로 보고 새로 발견하는 피드백.

## 3. 절대 지켜야 할 제약 (Δ7 계약)

- `tests/_v3_contract.py` + `tests/test_v3_contract_snapshot.py` = **F6 하니스**. 어떤 `data-*` 마커/판정문자열도 **삭제 금지**, 이동(relocation)만 허용 — 이동 시 반드시 `tests/test_daily_ohlcv_dashboard_tab.py`/`test_stom_rl_dashboard_tab.py`의 assert도 같이 재지정하고 `py -3.11 tests/_gen_v3_contract_snapshot.py`로 F6 스냅샷 재생성.
- **백엔드 동결** — `webui/app.py`, `webui/daily_ohlcv_dashboard.py`, `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py` 수정 금지. 예외 3건만 승인됨(P7b/P8/G6 — 전부 이미 사용됨). Disclosure 적용은 **프론트엔드 전용 작업이라 이 제약과 무관**.
- 매 단계 게이트: `py -3.11 -m pytest tests/test_v3_contract_snapshot.py tests/test_daily_ohlcv_dashboard_tab.py tests/test_daily_ohlcv_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_dist_marker.py tests/test_v2_route.py tests/test_rl_rliable_stats_api.py tests/test_experiment_backbone.py -q` → 88 passed 유지해야 함.
- `npm run build` (`cd webui/v2_src`) 0 에러 확인 후 커밋.
- **매 변경마다 실제 크롬 캡처로 확인** — 이번 세션에서 "테스트 green"만 믿고 "완료"라 보고했다가 두 번 반려당함. **캡처 없이 완료 선언 금지.**

## 4. 대시보드 실행 방법

```bash
# 서버 시작 (포트는 --port 아니라 env var로)
cd "D:/Chanil_Park/Project/Programming/Kronos"
KRONOS_WEBUI_PORT=8122 KRONOS_WEBUI_OPEN_BROWSER=0 py -3.11 webui/run.py
# 확인: curl http://127.0.0.1:8122/
```
- 백엔드(`app.py`) 수정 시 Flask 자동 리로드 안 됨 → **수동 재시작 필요**.
- 프론트 수정 시 `cd webui/v2_src && npm run build` 후 index.html은 no-cache라 새로고침만 하면 됨.
- Chrome MCP 도구는 세션 시작 시 deferred — `ToolSearch("select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__browser_batch")`로 한 번에 로드.

## 5. 이번 세션에서 완료된 것 (재작업 불필요)

**Phase 1 — P0~P9 구조 리모델링** (`docs/kronos_dashboard_v3_plan_2026-07-06.md`, 12커밋 `d17540c..5434783`):
토큰 통합, 4기둥 IA, F6 계약 하니스, Mission Control 실데이터화, D0-D9 게이트사다리(추가형), 실시간 RL 배선, MLflow+rliable 백본, 죽은코드 정리.

**Phase 2 — G0~G8 보고서 충실도 완성** (`docs/kronos_dashboard_v3_completion_plan_G0-G8_2026-07-07.md`, 9커밋 `e203313..79bb544`):
- G0: MC 카드 세로깨짐/잘림 버그 수정 (진짜 버그, 실캡처로 발견)
- G1: 일봉 D0-D9 중복 벽 **완전 삭제**(relocation-then-delete) — **유일한 완전 성공 사례**
- G2: 비용민감도/에쿼티드로다운/손실곡선 차트 (실데이터, fail-closed 정직)
- G3: 라이브 타일 4종 (LOSS/GPU/RAM/RL EQUITY)
- G4+G5: RL 다중런 오버레이 + 재생 스크러버
- G6: rliable IQM 테이블 (게이트된 백엔드 예외)
- G7: 팩토리 레지스트리 lineage 컬럼
- G8: 검증 (957 tests, architect APPROVE) + deslop

**공통 문제**: G0/G1 외에는 전부 "새 컴포넌트를 만들어 기존 구조 위에 추가"만 했고, 목업이 요구한 "기존 밀도를 줄이는" 작업(Disclosure 적용, 그리드 통합, 중복 삭제)은 하지 않음. 이게 지금 남은 작업의 본질.

## 6. 참고 — 왜 이런 일이 반복됐나 (자기 진단)

- Ralph PRD의 acceptance criteria를 "컴포넌트가 존재하고 테스트 통과"로 좁게 정의해서, "목업의 전체적 룩과 밀도"라는 더 큰 기준을 놓침.
- G1에서만 relocation-then-delete(진짜 축소)를 했고, 나머지는 안전한 additive 패턴을 반복 선택함 — 이건 과거 메모리(`remodel-full-overhaul-lesson.md`)가 이미 경고한 바로 그 실패 패턴("안전한 리팩터로 대체하지 말고 요청된 변혁을 전달하라")의 재발.
- 다음 세션은 **Disclosure 적용 + 그리드 통합**을 "추가 기능"이 아니라 **"기존 코드 삭제/압축" 작업으로 명확히 스코핑**해서 진행할 것.

## 7. 프로젝트 메모리 갱신 필요 여부

`remodel-full-overhaul-lesson.md`가 이미 존재하나, 이번 반복(2번째 반려)은 그 교훈이 부분적으로만 적용됐다는 새로운 데이터포인트. 다음 세션 완료 후, "additive 패턴을 반복 선택하는 경향"을 별도 feedback 메모리로 저장 검토.

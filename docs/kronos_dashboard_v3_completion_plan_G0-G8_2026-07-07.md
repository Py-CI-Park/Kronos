# Kronos v3 대시보드 — 보고서 충실 완성 계획 (G0–G8)

**STATUS: `pending approval`** · 브랜치 `dashboard-v3` · 2026-07-07
**합의:** Planner → Architect → Critic, Critic **APPROVE** (1회 반복, 소스 검증).
**목적:** 12커밋 v3(구조는 완성)가 보고서(Artifact 63f888aa)의 **구체 시각 산출물**을 덜 전달 + 라이브 버그 2개 → G0–G8로 격차 해소.
**경계:** 계획 아티팩트. 사용자 실행 승인(ralph/team) 전까지 소스 수정·커밋 없음.

## 원칙
1. 보고서 충실도 > 구조만. "테스트 green + 컴포넌트 착지"는 완료 아님 — 객관 체크리스트로 판정.
2. Δ7 불가침 — Gate-T 리터럴은 삭제 금지, **이전(relocation, assert 재지정 리뷰)**만.
3. 백엔드 동결 — 단, 문서화된 게이트 read-only 예외(P7b/P8/**G6**)만.
4. 정직한 표면 — 죽은 리터럴·조작된 green 금지.
5. 캡처 = **증거**(게이트 아님). 판정 = 객관 체크리스트 + F6/GateT/GateA(해당시)/GateD green + 빌드 0에러.

## 스토리
### G0 — MissionControl 버그 (순수 CSS)
`.gv`(:224-225) `white-space:nowrap` 제거 + `overflow-wrap:anywhere` + 2-line clamp; `.mc-line .nm/.sub`(:267-268) `word-break:keep-all`. 마커·스크립트 무변경.
- 체크리스트: 1280·820px에서 세로/1글자 제목 줄바꿈 없음; 주 판정에 중간-단어 … 잘림 없음.

### G1 — 일봉 요약-우선: relocation-then-delete
DailyGateLadder가 D0-D9 사실의 단일 소유자. (1) `dailyCockpitStages=['D0'..'D9']`+`data-daily-ohlcv-command-cockpit`+`data-daily-ohlcv-d0-d9-cockpit`를 DailyGateLadder.svelte로 이전. (2) `test_daily_ohlcv_dashboard_tab.py:97-99`를 relocation으로 재지정(동일 리터럴, 새 소유자 — 마커보존 리뷰, P9 선례). (3) DailyOhlcvTab의 중복 cockpit 섹션 삭제. F6를 새 소유자로 재생성.
- **리프코드 → Option A**(cockpit을 default-closed Disclosure로, assert 0수정): relocation이 >~10 assert 또는 Gate-T thrash 시에만.
- 체크리스트: 상시 표시 D0-D9 화면 **정확히 1개**(사다리), 2번째 그리드 없음; 다른 일봉 리터럴(000250·close-slot 19·verdict/lock·카드명·ResearchStatusShell) 제자리 무손상.

### G2 — 차트 3종 (§08)
신규 CostSensitivityChart(0/23/46bp, base_23bp 별표)·EquityDrawdownChart(연구 라벨)·LossCurveChart, EChartsRenderer+CSS변수. 기존 dailyOhlcvApi 차트 엔드포인트. 추가형.

### G3 — 라이브 타일 (§07)
LiveTraining/SystemHealth → 타일 4종(LOSS/GPU/RAM/RL EQUITY)+스파크라인, fail-closed. OpsStrip+G2 LossCurve 재사용.

### G4 — RL 다중 런 오버레이 (§07b)
RunSelector 추가형 `selectedNames[]`(게이트 파일 아님), LiveRlEventsCard N-시리즈, 기존 rlApi.rlEvents 런별 — 백엔드 0, network events-only.

### G5 — 롤아웃 재생 스크러버 (§07b)
LiveRlEventsCard 프레임 슬라이더(bounded tail), 기존 `truncated` 정직 렌더 — 백엔드 0.

### G6 — rliable IQM 테이블 (§07b, 게이트 예외)
신규 read-only 라우트 `/api/rl/rliable-stats`(파일 읽기, DB/파라미터/변경 없음, 파일 없으면 fail-closed) + rlApi.rliableStats() + RliableStatsCard(IQM+CI) + 신규 pytest `test_rl_rliable_stats_api.py` + **Gate A green**.

### G7 — 팩토리 레지스트리 UI (§08)
기존 `/api/rl/factory/*` 재사용(확인됨); 통합 list 엔드포인트 필요 시 게이트 read-only + Gate A + pytest(O1). 7 locks/RL LOCK 무손상, mode=ro.

### G8 — 폴리시
밀도·간격·잘림 전탭 정리; 전체 네비 캡처 스윕(desktop+narrow, light+dark).

## 시퀀싱
G0→G1 엄격; 이후 병렬 {G2→G3}{G4→G5}{G6,G7}; G8 최후.

## ADR
- **결정:** relocation-then-delete(G1) + 게이트 read-only G6 엔드포인트 + 캡처=증거·객관체크리스트. 모두 소스 검증됨.
- **동인:** Gate-T 소스-서브스트링 계약 / 보고서 산출물은 구체·시각적 / 백엔드 이미 풍부(events·factory·rliable).
- **대안:** G1-B 숨김앵커(죽은 리터럴, 기각), G1-C 재배치만(밀도감소 실패, 기각); Option A는 리프코드.
- **결과(수용):** (1) G1 시 F6 재생성(리터럴→DailyGateLadder 매핑)·의도적으로. (2) 이전 마커는 사다리 레일에 병합("D0-D9 1개" 체크가 오류 포착). (3) O1/O2 안전 기본값 보유, G7/G2 종료 전 해결.

## 다음: 실행 승인 (택1)
- **ralph** (순차 + 검증 루프) — 앞서 P0–P9에 사용
- **team** (병렬 조율)
승인 전 소스 수정·커밋 없음.

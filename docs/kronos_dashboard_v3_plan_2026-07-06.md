# Kronos Dashboard v3 — 전면 리모델링 실행 계획 (합의 승인본)

**STATUS: `pending approval`** · 브랜치 `dashboard-v3` · 2026-07-06
**합의:** Planner → Architect → Critic 3회 반복, Critic **APPROVE**.
**경계:** 이 문서는 계획 아티팩트입니다. **사용자 실행 승인 전까지** 소스 수정·커밋·PR·실행 스킬 착수 없음.

---

## 0. 요약

- **범위:** 프론트엔드 전면 재설계(`webui/v2_src`). 백엔드/API/DB/블루프린트/라우트명 **동결**.
- **전략:** **Option A — `v2_src` 제자리 진화**, 단계 게이트(P0–P9), 소스-서브스트링 계약 하니스(F6)로 가드.
- **"AI 퀀트" IA(코드 근거 교정):** `AI Quant` → ① **Kronos 예측**(독립 축) + ② **트레이딩 리서치**[일봉 D0–D9 파이프라인이 **D4=RL 스테이지**와 **종가매매 D4-하위 밴딧**을 포함; 별도 **인트라데이 커맨드센터**], 감싸는 **커맨드**(Mission Control)와 **라이브·시스템**.
- **실시간 RL·실험 플랫폼:** 기존 미배선 `rl_events` 스트림 배선 + **Aim(self-host)** 로깅 백본 + **rliable** 통계, 전부 self-host(데이터 반출 0).

---

## 1. 원칙 (Principles)

1. **보존 우선.** 어떤 재설계도 보호된 `data-*` 마커·판정 문자열·잠금·read-only DB를 훼손하지 않는다. 시각은 되돌릴 수 있으나 깨진 계약/유출된 실거래 어포던스는 아니다.
2. **사실당 단일 소스.** posture/lock/blocker는 한 번 계산(공유 모듈)해 어디서나 소비. 디자인은 한 토큰 시스템, 한 ECharts 테마. *(마커 리터럴은 예외 — §7 참조.)*
3. **연구 격리 · 반출 0.** 모든 신규 역량(Aim, 폰트, 통계)은 self-host/오프라인. 사이드카 부재 시 우아하게 저하(읽기=fail-open, 액션=fail-closed).
4. **요약 우선 · 정직한 상태.** 표면은 실데이터에서 판정을 파생하고 blocker/버그를 숨기지 않는다.
5. **제자리 · 단계 게이트 · no-big-bang.** 기존 라우트/블루프린트명 뒤에서 배포; 일괄 컷오버 금지.

## 2. 의사결정 동인 (Decision Drivers)

1. **계약 취약성 (지배적).** 릴리스 게이트는 **소스-서브스트링 계약** — pytest가 `webui/v2_src/src/**`를 `read_text()`해 리터럴을 assert. **Gate T = 525 asserts(470+55) / ~18 파일 / ~130+ `data-*`**, **별도 Gate A = 993 JSON-payload asserts**. 파일 이동/삭제가 지배적 위험.
2. **공유 플랫폼 결합.** 단일 Flask + 단일 Svelte + 공유 저장소가 이미 4개 연구 라인을 호스팅 → **재그룹화**이지 재플랫폼화 아님.
3. **반쯤 지어진 실시간 기반.** `rl_events` 스트림 + `/api/rl/runs/<run>/events` + `rlApi.rlEvents()`가 이미 존재·미연결 → **배선**으로 가치 해제(빌드 아님).

## 3. 선택지 & 기각 사유 (ADR alternatives)

- **Option A — 제자리 진화 (채택).** 계약 담지 파일을 제자리에서 편집(스냅샷-diff). 최소 회귀면·부분 배포·증분 승인.
- **Option B — 병렬 `v3_src` (탈출 해치).** 깨끗한 트리 포팅 후 컷오버. **기각(주력)** — 525 리터럴 재구현·이중 파이프라인이 릴리스 게이트 대비 회귀면 배증. **리프코드 트리거 하에만 발동**(§8).
- **Option C — 빅뱅 재작성. 기각** — 단계 게이트 부재, 전 기간 릴리스 스위트 red, 증분 승인 불가.

---

## 4. 공유 기반 (P0–P1에서 구축, 이후 전 단계가 소비)

- **F1 — 정규 토큰 시스템.** `--ink/--jade/--panel` + **accent와 분리된 시맨틱 상태 램프** `--status-ok/-warn/-danger/-muted`; light/dark `[data-theme]` 양방향.
- **F2 — ECharts 테마 모듈** (`charts/echartsTheme.ts`). CSS 변수 읽어 series/axis/grid/tooltip 단일화, `[data-theme]` 토글 시 재init.
- **F3 — 공유 posture 모듈** (`lib/posture.ts`). verdict(WATCH/NO-GO_RESEARCH_ONLY) + blocker 롤업(D0 price_basis/D1 universe/D5 walk-forward) + 7 false-lock. MissionControl/DailyOhlcvTab/DailyRlGuideTab/RLTradingTab + ResearchStatusShell 중복 대체.
- **F4 — 전역 컴포넌트 킷** (`lib/kit/`): Card/StatTile/GateLadder/StatusPill/PostureBanner/SectionHeader/Disclosure.
- **F5 — self-host 한글 웹폰트** (subset Pretendard/Noto Sans KR, `@font-face`, CDN 없음).
- **F6 — 소스-서브스트링 회귀 하니스** (§Δ2, 아래). Option A를 안전하게 만드는 핵심, **최우선 빌드 항목**.

---

## 5. 게이트 정의

- **Gate T (매 단계 필수):** `py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_tab.py tests/test_stom_rl_dashboard_tab.py -q` green.
- **Gate D:** `tests/test_v2_dist_marker.py tests/test_v2_route.py` green.
- **Gate A (조건부):** `tests/test_daily_ohlcv_dashboard_api.py -q` (993 asserts). `webui/app.py`/`webui/daily_ohlcv_dashboard.py` payload을 건드리는 단계(P2/P6/P7b)에서 필수.
- **캡처:** 가시 단계는 `http://127.0.0.1:8122/`에서 실제 브라우저 캡처(증거). green pytest가 합/불 기준선.
- **순서 불변식:** 매 단계 **F6 → Gate T/D (+payload 변경 시 Gate A) → build → capture**. build-green은 결코 마커 신호가 아님.

### Δ2 — F6 4-콤보 분류기 + 3 제외군 (합의 최종본)

F6는 두 Gate-T 테스트 파일을 파싱해 생성하는 **소스-서브스트링 가드** (`tests/_gen_v3_contract_snapshot.py` → `_v3_contract_snapshot.json`). 각 `assert`를 분류하고 리터럴을 `<var> = (SRC/…).read_text()` 바인딩으로 소스 파일에 귀속(**테스트 함수별** 바인딩).

**분류기 = binding × polarity 직교(4 콤보):**
- binding: `single-literal` | `loop-list`(`for m in [ … ]:` then `assert m …`)
- polarity: `in`→**MUST-BE-PRESENT** | `not in`→**MUST-BE-ABSENT**
1. single+present · 2. single+absent(정규화 `.lower()` 등 기록·재적용; 재출현 시 실패=안티슬롭 보존) · 3. loop+present(stom :95-108→api, :110-156→source) · 4. **loop+absent**(stom :75-84 라벨들→MUST-BE-ABSENT).
- **리터럴 추출:** double/single/mixed 외곽 따옴표 → 첫 비공백 문자로 균형 종료자 매칭.
- **주석 스트립은 균형 종료 따옴표 이후에만** (리터럴 내부 `#` 보호, stom :170).

**3 제외군(열거·체크인):** **E1** 구조/값 asserts(`==4727`,`set()==`,`len()<=2`,`is True`,`==14691020`)→Gate A · **E2** 비-소스바운드/빌드조건(`bundle_text` from `static/v2/dist`, stom :174-188의 5 asserts)→build+capture 소유(F6 아님) · **E3** 4콤보 미매칭→**loud hard-fail**.

**카운트 재조정(silent drop 불가):** `F6_parsed(present+absent+loop-expanded) == (470+55) − |E1| − |E2|(=5)`. generator가 각 수치+균형 방출, 불일치=hard fail. E1/E2 목록 체크인.

### P0.5 (P0 EXIT 게이트)
(1) 모든 assert가 4콤보 또는 E1/E2로 분류, E3 zero. (2) 재조정 균형 `== 525 − |E1| − 5`. (3) F6 baseline green(present 존재/absent 부재, 정규화 재적용). (4) Gate T+D green, **Gate A 재baseline**(브랜치 `M` 파일 `app.py`/`daily_ohlcv_dashboard.py`/`test_daily_ohlcv_dashboard_api.py` 커밋·안정화 후). (5) 원칙-2 중복 정책 서명.

---

## 6. 단계 계획 (P0–P9)

> 형식: 목적 · 파일 · 산출물 · 수용기준(테스트가능) · 검증 · 롤백/리스크 · 의존.

### P0 — 단일 디자인 시스템/토큰 통합
유령 토큰(`--text/--primary/--card/--shadow-card` + 하드코딩 hex) 제거 → `--ink/--jade/--panel`/상태램프. F1/F2/F4/F5 확립. 11개 유령-토큰 파일 표적 치환. **컨셉 Artifact**(토큰+컴포넌트 갤러리, 양 테마·차트) → 승인 → 포팅.
- 수용: `grep -rE "(--text|--primary|--card|--shadow-card)\b" src` = 0(정의 제외); StomDiagnostics/ResearchStatusShell 원시 hex = 0; 토글 시 전 차트 recolor; 상태램프 대비 ≥4.5:1.
- 의존: 없음(기반).

### P0.5 — 계약 인벤토리 reconciliation (P0 EXIT 게이트)
F6 생성·baseline(§Δ2/P0.5). **어떤 재설계 편집보다 먼저.**

### P1 — 계층형 셸 + IA
평면 12-탭 switch → 부모-자식 사이드바(커맨드/①Kronos 예측/②트레이딩 리서치/라이브·시스템) + 상단 Ops 스트립 + F3. **계약 담지 셸 파일 일괄 재작성 금지(원칙 5).**
- **P1-incremental(기본):** P1a posture.ts 추출(리터럴 유지) · P1b Sidebar 그룹화=기존 12키 위 표현층(`navigateToTab(id)` 보존, 키 개명 없음) · P1c OpsStrip 셸 · P1d IA 라벨. `App.svelte {#if}`와 라우트 주석(:21) 그대로.
- **P1-flag(narrow-B):** 증분 불가 시 플래그 뒤 새 셸 구축, 구 셸이 모든 Gate-T 리터럴 재현할 때까지 served/tested 유지.
- 수용: `test_v2_route.py`+`test_v2_dist_marker.py` green; 12키 도달; F3 단일소스(verdict/lock/blocker 리터럴 posture.ts에만). **P1 exit = F3 완전 채택**(인라인 lock/blocker/verdict 리터럴 0). Option-B 리프코드 결정점.
- 의존: P0. P2–P7 차단.

### P2 — Mission Control 실데이터 파생
하드코딩 판정 제거, F3 경유 blocker 롤업 단일화, 버그 정직 표면화.
- 수용: MissionControl에 F3 import 외 판정 리터럴 0; WATCH/NO-GO_RESEARCH_ONLY·D0/D1/D5 렌더 유지(F6 불변); 7 lock 비액션; **Gate A green**(payload 소비 시); blocking fixture에서 NO-GO 롤업.
- 의존: P0, P1(F3).

### P3 — Kronos 예측 그룹 통일
forecast+stom 테마·fetch 규약 통일, STOM 하드코딩 차트색 제거.
- 수용: STOM series 색이 CSS 변수 해석(리터럴 hex 0); live-training Kronos 폴링 유지; Gate T green + `test_stom_dashboard_helpers.py`.
- 의존: P0, P1.

### P4 — 일봉 D0–D9 요약 우선 재설계 (+ 고아 흡수)
게이트 사다리 D0→D9, **D4=RL 스테이지** + **종가매매 D4-하위 밴딧**, 고아 `DailyRlGuideTab`(~1400줄) 콘텐츠를 D4 하위로 흡수(파일은 P9까지 잔존).
- 수용: `test_daily_ohlcv_dashboard_tab.py`+`test_daily_ohlcv_dashboard_api.py` green; **종가매매 19 `data-*` 마커 보존**; `/daily-rl-guide`·`/daily-ohlcv/rl-guide` 해석; `000250`·`base_23bp` 렌더; 게이트 사다리·딥링크 캡처.
- 리스크: 최고 마커 밀도. **콘텐츠 먼저 이전, 파일은 P9에서 은퇴**, F6 게이트.
- 의존: P0, P1(F3). P9와 강결합(내부 식별자 이전 — 아래 R1).

### P5 — 인트라데이 커맨드센터 (RL evidence 일관화)
`rl` 탭 evidence 그리드 킷화, `ts_imb`=RULE 유지, opening/orderbook RL 유지. (라이브 스트리밍은 P7.)
- 수용: `test_stom_rl_dashboard_tab.py` + 관련 opening/factory 테스트 green; `ts_imb` 어디서나 RULE(정책 어포던스와 공치 금지); `base_23bp` 유지.
- 의존: P0, P1.

### P6 — 라이브 학습·컴퓨팅 (Ops 스트립 소스 + fail-closed)
Ops 스트립을 실소스(GPU/RAM/신선도)에 바인딩, 데이터 부재 시 fail-closed, 중복 진행률 통합.
- 수용: 소스 빈응답 시 stale/missing 명시(fixture); HeroStrip↔LiveTraining 진행바 중복 제거; **Gate A green**(payload 소비 시).
- 의존: P1(Ops 셸), P0.

### P7 — 실시간 RL 성과 (rl_events 배선, no-backend)
기존 `rlApi.rlEvents(run, limit)` → `load_rl_events(run_name, limit=_rl_table_limit())` 폴링. 라이브-tail 리워드/에쿼티 + 다중 런 오버레이(RunSelector 다중선택).
- 수용: 네트워크 캡처가 `/api/rl/runs/<run>/events`만; `git diff`로 `app.py`/`rl_dashboard_tables.py`/`webui/v2/__init__.py` **불변**; 오버레이 ≥2런; Gate T green.
- 의존: P0, P1, P5. **선행 검증 O1/O2.**

### P7b — 롤아웃 재생 (pre-gate 선택)
현재 tail/cursor 없음(`rl_dashboard_tables.py:186`). 착수 전 택1:
- **(a) no-backend(기본):** `limit`에서 캡, `truncated` 플래그 **정직 렌더**(경계 창임을 라벨).
- **(b) scoped backend:** `since`/`offset` cursor 추가 = 실제 백엔드 변경 → cursor 시맨틱 pytest 추가 + **Gate A green**.
- (b)는 (a)가 불충분하다고 판단될 때만.

### P8 — 실험 백본 (Aim self-host + rliable + registry UI)
Aim **사이드카**(로컬 포트, 격리 `.aim` 디렉토리, `.gitignore`) 공통 로깅 백본. rliable **오프라인** 통계 → `artifacts/*_rliable.json`(대시보드 read-only). `factory_registry.sqlite` 탐색 UI(`stom_rl/factory/run_registry.py` 재사용).
- **로깅 shim은 `stom_rl/rl_events.py`에 넣지 않음**(계약 담지·테스트 가드) → 학습/평가 파이프라인(`daily_rl_train`/`portfolio_sb3_train`/`sb3_eval`)에. `/events`·이벤트 스키마 byte-identical.
- 수용: factory 테스트 green; registry UI read-only(mode=ro/query_only); **사이드카 down에도 build/serve/test green**(우아한 저하); 외부 네트워크 호출 0(localhost만).
- 의존: P7(이벤트 모델). registry UI는 병렬 착수 가능.

### P9 — 정리 (이전+테스트 재작성, 삭제 아님)
**순서(각 단계 Gate-T green):** (1) `data-daily-rl-*` ~56개 + 가이드 리터럴 **및 내부 식별자**(R1: `activeGuideSection = $state('overview')`, `replayPaused = $state(true)`, `isGuideSection(...)`, `DEFAULT_COMPACT_OVERVIEW`)를 D4 목적지에 **verbatim 이전** — 재현 불가 시 Δ8 리프코드. (2) pytest asserts(라인 13/58/79/84-96/109) 목적지로 **재작성**(계약 *재배치*, 약화 아님 — Critic 검토). (3) **그제서야** `DailyRlGuideTab.svelte` 삭제/별칭. 사전 삭제 가드: 어떤 테스트도 해당 경로를 `read_text` 안 함 확인.
- 죽은 위젯 W1/W2/W7/W8 삭제(삭제 시점 import 0 재grep). 설정·docs 패스. `dashboard-v3 → master` PR.
- 의존: 전 단계, 특히 P4 패리티.

---

## 7. 원칙-2 재조정 (마커 중복)

~525 리터럴이 소스+테스트에 **의도적** 이중 존재(테스트가 `read_text` 서브스트링 assert). **"단일 소스"는 런타임 로직(F3 posture)으로 국한**, 마커 리터럴에는 적용 안 함(코드젠 인다이렉션은 `assert "literal" in read_text()` 모델을 깨뜨림). 마커 코드젠 없음.

## 8. Option B 리프코드 트리거

다음 중 하나 발생 시에만 `v3_src` 포크: (1) 어떤 단계의 Gate T가 **재배치가 아닌 계약 assert >15개** 편집 없이 green 불가; 또는 (2) P1a F3 완전 채택이 **≥2 셸 파일의 Gate-T 리터럴** 변경 강제; 또는 (3) 2개 연속 단계가 green 후 Gate T 회귀(thrash). 포크는 F6를 수용 목표로 상속(컷오버 전 모든 Gate-T 리터럴 재현).

## 9. 교차 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 마커 회귀(525, 게이트) | F6 소스-가드가 pytest read 미러; Gate T가 합/불선 |
| API payload 개명 | Gate A(993) — app.py/daily_ohlcv_dashboard.py 변경 시 필수 |
| 고아 가이드 삭제 | Δ5 이전→assert 재작성→삭제; 사전 삭제 `read_text` 가드 |
| 셸 재작성이 리터럴 훼손 | Δ6 증분/narrow-B 플래그; App.svelte/routes.ts 일괄 금지 |
| 롤아웃 재생 백엔드 크립 | Δ4 P7b pre-gate: (a) bounded-honest 기본 / (b) cursor+Gate A |
| Aim shim이 게이트 코드 접촉 | Δ9 학습/평가 파이프라인에; rl_events.py byte-identical |
| 마커 단일소스 | Δ7 중복 의도적; SoT는 런타임 로직 국한 |

## 10. 프리모템 (Pre-mortem)

1. **build-green / pytest-RED(지배적).** 재설계가 리터럴을 소유 파일 밖으로 이동. → F6가 **build보다 먼저** 매 단계; 순서 F6→Gate T/D→build→capture.
2. **P9 삭제 FileNotFoundError.** 게이트-read 파일 삭제. → Δ5 이전→재작성→삭제; 사전 삭제 가드.
3. **API-payload 키 개명이 993 assert 파손.** → payload 파일 변경 시 Gate A 필수.
4. **"새 페인트만 칠한 옛 대시보드."** → 가시 단계 컨셉-Artifact 승인이 의도된 IA/D4 하위레인 서명 강제; Critic이 IA 대 스펙 검사.
5. **rl_events 시맨틱 오가정.** cursor 없음 → P7b (a) bounded-honest 또는 (b) cursor+Gate A.

## 11. 시퀀싱 (병렬 vs 엄격)

엄격: P0 → P0.5 → P1. P1 = Option-B 결정점. 이후 병렬 레인: α(P2+P6) · β(P3) · γ(P4, 최중량 자체 executor) · δ(P5→P7 순차) · ε(P8 registry-UI 병렬, Aim은 P7 이후). 엄격 최후: P9(삭제+PR), P4 패리티 게이트.

## 12. 확장 테스트 플랜

- **Unit/contract:** 매 단계 릴리스 게이트 pytest; 표면별 tab/api 테스트; ripgrep 가드(유령토큰/하드코딩hex/dedup/죽은위젯).
- **Integration:** F6 마커 스냅샷-diff; 라우트 매트릭스(`/rl /daily-ohlcv /daily-rl-guide /daily-ohlcv/rl-guide`) P1/P4/P9 후.
- **E2E(실브라우저 8122):** 단계별 양 테마 캡처; P7 네트워크 캡처(events 엔드포인트만); P8 localhost-only + 사이드카-down 헬스.
- **Observability:** P6 fail-closed fixture; P7 라이브-tick; P2 verdict-flip fixture.

---

## 13. ADR (Architecture Decision Record)

- **결정:** Option A 제자리 진화, 단계 게이트, **소스-서브스트링** 계약 하니스(F6)가 두 실제 pytest 게이트를 미러.
- **동인:** (1) 게이트가 소스-서브스트링 계약(525 tab + 993 API) → 파일 이동/삭제가 지배 위험; (2) 공유 플랫폼(재그룹화≠재플랫폼); (3) `rl_events` cursor 부재 → 라이브-tail=배선, replay-with-cursor=신규 백엔드면.
- **대안:** B 병렬 `v3_src`(구체 리프코드 트리거 §8); C 빅뱅(기각).
- **채택 이유:** 계약-담지 파일 편집 최소화; 리터럴 재배치를 테스트-재작성 리뷰(P9)로 처리(위험한 삭제 회피).
- **결과(팀 수용):** (1) F6는 Gate-T 테스트/감시 소스 형태 변경 시 재생성·재baseline; E1/E2 제외목록은 체크인 유지 대상. (2) dist-바운드 5 asserts는 build+capture 소유(소스 회귀보다 늦게 포착). (3) `load_rl_events` limit 초과 풀 replay는 P7b로 연기, cursor(Gate-A 게이트) 선택 시만 배포, 아니면 정직 캡. (4) Option B는 정의된 리프코드 트리거 하 탈출 해치.
- **후속/열린 질문:** O1 P7b (a) vs (b); O2 `_rl_table_limit()` 경계가 유의미 tail 충분?; O3 rliable 수치 deps 격리 venv vs `py -3.11` 테스트 env; O4 Gate A 재baseline(브랜치 `M` 파일).

---

## 14. 다음 (실행 경로 — 사용자 승인 대기)

이 계획은 **`pending approval`** 입니다. 실행 승인 시 택1:
- **A. Team** (권장) — 병렬 조율 에이전트, 공유 작업목록. P0/P0.5부터.
- **B. Ralph** — 순차 실행 + 검증 루프.
- **C. 수동 단계별** — 제가 P0부터 직접, 각 가시 단계 컨셉 Artifact 먼저.
- **변경 요청 / 재검토.**

**승인 전까지 소스 수정·커밋·PR·실행 스킬 착수 없음.**

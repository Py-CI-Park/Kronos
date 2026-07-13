# Kronos 대시보드 v3 — 진행률 스코어카드 (섹션별·기능별 채점)

**작성일**: 2026-07-08 (최초 채점) · **갱신**: 2026-07-08 (G9a-e) → **2026-07-10 (G10-G14, 최종)** · **브랜치**: `dashboard-v3` · **기준 커밋**: `5ac5d4e`
**채점 기준**: Artifact 목업(`kronos_v3_remodel_report.html`, §00–§12)을 **정답지**로 삼아, 실제 라이브 대시보드(`http://127.0.0.1:8122/`)를 직접 캡처·DOM 조회로 대조. "테스트 green"이 아니라 **목업이 요구한 시각·구조 결과물이 실제로 존재하는가**를 기준으로 채점.
**채점 원칙**: 구조가 목업과 다르면 부분점수, 아예 없으면 0점, 목업과 동일 구조+실데이터면 만점. 근거 없는 추정 점수 없음 — 각 항목에 스크린샷/DOM 조회/grep 근거 명시.

> **2026-07-10 최종 갱신 — 종합 100/100 달성**: ralplan(Planner→Architect→Critic, 3라운드 합의 APPROVE) 계획 `.omc/plans/kronos-dashboard-v3-g10-to-100.md`을 ralph로 전체 실행. G11(전역 raw-enum 스윕, 독립 양방향 검증 PASS) · G12(accent `#0E9E85`·OpsStrip 순서 정합) · G13(RL 경계·형제탭 5개 전수 탐지, 전부 이미 충족 확인) · G14(3-페이즈 캡스톤: 독립 기계-감사 + 사용자 판단-클래스 4건 비준 + 폰트 self-host 적용). 최종 근거: `artifacts/g14_final_rescore.md`. **상세 핸드오프**: `docs/kronos_dashboard_v3_handoff_2026-07-10.md` (이 스코어카드보다 최신 상태를 담고 있으므로, 다음 작업 시 그 문서를 우선 참조할 것).
>
> **2026-07-08 갱신 요약**: "우선순위 개선 계획"의 5개 항목(G9a-e) 전부 실행·실캡처 재검증·개별 커밋 완료(`552e1f9`, `a063c2f`, `6a578c3`, `f61de25`, `d2736d6`, dist `7790143`). 통합 게이트 88 passed(제가 직접 재실행 확인) + `npm run build` 0 errors. 종합 **58 → 82/100**. 아래 원본 채점 테이블은 실행 전 스냅샷으로 보존하고, 각 섹션에 "갱신 결과" 블록을 추가함.
>
> **2026-07-08 추가 발견·수정**: G9 완료 후 사용자 요청으로 전체 12개 탭 재감사(콘솔 에러 점검 + Disclosure 실제 펼침 테스트 + 사이드바 중첩 클릭 테스트). 콘솔 에러 0건, 전 탭 정상 렌더 확인. **신규 결함 1건 발견**: Mission Control이 API 데이터 로드 후 원시 백엔드 enum(`D0_D9_EVIDENCE_VISIBLE_MODEL_BUILD_NO_GO`, `WATCH_RESEARCH_ONLY` 등)을 그대로 노출 — `git show 79bb544`로 G9 이전부터 있던 기존 버그임을 확인(회귀 아님). `humanize()` 매핑 함수로 즉시 수정, 실브라우저 재확인 후 커밋(`fac534d` 소스 + `8464c33` dist). 이 발견은 "테스트 88 passed + 화면 캡처 확인"만으로는 잡히지 않는 유형(런타임에 실제 데이터가 로드된 후에만 드러남)이라 별도로 기록.

---

## 종합 점수: **100 / 100** (2026-07-10 최종 · 58→82→100 전 과정은 아래 "갱신 결과" 참조)

**100점 판정 근거** (ralplan 계획이 정의한 "검증된 100" 조건 3가지, 전부 충족 — 상세는 `artifacts/g14_final_rescore.md`):
1. G14 판단-클래스 4건(RL경계·폰트·§08·표시정책) 전부 사용자 직접 비준 완료
2. Phase A 독립 기계-감사 전부 green (12탭 콘솔 0, F6 88 passed, G11/G12/G13 재확인) — 단 사전-존재 무관 백엔드 flaky 테스트 1건 발견·기록(범위 밖, §5 핸드오프 문서 참조)
3. §08(빈-데이터 fail-closed) 사용자가 명시적으로 완료로 수용

**82점 시점의 원본 채점 테이블은 아래 그대로 보존** (히스토리 참조용). 각 섹션의 G10-G14 최종 결과는 위 근거 문서를 참조.

| 축 | 점수 | 코멘트 |
|---|---|---|
| 백엔드 계약 보존 (Δ7, F6, 테스트) | **100/100** | 완벽 — 957 tests, 0 회귀 |
| 신규 기능 존재 여부 (G0–G8 컴포넌트) | **85/100** | 대부분 실제로 만들어졌고 동작함 |
| **목업이 요구한 "구조·밀도" 반영** | **30/100** | 핵심 실패 지점 — 아래 상세 |
| 시각 토큰 정확도 | **75/100** | 개념은 맞으나 수치 불일치 |

**핵심 진단(원본, 2026-07-08 최초)**: 컴포넌트는 만들었지만, 목업의 **진짜 요구사항("요약 우선으로 재설계", "밀도 감소")**은 일봉(G1) 한 곳에서만 지켜졌다. 나머지(Mission Control 그리드 통합, 라이브탭 압축, RL탭 Disclosure 적용)는 옛 구조 위에 새 카드만 추가하는 "additive" 패턴이 반복되어, 목업이 명시적으로 지적한 "과밀" 문제가 RL 탭에서는 오히려 카드 수가 늘어 **악화**됐다.

**갱신 후(2026-07-08, G9a-e 완료)**: "목업이 요구한 구조·밀도 반영" 축이 30/100 → **80/100**으로 상승 (RL탭 Disclosure 0→16, Mission Control 3섹션→1그리드, 라이브탭 중복삭제+2건 추가 접힘, 사이드바 중첩 0→1). 나머지 축(백엔드 100, 신규기능 85, 토큰정확도 90)은 유지 또는 소폭 상승. 남은 감점 요인: RL탭의 "항상-보임" 경계 판단(라이브 클러스터 vs 접힌 상세)이 목업처럼 명시적으로 스펙되지 않고 이번 실행에서 합리적으로 추정한 것이라 100%는 아님, CDN 폰트 미해결(§06), Ops 스트립 라벨 순서 미해결(§03).

---

## 섹션별 상세 채점

### §03 — 셸/사이드바: **65/100**

| 요구사항 | 상태 | 근거 |
|---|---|---|
| 4기둥 계층 사이드바 (커맨드/Kronos예측/트레이딩리서치/라이브·시스템) | ✅ 완료 | 실캡처 확인, `Sidebar.svelte` |
| Ops 스트립 (LIVE·신선도·GPU·RAM·폴링·자세) | 🟡 부분 | 존재하나 필드 순서/라벨이 목업과 다름 (`OPS·GPU·RAM·POLL·DATA`, "자세" 필드 없음 — RESEARCH_ONLY 뱃지가 헤더 우측에 별도 위치) |
| 7-lock postbar | ✅ 완료 | 정확히 일치 |
| **부모-자식 중첩 사이드바 항목** (목업: 일봉 D0-D9 아래 `D4·RL스테이지 / 종가매매밴딧 / RL가이드` 들여쓰기 자식) | ❌ **0%** | `grep -n "child" Sidebar.svelte` → **매치 0건**. 사이드바는 flat 리스트, 목업이 제안한 계층형(트리) 내비게이션이 전혀 구현 안 됨 |

**개선 방법**: `Sidebar.svelte`의 `groups` 배열에 `items[].children?: NavItem[]` 타입 추가, 트레이딩 리서치 그룹의 `daily-ohlcv` 아래 `daily-rl-guide`를 자식으로 들여쓰기 렌더(`.it.child` 패턴). Ops 스트립 필드 순서를 목업 순서(LIVE·신선도·GPU·RAM·폴링·자세)로 맞춤.

> **갱신 결과 (G9d, 커밋 `f61de25`) → 65 → 80/100**: `NavItem`에 `children` 필드 추가, `daily-rl-guide`를 `daily-ohlcv` 아래 중첩 자식으로 이동(중복 없이 1회만 렌더, `.nav-item--child` 신규 스타일). 실캡처로 들여쓰기 확인. `document.querySelectorAll('.nav-item--child').length` → **1**. 남은 감점: Ops 스트립 필드 순서는 미조정(우선순위 낮음, 별도 미착수).

---

### §04 — Mission Control: **55/100**

| 요구사항 | 상태 | 근거 |
|---|---|---|
| **6카드 단일 균일 그리드**(Kronos예측·일봉·종가매매·RL·시스템·**미해결blocker**가 전부 동급) | ❌ **구조 불일치** | 실제로는 3단 분리: "Kronos 예측"(1카드 독립 섹션) → "리서치 라인"(3카드) → "라이브·시스템"(1카드). blocker는 카드가 아니라 별도 우측 rail 패널 |
| 카드 실데이터 파생 (LIVE/FACT 태그) | ✅ 완료 | 스크린샷 확인, `overall_status`/`closeSlot` 등에서 파생 |
| 종가매매 0종목 버그 정직 노출 | ✅ 완료 | "⚠ contextual_bandit 0종목" 그대로 표기 |
| big-value 정보 배치 | 🟡 부분 | RL 카드 big-value가 목업 `D9 gate` 대신 `RESEARCH_ONLY`로, D9 gate는 footer로 이동 |

**개선 방법**: `MissionControl.svelte`의 `.mc-grid`를 목업처럼 **단일 6-카드 그리드**로 재구성 — 현재 분리된 Kronos예측/연구라인/라이브시스템 3섹션을 하나의 `lines` 배열로 합치고, blocker 롤업을 6번째 카드(`data-v="amber"`, 클릭 시 우측 rail로 스크롤 또는 확장)로 전환. `.mc-grid` 우측 rail(blocker/다음확인/시스템)은 유지하되 blocker "요약 카드"는 그리드에도 추가.

> **갱신 결과 (G9b, 커밋 `a063c2f`) → 55 → 90/100**: 3섹션(Kronos예측·연구라인·라이브시스템)을 단일 `lines` 배열로 병합, "연구 라인 6 cards · 6단 그리드"로 실캡처 확인. 6번째 카드로 "미해결 blocker"(3 blocker, FACT, footer "price_basis · universe · WF") 추가 — rail 패널과 `blockers` 소스 공유(`scrollToId`). LIVE/FACT 데이터 파생 로직 불변 확인. 다크모드 캡처로도 레이아웃 정상.

---

### §05 — 기능 재배치 (탭→v3 계층 매핑): **90/100**

| 요구사항 | 상태 |
|---|---|
| 12탭 전량 매핑 (유실 0) | ✅ 완료 — 모든 라우트 살아있음 |
| 죽은 위젯(W1/W2/W7/W8) 삭제 | ✅ 완료 (P9) |
| 유령 토큰 제거 | ✅ 완료 (P0) |
| daily-rl-guide 고아 탭 정식 편입 | 🟡 사이드바에 flat 항목으로만 추가, 목업이 원한 "일봉 D0-D9 하위 자식"으로는 미편입 (§03과 동일 문제) |

---

### §06 — 디자인 언어: **75/100**

| 요구사항 | 상태 | 근거 |
|---|---|---|
| 단일 토큰 시스템 (하드코딩 hex 0) | ✅ 완료 | 세션 전체 grep으로 확인, G0/G3/G5에서 hex 제거 완료 |
| accent = jade, hue 170 | 🟡 근접 | 실측 `oklch(56% .12 170)` — hue는 일치하나 목업 `#0E9E85`와 정확 대조 안 됨 (허용 가능한 차이지만 "그대로"는 아님) |
| radius 시스템 | 🟡 불일치 | 목업 `--r-lg: 14px` vs 실제 `18px` |
| 사이드바 너비 | 🟡 불일치 | 목업 `210px` vs 실제 `232px` |
| Pretendard + JetBrains Mono, tabular-nums | ✅ 완료 | `body font-family` 확인됨 |
| **"웹폰트 미링크"** (목업 §06 명시: "웹폰트 미링크(무음 폴백 방지)") | ❌ 반대로 구현 | `index.html`이 CDN(jsdelivr Pretendard + googleapis JetBrains)을 그대로 사용 — P0.5 세션에서 이미 발견했고 "self-host 불가로 CDN 유지"로 의도적 결정했으나, 이는 **목업이 명시한 원칙과 정면 배치** |
| card-grad/rim-light 프리미엄 depth | ✅ 완료 (R4 계승) | 다크모드 캡처로 확인 |

**개선 방법**: `core.css`의 `--r-lg`를 14px로, `--sidebar-w`를 210px로 조정(다른 곳 레이아웃 영향 검토 필요). CDN 폰트 self-host 여부는 **사용자 결정 필요** (목업 원칙 vs 실행 편의 트레이드오프).

> **갱신 결과 (G9e, 커밋 `d2736d6`) → 75 → 90/100**: `--r-lg` 18px→14px, `--sidebar-w` 232px→210px, 다크 오버라이드 없이 단일 정의라 양쪽 테마 자동 반영. 실측 JS: `getComputedStyle(root).getPropertyValue('--r-lg')` = "14px", `--sidebar-w` = "210px", 사이드바 실제 렌더 폭도 210px 일치. 다크모드 회귀 캡처로 카드 겹침·레이아웃 깨짐 없음 확인. 남은 감점: CDN 폰트는 미해결(의도적 트레이드오프, 사용자 결정 대기).

---

### §07 — 라이브·컴퓨팅·스테이터스: **50/100**

| 요구사항 | 상태 | 근거 |
|---|---|---|
| 4타일(LOSS/GPU/RAM/RL EQUITY) + 스파크라인 | ✅ 완료 | 실캡처 확인, `LiveMonitorTiles.svelte` |
| **"두 층 설계"의 취지 — 라이브 탭이 타일 중심으로 간결해짐** | ❌ **미달성** | 타일 바로 아래 옛 밀도 그대로: "현재손실/처리속도/러닝레이트"(LOSS 타일과 **데이터 중복**), TRAINING HEALTH 5카드, STAGE-AWARE PROGRESS, W3 풀차트 등. `grep -c Disclosure LiveTrainingTab.svelte` = **7건**(기존 P6 작업분, G3에서 추가 압축 없음) — 새 타일은 "위에 얹혔을 뿐" 기존 구조 압축 안 함 |
| stale/fail-closed 표기 | ✅ 완료 | RL EQUITY 타일이 정직하게 "확인 중" 표시 |

**개선 방법**: LiveTrainingTab 상단의 "현재손실/처리속도/러닝레이트" 미니카드 3개를 삭제(LOSS 타일과 완전 중복) 또는 Disclosure로 이동. TRAINING HEALTH·STAGE-AWARE PROGRESS 섹션을 기본-접힘 Disclosure로 전환해 목업이 원한 "타일 중심 간결함" 실현.

> **갱신 결과 (G9c, 커밋 `6a578c3`) → 50 → 85/100**: 중복 미니카드 행 삭제(두 Gate-T 테스트 파일 grep으로 미사용 리터럴 확인 후 안전 삭제), TRAINING HEALTH·STAGE-AWARE PROGRESS를 기본-접힘 Disclosure로 전환. 실캡처로 4타일 바로 아래 두 개의 ▶ 접힘 섹션만 보이고 옛 밀도 사라짐 확인. W3 손실곡선 등 유지 대상은 미변경.

---

### §07b — RL 실시간 성과: **60/100** (기능은 다 만들었지만 밀도 원칙 완전 실패)

| 요구사항 | 상태 | 근거 |
|---|---|---|
| 라이브 리워드/에쿼티 스트림 | ✅ 완료 | `LiveRlEventsCard.svelte`, 실캡처로 실데이터 확인 |
| 다중 런 오버레이 | ✅ 완료 | 2-run 비교 실캡처 확인 |
| 롤아웃 재생 스크러버 | ✅ 완료 | "frame 240/240" 실캡처 확인 |
| rliable IQM 테이블 | ✅ 완료 | 4개 알고리즘 실데이터 |
| **"요약 우선 IA" (§01 핵심 원칙)** | ❌ **0% 적용** | `grep -c Disclosure RLTradingTab.svelte` = **0건**. 15개 이상 카드(RULE MAINLINE RISK, SELECTED RUN, OPENING 30M RULE FILTER, PARTICIPANT PROXY, ORDERBOOK READINESS, FACTORY QUEUE, FACTORY LINEAGE, CALIBRATION, SESSION REPLAY, 성과리더보드×2, RUN SELECTOR, OVERLAY COMPARE, REALTIME EVENTS, RLIABLE STATS, 거래별 net-return, RULE filter controls...)가 **전부 항상-펼침 상태**로 나열됨. G4–G7이 여기에 카드 3개(오버레이·스크러버 UI·rliable·lineage컬럼)를 **더 추가**해 밀도가 오히려 **악화** |

**개선 방법(최우선)**: RL탭을 "요약 우선"으로 재구성 — ① 상단에 핵심 요약(런 상태·최신 verdict·라이브 카드)만 always-visible로 유지 ② RULE MAINLINE RISK/PARTICIPANT PROXY/ORDERBOOK READINESS/CALIBRATION/SESSION REPLAY/거래별 net-return/RULE filter controls 등 세부 증거 카드 전체를 `Disclosure`로 감싸 기본-접힘 처리(§03·§06이 이미 정의한 `Disclosure` 컴포넌트 재사용, `DailyOhlcvTab`의 15건 패턴과 동일하게). 이게 **목업이 처음부터 요구한 것**이며 가장 시급.

> **갱신 결과 (G9a, 커밋 `552e1f9`) → 60 → 90/100**: 16개 상세 증거 카드를 각각 `Disclosure`로 래핑(오더북/팩토리큐/팩토리리니지/캘리브레이션/엣지원장/사이징리스크/모델빌드/포워드원장/세션리플레이/rliable/RULE메인라인/run상세/오프닝워크플로/참여자프록시/증거차트/원시테이블), 실캡처로 전부 기본-접힘(▶) 확인. posture strip·RunSelector·라이브 리얼타임 클러스터(오버레이+스크러버 포함)는 always-visible 유지, 오히려 목록 상단으로 승격. `DailyOhlcvTab`의 15건과 대등한 수준(16건) 달성. 남은 감점: "always-visible 경계"가 목업에 명시적으로 스펙되지 않아 이번 실행에서 합리적으로 추정한 것이므로 100%는 아님.

---

### §08 — 시각화 (게이트사다리·차트): **75/100**

| 요구사항 | 상태 |
|---|---|
| D0-D9 게이트 사다리가 벽을 **대체**(숨김 아닌 삭제) | ✅ 완료 — G1의 유일한 완전 성공 사례, relocation-then-delete |
| 비용민감도(0/23/46bp) 차트 | ✅ 컴포넌트 존재하나 실데이터 fail-closed 빈 상태(연구 데이터 자체가 0건이라 정직한 표시 — 컴포넌트 자체는 맞게 만들어짐) |
| 에쿼티+드로다운 차트 | 🟡 동일 — fail-closed 빈 상태 |
| 시맨틱색≠accent, tabular-nums | ✅ 완료 |

---

## 우선순위 개선 계획 — 실행 결과 (2026-07-08)

| 순위 | 작업 | 상태 | 실제 점수 변화 | 커밋 |
|---|---|---|---|---|
| **1** | **RL탭 Disclosure 적용** (§07b) — 15개 카드 중 핵심 요약 외 전부 접기 | ✅ **완료** | §07b 60→90 | `552e1f9` |
| **2** | **Mission Control 6카드 단일 그리드로 통합** (§04) — blocker를 카드화, 3섹션→1그리드 | ✅ **완료** | §04 55→90 | `a063c2f` |
| **3** | **라이브탭 중복 카드 제거 + Disclosure** (§07) | ✅ **완료** | §07 50→85 | `6a578c3` |
| **4** | **사이드바 부모-자식 중첩** (§03) | ✅ **완료** | §03 65→80 | `f61de25` |
| **5** | 토큰 수치 정합(radius/sidebar폭) | ✅ **완료** | §06 75→90 | `d2736d6` |
| **6** | CDN 폰트 self-host 여부 결정 | ⬜ 미착수 | — | 사용자 판단 필요 |
| — | dist 리빌드 (1~5 통합 반영) | ✅ 완료 | — | `7790143` |

**검증 방법**: Workflow로 5개 항목 병렬 구현(각 항목 소스 편집 + 스코프드 pytest 자가검증) → 통합 에이전트가 전체 게이트(88 tests) + `npm run build`(0 errors) 실행 → **제가 직접** 크롬 실캡처(라이트+다크)로 6개 화면 재검증 + `py -3.11 -m pytest` 전체 게이트 독립 재실행(88 passed 재확인) → 5개 개별 커밋 + dist 커밋.

**실제 종합 점수 (1~5 완료 후)**: **82/100** (예상 80~85 범위 내).

---

## 채점 방법론 (재현 가능)

**최초 채점 시점 (커밋 `79bb544`) 근거:**
```bash
grep -c "Disclosure" webui/v2_src/src/tabs/RLTradingTab.svelte      # -> 0
grep -c "Disclosure" webui/v2_src/src/tabs/LiveTrainingTab.svelte   # -> 7
grep -c "Disclosure" webui/v2_src/src/tabs/DailyOhlcvTab.svelte     # -> 15
grep -n "child" webui/v2_src/src/layout/Sidebar.svelte              # -> 매치 없음
```

**갱신 채점 시점 (커밋 `7790143`, G9a-e 완료 후) 근거:**
```bash
grep -c "Disclosure" webui/v2_src/src/tabs/RLTradingTab.svelte      # -> 17 (import 1줄 + 태그 16개)
grep -c "Disclosure" webui/v2_src/src/tabs/LiveTrainingTab.svelte   # -> 5개 섹션(TRAINING HEALTH·STAGE-AWARE PROGRESS 신규 포함)
```
브라우저 DOM 조회(javascript_tool): `getComputedStyle(root).getPropertyValue('--r-lg')` = "14px", `--sidebar-w` = "210px", `document.querySelectorAll('.nav-item--child').length` = 1.
`py -3.11 -m pytest tests/test_v3_contract_snapshot.py tests/test_daily_ohlcv_dashboard_tab.py tests/test_daily_ohlcv_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_v2_dist_marker.py tests/test_v2_route.py tests/test_rl_rliable_stats_api.py tests/test_experiment_backbone.py -q` → 88 passed (제가 직접 재실행, 워크플로 자기보고와 별개로 확인).

실캡처: Mission Control(light+dark), Trading Command Center(전체+스크롤), 실시간 학습 — 전부 `http://127.0.0.1:8122/`에서 Chrome 확장으로 직접 캡처 후 목업 HTML과 섹션별 대조.

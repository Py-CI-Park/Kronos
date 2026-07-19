# Kronos RL 재개발 · 가시성 핸드오프 (2026-07-10)

> **브랜치**: `dashboard-v3` · **최신 커밋**: `a5d7459` · **작업 트리**: 완전 클린(self-contained)
> **이 문서 하나로 재개 가능**하도록 작성. 관련: [`kronos_full_inspection_and_rl_rebuild_plan_2026-07-10.md`](kronos_full_inspection_and_rl_rebuild_plan_2026-07-10.md)(전수검사) · [`kronos_rl_rebuild_implementation_plan_2026-07-10.md`](kronos_rl_rebuild_implementation_plan_2026-07-10.md)(WP 스펙) · [`kronos_research_runbook_2026-07-10.md`](kronos_research_runbook_2026-07-10.md)(컴퓨팅 런북) · [`stom_kronos_attribution_prereg_2026-07-10.md`](stom_kronos_attribution_prereg_2026-07-10.md)(R5a 사전등록)

---

## 0. TL;DR — 지금 상태

- **대시보드 v3 UI**: 구조·디자인은 이전 G-시리즈에서 완성(82/100). 이번 세션은 **RL 가시성 4개 화면(S1~S4)** 추가 + **실제 크롬 캡처로 시각 확인**(다크+라이트).
- **연구 백엔드**: 전수검사로 확정된 버그·결함을 코드로 수정·커밋 — **종가매매 0종목 버그(R1), 라이브 관측성 배선(R2), D4 equity=NAV+비개선판정(R3a), Kronos 평가 결정론·토크나이저 도구(R5b/c/d), Kronos 귀속 러너(R5a)**. 통합 **124 테스트 그린**.
- **남은 것 = 전부 "연구 실행"(컴퓨팅-게이트)**: 실제로 학습/평가를 돌려 신호·학습이 나오는지 측정. R5a(신호 판별)가 값싸고 최우선.
- **정직한 경계**: 지금 RL은 **학습이 되고 있지 않다**(감사 확인). 버그 수정 + 가시화만 했고, "잘 학습되는 RL"을 만든 게 아니다. **"우상향 그래프"는 연구 결과이지 약속 아님** — 정직한 답이 "신호 없음"일 수도 있다(false-lock 7종 불변).

---

## 1. 이번 세션 완료 (12 커밋, `d745b1c`→`a5d7459`)

| 커밋 | WP | 내용 | 검증 |
|---|---|---|---|
| `d745b1c` | 문서 | 전수검사 보고서 (문제 F1–F24) | 20 에이전트·15 적대검증 |
| `237708a` | 문서 | 상세 구현 계획서 (WP 스펙) | — |
| `f6541fc` | **R1** | 종가매매 **0종목 버그 수정** — train-only z-score 프로즌 정규화 + no-trade 센티널 + 강제 top-10 진단 | 11 |
| `307c421` | 문서 | 컴퓨팅-게이트 실행 런북 | — |
| `f448181` | **S2** | RL env→action→reward 루프 **상시화** + 실데이터 주입 | 13 v2 |
| `9f13fdd` | **R5b/c/d** | Kronos 평가 결정론(시드+5샘플) · 토크나이저 재구성 스크립트 · metrics.jsonl · checkpoint 게이트 | 11 |
| `04af4f0` | **R2** | close-slot 라이브 이벤트 배선 + 라운드보상 영속화 + 런 발견성 (RULE≠RL) | 16/83 |
| `27cfb96` | **R3a** | D4 **equity=순수 NAV** + 비개선 자가판정(`TRAINING_CURVE_NON_IMPROVING`) + daily-rl 이벤트 | 23/147 |
| `577d8e0` | **S1·S3·S4** | RL 가시성 3화면 (라이브 모니터·에피소드 티커·액션 피드 / 종가매매 에이전트 / MC 라이브+정리) + 적대검증 HIGH 버그 수정 | 19 v2 |
| `45343b0` | 정리 | 이전 v3 문서 추적 + `artifacts/` gitignore | — |
| `07a4ed0` | 정리 | **미추적이던 close-slot 백엔드 소스**(dataset/env/gate) + 테스트 + 런처 추적 | 18 |
| `a5d7459` | **R5a** | Kronos zero-shot 귀속 러너 + 사전등록 | 7 |

---

## 2. 불변 계약 (재개 시 반드시 준수)

구현 계획서 §0(C1–C10)이 정본. 요약:

- **C1 가드레일 문자열·마커 불변**: 모든 `data-*` 마커, `WATCH/NO-GO_RESEARCH_ONLY`, D0/D1/D5 blocker, false-lock 7종(실거래·브로커·주문·계좌·페이퍼·모델빌드·수익주장). 삭제 금지, **이동만 허용**(이동 시 관련 assert 재지정).
- **C5 동결 파일 (수정 금지)**: `webui/app.py`, `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py`.
- **C6 스키마 동결**: `stom_rl/rl_events.py` 수정 금지(이벤트 스키마 `stom_rl_live_event.v1`, `tests/test_stom_rl_live_events.py`가 가드). 계측은 **트레이너 쪽에서만**.
- **C7 신규 `/api/*` 금지** (SSE는 명시적 Gate-A 승인 전 금지).
- **C3 RULE≠RL**: `ts_imb`는 RULE. 라이브 이벤트/시리즈에서 RULE 베이스라인을 RL로 표기 금지(`algorithm='rule_baseline'` 태깅 또는 미방출).
- **C4 비용**: 주 기준 `base_23bp`(0/46bp는 컨트롤). Kronos 레거시 25bp와 혼동 금지.
- **C8 v2 SPA**: `webui/v2_src/src/`만 수정 → `cd webui/v2_src && npm run build` → SSR marker `kronos-v2-shell` 보존 → light/dark 검증.
- **C9 학습 변경 사전등록**: 신규/변경 학습 실행 전 dated prereg 문서.
- **C10 스테이징**: 학습은 스모크(축소)→풀. 스모크를 풀로 표기 금지.
- **캡처 규칙**(과거 2회 반려 교훈): **대시보드 변경은 실제 크롬 캡처 전 "완료" 선언 금지.**

---

## 3. 검증 게이트 (매 단계 그린 유지)

```bash
# 통합 백엔드 + 프론트 (이번 세션 기준 100+ passed)
py -3.11 -m pytest \
  tests/test_stom_rl_daily_close_slot_train.py tests/test_stom_rl_daily_close_slot_gate.py \
  tests/test_stom_rl_daily_close_slot_env.py tests/test_stom_rl_daily_close_slot_dataset.py \
  tests/test_stom_rl_close_slot_normalization.py tests/test_stom_rl_close_slot_wp_r2.py \
  tests/test_stom_rl_daily_portfolio_env.py tests/test_stom_rl_daily_rl_gate.py \
  tests/test_stom_rl_live_events.py tests/test_stom_rl_dashboard_api.py \
  tests/test_daily_ohlcv_dashboard_api.py tests/test_v2_dist_marker.py tests/test_v2_route.py \
  tests/test_stom_rl_dashboard_tab.py tests/test_daily_ohlcv_dashboard_tab.py \
  tests/test_training_progress.py tests/test_stom_kronos_attribution.py -q

# 프론트 빌드 (dist 갱신)
cd webui/v2_src && npm run build   # 0 ERRORS 필수

# 대시보드 실행 + 크롬 캡처
start_dashboard.bat    # 또는: KRONOS_WEBUI_PORT=8122 py -3.11 webui/run.py
# 127.0.0.1:8122/?tab=rl (S1) · ?tab=daily-ohlcv (S3) · ?tab=daily-rl-guide (S2) · / (S4)
```

---

## 4. 아키텍처 현황 (어디에 뭐가 있나)

- **대시보드 12탭** (`webui/v2_src/src/tabs/`): mission-control, live-training, forecast, stom, daily-ohlcv(+`dailyOhlcv/CloseSlotAgentScreen`·`DailyCloseSlotCard`), daily-rl-guide, rl(+`rlTrading/RlLiveScreen`), artifacts, history, system-health, settings, docs.
- **라이브 이벤트 배관**: `stom_rl/rl_events.py`(RlLiveEventWriter, 동결) → `/api/rl/runs/<run>/events` → `RlLiveScreen.svelte`(4s 폴링). daily 트레이너 2종은 이제 이벤트 방출(R2/R3a).
- **종가매매(close-slot)**: `stom_rl/daily_close_slot_{dataset,env,gate,train}.py` — D4-tier 밴딧. R1이 정규화 수정.
- **D4 일봉 RL**: `stom_rl/daily_portfolio_env.py`(equity=NAV, R3a) + `stom_rl/daily_rl_train.py`(표 Q + val NAV + 비개선판정 + 이벤트).
- **Kronos 예측**: `finetune/evaluate_stom_1s_checkpoint.py`(R5b 결정론) · `finetune/evaluate_tokenizer_reconstruction.py`(R5c 신규) · `finetune/run_zeroshot_attribution_eval.py`(R5a 신규).
- **레지스트리**: `webui/rl_runs/factory_registry.sqlite` + `stom_rl/factory/run_registry.py`.

---

## 5. 남은 작업 (전부 컴퓨팅-게이트 = 연구 실행)

우선순위 순. 전부 GPU/시간이 필요해 코드로는 준비됐어도 "실행"이 별도.

| 순서 | WP | 강화학습? | 상태 | 실행 |
|---|---|---|---|---|
| **1** | **R5a** Kronos zero-shot 귀속 | ❌ 예측모델 | **코드 완료** | `py -3.11 finetune/run_zeroshot_attribution_eval.py --run --seed 42 --sample-count 5 --device cuda:0` |
| 2 | **R3b** SB3 PPO 실데이터 | ✅ 진짜 RL | 어댑터 미작성 | 신규 `stom_rl/daily_portfolio_sb3_dataset.py` → `portfolio_sb3_train` 5k 스모크 → ≥200k |
| 3 | **R6** 시드×에피소드 스윕 | ✅ RL | checkpoint 게이트만 완료 | `daily_scenario_batch` 확장 + factory registry 등록 |
| 4 | **R4** 밴딧 정직화 | (라벨) | 분기규칙 확정 | R1/R2 결과 검토 → ε-greedy(train 한정) 또는 개명 |
| 5 | **R7** Aim + rliable | (통계) | 런북만 | self-host 설치 + 스윕 통계 리포트 |
| 6 | **F14** 300s 재튜닝 | ❌ 예측모델 | 게이트 | R5a가 "TUNING_HELPED_COST"일 때만 |

**R5a 판정 규칙**(사전등록 고정): NO_SIGNAL(랜덤 근처·재튜닝 동결) / TUNING_HARMFUL(데이터·토크나이저 수정) / TUNING_HELPED_COST(→F14) / INCONCLUSIVE(재실행).

---

## 6. 재개 방법 (다음 세션 step-by-step)

1. **상태 확인**: `git -C <repo> log --oneline -3` → `a5d7459` 확인. §3 검증 게이트 실행 → 그린 확인.
2. **방향 택1**:
   - **(A) "대시보드가 실제로 살아 움직이는 것"을 보고 싶다** → 작은 RL 학습을 로컬에서 돌려 `rl_live_events.jsonl` 생성(daily_rl 표 Q는 CPU 수 초). → `?tab=rl`의 S1 라이브 모니터·에피소드 티커가 실데이터로 채워짐. (데이터셋 준비 필요 시 D3 예측 산출물 경로 확인.)
   - **(B) "신호가 있는지" 판별** → R5a 실행(§5 순서 1). 결과로 R3b/F14 투자 여부 결정.
   - **(C) 코드 더 준비** → R3b 어댑터(`stom_rl/daily_portfolio_sb3_dataset.py`) 또는 R6 스윕 작성. 구현 계획서 §5(WP-R3b)·§8(WP-R6) 참조.
3. **학습 실행 시**: dated prereg 작성(C9) → 스모크 → 아티팩트/이벤트 스키마 검증 → 풀.
4. **대시보드 변경 시**: 빌드 → 테스트 → **실제 크롬 캡처**(C 캡처 규칙) 전 완료 선언 금지.
5. **커밋**: WP 단위 conventional commits, 검증 증거(테스트 출력·캡처·아티팩트 경로)를 메시지에 명시.

---

## 7. 정직한 경계 (기대 관리)

- 이번 작업은 **버그 수정 + 관측성**이다. "잘 학습되는 RL"이나 "우상향 수익"을 만든 게 아니다.
- 현재까지 증거: D4 보상 하락 · 종가매매 0종목(수정 전) · D5 walk-forward NO-GO · Kronos 방향정확도 랜덤 이하. **신호가 약하거나 없을 가능성을 배제하지 못함.**
- 대시보드는 **학습이 실제로 돌 때만** 라이브로 움직인다(지금은 대부분 fail-closed 빈 상태 → "안 변한 것처럼" 보임).
- 산출물의 정의: **"우상향이면 우상향이, 아니면 아닌 것이 정직하게 보이는, 버그 없는 시스템"** — 상승 자체는 연구 결과.

---

## 8. 환경 메모

- Python `py -3.11`. 프론트 `webui/v2_src` (`npm run build` = svelte-check + vite). 서버 `webui/run.py` on 127.0.0.1:8122 (`start_dashboard.bat`).
- torch 테스트는 Windows 기본 skip(`KRONOS_RUN_TORCH_TESTS`). close-slot/daily-rl/dashboard 테스트는 torch 불필요.
- `artifacts/`는 gitignore(생성물). 필요 시 `git add -f`.
- 크롬 캡처: MCP 도구 `ToolSearch("select:mcp__claude-in-chrome__tabs_context_mcp,...navigate,...computer,...javascript_tool")`.
- 커밋 시 GitKraken이 `.git/index.lock`을 잡으면 `rm -f .git/index.lock` 후 재시도(이 세션 반복 발생).

---

*다음 세션은 §6으로 시작. 첫 결정: 대시보드 라이브 시연(A) / R5a 신호 판별(B) / 코드 준비(C).*

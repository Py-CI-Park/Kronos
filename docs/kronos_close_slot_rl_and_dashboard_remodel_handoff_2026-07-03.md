# Kronos Close-Slot RL 개선 + 대시보드 리모델링 핸드오프 (2026-07-03)

> 이 문서는 **다른 Claude/GJC 세션이 대화 기억 없이 그대로 실행**할 수 있도록 작성된 자립형(self-contained) 핸드오프다.
> 모든 경로는 repo root (`D:/Chanil_Park/Project/Programming/Kronos`) 기준 상대경로다.

---

## 0. 이 핸드오프의 목적

세 가지 작업을 순서대로 실행한다.

1. **RL 라인 실제 작동시키기** — 지금 `contextual_bandit` 정책이 종목을 0개 선택하는 **피처 정규화 버그**를 고치고, 보상/액션/피처를 단계적으로 개선.
2. **대시보드 리모델링** — close-slot 연구 카드의 가독성(글자 과밀) 개선. Claude design 원칙 적용.
3. **프론트엔드 이중화 정리** — Next.js(Trading Command Center)와 Svelte(Kronos 대시보드) 두 앱이 공존하며 일봉 탭이 중복됨. 통합 방향 결정 및 정리.

각 작업은 반드시 **사전등록 문서 → bounded 실험/구현 → 통제군 대비 검증 → 결과 문서**를 지킨다. 큰 파괴적 변경(프론트엔드 통합, 기존 앱 삭제)은 **사용자 승인 후** 진행한다.

---

## 1. 절대 지켜야 할 가드레일 (변경 금지)

이 프로젝트의 가드레일은 "제한"이 아니라 **현재 데이터의 사실 상태**다. 라벨을 거짓으로 뒤집는 것은 화면에 거짓을 적는 것이므로 금지한다.

- `D0_PRICE_BASIS_NOT_VERIFIED`, `D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED` blocker는 **계속 노출**. 임의로 해결/삭제 금지.
- verdict는 gate가 실제로 증명하기 전까지 `WATCH_RESEARCH_ONLY` 또는 `NO-GO_RESEARCH_ONLY` 유지.
- `promotion_allowed / model_build_allowed / paper_forward_allowed / live_broker_order_allowed / profitability_claim_allowed / go_summary_allowed` = **항상 false**. true로 바꾸는 코드/문서 금지.
- `ts_imb`는 RULE baseline. **RL이라고 부르지 않는다.**
- DB(`_database/Stock_Database_ohlcv_1day.db`)는 **읽기 전용** (`mode=ro`, `PRAGMA query_only=ON`, helper `stom_rl.daily_ohlcv_db.connect_readonly`). 절대 mutate 금지.
- 선행 0 종목코드 문자열 보존 (예: `000250`을 int로 변환 금지).
- Primary cost = component `base_23bp`. `zero_control_0bp`/`stress_46bp`는 통제/민감도.
- bounded 실험(`max_symbols`, `max_rows_per_symbol`)을 full-universe/decision-grade 증거로 포장 금지. receipt/manifest에 범위를 투명하게 명시.
- 실거래/브로커/주문/계좌/paper-forward/수익 보장/deployable-alpha/GO 주장 금지.
- 기존 verdict/result 문서를 **덮어쓰지 말 것**. 새 날짜 문서를 만든다.
- repo 안전: 관련 없는 변경 revert/stash/삭제 금지. 특히 out-of-repo 파일 건드리지 말 것.

### "가드레일 도배 제거"의 올바른 의미
UI 가독성 문제의 큰 원인은 위 문구를 카드마다 **반복 나열**하기 때문이다. 리모델링에서는 **사실은 1곳에 깔끔한 상태칩/배지로 한 번만** 보여주고, 반복 텍스트를 제거한다. 이것은 허용되며 권장된다. (사실 자체를 지우는 것은 금지, 반복 도배를 지우는 것은 필수)

---

## 2. 현재 상태 스냅샷 (2026-07-03 기준)

### 2-1. 완료된 것
- Ultragoal(세션 `019ebee4-...`) G001~G004 **complete**. close-slot 종가매매 연구 문서 ledger + 읽기 전용 evidence 대시보드 출력 완료.
- 생성된 run IDs:
  - dataset: `daily_close_slot_research_dataset_2026_07_03`
  - train/policy: `daily_close_slot_research_policy_2026_07_03`
  - gate: `daily_close_slot_research_gate_2026_07_03`
- 최종 verdict: `WATCH_RESEARCH_ONLY` (bounded: `max_symbols=120`, `max_rows_per_symbol=260`).
- 문서: `docs/stom_daily_close_next_day_rl_prereg_2026-07-03.md`, `docs/stom_daily_close_next_day_rl_result_2026-07-03.md`.

### 2-2. 방금 고친 버그 (경로 앵커링)
- 증상: 배치(`start_kronos_dashboard_quiet.bat`, cwd=`webui/`)로 실행하면 close-slot 카드가 `NOT_STARTED`.
- 원인: `stom_rl/daily_close_slot_gate.py`, `stom_rl/daily_close_slot_train.py`가 산출물 root를 상대경로(`Path("webui")/...`)로 잡아 cwd=webui/에서 `webui/webui/rl_runs/...`로 깨짐.
- 수정: 두 파일을 나머지 코드베이스와 동일하게 `REPO_ROOT / "webui" / "rl_runs" / ...`로 통일. `REPO_ROOT`는 `stom_rl.daily_ohlcv_db`에서 import (이미 `daily_close_slot_dataset.py`가 사용 중).
- 검증: cwd=webui/에서도 `load_close_slot_latest()` → `WATCH_RESEARCH_ONLY`. close-slot 회귀 `77 passed`.

### 2-3. 미커밋 상태 (중요)
아래 close-slot 기능 전체가 **아직 커밋되지 않았다** (working tree에만 존재). 이 핸드오프는 **같은 working tree에서 실행**된다고 가정한다. 깨끗한 clone을 가정하지 말 것.

- 신규(untracked): `stom_rl/daily_close_slot_{dataset,env,train,gate}.py`, `tests/test_stom_rl_daily_close_slot_{dataset,env,train,gate}.py`, `webui/v2_src/src/tabs/dailyOhlcv/DailyCloseSlotCard.svelte`, `docs/stom_daily_close_next_day_rl_{prereg,result}_2026-07-03.md`, `artifacts/close_price_research_g00*`.
- 수정(modified): `webui/app.py`, `webui/daily_ohlcv_dashboard.py`, `webui/v2_src/src/lib/dailyOhlcvApi.ts`, `webui/v2_src/src/lib/routes.ts`, `webui/v2_src/src/layout/Sidebar.svelte`, `webui/v2_src/src/tabs/DailyOhlcvTab.svelte`, `tests/test_daily_ohlcv_dashboard_{api,tab}.py`, `webui/static/v2/dist/*`.
- 커밋 정책: 소스/문서와 생성물(`artifacts/`, `webui/rl_runs/`, dist)을 분리. `git add -A` 금지. 필요한 파일만 명시적으로 add.

---

## 3. 아키텍처 사실 (실행 전 반드시 이해)

**대시보드는 서로 다른 두 프론트엔드가 같은 Flask에서 서빙된다.**

| 경로 | 앱 | 기술 | 소스 | 빌드 산출물 | 백엔드 |
|---|---|---|---|---|---|
| `/`, `/?tab=daily-ohlcv` | Kronos 대시보드 | Svelte + Vite | `webui/v2_src/` | `webui/static/v2/dist/` | `webui/app.py` + `webui/daily_ohlcv_dashboard.py` |
| `/rl` | Trading Command Center | Next.js | `webui/trading_src/` | `webui/trading_src/out/` | `webui/trading_command.py` (`/api/trading-command/*`) |

- close-slot 연구는 **Svelte "Daily OHLCV" 탭**에 있음: `webui/v2_src/src/tabs/DailyOhlcvTab.svelte` → `webui/v2_src/src/tabs/dailyOhlcv/DailyCloseSlotCard.svelte`.
- API 계약: `webui/v2_src/src/lib/dailyOhlcvApi.ts`. 라우팅: `webui/v2_src/src/lib/routes.ts`.
- **라우팅 충돌**: `webui/v2/__init__.py`에서 `/daily-ohlcv`와 `/daily`는 **301로 `/rl?section=daily-gates`(Next.js)로 리다이렉트**된다. 따라서 Svelte 일봉 탭(close-slot 포함)은 `/?tab=daily-ohlcv`로만 접근된다. → 사용자가 "일봉 탭이 두 개"로 느끼는 근본 원인.
- 서빙 로직: `webui/v2/__init__.py` (`_serve_dashboard_shell`=Svelte, `_serve_trading_shell`=Next.js).

---

## 4. RL 현황과 핵심 버그 (Phase 1의 근거)

### 4-1. 현재 구조
- 이것은 엄밀한 순차적 RL이 아니라 **1-step contextual bandit + rule baseline** 라인이다. fill=`close_to_next_close_research_label` = **비실행 상한**.
- 소스: `stom_rl/daily_close_slot_dataset.py`(피처/라벨/분할), `daily_close_slot_env.py`(비용/보상 계산), `daily_close_slot_train.py`(정책/threshold), `daily_close_slot_gate.py`(fail-closed 게이트).

### 4-2. 피처 (현재 8개) — `stom_rl/daily_ohlcv_dataset.py::DEFAULT_FEATURE_COLUMNS`
```
return_1d, return_5d, volatility_5d, volume_ratio_5d,
hl_range, gap_from_prev_close, foreign_holding_ratio, institutional_net_buy
```
라벨: `future_return_1d, future_direction_1d, future_rank_pct_1d`.

### 4-3. 정책
`no_trade_control`, `deterministic_shuffle_top10_control`(control, action 아님), `momentum_top10_score_and_pick`, `contextual_bandit_linear_train_only_score_and_pick`, `frozen_d3_reledgered_score_and_pick`(가능 시).

### 4-4. 핵심 버그 (Phase 1이 고칠 것)
gate report의 정책 가중치:
```
institutional_net_buy: -0.9999   ← 점수를 지배
return_1d ~ 2.3e-07, return_5d ~ 5.4e-06, volume_ratio_5d ~ 3.1e-05, ...
threshold: 1,329,615
```
- `institutional_net_buy`는 스케일이 수백만, `return_1d`는 0.01 단위 → **정규화 없이 선형 점수 계산** → 사실상 점수=기관순매수.
- threshold가 기관순매수 raw 스케일(132만)로 잡혀 **거의 아무 종목도 threshold 통과 못 함** → contextual_bandit이 **0개 선택 → reward 0**.
- 즉 "정책이 나빠서 0"이 아니라 **"피처 스케일 버그로 판단 자체를 못 해서 0"**.
- bounded 결과 참고: no_trade=0, shuffle=-0.4748, momentum=+0.3088, contextual_bandit=0.

---

## 5. 작업 계획 (Phase별 · 실행 지침)

각 Phase는 독립 실행 가능. 순서 권장: **1 → 2 → 3 → 4 → 5 → 6 → (7 선택)**.
파괴적/대규모 변경(Phase 3 통합, Phase 6~7)은 착수 전 사용자 승인.

### Phase 1 — 피처 정규화로 정책 작동시키기 (최우선)
- **목표**: contextual_bandit 정책이 실제로 종목을 선택하도록 피처를 정규화한다.
- **대상 파일**: `stom_rl/daily_close_slot_train.py`(점수/threshold 계산), 필요 시 `stom_rl/daily_close_slot_dataset.py`(정규화 통계 저장), 테스트 `tests/test_stom_rl_daily_close_slot_train.py`.
- **변경 내용**:
  1. 선형 점수 계산 전에 피처를 **train split 통계로 정규화**(z-score 또는 rank-normalize). 정규화 파라미터(mean/std 또는 분위수)를 train manifest에 기록.
  2. threshold 탐색을 **정규화된 점수 스케일** 기준으로 재설계. 0..10개 선택이 실제로 발생하는지 확인.
  3. validation/test에는 train 통계를 **frozen 적용** (재적합 금지, `oos_rows_used_for_fit=0` 유지).
  4. leakage 방지: 미래 라벨/미래 통계 사용 금지 (`validate_no_feature_leakage` 유지).
- **수용 기준**:
  - contextual_bandit이 bounded 실험에서 평균 선택 종목 수 > 0 (0개 붕괴 해소).
  - train manifest에 정규화 방식/통계가 기록됨.
  - shuffle/no-trade 통제군 대비 delta가 산출됨(개선 여부와 무관하게 정직히 기록).
  - gate `WATCH_RESEARCH_ONLY` 유지, D0/D1 blocker 유지, 모든 false-lock 유지.
- **선행 문서**: 새 사전등록 `docs/stom_close_slot_feature_normalization_prereg_<날짜>.md`.
- **검증**: 아래 §6 close-slot 테스트 + bounded 재생성 + gate PASS.

### Phase 2 — 보상에 리스크 반영
- **목표**: 단순 수익률 보상에 리스크/낙폭 항을 추가해 "고변동 몰빵" 억제.
- **대상**: `stom_rl/daily_close_slot_env.py`(보상 컴포넌트), `daily_close_slot_train.py`, 테스트.
- **변경**: `수익 − λ·변동성` 또는 Sharpe/Sortino류, MDD 페널티, 집중도 페널티. 보상 컴포넌트를 manifest/게이트에 분해 노출(scalar-only 금지).
- **수용 기준**: 보상 분해가 artifact/게이트/대시보드에 노출, 통제군 대비 정직한 비교.

### Phase 3 — close-slot 카드 리모델링 (가독성) + 프론트엔드 통합 결정
- **목표**: `DailyCloseSlotCard.svelte`의 글자 과밀 제거, 정보 위계 부여. 동시에 프론트엔드 이중화 정리안 확정.
- **대상**: `webui/v2_src/src/tabs/dailyOhlcv/DailyCloseSlotCard.svelte`, `webui/v2_src/src/lib/dailyOhlcvApi.ts`(필요 시), 라우팅 `webui/v2/__init__.py`(리다이렉트 정리 시 — 승인 필요), 테스트 `tests/test_daily_ohlcv_dashboard_tab.py`(마커 유지).
- **Claude design 원칙**:
  1. **상태칩 1개**: `연구용 · WATCH · 실거래 아님` (색+아이콘). 반복 no-claim 문구는 하단 배지 1곳으로 통합.
  2. **핵심 지표 3~4개만 크게**: 선택 종목 수 / 비용 23bp / 기준선 대비 / 미해결 blocker 수.
  3. **세부(해시/경로/행수)는 접이식(accordion)** "세부 증거 ▸" 안으로.
  4. blocker(D0/D1)는 삭제 금지 → **경고 배너 1개**로 승격.
  5. 숫자 나열 → **바 차트/스파크라인/테이블**로 대체(정책별 기준선 대비, 비용 0/23/46bp, 종목 선택 테이블). `000250` 선행 0 유지.
  6. 폰트 위계(제목/지표/캡션), 여백/구분선.
- **테스트 마커 유지 필수**: `data-daily-close-slot-card`, `data-daily-close-slot-source-scope`, `data-daily-close-slot-db-access`, `data-daily-close-slot-no-claims` 등 기존 QA 훅을 깨지 말 것(테스트가 참조). 마커는 유지하되 시각 표현만 개선.
- **통합 결정**: Next.js(Trading Command Center) vs Svelte(Kronos 대시보드) 중 **하나로 수렴**하는 비교표 작성 → 사용자 승인 후 실제 정리. `webui/AGENTS.md`의 "내부 v2 경로 이름 변경 금지" 준수.
- **산출물**: 리모델링 목업(HTML/PNG) 먼저 → 승인 → Svelte 반영. `npm run build` 성공. 브라우저 스크린샷 증거.

### Phase 4 — 피처 확장
- **대상**: `stom_rl/daily_ohlcv_dataset.py::DEFAULT_FEATURE_COLUMNS` + `FEATURE_DEFINITIONS`, `daily_close_slot_dataset.py`(파생).
- **추가 후보**(모두 결정시점 과거값만, 미래 라벨 누수 금지):
  - 추세/모멘텀: return_10d/20d/60d, 이동평균 이격도(20/60), 신고가 근접도
  - 거래량: 거래대금(원), 거래량 z-score, 거래대금 급증, OBV 추세
  - 변동성/리스크: ATR, 상·하한가 빈도, 갭 빈도
  - 보조지표: RSI, MACD, 볼린저 %B, 스토캐스틱
  - 수급: 외국인/기관 순매수 누적(5·20일), 개인 순매수, 프로그램 매매
  - 시장맥락: 지수 수익률/변동성, 시장 breadth, 섹터 상대강도
- **수용 기준**: leakage 테스트 통과, train-only 정규화, 통제군 대비 개선 시에만 의미 부여.

### Phase 5 — 체결/유동성 현실화 (Mode B 방향)
- 거래량 대비 부분 체결, 저유동/거래정지/상하한가 제외, 변동성·거래대금 기반 동적 슬립피지. 별도 사전등록 필요.

### Phase 6 (선택) — 시장맥락 상태를 포함한 순차적 RL
- 현금비중/시장상태를 state에 넣은 진짜 RL. 필요성이 입증될 때만. 대규모 → 승인 필요.

---

## 6. 검증 명령어 (실행 후 반드시)

```powershell
# close-slot 코어
py -3.11 -m pytest tests/test_stom_rl_daily_close_slot_dataset.py tests/test_stom_rl_daily_close_slot_env.py tests/test_stom_rl_daily_close_slot_train.py tests/test_stom_rl_daily_close_slot_gate.py -q

# 대시보드 API/탭
py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_api.py tests/test_daily_ohlcv_dashboard_tab.py -q

# D4 호환 + dist 마커
py -3.11 -m pytest tests/test_stom_rl_daily_portfolio_env.py tests/test_stom_rl_daily_rl_gate.py tests/test_stom_rl_daily_scenario_runner.py tests/test_v2_dist_marker.py -q

# Svelte 빌드 (프론트엔드 변경 시)
cd webui/v2_src
npm run build

# 대시보드 실행/정지 (배치, 8122)
start_kronos_dashboard_quiet.bat
stop_kronos_dashboard.bat

# 라이브 확인 (예)
#  http://127.0.0.1:8122/?tab=daily-ohlcv   ← Svelte close-slot 카드
#  http://127.0.0.1:8122/api/daily-ohlcv/close-slot/latest
```

- 결과 doc/receipt에는 **정확한 command, run IDs, 경로, SHA, split, 비용, 기준선 delta, gate verdict, blocker, 대시보드 증거**를 기록.
- 산출물 위치: dataset `webui/rl_runs/daily_close_slot_dataset/`, train `webui/rl_runs/daily_close_slot_train/`, gate `webui/rl_runs/daily_close_slot_gate/`, receipt `artifacts/`.

---

## 7. Gotchas / 주의

- 대용량 full-universe 생성은 timeout(>600s) 위험. bounded 범위로 실행하고 범위를 receipt/manifest에 명시.
- 배치는 cwd=`webui/`에서 실행됨. 신규 경로 상수는 반드시 `REPO_ROOT` 앵커 사용(상대경로 금지). (Phase들에서 신규 root 추가 시 특히 주의)
- v1 fixture 호환 유지: 신규 스키마 검증은 `schema_version==2`에만 적용(기존 v1 테스트를 깨지 말 것).
- 문서는 UTF-8. 한글 컬럼(`외국인현보유비율`, `기관순매수`) 인코딩 주의.
- 기존 verdict/result 문서 mutate 금지. 새 날짜 문서 생성.
- out-of-repo 파일(`Kronos_market_regime_maturity/...`, `deep-interview-kronos-final.md`) 절대 건드리지 말 것.
- `webui/AGENTS.md`, `webui/v2_src/AGENTS.md`, `stom_rl/AGENTS.md`, `docs/AGENTS.md`, `tests/AGENTS.md`를 착수 전 재확인.

---

## 8. 참고 파일 인덱스

| 역할 | 경로 |
|---|---|
| close-slot 데이터셋/피처 | `stom_rl/daily_close_slot_dataset.py`, `stom_rl/daily_ohlcv_dataset.py` |
| close-slot 환경/보상 | `stom_rl/daily_close_slot_env.py` |
| close-slot 학습/정책/threshold | `stom_rl/daily_close_slot_train.py` |
| close-slot 게이트 | `stom_rl/daily_close_slot_gate.py` |
| 대시보드 백엔드(close-slot 로더) | `webui/daily_ohlcv_dashboard.py` |
| Flask 라우트 | `webui/app.py`, `webui/v2/__init__.py` |
| Trading Command Center 백엔드 | `webui/trading_command.py` |
| Svelte 일봉 탭 | `webui/v2_src/src/tabs/DailyOhlcvTab.svelte` |
| Svelte close-slot 카드 | `webui/v2_src/src/tabs/dailyOhlcv/DailyCloseSlotCard.svelte` |
| Svelte API 계약 | `webui/v2_src/src/lib/dailyOhlcvApi.ts` |
| 이번 연구 사전등록/결과 | `docs/stom_daily_close_next_day_rl_prereg_2026-07-03.md`, `docs/stom_daily_close_next_day_rl_result_2026-07-03.md` |
| 대시보드 실행/정지 배치 | `start_kronos_dashboard_quiet.bat`, `stop_kronos_dashboard.bat` |

---

## 9. 실행 시작 지점 (다음 세션용 한 줄)

> "이 저장소에서 `docs/kronos_close_slot_rl_and_dashboard_remodel_handoff_2026-07-03.md`를 읽고, §1 가드레일을 지키며 Phase 1(피처 정규화)부터 실행하라. Phase 3의 프론트엔드 통합과 Phase 6~7은 착수 전 사용자 승인을 받아라."

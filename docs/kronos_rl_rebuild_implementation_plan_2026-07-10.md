# Kronos RL 재개발 상세 구현 계획서 (2026-07-10)

> **상위 문서**: [`kronos_full_inspection_and_rl_rebuild_plan_2026-07-10.md`](kronos_full_inspection_and_rl_rebuild_plan_2026-07-10.md) (전수검사 보고서 — 문제 F1–F24 정의) · [`kronos_dashboard_v3_plan_2026-07-06.md`](kronos_dashboard_v3_plan_2026-07-06.md) (대시보드 P0–P9)
> **본 문서의 역할**: 전수검사 보고서의 Track R(연구 백엔드)·Track D 보강(S1–S3)을 **작업 패키지(WP) 단위로 즉시 개발 가능한 스펙**으로 전개. 각 WP는 변경 파일·함수·라인 앵커·데이터 스키마·테스트·완료 기준·롤백을 포함하며 독립적으로 실행·검증 가능하다.
> **라인 앵커 기준**: 커밋 `d745b1c` 시점. 앵커는 드리프트할 수 있으므로 **함수명 기준으로 탐색 후 작업**한다.

---

## 0. 불변 계약 (모든 WP 공통 전제)

작업 전 반드시 숙지. 위반 시 해당 WP는 실패로 간주한다.

| # | 계약 | 구체 내용 |
|---|---|---|
| C1 | 가드레일 문자열·마커 불변 | 모든 `data-*` 테스트 마커, `WATCH_RESEARCH_ONLY`/`NO-GO_RESEARCH_ONLY`, D0/D1/D5 blocker, false-lock 7종(실거래·브로커·주문·계좌·페이퍼·모델빌드·수익주장) |
| C2 | 데이터 불변 | read-only DB(`mode=ro`, `PRAGMA query_only`), 종목코드 선행 0 보존(`'000250'`은 문자열, int 변환 금지) |
| C3 | 라벨링 규율 | `ts_imb`는 RULE — RL로 표기 금지. RULE 베이스라인 이벤트/시리즈는 `algorithm='rule_baseline'` 태깅 또는 미방출. 학습곡선 상승은 "train-replay 내 보상 개선"으로 라벨, OOS 수익성 주장 금지 |
| C4 | 비용 기준 | 주 비용 `base_23bp` (0bp/46bp는 컨트롤). Kronos 평가 레거시 25bp와 혼동 금지 |
| C5 | P7 동결 파일 (v3 plan :126) | `webui/app.py`, `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py` — **본 계획의 어떤 WP도 이 3파일을 수정하지 않는다** (WP-R2는 `rl_dashboard_files.py`만 수정 — 동결 목록 외 확인됨) |
| C6 | P8 동결 스키마 (v3 plan :137) | `stom_rl/rl_events.py` 수정 금지 — 이벤트 스키마 `stom_rl_live_event.v1` byte-identical (`tests/test_stom_rl_live_events.py`가 가드). 계측은 **트레이너 쪽**에서만 |
| C7 | API 동결 | 신규 `/api/*` 엔드포인트 추가 금지 (기존 엔드포인트만 사용 — SSE는 명시적 Gate-A 승인 전 착수 금지) |
| C8 | v2 SPA 수정 규율 | `webui/v2_src/src/`만 수정 → `npm run build`로 dist 갱신 → SSR meta marker `kronos-v2-shell` 제거 금지 → light/dark 모두 검증 → `pytest tests/test_v2_*.py` 통과 |
| C9 | 학습 변경 사전등록 | 신규/변경 학습 실행(WP-R3 풀 런, WP-R4 탐색, F14 300s 재튜닝, WP-R6 스윕)은 착수 전 dated prereg 문서 작성 (`docs/stom_daily_close_next_day_rl_research_design_2026-07-01.md:315-323`의 continuous-improvement loop 준수) |
| C10 | 스테이징 | 모든 학습은 스모크(축소) → 아티팩트/스키마 검증 → 풀 순서. 스모크를 풀로 표기 금지 (`bounded experiment` 선언) |

**공통 검증 명령** (WP별 완료 기준에서 "표준 검증"으로 참조):

```bash
# 백엔드 WP
py -3.11 -m pytest tests/test_stom_rl_daily_close_slot_train.py tests/test_stom_rl_daily_close_slot_env.py tests/test_stom_rl_live_events.py tests/test_stom_rl_dashboard_api.py -q
# 프론트 WP
cd webui/v2_src && npm run build   # 0 오류 필수
py -3.11 -m pytest tests/test_v2_dist_marker.py tests/test_v2_route.py tests/test_stom_rl_dashboard_tab.py tests/test_daily_ohlcv_dashboard_tab.py -q
# 화면 변경 시: 8122 서버 + Chrome 헤드리스 실캡처 (light/dark)
```

---

## 1. WP 인덱스 & 의존성 그래프

```
WP-R1 (정규화+진단) ──→ WP-R2 (관측성) ──→ WP-S1/S3 (라이브 화면) ──→ WP-R4 (밴딧 정직화)
                              │
WP-R3a (NAV 수정) ────────────┤            WP-R3b (SB3 실데이터)  ← R3a, R2
WP-R5a/b/c (Kronos 귀속 3실험) — 완전 독립, 즉시 병렬             → F14 결정
WP-S2 (루프 시각화) — 독립 (기존 API만 사용), 즉시 병렬
WP-R6 (거버넌스) — R2 이후 권장       WP-R7 (Aim+rliable) — R6 스윕 이후 (= v3 plan P8)
```

| WP | 이름 | 해결 문제 | 규모 | 선행 |
|---|---|---|---|---|
| R1 | 종가매매 정규화 + no-trade 진단 | F1, F2 | M | 없음 |
| R2 | 학습 관측성 (보상 영속화 + 이벤트 계측 + 발견성) | F3–F6 | M | R1 |
| R3a | D4 equity=NAV 수정 + 자가 판정 | F7, F9 | M | 없음 |
| R3b | SB3 PPO 실데이터 학습 | F8 | L | R3a, R2 |
| R4 | 밴딧 정직화 (탐색 or 개명) | F10 | M | R1, R2 결과 |
| R5a | Kronos zero-shot 귀속 실험 | F11 | S | 없음 |
| R5b | 평가 결정론화 (시드+5샘플) | F12 | S | 없음 |
| R5c | 토크나이저 재구성 평가 | F13 | M | 없음 |
| R5d | 학습 곡선 로컬 영속화 | F15 | S | 없음 |
| R6 | 거버넌스 (준비도·레지스트리·별칭·스윕) | F16–F18 | M | R2 권장 |
| R7 | Aim + rliable 백본 (= P8 병합) | — | M | R6 |
| S1 | RL 학습 라이브 화면 | F20, F21, F23 | M | R2 |
| S2 | "RL이 뭔가" 루프 실데이터화 | F19 | M | 없음 |
| S3 | 종가매매 에이전트 화면 | F22 | M | R2 권장 (없이도 착수 가능) |
| S4 | JSON 덤프 정리 + 마이크로 위젯 | F24, F21 일부 | S | 없음 |

---

## 2. WP-R1 — 종가매매 정규화 수정 + no-trade 진단

**목표**: `institutional_net_buy` 가중치 독식(-0.9999) 제거 → 정책이 유의미한 다피처 스코어를 산출. "0종목"이 버그인지 정직한 최적인지 **기계적으로 구분 가능**하게.

### 2.1 변경 파일·함수

**`stom_rl/daily_close_slot_train.py`** (핵심):

1. `_fit_contextual_bandit_weights` (:203-237 부근)
   - 전달받은 fit rows(이미 train-split 한정 — `_expanding_refit_artifacts`에서 윈도우별 expanding train prefix)에서 **per-feature mean/std 계산** (또는 median/MAD robust — 기본은 mean/std, robust는 옵션 플래그).
   - 피처 행렬을 z-score 후, 기존 피처별 단변량 공분산 대신 **공동(joint) ridge 적합** 권장 — 검증된 참조 구현: `stom_rl/contextual_bandit.py:277-295` (z-score) 및 `:89-95` (predict 시 동결 stats 적용).
   - 반환 구조 변경: `{"weights": {...}, "feature_mean": {...}, "feature_std": {...}, "fit_method": "ridge_zscore_v1"}`.
   - std=0 피처는 `max(std, 1e-9)` 가드.
2. `_contextual_bandit_score` (:254-255 부근)
   - 시그니처에 scaler stats 추가. 스코어 = `Σ w_i · (x_i − mean_i)/max(std_i,1e-9)`.
   - **결측값은 raw 0.0이 아니라 train mean으로 대체** (z=0) — 현행 `or 0.0` 제거.
3. `_threshold_grid` (:318-341) — 입력이 z-스케일 스코어가 되므로 threshold_text 스케일이 정상화됨. **센티널 유지**하되:
4. `_choose_train_threshold` (:528-537)
   - 선택 결과에 `chosen_is_no_trade_sentinel: bool` 메타 추가 → manifest `threshold_selection`에 기록.
   - 타이브레이크 재검토: `mean_selected_count` **오름차순(적은 선택 선호) 항 제거 또는 반전**, 결정 근거를 `tie_break_policy` 필드로 기록.
5. `run_close_slot_training` (:967-976 부근)
   - **강제 top-10 진단 변형** 추가 평가: 동일 스코어로 `selection_threshold=None, max_slot_count=10` (메커니즘 기존재: `daily_close_slot_env.py:337-339` `normalize_close_slot_action`) → `baseline_summary`에 `contextual_bandit_linear_top10_forced_diagnostic` 행으로 발행. **primary는 threshold 정책 유지** — 진단 변형은 "신호가 23bp를 못 넘는 것"과 "스코어 자체 붕괴"를 분리하는 용도.
6. `fit_summary`/manifest에 scaler(mean/std)·fit_method 영속화. `CLOSE_SLOT_TRAIN_SCHEMA_VERSION` 범프.

**`stom_rl/daily_close_slot_gate.py`**: 스키마 버전·신규 필드(scaler, sentinel 플래그, 진단 변형 행) 존재 검사 추가. 기존 검사(`GATE_READY_STATUS_FOR_UNRESOLVED_D0_D1`, `GATE_D3_NOT_RELEDGERED`, `oos_rows_used_for_fit=0`) 불변.

**금지 경계** (감사 확정): env(`daily_close_slot_env.py`)는 스코어 소비자이므로 정규화 넣지 말 것. dataset panel에도 넣지 말 것(패널 하나가 전 스플릿을 관통 — 윈도우별 refit에는 윈도우별 stats 필요 → **fit 내부가 유일하게 누출 안전한 경계**).

### 2.2 신규/변경 테스트 (`tests/test_stom_rl_daily_close_slot_train.py`)

```
test_fit_no_single_weight_dominance      # 혼합 스케일 합성(1e6 vs 1e-2) → 어떤 |w|도 L1 질량 0.7 초과 금지
test_score_uses_frozen_train_stats       # val/test 스코어링이 fit 시점 mean/std 사용 (재계산 금지)
test_missing_value_imputed_to_train_mean # 결측 → z=0 (raw 0.0 아님)
test_sentinel_flag_surfaced              # 센티널 선택 시 chosen_is_no_trade_sentinel=True가 manifest에
test_forced_top10_diagnostic_present     # baseline_summary에 진단 변형 행 존재 + 항상 ≤10 선택
test_schema_version_bumped               # gate가 신 스키마 수용, 구 아티팩트는 명시 거부
```

### 2.3 완료 기준

1. 표준 검증(백엔드) 그린 + 위 신규 테스트 그린.
2. 재학습 1회(스모크 → 풀): manifest `fit_summary.weights`에서 최대 |w|의 L1 점유 < 0.7, scaler 필드 존재.
3. 진단 변형이 비자명 선택(>0 종목)을 산출하고, primary 정책의 선택 수·센티널 여부가 플래그로 판독 가능.
4. **정직성 확인**: 정규화 후에도 primary가 0종목이면 그것은 버그가 아니라 "23bp 하 신호 부족"으로 문서화 (센티널 플래그 + 진단 변형 대비로 입증).

**롤백**: 스키마 버전이 게이트에서 분기되므로 구 아티팩트와 공존 가능. 커밋 리버트만으로 복원.

---

## 3. WP-R2 — 학습 관측성 (보상 영속화 + 이벤트 계측 + 발견성)

**목표**: "라운드마다/에피소드마다 얼마나 나아지는가"의 **데이터 소스**를 만들고, 라이브 카드가 daily 레인을 실제로 표시하게 함. **백엔드 API 변경 0** (C5/C7 준수 — 기존 `/api/rl/runs/<run>/events` 재사용).

### 3.1 `stom_rl/daily_close_slot_train.py`

1. **rid 호이스트**: `run_close_slot_training` 상단(현행 :998-1007의 rid/output_dir 결정을 `_expanding_refit_artifacts` 호출(:921) **이전**으로 이동). `FileExistsError` 검사(:1005-1006)는 `rl_live_events.jsonl` 단일 파일 허용목록으로 완화(그 외 파일 존재 시엔 기존대로 오류 — overwrite 보호 유지).
2. **라운드별 보상 영속화** (F3):
   - `_episode_ledgers_from_policy_payload` (:671-687): episode dict에 `reward`, `net_pnl_krw`, `cost_krw`, `filled_slots` 추가 (이미 손에 있는 ledger rows에서 복사).
   - `_expanding_refit_artifacts` (:721-782): 윈도우별 요약을 `walk_forward_windows` 엔트리에 저장:
     ```json
     {"window_id": "...", "replay_mean_reward_base_23bp": 0.0,
      "replay_cumulative_reward": 0.0, "mean_selected_count": 0.0, "date_count": 20}
     ```
3. **이벤트 계측** (F4): 옵션 파라미터 `event_writer: RlLiveEventWriter | None = None` (기본 None → 동작 byte-identical).
   - 윈도우별: replay 평가 직후(:757-760 앵커)에 1이벤트 — `global_step=window_index, reward=replay_mean, phase='walk_forward', algorithm='contextual_bandit', source='daily_close_slot_train', info={window_id, threshold_text}`.
   - 날짜별: `_evaluate_policy_rows` ledger append(:399 앵커)에서 — `reward=ledger['reward'], equity=net_pnl_krw 누적합, timestamp=date`.
   - **C3 필수**: 방출은 `POLICY_CONTEXTUAL_BANDIT` 호출(:747-756, :967-976)에서만. no_trade/shuffle/momentum/D3-frozen 베이스라인 평가(:934-996)는 미방출(또는 `algorithm='rule_baseline'` 태깅). `RlLiveEvent.source` 기본값이 `'sb3_smoke'`이므로 **source 명시 필수**.

### 3.2 `stom_rl/daily_rl_train.py`

1. **rid 호이스트**: `run_and_write_daily_rl`(:1716-1725)에서 `rid = _validate_run_id(run_id or timestamp)` 결정 (현행 `write_rl_artifacts`:1365에서 사후 결정 → 학습 중 라이브 기록 불가 문제 해소). 비어있지 않은 디렉토리 검사(:1368-1369)는 `LIVE_EVENT_FILE_NAMES` 허용목록으로 완화.
2. **이벤트 계측**: `train_tabular_q_policy`(:625-679)에 `event_writer` 옵션 — 에피소드 루프(:663-677 앵커)에서 `phase='train', episode, global_step=누적 step, reward=total_reward, equity=env.equity, algorithm='tabular_q', source='daily_rl_train'`. `evaluate_policy`(:704-731)의 :729-731 앵커에서 `phase=f'eval_{split_label}', reward, equity=info['equity'], timestamp=info['date']`.
3. `run_daily_rl`(:1135-1151) 경유로 writer 관통.

### 3.3 발견성 (F5) — `webui/rl_dashboard_files.py` (:17-28)

```python
ARTIFACT_SIGNATURES = (
    ...기존 10종...,
    ("daily_ohlcv_portfolio", "rl_manifest.json"),
    ("daily_close_slot_train", "close_slot_train_manifest.json"),
)
```
+ `webui/v2_src/src/lib/rlRows.ts`에 두 타입의 `typeLabel`/`typeTone` 추가. (동결 3파일 비접촉 — 감사에서 확인: `rl_dashboard_runs.py`가 `ARTIFACT_SIGNATURES`를 import하므로 이 튜플 확장만으로 목록 노출됨.)

### 3.4 대시보드 시리즈 — `webui/daily_ohlcv_dashboard.py`

`_close_slot_walk_forward_summary`(:808-819)가 신규 라운드별 보상 필드를 그대로 노출(기존 payload 확장 — 신규 엔드포인트 아님). `DailyCloseSlotCard.svelte`에 "라운드별 replay 보상 (train 내 frozen-replay · 수익 주장 아님)" 미니 차트 1개 추가.

### 3.5 테스트

```
test_close_slot_events_schema            # 방출 파일 schema_version == stom_rl_live_event.v1 (rl_events.py 무수정 증명)
test_rule_baseline_never_labeled_rl      # 베이스라인 평가 경로에서 algorithm='contextual_bandit' 이벤트 0건
test_walk_forward_windows_carry_rewards  # 윈도우 엔트리에 replay_mean_reward_base_23bp 존재
test_daily_runs_discoverable             # 두 daily 런 디렉토리가 list_rl_runs에 등장 (artifact_type != 'unknown')
test_writer_none_byte_identical          # event_writer=None 시 기존 아티팩트와 동일 (회귀 없음)
test_live_file_allowlist                 # rl_live_events.jsonl만 있는 디렉토리는 FileExistsError 미발생
```

### 3.6 완료 기준

1. 표준 검증 그린 + 신규 테스트 그린. `tests/test_stom_rl_live_events.py` 무변경 그린 (C6 증명).
2. close-slot 재학습 실행 중 **대시보드 라이브 카드가 라운드별 보상을 실시간 표시** — 실브라우저 캡처 1장(진행 중) + 1장(완료 후).
3. RunSelector에 daily 런 2종이 목록으로 등장.

**리스크**: Gate A(아티팩트 스냅샷 게이트)가 run-list payload를 커버하면 재베이스라인 필요 — 착수 시 확인. **롤백**: writer 기본 None이므로 계측 자체는 무해; 시그니처 2줄과 스키마 필드만 리버트 대상.

---

## 4. WP-R3a — D4 equity=NAV 수정 + 비개선 자가 판정

**목표**: "우상향이 수식상 불가능한 그래프" 제거 (F7). 학습이 안 되면 안 된다고 스스로 말하는 런 (F9).

### 4.1 변경

1. **`stom_rl/daily_portfolio_env.py` `step()`** (:349-375 부근):
   - 현행 `self.equity *= 1.0 + reward` (reward에 노출·집중·churn·드로다운 페널티 포함) →
   - `self.equity *= 1.0 + net_return_after_cost` (순수 NAV), `self.shaped_equity *= 1.0 + reward` (셰이핑 진단용 별도 필드). reward 자체(학습 신호)는 불변 — **곡선/텔레메트리 의미만 분리**.
   - `info`에 `equity`(NAV)·`shaped_equity` 병기.
2. **`stom_rl/daily_rl_train.py`**: `build_learning_curve`(:353)·`episode_rows`(:664-677)가 `final_equity`(NAV)와 `final_shaped_equity` 모두 방출. 스키마 필드 추가는 additive.
3. **val 평가 콜백** (F9): `run_daily_rl`(:1113 부근)에서 K 에피소드마다(기본 K=1, 에피소드 수가 작으므로) greedy 정책을 val 스플릿에 `evaluate_policy`로 평가 → `learning_curve.csv`에 `val_nav` 열 추가.
4. **자가 판정**: `_verdict_for_d4`(:1068)에 rolling val NAV 기울기 ≤ 0이면 reasons에 `TRAINING_CURVE_NON_IMPROVING` 추가 → 대시보드에 그대로 노출 (침묵 통과 금지).
5. **`webui/daily_ohlcv_dashboard.py` `learning_curve_preview`**(:5258-5298): NAV 시리즈를 플롯 (shaped는 보조 시리즈).
6. seed-7 구성 재실행으로 정직한 곡선 재생성 (스모크 규모 그대로 — 이 WP는 학습 스케일업이 아니라 **의미 수정**).

### 4.2 테스트·완료 기준

- `test_equity_is_pure_nav` (페널티 있는 스텝에서 equity 변화 == net_return_after_cost), `test_shaped_equity_separate`, `test_non_improving_verdict_fires` (합성 하락 곡선 → reason 존재), `test_learning_curve_has_val_nav`.
- 완료: 재생성 런의 learning_curve.csv에 NAV·val_nav 존재, 대시보드 프리뷰가 NAV 표시(캡처), 비개선 시 판정 문구 노출(캡처).

---

## 5. WP-R3b — SB3 PPO 실데이터 학습 (첫 "진짜 RL" 아티팩트)

**목표**: "PPO가 우리 데이터에서 학습하는가"의 최초 실증 아티팩트. GPU 사용. 라이브 스트림 방출.

### 5.1 구현

1. **신규 `stom_rl/daily_portfolio_sb3_dataset.py`**: D3 예측 런의 `predictions.csv` → `PortfolioEnv` candidate 스키마(dates, 6자리 zero-padded codes 문자열 유지(C2), scores, future_return_1d) 변환 어댑터. 결측 next-day는 fail-closed 제외 + 카운트 기록.
2. **실행 경로**: `stom_rl/portfolio_sb3_train.py`를 `candidate_path=<어댑터 출력>`으로 —
   - `total_timesteps ≥ 200_000` (스모크는 5_000으로 선행)
   - `device` 핀 해제: `"cpu"` 고정(:90) → 설정 가능하게, 기본 `"auto"`; summary에 `device_used: str(model.device)` 기록 (F: R6와 공유)
   - `EvalCallback` 10k step마다 val NAV → **기존 `RlLiveEventWriter`로 방출** (이 트레이너는 이미 writer 사용 중 :46/:353 — phase='eval' 이벤트 추가만)
   - `MaskablePPO` 에스컬레이션 트리거(invalid action rate)가 발화하면 `sb3-contrib` 도입을 별도 결정으로 기록 (자동 설치 금지)
3. **사전등록(C9)**: `docs/stom_daily_sb3_ppo_prereg_<date>.md` — 데이터 범위, timesteps, 시드(≥3), 성공/실패 판정 기준(예: val NAV가 no-trade·momentum 베이스라인 대비 열위면 NON_IMPROVING — 그것도 유효 결과), 비용 23bp.
4. 산출 런은 R2의 시그니처로 대시보드 목록·라이브 카드에 자동 표시.

### 5.2 완료 기준

- 스모크(5k) 통과 → 풀(≥200k) 1회 완주. summary에 `device_used`가 cuda 표기.
- 학습 중 라이브 카드에서 reward/equity 스트림 확인 (캡처).
- 사전등록 문서의 판정 기준에 따라 결과 기록 — **개선이면 개선, 아니면 NON_IMPROVING을 그대로 문서화** (C3).

---

## 6. WP-R4 — 밴딧 정직화 (R1·R2 결과로 분기 결정)

**분기 규칙** (착수 전 R1·R2 결과 검토):

- **분기 A (신호 존재)**: R1 후 primary 정책이 유의미 선택을 하고 진단 변형과의 격차가 해석 가능 → **탐색 도입**: seeded ε-greedy를 **train replay 윈도우 내부에서만** (`daily_close_slot_gate.py:218-249`의 `oos_rows_used_for_fit=0` 불변 유지, val/test 절대 금지). ε 스케줄·시드는 prereg(C9).
- **분기 B (신호 부족/판단 유보)**: **정직 개명** — `POLICY_CONTEXTUAL_BANDIT`(train.py:43) → `linear_ridge_score_and_pick_train_only` 전 표면(manifest·gate·dashboard·테스트) 일괄 개명. RL/밴딧 표기 제거 (C3와 동일 규율).

**공통**: `_feedback_weight_by_key`(:240-251)의 `abs(net_return)` 가중 → **signed** 가중(승자 상향, 패자 단위 또는 하향)으로 교체하거나 제거. 방향 맹목 가중은 어느 분기에서도 유지하지 않는다.

**완료 기준**: 분기 결정 기록(ADR 한 단락) + 해당 분기 구현 + 게이트/테스트 그린. 분기 A면 탐색 on/off A-B 아티팩트 비교 1회.

---

## 7. WP-R5 — Kronos 귀속 실험 3종 + 곡선 영속화 (완전 독립·즉시 병렬)

### R5a — zero-shot 사전학습 베이스라인 (결정적 실험, S)

```bash
# 기존 스크립트 그대로 사용 — 코드 변경 불필요 (모델 경로만 교체)
python finetune/evaluate_stom_1s_checkpoint.py \
  --model-path NeoQuasar/Kronos-small \
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base \
  <docs/stom_2025_full_small_walkforward_eval_dashboard.md:25-40의 36x3x50 walkforward 플래그 동일 적용> \
  --prefix stom_1s_pred60_2025_pretrained_zeroshot_eval
```
산출: 동일 681 윈도우에서 direction/Top-K/MAPE 비교표 → `docs/stom_kronos_attribution_report_<date>.md`에 finetuned vs pretrained vs random 3열 기록. **해석 규칙**: pretrained ≈ finetuned ≈ random → "신호 부재" 우세 / finetuned < pretrained → "튜닝이 유해" / finetuned > pretrained (그러나 둘 다 게이트 실패) → "튜닝 유효하나 지평-비용 불일치".

### R5b — 평가 결정론화 (S)

`finetune/evaluate_stom_1s_checkpoint.py`: `main()` 상단에 `torch.manual_seed(args.seed)` + numpy 시드 추가(현행: args.seed는 random 베이스라인만 시드). `sample_count`(기본 5 = `config.py:200` `inference_sample_count`)·`temperature`·`top_p`를 `parse_args`→`kronos_predictions`(:191-228)로 관통, 비교 JSON(:401-410)에 기록. 플래그십 평가 1회 재실행 → 0.4479 vs 0.4493 격차 중 디코딩 노이즈 비중 정량화.

### R5c — 토크나이저 재구성 평가 (M)

신규 `finetune/evaluate_tokenizer_reconstruction.py`: `test_data.pkl`을 QlibDataset 방식 윈도우로 로드, `F.mse_loss(z, x)` (train_tokenizer.py의 val 메트릭과 동일 정의 — 현행 파일 기준 :282-284 부근)를 (a) `NeoQuasar/Kronos-Tokenizer-base` (b) `outputs/stom_1s_grid_pred60_2025_full_small/finetune_tokenizer/checkpoints/latest_train_model` 각각에 대해 batch 1·고정 시드로 산출 → 체크포인트 옆 JSON 저장. `tokenizer_run_manifest.json`의 `validation_completed: false` 공백을 사후적으로 폐쇄.

### R5d — 곡선 영속화 (S)

`finetune/train_predictor.py`(:139-152, :189-202)·`train_tokenizer.py`: `KRONOS_USE_COMET` 무관하게 `<save_dir>/metrics.jsonl`에 log_interval마다 1줄(step, lr, loss 성분)·epoch마다 val loss append. `finetune/training_progress.py`가 노출하도록 확장.

### F14 결정 규칙 (300s 재튜닝 — L, 본 계획에서는 **결정만** 정의)

R5a·R5b 완료 후: (i) 튜닝이 유해하지 않고 (ii) 300s 엣지가 결정론 평가에서도 유지되면 → `qlib_stom_pipeline.py --horizon-seconds 300` 신규 export + budget 규모 선행 + 비용 게이트를 **23bp 기준**(0/23/46 그리드, C4)으로 정렬해 prereg 후 실행. 아니면 Kronos 재튜닝 동결을 문서화.

### 완료 기준 (R5 전체)

- 귀속 보고서 1편 (`docs/stom_kronos_attribution_report_<date>.md`) — 3열 비교표 + 해석 규칙 적용 결론 + F14 go/no-go.
- 신규 스크립트·플래그의 스모크 테스트 (27-윈도우 축소 구성으로 CI 가능 수준).

---

## 8. WP-R6 — 거버넌스 (준비도·레지스트리·별칭·스윕)

1. **준비도 게이트** (F16): `webui/app.py` — **주의: C5 동결 파일**. 따라서 구현은 두 안 중 하나로: (a) Gate-A 절차를 밟아 동결 해제 승인 후 `build_training_readiness`(:497-508)에 `finetune_predictor/checkpoints/best_model` 디렉토리 존재 검사 추가, 또는 (b) 동결 유지 시 `finetune/training_progress.py`(비동결)에서 `checkpoint_exists` 필드를 status payload에 추가하고 app.py는 무수정 소비. **기본 선택: (b)**. + 단위 테스트.
2. **레지스트리 등록** (F17): `stom_rl/daily_rl_train.py` `run_and_write_daily_rl`(:1716)에서 `stom_rl/factory/run_registry.register_run(...)` 호출 — `stage='smoke' if episodes < 128 else 'full'`, seed, cost_bps=23, prereg_doc 경로, 완료 시 `set_status('done', verdict)`. R3b의 SB3 런도 동일.
3. **별칭 표시** (F17): `write_rl_artifacts`(:1351)가 `rl_manifest.json`에 `parent_training_run` 필드(키: seed, episodes, prediction_manifest_sha, source_hashes) 기록. 기존 3개 중복 디렉토리(`portfolio_2026_06_13_d4b_telemetry`, `_d4c_policy_eval`, `_g003_state_visualization`)에 `ALIAS_OF.txt` 1줄 백필.
4. **시드 민감도 스윕** (F18): `stom_rl/daily_scenario_batch.py` 확장 — 그리드 seeds {7,17,29,41,53} × episodes {8,32,128}, `run_and_write_daily_rl` 재사용, `webui/rl_runs/daily_ohlcv_portfolio/_scenario_runs/` 하위 `stability_summary.json`(셀별 val+test net return, trade count, never-trade flag). prereg(C9) 후 실행. **해석**: 8ep-hold vs 12ep-loss 반전이 노이즈인지 문서화 — 더 깊은 방법 제안의 전제 데이터.
5. **finetuned 체크포인트 스모크 회귀** (kronos-finetune F 저심각): `tests/test_kronos_regression.py` 옆에 opt-in 테스트 — 최신 `finetune/outputs/*/finetune_predictor/checkpoints/best_model` 로드 → 300-bar 합성 윈도우 predict → 유한 출력 + predict-window 일치 assert (Windows opt-in 가드 유지).

**완료 기준**: 신규 D4/SB3 런이 registry에 행으로 존재(SELECT 확인), 준비도 payload에 checkpoint_exists, 스윕 요약 산출, 전체 pytest 그린.

---

## 9. WP-R7 — Aim + rliable 백본 (= v3 plan P8과 동일 항목, 병합 실행)

1. **Aim(self-host)**: `pip install aim` → `aim init`/`aim up` 로컬 기동 스크립트(`scripts/aim_up.bat`). 어댑터 신설 `stom_rl/experiment_tracking_aim.py` — 주의: 기존 `stom_rl/experiment_tracking.py`는 "NOT WIRED" MLflow 심 → **대체 결정을 ADR 한 단락으로 기록** 후 Aim 어댑터로 통일(심 삭제는 별도 정리 커밋). R2/R3의 event_writer 훅 옆에 optional Aim run 로깅(기본 off, env flag `KRONOS_USE_AIM=1`) — 데이터 반출 0 (localhost).
2. **rliable**: `pip install rliable` → `scripts/rl_report_rliable.py` — R6 스윕의 multi-seed 결과에서 IQM·stratified bootstrap CI·performance profile 산출 → `artifacts/rl_reliability_report_<date>.json` + docs 요약. **라벨**: 전부 연구용, 수익 주장 아님(C3).
3. requirements 반영은 `webui/requirements.txt`가 아닌 연구용 별도(`stom_rl/requirements-research.txt` 신설) — 대시보드 서버 의존성 오염 방지.

**완료 기준**: Aim UI 로컬 접속 확인(캡처), 스윕 데이터 기반 rliable 리포트 1건, 기본 off 플래그 동작 테스트.

---

## 10. WP-S1 — "RL 학습 라이브" 화면 (백엔드 변경 0)

**신규 `webui/v2_src/src/tabs/rlTrading/RlLiveScreen.svelte`** — RLTradingTab 최상단(Disclosure 스택 위, 현행 LiveRlEventsCard 슬롯 :335 대체) 마운트.

| 요소 | 데이터 소스 (전부 기존) | 구현 |
|---|---|---|
| 헤더 스트립 (run·algorithm·phase·LIVE/IDLE pill) | `rlApi.rlEvents(run, 240)` 4s 폴링 (LiveRlEventsCard :70-114 재사용) | 기존 readouts(:267-273) 이식 |
| reward+equity 듀얼 라이브 차트 + 스크러버 | 동일 | 기존(:218-247, :282-300) 이식 |
| 일별 수익/에쿼티 곡선 (portfolio 런) | `rlApi.rlEquity` (RLTradingTab :170 기로드) | `equityChartOption`(chartOptions.ts:60-70) 재사용 |
| **에피소드 티커 (신규 — "나아지는가" 장기 추이)** | events rows의 `episode_id` 필드 (rl_events.py:67) | 클라이언트 그룹핑 → `EP n · Σreward` 칩 + 에피소드별 총보상 미니바 |
| **액션 피드 레일 (신규)** | 동일 rows의 `action_name` (rl_events.py:81 — 이미 브라우저 도달) | 최근 ~20행 `step · action_name · reward · equity`, hold/buy/sell 색상 |
| 콜드 로드 기본 런 수정 | `choosePreferredRun`(RLTradingTab :120-130) | `live_event_count>0` 런 우선 (RULE 아티팩트 기본 선택 → IDLE 공백 문제 해소) |
| 오버레이 정렬 수정 (F23) | LiveRlEventsCard 오버레이 분기(:193-212) | category x축 → value x축 + `[global_step, equity]` 튜플, 스크러버 윈도우는 시리즈별 step 범위 기준(:166의 primary frame index 슬라이스 제거) |

**라벨 계약**: 제목 "학습 라이브 (연구 전용)" — 'trading' 금지. 안전 문구는 LiveRlEventsCard:312-314 문자열 그대로. 이벤트 없는 런의 빈 상태는 백엔드 메시지("live event log is not available for this run") 그대로 표기. ts_imb 시리즈명 "ts_imb baseline" 유지 (RL 표기 금지).

**착수 전 체크** (감사 F 지적): `/api/rl/runs` 각 런에 `/events` 호출해 rows>0 여부 실측 — daily 런이 미방출 상태면 S1의 에피소드 티커는 `rlApi.rlEpisodes` CSV 폴백 + 정직한 빈 상태 문구.

**완료 기준**: 표준 검증(프론트) 그린 + 기존 마커 계약 유지 + light/dark 실캡처 각 1장(라이브 상태 1장 포함, R2 완료 후).

---

## 11. WP-S2 — "RL이 뭔가" — 루프 시각화 상시화 + 실데이터 주입 (독립·백엔드 변경 0)

**`webui/v2_src/src/tabs/DailyRlGuideTab.svelte`**:

1. 루프 SVG(:302-368)+스토리보드(:371-382)를 감싼 Disclosure(:292/:384) **제거** → overview 섹션에서 상시 노출.
2. SVG 하드코딩 `<text>` 리터럴(:331-349)을 최신 active_replay 프레임 실값으로 치환 — 기존 헬퍼 `frameState()/frameAction()/frameReward()`(:88-91) 사용:
   - STATE 노드: `position_count · top_score_bucket · top_candidate_code`
   - AGENT 노드: `frameAction().executed`를 hold/buy/add/sell/reduce 중 하이라이트
   - REWARD 노드: `net_return_after_cost − turnover_cost − penalties = reward` + "23bp 왕복 비용" 콜아웃 (필드 전부 `daily_ohlcv_dashboard.py:5395-5406`이 이미 제공)
3. SVG 아래 "오늘의 한 사이클" 3카드: state 피처 → action(=선택 종목/hold) → reward(=익일수익−23bp). 프레임 없으면 fail-closed `—` + 기존 `MISSING_REPLAY_ARTIFACT` pill(:994). **수치 합성 절대 금지**.
4. ResearchStatusShell 잠금(:238-247)과 `RESEARCH_ONLY_ENV_BUILT_NOT_PROFIT_READY` pill(:280)을 다이어그램 **위에** 유지 — 루프는 항상 no-profit 배너 아래에서 읽힌다.

데이터: 기존 `GET /api/daily-ohlcv/rl-env-guide` (dailyOhlcvApi.ts:795) — 백엔드 무변경.

**완료 기준**: 가이드 탭 랜딩 즉시 루프+실값 보임(캡처, light/dark), 마커·no-claim 문구 불변, 표준 검증 그린.

---

## 12. WP-S3 — "종가매매 에이전트" 화면 (백엔드 변경 0)

**신규 `webui/v2_src/src/tabs/dailyOhlcv/CloseSlotAgentScreen.svelte`** — `DailyOhlcvTab.svelte`(:274)에서 DailyCloseSlotCard **위에** 마운트.

| 요소 | 데이터 소스 (전부 기존) | 구현 |
|---|---|---|
| 히어로 "오늘 선택 종목" | `selection.selection_rows` (dailyOhlcvApi.ts:616-632) 최신일 그룹 | 코드 문자열 보존(C2). `selected_count==0`이면 → |
| **0종목 결함 카드 (전면, 각주 아님)** | `threshold_selection` (dailyOhlcvApi.ts:553-564) | "0종목 선택 — 피처 정규화 버그 (알려진 결함, FACT)" (MissionControl:95 문구 재사용) + `hold_cash_action`/임계값 설명. R1 배포 후에는 `chosen_is_no_trade_sentinel` 값에 따라 "버그" ↔ "23bp 하 무거래가 정직한 최적" 문구 분기 |
| 종목별 판단 피처 (score vs threshold 바) | `latest.samples.policy_scores` / `selection.policy_score_sample` (:602-614, :770) | date·code·바 차트 |
| 익일 결과 원장 스테퍼 | 기존 SessionReplayCard 인터랙션(:76-96) 그대로 이식 | `entry_close → next_close → net_pnl_krw − cost_krw` + "Running TAKE net (23bp)" 누적 |
| 누적 연구용 에쿼티 | `closeSlotEquity` → EquityDrawdownChart (DailyCloseSlotCard:172-175와 동일) | R2 후 라운드별 보상 미니차트 병설 |

**라벨 계약**: `no_claim_labels` pill + false-lock 그리드(DailyCloseSlotCard:206-218, :239-244) 이식, 모든 KRW 값에 "연구 환산 · 수익 주장 아님", 헤더 pill "연구용 · {verdict} · 실거래 아님"(:116 패턴).

**완료 기준**: 19종 `data-daily-close-slot-*` 마커 계약 불변(신규 화면은 자체 `data-close-slot-agent-*` 마커 추가), 표준 검증 그린, 캡처 (0종목 결함 상태 1장 + R1 후 선택 상태 1장).

---

## 13. WP-S4 — JSON 덤프 정리 + 마이크로 위젯 (S)

1. `DailyRlGuideTab.svelte`: 본문 내 5개 `<pre class="ai-format-box">{safeJson(...)}` 블록(:467, :529, :557, :789, :909, :935)을 raw 섹션(`isGuideSection('raw')`, :1143)으로 이동, 각 자리는 2-3줄 인간어 key-value로 대체.
2. `DailyCloseSlotCard.svelte:124`: `execution_realism` enum 앞에 평문 주석("체결 현실성: 사전 피처 없는 상한 추정 (…)").
3. `RLTradingTab.svelte` 미니그리드(:273-280)에 7번째 셀 "Reward trend (연구용)" — 기로드 episodes rows(:171)로 에피소드별 총보상 스파크바.
4. `MissionControl.svelte` RL 카드(:96-98): LIVE 서브라인(rlEvents tail의 최신 step+reward, 실패 시 기존 PENDING 패턴 '확인 중' :34) + "가이드 보기" 두 번째 클릭 타깃(`daily-rl-guide`, routes.ts:17). verdict NO-GO는 FACT 그대로.

---

## 14. 실행 스케줄 제안 (개발 세션 단위)

| 순서 | 병렬 슬롯 A (연구 백엔드) | 병렬 슬롯 B (독립 작업) |
|---|---|---|
| 1 | **WP-R1** (정규화+진단) | **WP-R5a/b** (zero-shot·결정론 — 스크립트 실행 위주) + **WP-S2** |
| 2 | **WP-R2** (관측성) — R1 재학습과 함께 검증 | **WP-R5c/d** + **WP-S4** |
| 3 | **WP-S1 + WP-S3** (라이브 화면 — R2 데이터 소비) | **WP-R3a** (NAV 수정) |
| 4 | **WP-R3b** (SB3 실데이터 — prereg 후) | **WP-R6** (거버넌스) |
| 5 | **WP-R4** (분기 결정 — R1·R2 결과 검토 후) | **WP-R7** (Aim+rliable — R6 스윕 소비) |
| 6 | F14 결정 (300s 재튜닝 go/no-go — R5 보고서 기반) | 잔여 정리 · dashboard-v3 → master PR 준비 |

각 세션 종료 시: 표준 검증 + 커밋(WP 단위, conventional commits) + 필요 시 실캡처를 `artifacts/`에 증거로.

---

## 15. 리스크 레지스터

| 리스크 | 확률 | 완화 |
|---|---|---|
| R1 후에도 0종목 (신호 부족이 진실) | 중 | 설계상 수용 — 센티널 플래그+진단 변형으로 "버그 아님"을 입증하고 S3가 정직 문구로 분기. R4는 분기 B(개명)로 |
| R3b PPO가 학습 안 함 (NON_IMPROVING) | 중~높음 | prereg에 실패 판정 기준 명시 — 그것도 유효 결과. false-lock 불변이므로 과장 위험 없음 |
| Gate A 스냅샷 재베이스라인 필요 (R2 시그니처 추가) | 중 | 착수 시 Gate A assert 범위 확인, run-list 커버 시 재베이스라인 절차 선행 |
| 라인 앵커 드리프트 | 확실 | 함수명 기준 탐색 원칙(문서 서두), WP별 앵커는 참고용 |
| `webui/app.py` 동결 vs 준비도 수정 충돌 | 낮음 | R6-1을 (b)안(비동결 파일에서 필드 추가)으로 기본 선택 |
| SB3/Aim 의존성의 대시보드 오염 | 낮음 | 연구용 requirements 분리(`stom_rl/requirements-research.txt`), Aim은 env flag 기본 off |
| 학습 곡선이 올라가도 OOS는 아님 (기대 관리) | 확실 | 모든 곡선 라벨에 스코프 명시(C3), D5 게이트 불변 — 대시보드는 게이트 결과를 미화하지 않음 |

---

## 16. 완료의 정의 (프로그램 레벨)

본 계획 전체가 완료되면 사용자는 다음을 **실제로 보게 된다**:

1. 종가매매가 종목을 실제로 선택하거나, 선택하지 않는 이유가 화면에 사실로 표기됨 (R1+S3)
2. 학습이 도는 동안 라운드/에피소드/일별 보상·에쿼티가 **라이브 그래프로 움직임** (R2+S1)
3. "RL이 뭔가"가 첫 화면에서 오늘의 실데이터 수치로 설명됨 (S2)
4. GPU에서 도는 진짜 RL(PPO) 학습 런 1회전과 그 정직한 판정 (R3a+R3b)
5. Kronos 튜닝 실패의 원인이 대조 실험으로 귀속된 보고서 (R5)
6. 모든 실험이 레지스트리·Aim·rliable로 추적·비교·통계화됨 (R6+R7)

단, **우상향 수익 곡선 자체는 산출물이 아니라 연구 결과**다 — 본 계획의 산출물은 "우상향이면 우상향이 보이고, 아니면 아닌 것이 보이는, 버그 없는 정직한 시스템"이다.

---

*착수 승인 시 세션 1(WP-R1 + WP-R5a/b + WP-S2)부터 시작한다. 각 WP 완료 시 본 문서의 완료 기준 대비 증거(테스트 출력·캡처·아티팩트 경로)를 커밋 메시지에 명시한다.*

# STOM RL 랩 — compact 이후 재개(RESUME) 핸드오프

- 작성일: 2026-05-28
- 목적: **context compact 이후 이 문서 하나만 읽고 동일하게 작업을 이어가기 위한 자체 완결형 핸드오프.**
- 브랜치: `feature/stom-rl-lab`
- 데이터(유일): `D:\Chanil_Park\Project\Programming\Kronos\_database\stock_tick_back.db` (1초봉, 개장 09:00–09:30, 이벤트 트리거 기록, 28GB, UTF-8 한글 컬럼, 종목코드 선행 0 주의)

---

## 0. 한 줄 현황 (먼저)

**강화학습(RL)은 우상향 곡선을 못 만든다(인트라데이 알파 부재 3중 증명). 우상향 곡선을 만드는 것은 RL이 아니라 "시초 갭상승 룰 전략"이며, 사용자 실비용 23bp에서 검증 완료(매년·5경계 OOS 양수). 다음 할 일 = 이 룰 곡선을 대시보드에 시각화(우상향 그래프) + 실거래 직전 게이트(realized-fill / SL gap-through / paper replay).**

---

## 1. 사용자(트레이더) 핵심 사실

- 한국 퀀트 트레이더. 전략 = **"시초 급등 / 9시 시초 갭 상승"** (opening gap-up momentum).
- 전략 스펙(사용자 지정): **진입 등락율 ≥ 2%**, **청산 = TP(목표수익) / SL(손절) 또는 09:25 시간청산**.
- **실제 왕복 체결비용 = 23bp** = 매수 수수료 0.015% + 매도 수수료 0.015% + 증권거래세 0.20%(매도측). (사용자가 명시 확정함.)
- 사용자가 원하는 것: **유튜브 NEAT 영상 스크린샷처럼 "꾸준히 우상향하는 수익 곡선"**, 실거래 직전 상태.
- 정직 원칙(내가 약속한 것): **안 맞는 프레임에 데이터를 욱여넣어 거짓 결론 내지 않는다.** 룰 전략 결과를 "RL"이라 라벨하지 않는다.

---

## 2. 무엇이 증명/검증되었나 (확정 사실)

### 2-A. RL(딥러닝 포트폴리오 선택)은 알파 없음 — 3중 증명
- 인트라데이 종목선택(cross-sectional) RL/ranker 알파는 **1초·1분·세션프록시 전부 shuffle 검정 통과 못함(NO)**.
- 즉 PPO/DQN 포트폴리오 선택 정책의 NAV는 우상향하지 않음. 제약은 알고리즘이 아니라 **신호/데이터**.
- 근거 문서: `docs/stom_rl_deep_rl_verdict_2026-05-27.md`, `docs/stom_rl_signal_test_2026-05-27.md`, `docs/stom_rl_1min_signal_verdict_2026-05-27.md`, `docs/stom_rl_story_b1_session_proxy_verdict_2026-05-27.md`.
- 유튜브 영상은 **NEAT(신경진화)** 로 우리 DQN/PPO와 근본적으로 다르고, 그런 매끈한 곡선은 대개 in-sample/과적합 전시물.

### 2-B. 시초 갭상승 룰 전략 = 첫(그리고 유일한) 양수 신호, 검증됨
- 진입 등락율≥2% + **진입필터** + TP5%/SL1% + 09:25 청산.
- **진입필터 정의** (`stom_rl/gap_up_backtest.py`):
  - `none`: 2% 갭만.
  - `ts`: **체결강도 ≥ 100** (STOM "at par").
  - `ts_imb`: 체결강도 ≥ 100 **AND** 호가 imbalance(매수총잔량/(매수+매도)) ≥ 0.5.
- **사용자 실비용 23bp 결과** (`docs/stom_rl_gap_up_realcost_2026-05-28.md`):

  | 필터 | N | @23bp/trade | de-idealized* | breakeven | 여유 |
  |---|---|---:|---:|---:|---:|
  | none | 1349 | +0.246% | +0.206% | 42.7bp | 1.9× |
  | +ts | 425 | +0.633% | +0.593% | 82.7bp | 3.6× |
  | **+ts_imb** | 235 | **+0.952%** | **+0.912%** | 116.6bp | **5.1×** |

  \* de-idealized = 이상적 TP/SL 체결 낙관 보정(~−0.04%).
- **레짐 견고**(`docs/stom_rl_gap_up_regime_validation_2026-05-28.md`): 2022~2026 매년 양수, **5/5 holdout 경계 OOS 양수**, 슬리피지 38bp까지 생존. Architect가 inflating-bug 없음 검증.
- **universe = 사용자 실거래 대상(STOM 트리거 종목)과 일치** → 배포 관점에서 편향 아님.

### 2-C. 누적 equity 곡선 (캐시에서 즉시 계산, @23bp, TP5/SL1) — 이게 "우상향 그래프"
| 필터 | N | 누적%(비복리) | exp/trade | 승률 | 최대낙폭 | 최장연패 |
|---|---:|---:|---:|---:|---:|---:|
| UNFILTERED | 1349 | +332.2% | +0.246% | 29% | −26.0% | 17 |
| +ts | 425 | +269.0% | +0.633% | 36% | −19.3% | 12 |
| **+ts_imb** | 235 | **+223.6%** | +0.952% | 42% | **−15.7%** | **9** |

→ **ts_imb가 가장 매끈한 우상향** (낙폭·연패 최소). 단 **비복리 per-trade % 단순합**이고, 승률 42%·TP5/SL1 비대칭이라 영상처럼 완벽히 매끈하진 않음(거칠지만 검증된 진짜).

---

## 3. 핵심 파일 (코드/데이터/산출물)

| 용도 | 경로 |
|---|---|
| **갭상승 백테스트(메인)** | `stom_rl/gap_up_backtest.py` |
| 백테스트 테스트(36 pass) | `tests/test_stom_rl_gap_up_backtest.py` |
| **누적곡선 빌더(캐시→즉시)** | `.omx/artifacts/gap_up_backtest/build_equity_curve.py` |
| 캐시 인스턴스(1349, gitignored) | `.omx/artifacts/gap_up_backtest/instances.json` (keys: per-TP/SL `*_net_pct`@25bp, `pass_ts`, `pass_ts_imb`, `entry_*`, `session`, `symbol`, `split`) |
| 레짐 요약 | `.omx/artifacts/gap_up_backtest/regime_summary.json`, `regime_analysis.json` |
| paper replay(read-only 하니스) | `stom_rl/paper_replay.py` |
| 대시보드 라이브 이벤트 콜백 | `stom_rl/portfolio_sb3_train.py` (`RlLiveEventTrainingCallback`), `stom_rl/rl_events.py` |
| 대시보드 run 발행 | `stom_rl/portfolio_run_publish.py` |
| 워크포워드/shuffle | `stom_rl/portfolio_walk_forward.py` |
| 비용/리스크 게이트 | `stom_rl/cost_gate.py`, `stom_rl/risk_gate.py`, `stom_rl/accounting.py` |
| 대시보드 run 파일 | `webui/stom_predictions/` |

비용은 **flat 가산적**: `net@c = net@25 + (25−c)/100` (per-trade %). 그래서 캐시(25bp)에서 23bp는 `+0.02%p`만 더하면 됨 — DB 재실행 불필요.

---

## 4. 진행 상태

### 4-A. 완료(2026-05-28, 이번 세션) — 우상향 곡선 시각화 (1)+(2)
1. **PNG 곡선 생성 완료**: `.omx/artifacts/gap_up_backtest/equity_curve.png` — 3필터(none/ts/ts_imb) 누적 우상향, 한글 라벨(Malgun Gothic). 빌더: `build_equity_curve.py --png`.
2. **대시보드 run 3개 발행 완료**: `webui/rl_runs/gap_up_{none,ts,ts_imb}_equity/` — `/api/rl/runs` 노출 확인, ts_imb events 235건 equity **987,700→3,236,073**(+223.6% 우상향), `algorithm=rule:gap_up_ts_imb`, `is_reinforcement_learning=False`(정직 라벨).
   - 발행 스크립트(신규): `stom_rl/gap_up_dashboard_publish.py` + 테스트 `tests/test_stom_rl_gap_up_dashboard_publish.py`.
   - 대시보드 follow/replay 뷰: `http://127.0.0.1:5070/rl` → run `gap_up_ts_imb_equity` 선택 → NAV(equity) 곡선.

### 4-B. 완료(2026-05-28) — 체결 de-idealization 게이트 1+2
3. **realized-fill / SL gap-through 구현 완료**: `stom_rl/gap_up_backtest.py`에 `fill_mode`(`idealized`/`realized`/`sl_gap_stress`) + `--fill-mode` 추가. 41 tests pass. 상세: `docs/stom_rl_gap_up_fillmode_2026-05-28.md`.
   - **ts_imb 결과 @23bp**: idealized +0.952 → realized +0.906(−0.045%p) → **sl_gap_stress(최악) +0.811**(−0.140%p). breakeven 대비 ~4× 여유, 체결낙관 제거에 견고.
   - **정직한 한계**: 2022(최약·소표본)는 realized/최악에서 −0.01~−0.05로 뒤집힘. 2023~2026은 전 모드 강한 양수. 필터 없는(none) 전략은 최악모드에서 2년 음수+낙폭 −65%로 무너짐 → 필터(ts_imb)가 핵심.
   - **de-idealized 곡선 대시보드 발행됨**: `gap_up_ts_imb_realized`(+213.0%), `gap_up_ts_imb_sl_gap_stress`(+190.7%).
   - 비교 산출물: `.omx/artifacts/gap_up_{idealized,realized,sl_gap_stress}/`, 추출기 `.omx/artifacts/gap_up_backtest/fill_mode_compare.py`.

### 4-C. 남은 것 (정직한 한계 / 선택)
4. **게이트 3 (진짜 큐·부분체결 paper replay)**: **데이터 부재로 불가** — L2 큐포지션 데이터 없음(DB는 매수/매도총잔량 합계만). realized/stress 체결 + 슬리피지 38bp 스윕이 우리 데이터로 가능한 체결현실성 상한.
5. **대시보드 서버 재시작 필요**(아래 명령어 §5) — 어제(2026-05-27) 기동 프로세스라 stale, 신규 run 요약카드 미표시. 데이터·`/events` 곡선은 정상.
6. (선택) 2022 약세 원인 분석(소표본 vs 레짐), full-universe 재실행, 실주문 슬리피지 모델.

---

## 5. compact 이후 재개 명령어 (그대로 복붙)

### (즉시·DB 불필요) 누적 우상향 곡선 재생성 — 콘솔
```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
py -3.11 .omx\artifacts\gap_up_backtest\build_equity_curve.py
```

### (즉시) 우상향 곡선 PNG 저장 (영상 스크린샷 대용)
```powershell
py -3.11 .omx\artifacts\gap_up_backtest\build_equity_curve.py --png
# 출력: .omx\artifacts\gap_up_backtest\equity_curve.png
```

### (검증 재현) 실비용/필터 cost-sweep + breakeven
```powershell
py -3.11 stom_rl\gap_up_backtest.py --max-symbols 120 --cost-bps 23
```

### (검증 재현) 레짐 robustness(연도별·5경계·슬리피지) @23bp
```powershell
py -3.11 stom_rl\gap_up_backtest.py --regime-analysis --regime-cost-bps 23 --max-symbols 120
```

### 테스트(36 pass 확인)
```powershell
py -3.11 -m pytest tests\test_stom_rl_gap_up_backtest.py -q
```

### 체결 de-idealization 재현 (realized / 최악)
```powershell
py -3.11 stom_rl\gap_up_backtest.py --fill-mode realized      --max-symbols 120 --regime-analysis --regime-cost-bps 23 --artifacts-dir .omx\artifacts\gap_up_realized
py -3.11 stom_rl\gap_up_backtest.py --fill-mode sl_gap_stress --max-symbols 120 --regime-analysis --regime-cost-bps 23 --artifacts-dir .omx\artifacts\gap_up_sl_gap_stress
py -3.11 .omx\artifacts\gap_up_backtest\fill_mode_compare.py    # 3모드 비교표
# de-idealized 곡선 대시보드 발행
py -3.11 -m stom_rl.gap_up_dashboard_publish --instances .omx\artifacts\gap_up_realized\instances.json --filter ts_imb --cost-bps 23 --run-name gap_up_ts_imb_realized
```

### 대시보드 (서버 stale면 재시작 필요)
- URL: `http://127.0.0.1:5070/rl` → run 선택 → 라이브 이벤트/NAV 스트림.
- 서버가 신규 run을 `unknown`으로 표시하면(어제 기동 등 stale) 재시작: 5070 리슨 PID kill 후
  ```powershell
  py -3.11 webui\run.py    # 또는 기존 기동 방식
  ```

> `--max-symbols 0`은 full universe(800+ 종목)라 느림 → 검증엔 120으로 충분(1349 인스턴스 캐시와 정합).

### compact 후 첫 프롬프트로 쓸 한 줄 (나에게)
```
docs/stom_rl_resume_handoff_2026-05-28.md 읽고 STOM RL 랩 이어서 진행.
다음: ts_imb 우상향 곡선 PNG + 대시보드 시각화(섹션4의 1·2), 이어서 realized-fill/SL-gap/paper replay 게이트.
```

---

## 6. 정직성 가드레일 (재개 시 반드시 유지)

- 룰 전략 곡선을 **"강화학습/RL"이라 부르지 않는다.** (RL은 알파 부재 증명됨.)
- 누적곡선은 **비복리 per-trade % 합** — "연수익률"이나 "계좌 자산곡선"으로 과장하지 않는다.
- 영상의 매끈한 곡선 = 보통 in-sample/과적합. 우리 곡선은 거칠지만 OOS·매년·5경계 검증됨 — 그게 더 가치 있음.
- 실거래 직전엔 realized-fill / SL gap-through / paper replay로 **체결 현실성** 확정 전까지 "실거래 준비 완료"라고 말하지 않는다.

## 7. 관련 문서 읽기 순서
1. (본문) `docs/stom_rl_resume_handoff_2026-05-28.md` ← 지금 이 파일
2. `docs/stom_rl_gap_up_realcost_2026-05-28.md` — 실비용 23bp 확정 결과
3. `docs/stom_rl_gap_up_regime_validation_2026-05-28.md` — 레짐/슬리피지 검증
4. `docs/stom_rl_gap_up_cost_filter_2026-05-27.md` — 비용모델+필터 첫 양수
5. `docs/stom_rl_gap_up_backtest_2026-05-27.md` — 필터 전 기준선(0/16)
6. `docs/stom_rl_deep_rl_verdict_2026-05-27.md` — RL 알파 부재 종합

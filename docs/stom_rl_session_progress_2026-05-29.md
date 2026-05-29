# STOM RL 랩 — 2026-05-29 세션 진행/재개 핸드오프

- 작성일: **2026-05-29 KST**
- 브랜치: `feature/stom-rl-lab`  / HEAD: `f082992`
- 상위 마스터 앵커: `docs/stom_rl_resume_commit_2026-05-29.md`
- 목적: 이 세션에서 한 일(Page A + RL 트랙 R0/R1/R1b + Page B 착수)을 다음 대화가 그대로 이어가게 한다.

---

## 0. 한 줄 현황

**Page A(사이징) 완료 · RL 트랙(R0 딥리서치→R1 천장→R1b 인과 baseline) 완료로 "청산 RL 폐기" 판정 · 현재 Page B(full universe) 백테스트 실행 중.** 검증된 수익원은 변함없이 **시초 갭상승 룰 전략 + 사이징(RULE, NOT RL)**.

---

## 1. 이 세션 커밋 (시간순)

| 커밋 | 내용 |
|---|---|
| `4a0937a` | Page A 사이징/리스크 설계 + RL 타당성 딥리서치(R0) |
| `dd039c8` | R1 oracle-exit 천장 테스트 |
| `f082992` | R1b 인과적 청산 baseline — 청산 RL 게이트 종결 |

전체 게이트 테스트: **138 passed** (backtest 41 + dashboard 6 + risk 54 + exit_oracle 15 + exit_baselines 22). 각 페이지 code-reviewer APPROVE.

---

## 2. 핵심 결론 (정직성 가드레일 유지: RULE strategy, NOT reinforcement learning)

1. **Page A**: `ts_imb` 룰을 **f=10%/회·동시보유 3·일손실 -3%**로 사이징. 1R=계좌 0.123%, 최장연패 9 와도 누적 -0.55~-1.1%, 계좌 MDD 순차 -1.6~-2.0%. Kelly는 퇴화(full ≈ 계좌 22배)라 낙폭 기준 사이징. (`stom_rl/gap_up_risk_sizing.py`, doc `..._risk_sizing_2026-05-29.md`)
2. **R0 딥리서치**(105 에이전트 적대적 검증): 비용차감 OOS에서 수익난 시초/장중 RL 사례 **0건**. 모든 "RL이 이겼다"류 0-3 기각. RL은 알파원 아님. (doc `..._rl_feasibility_research_2026-05-29.md`)
3. **R1 천장 테스트**: 완전예지 청산 대비 룰 capture 17.8%, regret +4.18%(손절이 55%). 단 완전예지는 hindsight → 필요조건일 뿐. (`stom_rl/exit_oracle.py`, doc `..._oracle_exit_ceiling_2026-05-29.md`)
4. **R1b 인과 baseline**: SL확대·트레일링 9개 변형 중 **현행 TP5/SL1이 평균net·Sharpe 모두 1위**. IS최적 trail_1이 OOS −0.71%(과적합), DSR 0.931<0.95. → **청산 RL(R3) 폐기**. (`stom_rl/exit_baselines.py`, doc `..._exit_baseline_2026-05-29.md`)

---

## 3. 페이지 로드맵 (현재)

| 페이지 | 상태 |
|---|---|
| Page A 사이징/리스크 | ✅ 완료 |
| R0 RL 딥리서치 / R1 천장 / R1b 인과 baseline | ✅ 완료 → RL 청산 폐기 |
| R3 offline RL 청산 | ❌ 폐기(R1b 게이트 실패) |
| R2 메타라벨링(진입) | ⬜ 선택·저우선 |
| **B full universe 재검증** | 🔄 **실행 중** |
| C 유동성/꼬리 → D paper → E broker | 이후 (E는 승인 전 금지) |

---

## 4. Page B 진행 상태 + 재개 방법

실행 중 명령:
```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.11 -X utf8 stom_rl/gap_up_backtest.py --max-symbols 0 --regime-analysis --regime-cost-bps 23 --artifacts-dir .omx/artifacts/gap_up_full
```
- 산출(완료 시): `.omx/artifacts/gap_up_full/summary.json`, `instances.json`, `regime_analysis.json` (gitignored)
- 미완 시 재실행: 위 명령 그대로. (장시간: 2427종목 ≈ bounded 120의 ~20배)

**완료 후 할 일(Page B 판정)**: `summary.json`의 `filter_analysis`(ts_imb N·breakeven IS/OOS)와 `regime_analysis`(per-year)를 **bounded-120 기준치와 비교**:
- 비교 기준(bounded, 23bp, idealized): ts_imb **N=235, 기대값 +0.952%/trade, breakeven 116.6bp, 연도별 2022만 약세(소표본)**.
- 판정: full universe에서 ts_imb 기대값이 **비용 후 양수 유지 + 연도패턴/ breakeven 여유 정합** → 엣지가 표본 한정 아님 확정. 아니면 표본 의존 경고.
- 결과 문서: `docs/stom_rl_gap_up_full_universe_2026-05-29.md` 작성(미작성 task #5).

---

## 5. 다음 대화 첫 행동

1. 이 문서 + `docs/stom_rl_resume_commit_2026-05-29.md` 읽기.
2. `git branch --show-current`(feature/stom-rl-lab), `git log --oneline -5`, 핵심 테스트 확인:
   ```powershell
   py -3.11 -m pytest tests/test_stom_rl_gap_up_backtest.py tests/test_stom_rl_gap_up_dashboard_publish.py tests/test_stom_rl_gap_up_risk_sizing.py tests/test_stom_rl_exit_oracle.py tests/test_stom_rl_exit_baselines.py -q
   ```
   기대: `138 passed`.
3. `.omx/artifacts/gap_up_full/summary.json` 존재 여부 확인:
   - 있으면 → Page B 비교/문서화(§4) 진행.
   - 없으면 → Page B 재실행(§4 명령).
4. 모든 문서/코드/대시보드 표현은 **"RULE strategy, NOT reinforcement learning"** 유지.

---

## 6. 정직성 가드레일 (불변)

- 갭상승 곡선을 RL이라 부르지 않는다. 누적은 비복리 per-trade % / fixed-notional.
- "실거래 준비 완료" 미선언. 실주문 전 Page C(유동성/꼬리)·D(read-only forward) 필요. E(broker)는 명시 승인 전 금지.
- 2022 약세는 N=39 소표본 변동성(레짐 붕괴 단정 금지).

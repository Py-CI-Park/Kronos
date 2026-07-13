# Daily Close-to-Next-Close 10-Slot 연구 사전등록 — 2026-07-03

## 상태

`EXPERIMENTAL_ONLY` / `RESEARCH_ONLY` 사전등록 문서다. 이 문서는 종가 매수 → 익일 종가 매도 연구를 체계적인 문서 ledger와 읽기 전용 최신 evidence 대시보드 출력으로 진행하기 위한 실행 전 동결 계약이다.

실거래, 브로커, 계좌, 주문, paper-forward, 수익성 보장, model-build readiness, deployable-alpha, `GO` 주장은 없다. `ts_imb`는 RULE baseline이며 RL로 부르지 않는다. 대시보드 라이브 출력은 최신 연구 산출물의 읽기 전용 evidence refresh를 뜻하며 live trading이 아니다.

## 연구 가설

Daily OHLCV 기반 Mode A close-label 연구에서, 날짜별 후보 종목에 causal score를 부여하고 threshold 이상 후보를 최대 10개까지 선택하면, 23bp 비용 차감 후 익일 종가 청산 basket reward가 no-trade, deterministic shuffle, RULE/momentum, frozen D3 re-ledger baseline보다 개선되는지 검증한다.

통과하더라도 운영/실거래 후보가 아니다. D0 가격 보정 근거와 D1 universe 공식성/수동 검토가 해결되기 전까지 verdict는 `NO-GO_RESEARCH_ONLY` 또는 `WATCH_RESEARCH_ONLY`다.

## 고정 연구 모드

| 항목 | 값 |
|---|---|
| 연구 모드 | Mode A DB-only close-to-next-close label research |
| fill mode | `close_to_next_close_research_label` |
| execution realism | `non_executable_upper_bound_without_preclose_features` |
| decision time label | `after_current_daily_close_research_only` |
| entry fill assumption | `official_daily_close_research_fill` |
| exit fill assumption | `next_official_daily_close_research_fill` |
| closing auction queue model | unavailable |
| partial fill model | unavailable |
| closing auction volume | unavailable |
| liquidity proxy | daily volume only |

Mode B pre-close/tick/orderbook/closing-auction approximation은 본 사전등록 범위 밖이다.

## 데이터와 blocker

| 항목 | 고정값/규칙 |
|---|---|
| DB | `_database/Stock_Database_ohlcv_1day.db` |
| DB 접근 | read-only, query-only |
| 가격 basis | `price_basis=unknown` |
| 가격 basis 상태 | `UNKNOWN_CONFIRMED` |
| decision-grade return | `BLOCKED_UNTIL_PRICE_BASIS_VERIFIED` |
| universe | 기존 D1 universe as-is, `WATCH` |
| 코드 처리 | 6자리 문자열 보존; 예: `000250`을 int로 변환 금지 |
| missing next close | 0수익 처리 금지; blocked/audited |
| split-like unknown adjustment | 기존 D0 정책에 따라 제외 또는 blocker 기록 |

## Action / selection 계약

| 항목 | 규칙 |
|---|---|
| slot count | 10 |
| max selected count | 10 |
| selection cardinality | `threshold_selected_0_to_10` |
| threshold | train-only fit으로 선택, validation/test에는 frozen 적용 |
| 선택 규칙 | `score >= selection_threshold` inclusive |
| 정렬 | score desc, tie_score desc/missing last, code asc, table asc, candidate_index asc |
| cash hold | 10개 미만 선택 시 남은 slot은 `cash_hold` |
| replay adapter | selected-code list는 replay/test adapter일 뿐 policy action 아님 |
| shuffle | baseline/control only, real policy action 아님 |

## 비용 모델

| scenario_id | sell_tax_bp | buy_commission_bp | sell_commission_bp | buy_slippage_bp | sell_slippage_bp | total_bp | 사용 |
|---|---:|---:|---:|---:|---:|---:|---|
| `zero_control_0bp` | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | control only |
| `base_23bp` | 20.0 | 1.5 | 1.5 | 0.0 | 0.0 | 23.0 | primary |
| `stress_46bp` | 20.0 | 1.5 | 1.5 | 11.5 | 11.5 | 46.0 | stress |

Scalar-only v2 비용 회계는 금지한다. 비용은 component별 bp와 KRW 금액을 artifact, gate, dashboard에 노출해야 한다.

## 보상 회계

Primary ledger는 integer-share 회계다.

```text
slot_cash = total_capital_krw / 10
shares_i = floor(slot_cash / entry_close_i)
entry_notional_i = shares_i * entry_close_i
exit_value_i = shares_i * next_close_i
gross_pnl_i = exit_value_i - entry_notional_i
cost_i = buy_commission_i + buy_slippage_i + sell_tax_i + sell_commission_i + sell_slippage_i
net_pnl_i = gross_pnl_i - cost_i
reward = sum(net_pnl_i) / total_capital_krw
```

Unused cash, empty slots, unaffordable slots, and cash_hold slots have 0 PnL. Missing next close is blocked/audited, never zero-return trade.

## Baselines / comparator 순서

실행 순서는 아래를 고정한다.

1. no-trade cash;
2. deterministic shuffle top-10 control;
3. RULE/momentum top-10;
4. frozen D3 score/selection re-ledgered through close-slot accounting when available;
5. supervised/ranker comparator;
6. contextual bandit/RL-style score policy.

D3가 없거나 close-slot accounting으로 재원장화할 수 없으면 D3-dependent claim은 `WATCH` 또는 `BLOCK`으로 기록한다. 기존 D3 PnL/NAV/metric을 직접 비교하지 않는다.

## Train / validation / test 동결 규칙

- Threshold 선택, replay feedback, reward-weighted refit은 train split만 사용한다.
- Validation/test는 frozen replay only다.
- 모든 train manifest, walk-forward window, gate report, dashboard payload에 `oos_rows_used_for_fit=0`을 기록한다.
- Validation/test 결과를 본 뒤 threshold, feature, split, cost, policy를 수정하면 새 사전등록과 새 run id가 필요하다.

## 예정 run IDs와 artifact roots

| 단계 | 예정 run id | root |
|---|---|---|
| dataset | `daily_close_slot_research_dataset_2026_07_03` | `webui/rl_runs/daily_close_slot_dataset/` |
| train/policy | `daily_close_slot_research_policy_2026_07_03` | `webui/rl_runs/daily_close_slot_train/` |
| gate | `daily_close_slot_research_gate_2026_07_03` | `webui/rl_runs/daily_close_slot_gate/` |

실제 실행 중 run id가 충돌하면 접미사 `_r2`, `_r3`를 붙이고 result doc에 정확한 최종 run id를 기록한다.

## 필수 artifact ledger

| artifact | 필수 내용 |
|---|---|
| dataset manifest | schema version, source DB hash/fingerprint, universe SHA, D0/D1 labels, feature list, split, row counts, panel hash, false locks |
| label audit | missing next close, invalid price/volume, split-like window, unaffordable slot, excluded/quarantined rows |
| train manifest | dataset SHA, primary cost scenario, threshold search, walk-forward config, replay mode, false locks |
| threshold search | threshold grid, chosen row, train-only fit range, mean/median reward, mean selected count, OOS fit count |
| date/slot ledgers | selected/cash_hold/blocked/replay_unfilled slots, integer shares, costs, net PnL, reward |
| cost scenario summary | zero/base/stress component bp/KRW totals and selected/hold counts |
| replay episode ledgers | replay split/date/policy, feedback source split, selected/hold counts, held-out freeze evidence |
| gate report | verdict, blockers, lineage errors, baseline deltas, D0/D1/D3/D5 status, false locks |
| dashboard evidence | API payload sample, chart/card evidence, screenshot/browser transcript if UI is exercised |

## Gate 기준

| Gate | 기준 | 실패 상태 |
|---|---|---|
| G1 lineage | dataset→train→gate→dashboard parent hashes/row counts match | `NO-GO_CONTROL` or `BLOCKED_INVALID_ARTIFACT` |
| G2 leakage | no future label as feature; no OOS fit | `NO-GO_CONTROL` |
| G3 cost | 23bp primary and 0/46bp sensitivity visible; scalar-only rejected | `NO-GO_CONTROL` |
| G4 baselines | no-trade and shuffle required; RULE/momentum and D3 handled per availability | `NO-GO_BASELINE` / `WATCH` |
| G5 absolute | OOS/test reward after 23bp > 0 | `NO-GO` |
| G6 baseline delta | policy beats shuffle/RULE/D3 where available on identical dates/accounting | `NO-GO_BASELINE` |
| G7 stability | fold/drawdown/worst-window acceptable and not 0bp-only | `NO-GO_RISK` |
| G8 blocker state | D0/D1 visible; promotion/live/paper/profit/model flags false | `WATCH_RESEARCH_ONLY` / `NO-GO_RESEARCH_ONLY` |
| G9 dashboard | GET-only latest evidence; malformed latest fails closed | `BLOCKED_DASHBOARD_EVIDENCE` |

All gates must pass before any stronger research-candidate language. Even then, no live/broker/order/profit readiness claim is allowed.

## Dashboard evidence checklist

`/daily-ohlcv` close-slot card/API must show:

- `RESEARCH_ONLY`, `EXPERIMENTAL_ONLY`, `NO-GO` or `WATCH`;
- `close_to_next_close_research_label` and non-executable Mode A caveat;
- D0 price-basis unknown and D1 universe WATCH;
- 23bp primary, 0bp control, 46bp stress component costs;
- train-only threshold and `oos_rows_used_for_fit=0`;
- selected count, cash_hold count, blocked/unfilled count;
- replay/walk-forward summaries;
- baseline comparison and D3 re-ledger status when applicable;
- run IDs, paths, SHAs, row counts, lineage validation;
- false locks/no-claim labels;
- no POST/PUT/PATCH/DELETE order, broker, account, paper, model-build, profit, or GO control.

Manual refresh is sufficient. Any auto-refresh must remain GET-only evidence refresh.

## Result document rule

After execution, create a new dated result document. It must include exact commands, run IDs, paths, SHAs, costs, split labels, baseline deltas, selected/hold counts, drawdown/fold/cost sensitivity, gate verdict, blockers, and dashboard evidence.

Do not mutate this preregistration after seeing OOS/test results except to append an explicit correction note. Hypothesis or threshold changes require a new preregistration.

## Verification commands after approved execution

```powershell
py -3.11 -m pytest tests/test_stom_rl_daily_close_slot_env.py tests/test_stom_rl_daily_close_slot_dataset.py tests/test_stom_rl_daily_close_slot_train.py tests/test_stom_rl_daily_close_slot_gate.py -q
py -3.11 -m pytest tests/test_daily_ohlcv_dashboard_api.py tests/test_daily_ohlcv_dashboard_tab.py -q
py -3.11 -m pytest tests/test_stom_rl_daily_portfolio_env.py tests/test_stom_rl_daily_rl_gate.py tests/test_stom_rl_daily_walk_forward.py -q
```

Frontend source가 바뀌면:

```powershell
cd webui/v2_src
npm run check
npm run build
```

## 최종 해석 경계

본 연구는 종가 매매 research ledger와 dashboard evidence workflow다. 결과가 좋아도 실거래, 주문, 브로커, 계좌, paper-forward, 수익성 보장, deployable-alpha, model-build readiness, GO로 해석하지 않는다.

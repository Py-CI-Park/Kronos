# Daily Close-to-Next-Close 10-Slot RL Research Design — 2026-07-01

## Verdict

`RESEARCH_DESIGN_ONLY` / `NO-GO_RESEARCH_ONLY` until fresh evidence exists.

Using the current daily OHLCV DB **as-is**, Kronos can build a research-only lane that chooses up to 10 stocks for a close-to-next-close strategy: buy at today's close, sell at the next trading day's close, and score the selected basket after cost. However, this lane must be labelled as research evidence, not live trading, not broker/order readiness, not paper-forward permission, and not a profit claim.

The most important modeling point: with mandatory one-day holding and full exit next close, the problem is closer to a **daily contextual bandit / top-K ranking policy** than a full multi-step portfolio RL problem. It can still be implemented with RL-style policy learning, but simple baselines and supervised/ranking methods must remain first-class controls.

## Source market mechanics: KRX closing auction

KRX's regular session is 09:00–15:30, with continuous auction until 15:20 and a closing auction from 15:20–15:30. KRX describes the opening/closing auction as a periodic call auction: orders are collected for a period and matched at a single price under price/time priority.

Key mechanics for this research design:

1. **Closing auction window**: 15:20–15:30 KST for the regular-session closing auction.
2. **Single-price execution**: the closing auction determines a single closing price.
3. **Randomized close**: KRX can close a periodic call auction at a random time within 30 seconds from the scheduled closing point to deter unfair trading.
4. **VI interaction**: if volatility interruption is triggered during a periodic call auction, the auction can be extended by two minutes.
5. **Backtest caveat**: daily OHLCV contains the final close, but it does not contain auction order book, indicative price, queue priority, partial-fill, or closing-auction volume. Therefore `buy@close` is a research fill assumption, not proof that a real order would have fully filled at that price.

Primary sources:

- KRX trading guide PDF: `https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf`
- KRX periodic call auction principles: `https://global.krx.co.kr/contents/GLB/06/0602/0602020202/GLB0602020202T6.jsp`
- KRX periodic call auction method: `https://global.krx.co.kr/contents/GLB/06/0602/0602010202/GLB0602010202T1.jsp`

## Current Kronos data assumed for this lane

Source DB:

```text
_database/Stock_Database_ohlcv_1day.db
```

Observed current DB summary from the dashboard/API and prior D0 artifacts:

| Item | Current state |
|---|---:|
| Daily tables | 4,727 |
| Total rows | 14,691,020 |
| Date range | 19860415 ~ 20260612 |
| Latest date | 20260612 |
| Latest-date tables | 4,287 |
| Latest coverage fraction | ~90.69% |
| Price basis | `unknown` |
| Price basis status | `UNKNOWN_CONFIRMED` |
| Decision-grade return status | `BLOCKED_UNTIL_PRICE_BASIS_VERIFIED` |

Expected per-symbol columns:

```text
date, open, high, low, close, volume,
상장주식수, 외국인주문한도수량, 외국인현보유수량, 외국인현보유비율,
기관순매수, 기관누적순매수
```

Important inherited blockers:

```text
D0_PRICE_BASIS_NOT_VERIFIED
D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED
```

The user explicitly allowed assuming the DB as-is for research. That is acceptable for exploratory development, but every artifact must preserve the `price_basis=unknown` and `universe WATCH` labels.

## Proposed strategy contract

User-facing hypothesis:

> Each trading day, after forming a daily research signal, choose up to 10 stocks. Allocate a fixed configured capital across 10 slots. Research-fill selected stocks at today's close, exit all selected stocks at the next trading day's close, and score the next-day basket after costs.

Canonical research parameters:

| Parameter | Proposed default |
|---|---:|
| Total capital | user-specified, e.g. `capital_krw` |
| Slot count | 10 |
| Per-slot budget | `capital_krw / 10` |
| Holding period | 1 trading day |
| Entry research fill | today's `close` |
| Exit research fill | next trading day's `close` |
| Primary cost | 23bp round trip |
| Cost sensitivity | 0bp / 23bp / 46bp |
| Quantity model | integer shares, leftover cash recorded |
| Missing next-day label | no trade / blocked row |
| Split-like unknown adjustment window | exclude or flag using existing D0 policy |
| Promotion state | `NO-GO_RESEARCH_ONLY` until D0/D1/D5 clear |

Reward for a selected basket on date `t`:

```text
slot_cash = total_capital / 10
shares_i = floor(slot_cash / close_i_t)
entry_value_i = shares_i * close_i_t
exit_value_i = shares_i * close_i_t+1
gross_pnl_i = exit_value_i - entry_value_i
cost_i = entry_value_i * round_trip_cost_rate
net_pnl_i = gross_pnl_i - cost_i
basket_return = sum(net_pnl_i) / total_capital
```

A fractional-share research variant can be allowed only as a diagnostic baseline. The main Korean equity simulation should use 1-share trading units and record `unfilled_slot_reason=slot_cash_below_close` when the slot budget cannot buy one share.

## Causal timing modes

There are two separate research modes. They must not be mixed.

### Mode A — DB-only close-to-next-close label research

- Uses daily bar fields including today's final close/volume/기관/외국인 fields.
- Selects stocks as if today's final close is available before the entry fill.
- Buys at today's close and sells at next close.
- This is useful for measuring whether end-of-day features contain next-day signal.
- It is **not execution-realistic**, because a real order must be placed during the closing auction before the final close is known.

Required label:

```text
fill_mode = close_to_next_close_research_label
execution_realism = non_executable_upper_bound_without_preclose_features
```

### Mode B — executable closing-auction approximation

- Signal must be formed before the closing auction match, e.g. before or during 15:20–15:30.
- Current daily DB alone is insufficient because it lacks pre-close snapshot, indicative closing price, auction imbalance, queue, and closing auction volume.
- Requires STOM 1-second/tick/orderbook-derived pre-close features or a separate pre-close snapshot dataset.
- Fill remains an approximation unless closing auction fill/volume assumptions are modelled.

Required label:

```text
fill_mode = preclose_decision_to_closing_auction_fill_research_approximation
required_extra_data = preclose_tick_or_orderbook_snapshot
```

Recommended first implementation: **Mode A only**, with an explicit non-executable label. Mode B should be a later research lane once pre-close features exist.

## RL feasibility

### Can RL do this?

Yes, as research. The action is selecting up to 10 symbols from the daily candidate universe, and the reward is the next-day close-to-close basket return after costs.

### Is it really full RL?

For the exact one-day hold/full-exit rule, the environment has little path dependence. Every day is mostly independent:

```text
observe today's features -> choose 10 names -> receive next-day reward -> reset positions
```

This is best framed as:

1. **Contextual bandit**: choose 10 arms from a daily candidate set.
2. **Learning-to-rank / supervised gate**: score symbols, pick top 10, compare to controls.
3. **RL-style policy** only when state includes capital path, drawdown, abstention state, regime state, turnover budgets, or multi-day constraints.

Therefore the first serious lane should compare at least:

- no-trade cash
- random/shuffle top-10
- equal-weight top-10 momentum
- existing D3 rankers
- supervised ranker/classifier
- contextual bandit policy
- RL policy only if it adds non-trivial state/action value

If RL does not beat no-trade, shuffle, and D3 baselines after 23bp, it remains `NO-GO`.

## Existing reusable Kronos pieces

| Existing file/module | Reuse |
|---|---|
| `stom_rl/daily_ohlcv_db.py` | read-only DB access, table/name validation, price-basis blocker, split-like windows |
| `stom_rl/daily_ohlcv_universe.py` | common-equity heuristic universe and quarantine evidence |
| `stom_rl/daily_ohlcv_dataset.py` | daily feature/label construction, close-to-next-close label, chronological split, leakage report |
| `stom_rl/daily_prediction.py` / `daily_ranker.py` | D3 baseline/ranker comparator |
| `stom_rl/daily_portfolio_env.py` | existing research-only environment with `close_to_next_close_research_label` fill assumption |
| `stom_rl/daily_rl_train.py` | tabular-Q style training telemetry, costs, action/reward diagnostics |
| `stom_rl/daily_walk_forward.py` | D5 gate style: folds, no-OOS-retuning, no-trade/shuffle/D3 controls, cost sensitivity |
| `webui/daily_ohlcv_dashboard.py` | API adapter for D0-D9 read-only dashboard surfaces |
| `/daily-ohlcv` dashboard | evidence viewer for datasets, predictions, RL telemetry, walk-forward, registry |

Important mismatch: the current `DailyPortfolioEnv` allows hold/add/sell/reduce over a continuing portfolio. The requested strategy is simpler and stricter: **select up to 10 at close, exit all next close, no multi-day holding**. A new specialized environment is cleaner than overloading the current D4 environment.

Architect review notes for the close-slot lane:

- `DailyPortfolioEnv` appends one new candidate through `buy/add`; it does not select a same-day basket of 10 symbols in one decision.
- Current reward averages held returns, so 1 held name can behave like full exposure; the close-slot lane must compute integer-share `sum(net_pnl_i) / total_capital_krw`, with unused cash and empty/unfilled slots contributing zero PnL.
- Current positions can persist until a later sell/reduce; the close-slot lane must auto-exit after applying `future_return_1d`.
- Missing next-day labels must not become zero-return trades. They should be excluded or fail closed with a label-audit row.
- Close-slot artifacts should include `entry_date`, `exit_date`, `entry_close`, `exit_close`, `total_capital_krw`, `slot_count`, `slot_capital_krw`, source hashes, and matching D2/D3 run ids.

## Proposed new research modules

Recommended names:

```text
stom_rl/daily_close_slot_dataset.py
stom_rl/daily_close_slot_env.py
stom_rl/daily_close_slot_train.py
stom_rl/daily_close_slot_gate.py
```

Generated artifacts:

```text
webui/rl_runs/daily_close_slot_dataset/<run_id>/
webui/rl_runs/daily_close_slot_policy/<run_id>/
webui/rl_runs/daily_close_slot_gate/<run_id>/
```

Durable docs:

```text
docs/stom_daily_close_next_day_rl_prereg_YYYY-MM-DD.md
docs/stom_daily_close_next_day_rl_result_YYYY-MM-DD.md
```

## Proposed environment

Observation per date:

```text
candidate_count
market_regime_proxy
cross_section_score_dispersion
recent_market_return_bucket
recent_market_volatility_bucket
per-symbol feature vector for top N candidates
```

Per-symbol features can start from existing D2 fields:

```text
return_1d
return_5d
volatility_5d
volume_ratio_5d
hl_range
gap_from_prev_close
foreign_holding_ratio
institutional_net_buy
```

Action space options:

1. **Score-and-pick**: policy outputs a score per candidate, choose top 10.
2. **Discrete top-K template**: choose among candidate filters/templates.
3. **Sequential slot fill**: fill slot 1..10 one at a time from a candidate list.

Recommended first action space: **score-and-pick top 10**. It is easier to compare against ranking baselines and avoids huge combinatorial action spaces.

Reward:

```text
basket_net_return_after_23bp
- drawdown_penalty
- turnover_or_unfilled_penalty
- concentration/liquidity penalty if added
```

For the strict one-day strategy, turnover is naturally high because the basket exits every day. Cost must be charged every day for every filled slot.

### Mode A environment contract

The Mode A environment should be deterministic and auditable. Each episode is a chronological sequence of trading dates, but every action has a forced one-day lifecycle:

```text
state_t = features known after date t daily bar is formed
action_t = choose 0..10 codes from candidate set C_t
fill_t = research entry at close_t for each selected code
reward_t = next_close_t+1 basket return after cost and penalties
terminal_trade_t = all selected codes auto-exit at next_close_t+1
state_t+1 = next eligible trading date, no carried position
```

Required environment conditions:

| Condition | Requirement |
|---|---|
| Candidate set | same-date candidates only; preserve six-character string codes |
| Decision time label | `after_current_daily_close_research_only` for Mode A |
| Entry fill | `entry_close` from the same daily row; research-only |
| Exit fill | `exit_close` from the next row of the same symbol table |
| Holding | exactly one trading day, auto-exit after reward |
| Slots | fixed `slot_count=10`; empty slots earn zero |
| Capital | `total_capital_krw` and `slot_capital_krw` recorded in manifest |
| Shares | integer share simulation for the primary ledger |
| Missing labels | exclude/fail closed; never coerce missing next close to zero return |
| Costs | 23bp primary round trip, with 0bp and 46bp sensitivity |
| Upstream blockers | D0/D1 status copied into every run and gate artifact |

Primary reward/accounting formula for the primary integer-share ledger:

```text
slot_cash = total_capital_krw / 10
shares_i = floor(slot_cash / entry_close_i)
entry_value_i = shares_i * entry_close_i
unused_cash_i = slot_cash - entry_value_i
exit_value_i = shares_i * exit_close_i
gross_pnl_i = exit_value_i - entry_value_i
cost_i = entry_value_i * 0.0023
net_pnl_i = gross_pnl_i - cost_i
cash_pnl_i = 0 for unused cash, empty slots, or unaffordable slots
basket_return = sum(net_pnl_i for active slots) / total_capital_krw
reward = basket_return - drawdown_penalty - missing_label_penalty - liquidity_penalty
```

Do not mix this integer-share ledger with a pure `1/10` fractional-return ledger. A fractional-share variant may be emitted as a diagnostic artifact, but the manifest must label it separately and the dashboard must show the integer-share primary result first.

Continuous-improvement research loop:

1. Freeze the candidate universe, features, split, cost model, and baseline list in a preregistration.
2. Train only on `train`; select hyperparameters only inside training or a separately declared validation protocol.
3. Evaluate on `val` and `test` without OOS retuning.
4. Record every selected basket, unfilled slot, rejected candidate, reward component, and source hash.
5. Compare against no-trade, deterministic shuffle, equal-weight top-10, momentum top-10, and frozen D3 baselines on identical dates.
6. Classify failures before changing the policy: leakage, cost sensitivity, fold instability, drawdown, liquidity, D0/D1 blocker, or D3 underperformance.
7. Start a new dated preregistered run for each hypothesis change; never mutate old generated artifacts to improve a result.

Recommended first research policy stack:

| Stage | Policy | Purpose |
|---|---|---|
| B0 | no-trade cash | minimum control |
| B1 | deterministic shuffle top-10 | noise floor |
| B2 | equal-weight momentum top-10 | simple RULE baseline |
| B3 | frozen D3 score top-10 | existing supervised/ranker comparator |
| P1 | contextual bandit score policy | first learnable policy for one-day independent rewards |
| P2 | conservative RL with regime/drawdown state | only if P1 shows stable signal and state adds value |

Promotion remains blocked unless P1/P2 beats controls after 23bp and survives the D5-style gate.

## Liquidity and fill assumptions

Daily OHLCV is not enough to prove closing-auction fills. The research lane should record these fields:

```text
entry_fill_assumption = official_daily_close_research_fill
exit_fill_assumption = next_official_daily_close_research_fill
closing_auction_queue_model = unavailable
partial_fill_model = unavailable
closing_auction_volume = unavailable
liquidity_proxy = daily_volume_only
execution_realism = research_label_only
```

Minimum liquidity filters for DB-only research:

- exclude zero/negative close or volume;
- require `shares >= 1` for each slot;
- optionally require `entry_value <= x% * daily_traded_value`; because closing-auction volume is unavailable, this is only a weak proxy;
- record rejected candidates and reasons.

## Dashboard integration plan

Add a new Daily OHLCV section or visual lane rather than modifying the RL dashboard's research-only guardrails.

Proposed API endpoints:

```text
GET /api/daily-ohlcv/close-slot/latest
GET /api/daily-ohlcv/close-slot/artifacts
GET /api/daily-ohlcv/close-slot/gate/latest
GET /api/daily-ohlcv/charts/close-slot-equity
GET /api/daily-ohlcv/charts/close-slot-selection
```

Dashboard cards:

1. **Strategy contract card**
   - 10 slots, fixed capital, close-to-next-close, 23bp, DB-as-is assumption.
2. **Timing realism card**
   - Mode A non-executable close-label research vs Mode B pre-close auction approximation.
3. **Selection quality card**
   - selected count, unfilled slots, daily basket return, hit rate, turnover, drawdown.
4. **Baseline comparison card**
   - no-trade, shuffle, equal-weight top-10, D3 ranker, supervised, bandit/RL.
5. **Gate card**
   - D0/D1/D3/D5 blockers, cost sensitivity, fold consistency, `NO-GO` reasons.
6. **Artifact lineage card**
   - source DB fingerprint, universe manifest SHA, dataset manifest SHA, policy artifact hash.

Hard dashboard labels:

```text
RESEARCH_ONLY
NO-GO until gates pass
close_to_next_close_research_label
not broker/order/live/paper-forward
price_basis unknown
universe WATCH
```

## Acceptance gates before any stronger claim

A close-slot policy must pass all of these before it can even be considered a research candidate:

1. D0/D1 blockers visible, or independently resolved.
2. No feature/label leakage: features available at the declared decision time.
3. Chronological train/val/test split with purge/embargo.
4. No OOS retuning.
5. Baseline comparison against no-trade, shuffle, equal-weight top-10, frozen D3.
6. 23bp primary cost and 46bp stress remain visible.
7. Integer-share capital simulation with leftover cash and unfilled slots recorded.
8. Fold consistency, max drawdown, turnover/cost, and worst-fold checks.
9. Generated artifacts immutable under `webui/rl_runs/` with source hashes.
10. Dashboard read-only API; no POST/PUT/DELETE order surface.

## Recommended implementation sequence

### Step 1 — preregister

Create a preregistration doc defining:

- Mode A only;
- 10 slots;
- fixed capital parameter;
- no OOS retuning;
- primary cost 23bp;
- baselines and failure rules;
- DB-as-is caveat and D0/D1 labels.

### Step 2 — close-slot dataset artifact

Create `daily_close_slot_dataset.py` that consumes D2-style features but emits a close-slot-specific panel:

```text
date, code, close, next_close, future_return_1d,
slot_affordability, daily_value_proxy, features..., split, blockers
```

### Step 3 — baselines first

Before RL, implement:

- no-trade cash;
- random/shuffle top-10;
- equal-weight top-10 by momentum;
- D3 score top-10;
- simple supervised score top-10.

### Step 4 — contextual bandit / RL research

Only after baselines exist, add a policy learner:

- score candidates;
- choose top 10;
- train only on train split;
- freeze before val/test;
- write telemetry and selected baskets.

### Step 5 — D5-style gate

Evaluate with forward folds, no retuning, cost ladder, drawdown, turnover, baseline deltas, and reject if the policy only wins under cherry-picked folds or 0bp.

### Step 6 — dashboard lane

Expose read-only artifacts and charts under `/daily-ohlcv`. Keep all guardrails and fail-closed behavior.

## Current answer to the user question

Yes, it is possible to develop a research-only RL/bandit lane for selecting 10 close-buy candidates using the daily DB as-is. The current DB already contains enough daily fields to create close-to-next-close labels and candidate features, and existing Kronos code already has much of the D0-D5 evidence machinery.

But the first correct implementation should not start by claiming "RL model success." It should start with a preregistered 10-slot close-to-next-close research contract, then baselines, then a contextual bandit/RL policy, then a D5-style gate and dashboard evidence surface.

The current expected status after initial implementation should remain:

```text
RESEARCH_ONLY
NO-GO until D0/D1/D3/D5 and close-slot gates pass
```

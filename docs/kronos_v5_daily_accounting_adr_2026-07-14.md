# Kronos V5 daily close-slot accounting ADR — 2026-07-14

## Status

Accepted for research-only accounting. This ADR does not authorize live, broker, account, order, paper-forward, model-build, profitability, GO, or readiness claims.

## Decision

The V5 close-slot accounting horizon is `CS_T_CLOSE_TO_T1_CLOSE_V1`: enter at the current daily close, explicitly liquidate at the next daily close, and carry no position beyond that terminal mark.

Canonical research sizing is 1,000,000 KRW total capital, at most two codes, 25% capital per code, and the remaining 50% held as cash. Codes are preserved as zero-padded six-digit strings and ordered ascending by that string for the canonical accounting oracle. Daily close-slot replay adapter accounting preserves source-exact string/`Decimal` marks through normalization; display floats may be emitted for compatibility, but share floors and cash/cost calculations consume the source-exact marks when present.

## Cost schedules

| scenario | buy commission | buy slippage | sell commission | sell tax | sell slippage | total |
|---|---:|---:|---:|---:|---:|---:|
| `zero_control_0bp` | 0bp | 0bp | 0bp | 0bp | 0bp | 0bp |
| `base_23bp` | 1.5bp | 0bp | 1.5bp | 20bp | 0bp | 23bp |
| `stress_46bp` | 1.5bp | 11.5bp | 1.5bp | 20bp | 11.5bp | 46bp |

Costs are component charges applied once: buy commission/slippage on entry notional, sell tax/commission/slippage on liquidation value. The implementation must not additionally apply a scalar round-trip haircut.

## Equations and rounding

All money arithmetic uses `Decimal` and `ROUND_HALF_UP`.

- money quantum: `0.000001` KRW
- ratio/reward quantum: `0.000000000001`
- entry buy reserve: `entry_close * (1 + (buy_commission_bp + buy_slippage_bp) / 10000)`
- shares: `floor(slot_cash / entry_buy_reserve)`
- notional: `shares * entry_close`
- liquidation value: `shares * next_close`
- gross PnL: `liquidation_value - notional`
- cost: sum of the five component costs above, each rounded to money quantum
- net PnL: `gross_pnl - cost`
- terminal NAV: `capital + sum(net_pnl)`
- reward: `sum(net_pnl) / capital`

Rows with missing/nonfinite marks, unsupported horizons, duplicate cost application, or negative/non-preservable six-digit codes fail closed.

Public money/ratio serialization canonicalizes any quantized zero to positive zero, so values that round from a small negative magnitude do not publish `-0.0`.

## Verification design

`stom_rl/v5_accounting.py` is the production Decimal oracle. `tests/oracles/v5_close_slot_oracle.py` is an independent test-only Decimal oracle and imports no production accounting helper. `tests/test_kronos_v5_close_slot_accounting.py` compares every ledger row and summary cash/lot/cost/NAV/reward field for 0bp, 23bp, and 46bp schedules, plus fail-closed adversarial cases. Adapter-boundary oracle inputs are hand-authored rather than produced by production normalization and cover source-exact boundary share flooring, replay slot/code order, and negative-zero public serialization.

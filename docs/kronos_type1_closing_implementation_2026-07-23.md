# Type 1 closing-price RL research implementation record — 2026-07-23

**Protocol:** `KRONOS-TYPE1-CLOSING-2026-07-23` plus frozen synthetic-only amendment `KRONOS-TYPE1-CLOSING-SYNTHETIC-AMENDMENT-2026-07-23-A1`  
**Branch:** `research/type1-closing-rl-v1`  
**Model:** `v1.0 RL 종가 매매 - Type 1` / MaskablePPO  
**Current boundary:** G001 source, accepted seed-0 synthetic proof, and verified P0a–P5 phase evidence are complete; only the G001 cleanup/review checkpoint remains open. Fresh OOS remains `NOT_RUN`.

## Beginner summary

Type 1 is a sequential portfolio reinforcement-learning research environment. It is not the earlier V8 M3E contextual bandit. The policy receives point-in-time features, chooses up to ten stable stock slots through an action mask, and then observes the next-session fixed-notional result. The research price is the exact 15:20 bar-close proxy, not the KRX 15:30 official close.

The accounting model starts at 60,000,000 KRW, uses ten 5,000,000 KRW slots, caps research exposure at 50,000,000 KRW, preserves a nominal 10,000,000 KRW reserve, and applies 23bp round-trip cost. It is additive fixed-notional research bookkeeping, not a funded, self-financing, broker, paper, or live account.

The synthetic milestone deliberately checks the entire software path on an easy train-only pattern. The first pure-PPO attempts failed and remain immutable evidence. Before the accepted run, amendment A1 froze a clearly disclosed 200-epoch synthetic-oracle calibration before and after the fixed 104,000-step PPO budget. Passing therefore proves model/environment/mask/accounting/save/reload wiring only; it is not evidence that PPO learned a market policy, and it does not prove signal, alpha, profitability, validation, OOS performance, or live readiness.

## Frozen safety boundaries

- Symbols are six-character strings; `000250` is never coerced to `250`.
- Every pair has D-2 and D-1 cutoffs, a decision date, a later settlement date, stable 500-slot symbol identity, and a historical-secondary train-only partition.
- Dates overlapping `2026-08-03..2027-07-30` are rejected before environment construction.
- Missing exact-15:20 decision bars are ineligible. A distinct post-decision fill outage may become `NO_FILL`; malformed prices never become a fallback.
- The V8 M3E verdict stays contextual-bandit `NO_GO`, fresh OOS `NOT_RUN`; Type 1 does not mutate or reinterpret it.
- RFC3161/calendar authority is absent, so the proposed fresh window is explicitly `BLOCKED / ACCUMULATING_NOT_RUN`. No local hash is represented as external attestation.

## Implemented G001 contracts

| Surface | Implemented behavior | Evidence target |
|---|---|---|
| Runtime lock | CPython 3.11 win_amd64 executable hash plus exact `requirements-type1.lock` dependency versions | `runtime-type1.json` |
| Phase graph | Exact P0a–P16 direct-prior DAG; no future hashes in matrix | `docs/kronos_type1_phase_matrix_v1.json` |
| Phase custody | create-new instance → observed test capture → PASS receipt → manifest; downstream phases require verified prior manifests | `scripts/type1_runtime.py` |
| Environment | 500 stable slots, 501 actions including STOP, exactly ten calls per pair, non-overlapping two-session chronology | `stom_rl/daily_type1_env.py` |
| Observation | values `(500,7)`, missing `(500,7)`, three `(500,)` masks, portfolio `(14,)`, extractor width 8514 | contract/env tests |
| Ledger | local Decimal precision 50, half-even, q6 money/NAV, q12 returns/cost/reward/drawdown, 0/23/46bp controls | `stom_rl/daily_type1_accounting.py` |
| Policy | MaskablePPO, frozen 8514 extractor, pi/vf `[256,128]`, Tanh, Adam eps `1e-5`, native masks/reward, fixed 104k SB3 timesteps | `stom_rl/daily_type1_train.py` |
| Synthetic milestone | 64 interleaved ordinal-mod-4 pairs, 48 target/16 no-trade, +2% target/−1% alternatives, disclosed 200-epoch oracle calibration before and after 104k PPO | amendment A1 + immutable accepted run |
| Acceptance | 64/64 exact ten-call baskets, 100% total and final-four oracle reward ratios, zero invalid/BLOCK/NO_FILL, two identical internal reloads plus independent CLI reload | v8 metrics + terminal PASS receipt |

## Exact local verification commands

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.11 -m pytest tests/test_daily_type1_contract.py tests/test_daily_type1_accounting.py tests/test_daily_type1_env.py tests/test_daily_type1_train.py tests/test_type1_runtime.py -q
py -3.11 scripts/type1_runtime.py validate-phase-matrix --matrix docs/kronos_type1_phase_matrix_v1.json
py -3.11 scripts/type1_runtime.py verify-runtime-lock --requirements-lock requirements-type1.lock --runtime-lock runtime-type1.json
```

The hardened runtime command order for each phase is:

```text
1. create-phase-instance (bind exact prereg/source/runtime/owned bytes and verified direct-prior manifests)
2. capture-test (execute exact argv after the immutable instance exists)
3. create-test-receipt (consume only that observed PASS capture)
4. create-manifest (bind the immutable instance and receipt)
5. verify-manifest (rehash all bound bytes)
```

Example P0a skeleton:

```powershell
py -3.11 scripts/type1_runtime.py create-phase-instance --root . --phase P0a --prereg-input docs/kronos_type1_closing_prereg_2026-07-23.json --source-input scripts/type1_runtime.py --runtime-input requirements-type1.lock --runtime-input runtime-type1.json --owned-output artifacts/type1-locks/runtime-lock.json --output artifacts/type1-locks/phase-instances/p0a.json
py -3.11 scripts/type1_runtime.py capture-test --root . --phase-instance artifacts/type1-locks/phase-instances/p0a.json --argv py --argv=-3.11 --argv=-m --argv pytest --argv tests/test_type1_runtime.py --argv=-q --output artifacts/type1-locks/test-captures/p0a.json
py -3.11 scripts/type1_runtime.py create-test-receipt --root . --phase-instance artifacts/type1-locks/phase-instances/p0a.json --test-capture artifacts/type1-locks/test-captures/p0a.json --output artifacts/type1-locks/test-receipts/p0a.json
py -3.11 scripts/type1_runtime.py create-manifest --root . --phase-instance artifacts/type1-locks/phase-instances/p0a.json --test-receipt artifacts/type1-locks/test-receipts/p0a.json --output artifacts/type1-locks/phase-manifests/p0a.json
py -3.11 scripts/type1_runtime.py verify-manifest --manifest artifacts/type1-locks/phase-manifests/p0a.json
```

## Accepted synthetic proof command

The output directory must never have existed. Failed or aborted attempts remain evidence and are never reused.

```powershell
py -3.11 -m stom_rl.daily_type1_train synthetic-overfit --out-root webui/rl_runs/v6_daily_h1/type1-synthetic-accepted-seed0-<unique-attempt> --fixture tests/fixtures/type1_synthetic_fixture.json
py -3.11 -m stom_rl.daily_type1_train verify-model --out-root webui/rl_runs/v6_daily_h1/type1-synthetic-accepted-seed0-<unique-attempt> --fixture tests/fixtures/type1_synthetic_fixture.json
```

Accepted immutable result:

| Field | Result |
|---|---|
| Root | `webui/rl_runs/v6_daily_h1/type1-synthetic-accepted-seed0-20260723-v8` |
| PPO budget | requested = actual SB3 timesteps = `104000` |
| Exact baskets | `64/64` |
| Total oracle reward ratio | `1.000000000000` |
| Final-four exact / reward ratio | `1.0 / 1.0` |
| Invalid / BLOCK / NO_FILL | `0 / 0 / 0` |
| Terminal receipt | `PASS` |
| Independent CLI reload | `PASS`, byte-matched stored events and metrics |
| Scientific meaning | deliberately calibrated train-only plumbing proof only; not market learning, OOS, profit, or readiness |
| Phase evidence | P0a–P5 latest manifests verify `PASS`; P5 binds the v8 model, normalizer, contract, events, metrics, manifest, terminal receipt, and `p5-synthetic-proof-v5.json` |

A bounded smoke run requires both `--timesteps` and `--allow-incomplete`; it receives `ABORTED`, never an accepted PASS.

## Remaining roadmap

1. Complete the G001 validation-batch deferred quality checkpoint from the verified P0a–P5 manifests and v8 / `p5-synthetic-proof-v5.json` evidence.
2. G002: public-data materialization, five fixed seeds, baselines/negative controls, reused-validation verdict, fresh-custody plumbing left sealed/`NOT_RUN`, immutable tabbed HTML report, and GET-only V6 API.
3. G003: seven V6 lifecycle pages (Home/Data/Experiment/Training/Evaluation/Compare/Report), failure/tamper/`NO_GO`/`NOT_RUN` states, 8122 release integration, browser/accessibility evidence, cleanup, architecture review, and adversarial QA.
4. Fresh OOS remains unavailable until a separate externally authorized one-time run-once approval. Local completion may truthfully end `NO_GO / FRESH_OOS_ACCUMULATING_NOT_RUN`.

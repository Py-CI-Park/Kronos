# Kronos 90→95 Fresh HEAD Baseline (2026-07-11)

> **This supersedes the provisional 42/100.** Plan Todo 5 requires the provisional
> figure to be replaced by scorer-generated evidence at the current clean
> integration SHA. The v1 scorer, which demands five real checks per criterion
> (contract + happy test + failure test + runtime/canonical evidence +
> independent review with an evidence hash), yields a **6/100** honest baseline.
> The provisional 42 was optimistic management evidence; it is not preserved for
> narrative consistency. Historical 82/100, 100/100, 124-test, 144/2, and
> screenshot claims are context only and were fed into nothing here.

## Provenance

| Field | Value |
| --- | --- |
| Commit | `51e35ead3b518abb590b4543063aebf9366b1e7a` (`dashboard-v3`) |
| Working tree | clean at measurement time |
| Python | 3.11.9 |
| Node / npm | v22.14.0 / 11.12.1 |
| Scorecard | `docs/kronos_90_to_95_scorecard_v1.json` (schema 1.0.0) |
| Scorer | `scripts/score_kronos_90_to_95.py` |
| Evidence bundle | `.omo/evidence/task-5-baseline/` |

## Measurements (commands, exits, hashes)

| Measurement | Command | Result |
| --- | --- | --- |
| Wave-0 contract suites | `py -3.11 -m pytest tests/test_kronos_90_to_95_scorecard.py tests/test_stom_rl_run_registry_promotion.py tests/test_daily_ohlcv_authority_selection.py tests/test_stom_rl_events_contract.py tests/test_dashboard_v3_execution_boundaries.py -q` | **84 passed** |
| Scoped RL/dashboard regression | `py -3.11 -m pytest tests/test_stom_rl_dashboard_api.py tests/test_stom_rl_dashboard_tab.py tests/test_daily_ohlcv_dashboard_api.py tests/test_v2_route.py tests/test_v2_dist_marker.py -q` | **78 passed, 2 skipped** |
| Frontend check | `npm run check` (webui/v2_src) | exit 0 — 274 files, **0 errors, 5 warnings** (`npm_check.txt` sha256 `4144447b…`) |
| Frontend build | `npm run build` | exit 0 — built 44s (`npm_build.txt` sha256 `12b215eb…`) |
| Dependency audit | `npm audit --json` | **1 high, 5 moderate, 0 critical** (`npm_audit.json` sha256 `f4158ee5…`) |
| Python static | `py -3.11 -m py_compile` (Wave-0 changed files) | 0 errors |
| Scorer reproducibility | scored twice | **byte-identical** |
| LSP daemon | — | not separately invoked this pass; static = py_compile + svelte-check. LSP repair = Todo 22. |
| Critical-page browser capture | — | **NOT captured** (needs a running server); all A/B `runtime_evidence` checks remain FAIL until Todo 12/23. |

## Score

| Category | Score | Gate-90 floor | Gate-95 floor |
| --- | ---: | ---: | ---: |
| A Evidence truth | **0 / 20** | 19 | 19 |
| B UI/performance/accessibility | **0 / 20** | 18 | 19 |
| C Research engineering | **0 / 20** | 17 | 19 |
| D Research integrity/reproducibility | **2 / 20** | 18 | 19 |
| E Release/security/quality | **4 / 20** | 18 | 19 |
| **Total** | **6 / 100** | ≥90 | ≥95 |

- **Gate 90: FAIL. Gate 95: FAIL.**
- Separate outputs: dashboard/release = 4/60; research-pipeline = 2/40.
- **Model verdict: NO-GO** (separate; no model has cleared any gate). This does not subtract from — nor add to — the engineering score.
- Hard caps active: **none** (all tests/build pass, clean tree, no fabrication, no frozen-file violation, no alpha claim made).

## The six credited checks (only fresh artifacts count)

| Check | Basis |
| --- | --- |
| `E1.contract` | pytest suites + `webui/v2_src` check/build scripts are wired and runnable |
| `E1.happy_test` | 84 contract + 78 scoped pytest pass; `npm run check` exit 0; `npm run build` exit 0 |
| `E1.runtime_evidence` | real build/test logs + hashes at this SHA (`npm_build.txt`, `npm_check.txt`, `redteam/*_pytest.txt`; no JUnit XML this pass — LSP/JUnit are Todo 22 scope) |
| `E4.happy_test` | clean tree; `.omo/evidence` git-ignored; Todo-4 verifier `clean_tree` gate passes post-commit |
| `D4.contract` | `run_registry.promote_run` — explicit, hash+size-validated, no-partial-write promotion (`bea5b23`) |
| `D4.happy_test` | `test_stom_rl_run_registry_promotion.py` proves promotion + fail-closed paths; G001 scorer forbids alpha bonus |

> **Conservative under-crediting is deliberate.** `E4.contract` (clean tree +
> source/generated separation + a current dated handoff) is left FALSE even
> though the tree is clean and generated evidence is isolated, because the
> "current dated handoff" it refers to is the Todo-25 completion handoff, not
> this baseline. Under-crediting can only lower the score, never inflate it.

## Point-loss ledger (every lost point mapped to its owning todo)

| Criterion | Score | Lost | Owning todo(s) | Why lost at baseline |
| --- | ---: | ---: | --- | --- |
| A1 lifecycle LIVE/STALE/REPLAY | 0/5 | 5 | 6 | UI still derives LIVE from `polling && events.length>0` |
| A2 action availability + metric units | 0/5 | 5 | 7 | `rlRows.ts` still coerces null→0/HOLD; units unlabelled in UI |
| A3 latest/today/OOS authoritative | 0/5 | 5 | 8 | dashboard headline not yet wired to the authority/OOS contract |
| A4 selected verdict/blockers visible | 0/5 | 5 | 8 | verdict/blocker/seed/split/freshness not surfaced per selected run |
| B1 responsive + CJK | 0/5 | 5 | 10 | no measured 375/768/1280×light/dark fit; no captures |
| B2 WCAG AA + keyboard + chart alt | 0/5 | 5 | 10 | svelte-check shows 5 a11y/CSS warnings; no axe/keyboard proof |
| B3 independent per-card states | 0/5 | 5 | 9 | no request-race/abort handling; monolithic hydration |
| B4 latency targets | 0/5 | 5 | 9 | no timing script/JSON results captured |
| C1 close-slot honest CLI | 0/5 | 5 | 15 | buy-cost reservation, tie-break, honest identity not done |
| C2 daily R3b SB3 adapter/path | 0/5 | 5 | 16,17,18 | adapter + 5k smoke + ≥200k path not built |
| C3 R5 attribution + reconstruction | 0/5 | 5 | 13 | pretrained zero-shot comparison + reconstruction not run |
| C4 registry/R6/R7 consumers | 0/5 | 5 | 19,21 | R6 sweep, Aim, rliable not built on authoritative seeds |
| D1 prereg + 23bp/0/46 + purge/embargo | 0/5 | 5 | 16,17,18 | per-experiment prereg/control validation not produced |
| D2 baselines + shuffle/negative controls | 0/5 | 5 | 15,17,18 | full baseline/control tables not computed |
| D3 ≥3-seed stability + bootstrap CI | 0/5 | 5 | 18,19 | multi-seed sweep + rliable uncertainty not run |
| D4 explicit promotion, preserved NO-GO | **2/5** | 3 | 2 (partial), 18,19 | promotion contract + test done (G002); NO-GO-audit + runtime promotion + review pending |
| E1 green tests/build/static | **3/5** | 2 | 22,24 | failure-path artifact + independent review pending |
| E2 trusted-local security boundary | 0/5 | 5 | 11 | CORS unrestricted; no path/resource bounds (Gate-A pending) |
| E3 dependency advisories | 0/5 | 5 | 11,22 | 1 high + 5 moderate present; no disposition |
| E4 clean release + final reviews | **1/5** | 4 | 24,25 | clean tree only; final four + two visual reviews pending |

## Reproducibility

`py -3.11 scripts/score_kronos_90_to_95.py --evidence .omo/evidence/task-5-baseline/baseline_evidence.json`
returns byte-identical JSON on repeat runs (`baseline_scored.json`). Removing any
one credited artifact drops its check to 0 rather than inheriting historical
credit — the scorer rejects a passed check that cites no evidence.

## Exit conditions

Gate 90 requires total ≥90 with floors A≥19/B≥18/C≥17/D≥18/E≥18 (Todo 20 decision).
Gate 95 requires total ≥95 with every category ≥19 (Todo 25 decision). From this
6/100 baseline, Waves 1–3 (Todos 6–25) own the remaining 94 points; the two
gate decisions are the only places an overall pass may be declared.

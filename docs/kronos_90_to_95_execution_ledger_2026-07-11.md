# Kronos 90→95 Execution Ledger (2026-07-11)

> **Authoritative execution-boundary record for plan Todo 4.** This ledger, plus
> `scripts/verify_dashboard_v3_execution_boundaries.py` and
> `tests/test_dashboard_v3_execution_boundaries.py`, locks branch ancestry, file
> ownership, dependency order, generated-evidence roots, merge gates, and the
> narrow `webui/app.py` Gate-A exception. It performs **no** product-code
> mutation and does **not** edit `webui/app.py`.

## Integration head and base

| Field | Value |
| --- | --- |
| Branch | `dashboard-v3` |
| Integration HEAD (at ledger time) | `52612c806f6c6e4740703e5f42f8ca755d3b1d05` |
| Verified integration base | `044b5468be2baa11ef451da32ff3999c7c8ab83b` (`044b546`) |
| Base is ancestor of HEAD | yes (`git merge-base --is-ancestor 044b546 HEAD`) |
| Upstream tracking | none configured (publication deferred to Todo 25, user-approved) |

The base commit `044b546` and every commit added by this program (`e73d555`
plan → `46770ba` G001 → `bea5b23` G002 → `52612c8` G003 → this ledger) form a
single linear ancestry on `dashboard-v3`. No development occurs on any other
branch or worktree.

## Branch ancestry (archival proof)

Every branch below was verified to be an **ancestor of HEAD** (fully merged into
`dashboard-v3`), so treating it as archival is truthful. A branch that is NOT an
ancestor must never be called archival nor used as a base.

| Branch | Ancestor of HEAD | Disposition |
| --- | --- | --- |
| `master` | yes | archival; publication target for the final PR only |
| `dashboard-remodel` | yes | archival |
| `feature/stom-rl-lab` | yes | archival |
| `feature/dashboard-research-command-center` | yes | archival (also checked out in a second worktree, below) |
| `review/daily-ohlcv-rl-core` | yes | archival |
| `review/dashboard-backend-api` | yes | archival |
| `review/dashboard-frontend-dist` | yes | archival |
| `review/dashboard-frontend-src` | yes | archival |
| `review/research-docs-governance` | yes | archival |
| `research/deeprl-feasibility` | yes | archival |
| `research/rule-strategy` | yes | archival |

Diverged / non-archival (do NOT base work on these):
`backup/pre-korean-commit-messages-20260507-103421` is **diverged** (not an
ancestor); it is a backup, never a development base.

### Worktrees

```
D:/Chanil_Park/Project/Programming/Kronos                         52612c8 [dashboard-v3]   <- work here
D:/Chanil_Park/Project/Programming/Kronos_market_regime_maturity  f164a92 [feature/dashboard-research-command-center]  <- DO NOT develop here
```

The second worktree is on an archival branch. It must not be used for any
execution in this program.

## Permitted purpose branches

Fork only these from the latest verified `dashboard-v3` integration head; merge
back only after the lane gate passes:

`fix/dashboard-v3-evidence-truth`, `fix/dashboard-v3-responsive-a11y`,
`fix/dashboard-v3-local-security`, `research/kronos-r5-results`,
`feature/daily-close-sb3-r3b`, `research/daily-close-r4-honesty`,
`feature/rl-governance-r6-r7`, `release/dashboard-v3-95`.

Wave-0 foundation goals (Todos 1–5) land directly on `dashboard-v3` because
every later lane forks from them.

## Frozen-file ownership

| Path | Ownership | Rule |
| --- | --- | --- |
| `webui/app.py` | **GATE_A_ONLY** | No edit without an explicit user Gate-A approval immediately before the edit, and only within the allowlist below. Denial routes work through non-frozen adapters/config; no route additions. |
| `webui/rl_dashboard_tables.py` | **FROZEN** | No edit. Route freshness/authority through `rl_dashboard_runs.py`/`rl_dashboard_files.py`/run metadata. |
| `webui/v2/__init__.py` | **FROZEN** | No edit. |
| `stom_rl/rl_events.py` | **SCHEMA_FROZEN** | No `SCHEMA_VERSION` change. Additive `info` metadata and run-level defaults ARE permitted (already exercised by Todo 3). |

> **Wording reconciliation (resolves the Todo-4 shorthand).** Plan Todo 4 prose
> (`docs/kronos_90_to_95_completion_master_plan_2026-07-11.md:183`) says "keep …
> `stom_rl/rl_events.py` frozen." The authoritative frozen-file table (plan line
> 56) and this ledger define it precisely as **schema-frozen** — additive `info`
> metadata is permitted with `SCHEMA_VERSION` unchanged. Todo 3 (`52612c8`)
> complied. F1/F4 final audits MUST use the schema-frozen definition and not
> raise a false frozen-file violation for that additive change.

## Gate-A allowlist (webui/app.py)

Todo 11 may edit **only** these regions, under a separate explicit user approval
requested immediately before the edit. Line numbers are on HEAD `52612c8`. Any
diff line outside every range fails the diff-guard in the verifier.

| Region | Lines | Permitted change |
| --- | ---: | --- |
| `cors_restriction` | 399 | restrict `CORS(app)` to configured loopback origins |
| `load_data_path_containment` | 2070–2131 | constrain `/api/load-data` `file_path` to approved data roots |
| `predict_resource_bounds` | 2133–2352 | cap `/api/predict` `lookback`/`pred_len`/`sample_count`; contain `file_path` |
| `load_model_bounds` | 2355–2392 | bound `/api/load-model` heavy model action |
| `debug_default_off` | 2519–2521 | confirm debug defaults off (`KRONOS_WEBUI_DEBUG`) |

Existing safe patterns to preserve (not weaken): docs path-containment
`_safe_wiki_path` (2434–2446) and the debug-off default (2520). No new routes.

### Route / contract snapshot (pre-Gate-A)

| Field | Value |
| --- | --- |
| `webui/app.py` route count | 108 |
| routes sha256 | `89213b31ff4d28af509a53ffc4826771c08a79c1c14172b5f2768e05d49e0f02` |
| file sha256 | `fd4f38a31a7c9516a34aa8052e6ce2001f1f59de344e2549506edbc29bf52014` |

Any Gate-A edit must re-snapshot and prove the route set is unchanged (routes
sha256 stable) — only in-function security wiring may change.

## Generated-evidence roots

`.omo/evidence/` is git-ignored session evidence (per `.gitignore:95`). Nothing
under it is committed. Canonical promotion of any artifact is explicit,
hashable, size-bounded, and verdict-labeled (Todo 2 contract).

## Dependency order and merge gates

Execution follows the plan's dependency matrix (Todos 1→25). A lane merges to
`dashboard-v3` only after: a clean-tree assertion, `merge-base --is-ancestor`
of the current integration head, the lane's targeted gate (tests/build/runtime/
security/review as applicable), and — for any `webui/app.py` change — a passing
Gate-A allowlist diff-guard. The final release integration and publication
(Todo 24–25) wait for the user's explicit approval.

## Verifier

`scripts/verify_dashboard_v3_execution_boundaries.py` reproduces every check
above and exits non-zero if any boundary gate fails (clean tree, expected
branch, base-is-ancestor, all-archival-are-ancestors, app.py-within-Gate-A).
`tests/test_dashboard_v3_execution_boundaries.py` covers the allowlist
diff-guard (allowed change passes; any out-of-range hunk fails), ancestry, and
the frozen-file ownership records.

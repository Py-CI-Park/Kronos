# Kronos 90->95 Scorecard v1 (human-readable rubric)

> Machine source of truth: `docs/kronos_90_to_95_scorecard_v1.json` (schema 1.0.0).
> Scorer: `scripts/score_kronos_90_to_95.py`. Base: `dashboard-v3@044b546`.
> This document is generated to mirror the JSON; edit the JSON and regenerate, never hand-edit divergently.

## Scoring model
- 20 criteria (A1..E4), each with exactly 5 criterion-specific binary one-point checks.
- Criterion score = integer 0-5 (passed checks). Category = integer 0-20. Total = integer 0-100.
- No PARTIAL, no discretionary rounding, no alpha bonus. A passed check MUST cite an evidence reference.

## Fixed check kinds
- `contract` — contract/implementation exists
- `happy_test` — happy-path automated test passes
- `failure_test` — failure-path automated test passes
- `runtime_evidence` — real runtime/canonical evidence captured
- `independent_review_hash` — independent review plus evidence hash

## Three separate outputs
- **dashboard_release**: categories A, B, E (max 60, contributes to gate).
- **research_pipeline**: categories C, D (max 40, contributes to gate).
- **model_verdict**: unscored; values ['GO', 'WATCH', 'NO-GO', 'INCONCLUSIVE', 'NON_IMPROVING']. Separate verdict; contributes zero engineering points; positive alpha earns no bonus.

## Categories, floors, and gates
| Cat | Name | Max | Gate-90 floor | Gate-95 floor |
| --- | --- | ---: | ---: | ---: |
| A | Evidence truth | 20 | 19 | 19 |
| B | UI/performance/accessibility | 20 | 18 | 19 |
| C | Research engineering | 20 | 17 | 19 |
| D | Research integrity/reproducibility | 20 | 18 | 19 |
| E | Release/security/quality | 20 | 18 | 19 |

Gate 90: total >= 90, all floors met, no active hard cap capping below 90.
Gate 95: total >= 95, all floors met, no active hard cap capping below 95.

## Hard caps
| Cap id | Caps below | Description |
| --- | ---: | --- |
| `failed_test_or_build` | 90 | any failed test or build |
| `p0_evidence_fabrication` | 90 | P0 evidence fabrication |
| `missing_required_oos_or_control` | 90 | missing required OOS/control evidence |
| `unapproved_frozen_or_api_change` | 90 | unapproved frozen-file/API change |
| `dirty_release_tree` | 90 | dirty release tree |
| `cherry_pick_or_trainval_as_oos` | 95 | cherry-picking or presenting train/val as OOS |

## Criteria and their five binary checks
### A1 (A) — Freshness-aware run lifecycle status
Required evidence: API fixture + live browser transition capture

- **A1.contract** — Run discovery/detail derives LIVE only from an explicit running state plus an advancing event file within two poll intervals; finished/stale/replay runs are typed COMPLETED/STALE/REPLAY, never LIVE.
- **A1.happy_test** — Automated test proves a running, advancing stream renders RUNNING then deterministically transitions to COMPLETED.
- **A1.failure_test** — Automated test proves a static historical JSONL (rows present, no advance) renders STALE/REPLAY and never LIVE.
- **A1.runtime_evidence** — Live browser capture records at least two advancing steps and the RUNNING->COMPLETED/STALE transition on the real built surface.
- **A1.independent_review_hash** — Independent reviewer confirms no polling/row-presence/fetch-time path can mark LIVE, and the API fixture + capture bundle hash is recorded.

### A2 (A) — Explicit action availability and metric kind/unit
Required evidence: schema/adapter tests + populated UI capture

- **A2.contract** — Adapters preserve null action as NOT_RECORDED/-- and carry explicit reward_kind/reward_unit/equity_kind/equity_unit; no null-to-zero/HOLD coercion exists.
- **A2.happy_test** — Automated test proves a stream declaring units renders the declared reward/equity kind and unit correctly.
- **A2.failure_test** — Automated test proves a null-action row renders NOT_RECORDED and a cross-unit overlay (NAV vs KRW) is rejected/separated.
- **A2.runtime_evidence** — Populated UI capture shows NOT_RECORDED and declared units on real data through the built surface.
- **A2.independent_review_hash** — Independent reviewer confirms schema/adapter tests plus UI capture, and records the evidence bundle hash.

### A3 (A) — Authoritative test-OOS latest/today selection
Required evidence: isolated-root API tests + canonical/smoke failure scenario

- **A3.contract** — latest/today selection uses explicit authority/status/completion (mtime only as final tie-break), test OOS is primary, and disposable smoke cannot become production latest.
- **A3.happy_test** — Isolated-root API test proves a canonical test-OOS run wins latest and today matches date/policy/split/authority.
- **A3.failure_test** — Isolated-root API test proves a newer disposable smoke or older/first-aggregate row cannot steal latest/primary.
- **A3.runtime_evidence** — Canonical-vs-smoke scenario on the real surface shows the authoritative test-OOS headline, not the smoke.
- **A3.independent_review_hash** — Independent reviewer confirms isolated-root tests and the canonical/smoke scenario, recording the bundle hash.

### A4 (A) — Selected-run verdict, blockers, and freshness visibility
Required evidence: selected-run browser capture + payload assertion

- **A4.contract** — Selected-run payload surfaces verdict, the full API blocker list, D0/D1/D5, cost, seed, split, and artifact freshness without hardcoded counts/text.
- **A4.happy_test** — Automated payload assertion proves verdict/blockers/seed/split/cost/date/artifact-age are present for a selected run.
- **A4.failure_test** — Automated test proves a run with a different blocker list is not rendered with a hardcoded count or stale normalization text.
- **A4.runtime_evidence** — Selected-run browser capture shows the verdict/blocker/freshness fields populated from the API on the real surface.
- **A4.independent_review_hash** — Independent reviewer confirms payload assertion + browser capture and records the bundle hash.

### B1 (B) — Responsive fit and CJK integrity on four audited pages
Required evidence: automated measurements + 24 fresh captures

- **B1.contract** — Four audited pages use controlled widths/tokens so content fits 375/768/1280 in light/dark with no clipping or CJK collapse.
- **B1.happy_test** — Automated DOM measurement asserts scrollWidth<=clientWidth for four pages x three widths x two themes.
- **B1.failure_test** — Automated fixture injects an overlong Korean run ID and rejects overflow or one-character collapse.
- **B1.runtime_evidence** — 24 fresh production-build captures (4 pages x 3 widths x 2 themes) show no overflow/clipping.
- **B1.independent_review_hash** — Independent visual reviewer confirms the measurements and 24 captures and records the bundle hash.

### B2 (B) — WCAG AA contrast, keyboard, and chart alternatives
Required evidence: axe/DOM assertions + keyboard trace

- **B2.contract** — Text/status controls meet AA contrast; interactive elements expose aria state and focus-visible order; charts provide a text/data alternative.
- **B2.happy_test** — axe/DOM assertions pass for contrast, aria-pressed/state, and focus order on the audited pages.
- **B2.failure_test** — Automated test proves a chart without an accessible name/summary/data alternative fails the a11y gate.
- **B2.runtime_evidence** — Keyboard-only traversal trace reaches and announces every interactive control on the real surface.
- **B2.independent_review_hash** — Independent reviewer confirms axe results + keyboard trace and records the bundle hash.

### B3 (B) — Independent per-card loading/error/empty states
Required evidence: delayed/out-of-order request test + browser trace

- **B3.contract** — Run selection uses request-generation/abort tokens and each card owns independent loading/error/empty/stale state so mixed state cannot render.
- **B3.happy_test** — Delayed/out-of-order request test proves rapidly switching runs ends with only the newest run's data.
- **B3.failure_test** — Automated test proves a stalled non-critical endpoint renders ERROR/RETRY for that card while others hydrate (not MISSING).
- **B3.runtime_evidence** — Browser trace under injected latency shows no mixed-run state and per-card independent states.
- **B3.independent_review_hash** — Independent reviewer confirms the race test + browser trace and records the bundle hash.

### B4 (B) — Quantitative page and API latency targets
Required evidence: repeatable timing script + JSON results

- **B4.contract** — Critical loaders are split and backend validation/tail reads are bounded/memoized so latency targets are achievable.
- **B4.happy_test** — Repeatable timing script asserts first meaningful card <=3s and full critical hydration <=10s on the recorded corpus.
- **B4.failure_test** — Timing test proves a warm critical API breaching <=2s (or cold <=5s) fails the latency gate rather than passing silently.
- **B4.runtime_evidence** — JSON timing results from the representative corpus record the measured card/API latencies.
- **B4.independent_review_hash** — Independent reviewer confirms the timing script + JSON results and records the bundle hash.

### C1 (C) — Honest close-slot CLI accounting and identity
Required evidence: unit/integration tests + smoke manifest

- **C1.contract** — The standard close-slot CLI writes live events, reserves buy-side costs when sizing, honors the documented tie-break, and uses honest algorithm identity (no misused contextual-bandit label).
- **C1.happy_test** — Unit/integration tests prove cash reserves buy costs, tie_score is deterministic, and the default CLI emits truthful events.
- **C1.failure_test** — Test proves an aggregate-positive/test-negative fixture cannot obtain GO or a primary positive headline.
- **C1.runtime_evidence** — Bounded real-data smoke manifest shows nonempty truthful events and a complete test ledger.
- **C1.independent_review_hash** — Independent reviewer confirms tests + smoke manifest and records the bundle hash.

### C2 (C) — Genuine daily R3b SB3 adapter and training path
Required evidence: tests, model artifact, events, device/lineage summary

- **C2.contract** — A daily R3b adapter maps official daily predictions with 23bp defaults, fold-specific fit, configurable device, and a >=200k/seed path distinct from the tabular lane.
- **C2.happy_test** — E2E test trains a short test model through the adapter and discovers it under the default dashboard root.
- **C2.failure_test** — Test proves shuffled/missing-hash/wrong-cost input fails before model.learn.
- **C2.runtime_evidence** — Real model artifact, events, and device/lineage summary exist for the 5k smoke and the full path.
- **C2.independent_review_hash** — Independent reviewer confirms adapter tests + artifact/lineage summary and records the bundle hash.

### C3 (C) — Deterministic R5 attribution and reconstruction
Required evidence: dated result, JSON, hashes, seed42/sample5

- **C3.contract** — R5 produces deterministic pretrained/finetuned/random zero-shot comparison and base-vs-finetuned tokenizer reconstruction on the exact lineage.
- **C3.happy_test** — Deterministic rerun yields identical comparison metrics within the preregistered tolerance.
- **C3.failure_test** — Corrupt/missing comparison input returns INCONCLUSIVE without interpreting partial metrics.
- **C3.runtime_evidence** — Dated result + JSON with seed42/sample5, reconstruction MSE, and input/output hashes exist.
- **C3.independent_review_hash** — Independent reviewer confirms the deterministic result + hashes and records the bundle hash.

### C4 (C) — Authoritative multi-seed governance consumers
Required evidence: SQLite query, stability JSON, Aim capture, IQM/CI report

- **C4.contract** — Registry/aliases, the R6 sweep, optional Aim, and R7 rliable consume authoritative identical-config multi-seed outputs only.
- **C4.happy_test** — Test proves the registry returns one authoritative row per real run and rliable accepts only identical-config seeds.
- **C4.failure_test** — Test proves duplicate run IDs from one seed are rejected as rliable/seed inputs.
- **C4.runtime_evidence** — SQLite query, stability JSON, Aim capture, and IQM/CI report from the real seeds exist.
- **C4.independent_review_hash** — Independent reviewer confirms the governance consumers + reports and records the bundle hash.

### D1 (D) — Preregistration, cost controls, and chronological hygiene
Required evidence: manifest/gate validation

- **D1.contract** — Each experiment has a prereg, 23bp primary with 0/46 controls, chronological purge/embargo, and recorded seed and source hashes.
- **D1.happy_test** — Manifest/gate validation passes for a compliant run (prereg + 23bp/0/46 + purge/embargo + hashes).
- **D1.failure_test** — Validation rejects a run missing prereg, controls, embargo, or source hashes.
- **D1.runtime_evidence** — Real manifest/gate output records the prereg reference, controls, and hashes.
- **D1.independent_review_hash** — Independent reviewer confirms the manifest/gate validation and records the bundle hash.

### D2 (D) — Complete baselines and negative/shuffle controls
Required evidence: baseline/control tables and gate results

- **D2.contract** — Test OOS plus no-trade, momentum/RULE, buy-hold where relevant, and shuffle/negative controls are all present for alpha claims.
- **D2.happy_test** — Baseline/control tables assert every required baseline and control is computed on test OOS.
- **D2.failure_test** — Gate proves an alpha claim missing a shuffle/negative control or the test-OOS baseline fails.
- **D2.runtime_evidence** — Real baseline/control tables and gate results exist for the evaluated run.
- **D2.independent_review_hash** — Independent reviewer confirms baseline/control coverage and records the bundle hash.

### D3 (D) — Multi-seed stability and bootstrap uncertainty
Required evidence: stability and rliable reports

- **D3.contract** — >=3 identical-config SB3 seeds plus the planned 5x3 D4 sweep report MDD and bootstrap uncertainty.
- **D3.happy_test** — Stability report reproduces one seed summary from raw ledgers and aggregates all seeds.
- **D3.failure_test** — Test proves a seed with negative test OOS or high MDD cannot be omitted from the aggregate.
- **D3.runtime_evidence** — Real stability and rliable reports with IQM/CI and MDD exist.
- **D3.independent_review_hash** — Independent reviewer confirms stability/rliable reproducibility and records the bundle hash.

### D4 (D) — Explicit promotion and preserved NO-GO
Required evidence: promotion manifest + docs/AGENTS audit

- **D4.contract** — Artifact promotion is explicit/hashable; NO-GO/NON_IMPROVING is never softened; a positive result earns no bonus.
- **D4.happy_test** — Promotion-manifest test proves canonical promotion is explicit and verdict-labeled.
- **D4.failure_test** — Audit proves a softened NO-GO or an unlabeled bulk promotion is rejected.
- **D4.runtime_evidence** — Real promotion manifest + docs/AGENTS honesty audit output exist.
- **D4.independent_review_hash** — Independent reviewer confirms promotion + honesty audit and records the bundle hash.

### E1 (E) — Green tests, build, and changed-file static checks
Required evidence: logs/JUnit/LSP JSON/build hashes

- **E1.contract** — Targeted and full tests, npm check/build, and changed-file LSP/static checks are wired and runnable.
- **E1.happy_test** — Targeted + full pytest and npm check/build pass with recorded logs/JUnit.
- **E1.failure_test** — A deliberately failing test/build or error-severity diagnostic causes the gate to fail (no suppression).
- **E1.runtime_evidence** — Real logs/JUnit/LSP JSON/build hashes from this SHA exist.
- **E1.independent_review_hash** — Independent reviewer confirms the logs/JUnit/LSP/build evidence and records the bundle hash.

### E2 (E) — Trusted-local security boundary
Required evidence: security tests + runtime probes

- **E2.contract** — Loopback binding, restricted CORS/path roots, debug-off default, sanitized docs, and bounded heavy inputs are enforced.
- **E2.happy_test** — Security tests prove an allowed root + loopback origin succeeds.
- **E2.failure_test** — Security tests reject arbitrary absolute paths, disallowed origins, oversized params, and remote debug.
- **E2.runtime_evidence** — Runtime probes confirm debug off, loopback binding, and inert docs rendering.
- **E2.independent_review_hash** — Independent security reviewer confirms tests + probes and records the bundle hash.

### E3 (E) — Dependency advisory disposition
Required evidence: npm audit/outdated + disposition

- **E3.contract** — No high/critical advisories remain; production-reachable moderates are fixed or explicitly isolated with owner/deadline.
- **E3.happy_test** — npm audit --json shows zero high/critical (or an explicit 90-gate temporary reachability disposition).
- **E3.failure_test** — An unmitigated production-reachable moderate without owner/deadline fails the disposition check.
- **E3.runtime_evidence** — Real npm audit/outdated output plus the disposition record exist.
- **E3.independent_review_hash** — Independent reviewer confirms the audit + disposition and records the bundle hash.

### E4 (E) — Clean release state and final reviews
Required evidence: git audit + reviewer receipts

- **E4.contract** — Clean tree, source/generated separation, and a current dated handoff are in place.
- **E4.happy_test** — Git audit proves a clean tree and source/generated separation at the release SHA.
- **E4.failure_test** — A dirty tree, bulk generated commit, or ack-only reviewer fails the release check.
- **E4.runtime_evidence** — Final four review receipts and two visual review receipts (all APPROVE) exist.
- **E4.independent_review_hash** — Independent reviewer confirms git audit + all reviewer receipts and records the bundle hash.


# Kronos 90점 진입·95점 최종 완성 마스터 플랜 (2026-07-11)

> **기준 브랜치/커밋**: `dashboard-v3` / `044b5468be2baa11ef451da32ff3999c7c8ab83b`
> **현재 상태**: clean worktree, upstream 미설정, 보고된 준비도 42/100은 Task 1/5 재기준화 전 잠정치
> **목표**: 시스템·연구 파이프라인 품질 Gate 90 통과 후 최종 Gate 95 이상. 모델 수익성/우상향은 별도 verdict이며 점수 보너스가 아니다.
> **상위 근거**: `docs/kronos_full_inspection_and_rl_rebuild_plan_2026-07-10.md`, `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md`, `docs/kronos_rl_rebuild_and_visibility_handoff_2026-07-10.md`

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**What you'll get:** 현재 약 42점으로 평가된 연구 대시보드의 P0 의미 오류를 먼저 제거하고, 실제 일봉 강화학습·Kronos 귀속·다중 시드 거버넌스까지 완료한 뒤 전체 90점 게이트를 통과하며, 통계·보안·접근성·릴리스 검증을 닫아 최종 95점 이상을 독립적으로 재현하는 실행 계획입니다.

**Why this approach:** 모델 수익성과 시스템 완성도를 분리합니다. 모델이 실패해도 그 실패를 사전등록·재현·대조·OOS 기준으로 정확히 보여주면 시스템 품질은 95점을 받을 수 있으며, 좋은 그래프를 만들기 위해 결과를 선택하는 방식은 점수 자체를 무효화합니다.

**What it will NOT do:** 우상향이나 수익을 보장하지 않습니다. 실거래·브로커·주문·계좌 기능을 만들지 않습니다. 과거 실패를 숨기거나 스모크·검증 수익을 테스트 수익으로 바꾸지 않습니다.

**Effort:** XL
**Risk:** High - 실제 GPU 연구, 의존성·보안 호환성, 오래된 산출물 선택, 여러 화면의 의미 계약이 함께 얽혀 있습니다.
**Decisions to sanity-check:** 95점은 수익 점수가 아니라 증거·재현성·UI·보안·릴리스 품질 점수입니다. 90점은 P0 의미 오류 제거와 R5·R3b·R6 실제 연구 증거가 모두 있어야 통과하며, 95점은 R7 통계·전 탭 검증·릴리스 독립 검토까지 닫아야 합니다.

Your next move: 이 문서 커밋 후 실행 요청 시 목적 브랜치별로 순차 착수합니다. 전체 실행 상세는 아래에 있습니다.

---

> TL;DR (machine): XL/high-risk; 25 atomic todos across score governance, evidence truth, UI/security, R5/R3b/R4/R6/R7, and independent 90/95 release gates; positive alpha is not a completion prerequisite.

## Scope
### Must have
- A versioned, machine-readable 100-point scorecard that can be independently rescored from evidence. The reported 42/100 is provisional until Todo 1 rebaselines `dashboard-v3@044b546`.
- Three separate outputs: dashboard/release quality score, research-pipeline completion score, and model verdict. Only the first two contribute to the 90/95 engineering target; positive alpha contributes zero bonus.
- Gate 90: total >=90, category floors A>=19, B>=18, C>=17, D>=18, E>=18, zero P0 truth defects, canonical R5/R3b/R6 evidence, and targeted tests/build/runtime/critical visual/security disposition all pass.
- Gate 95: total >=95, each category >=19/20, full tests/static/security/all-tab visual QA/reproducibility/final review all pass.
- Fixed score categories, each 20 points: A evidence truth, B UI/performance/accessibility, C research engineering, D research integrity/reproducibility, E release/security/quality.
- Purpose branches from clean `dashboard-v3@044b546`, atomic commits, isolated generated evidence, and merge-back only after lane gates.
- Evidence-truth fixes for LIVE/stale/completed, action availability, reward/equity unit and kind, OOS headline, today/latest semantics, selected verdict/blockers, authoritative runs, and async request races.
- Responsive, dark/light, CJK, keyboard, chart semantics, loading/error/empty states, and quantitative API/page latency remediation.
- R5 attribution/reconstruction decision, R4 honest identity, genuine daily SB3 R3b staged execution, R6 registry/sweep, and R7 Aim/rliable.
- Local-only security boundary, scoped dependency/static cleanup, clean release state, and a new dated handoff.
### Must NOT have (guardrails, anti-slop, scope boundaries)
- No live trading, broker, account, order, paper-trading, model-build, or profitability feature/claim.
- No requirement that a model make money. A preregistered, reproduced, correctly surfaced NO-GO can receive full engineering/research-process credit.
- No hidden failed test split, val+test headline replacing test OOS, cherry-picked seed, or forced upward curve.
- No mutation of local Korean databases; DB access remains read-only and six-digit codes remain strings.
- No development from or replay of historical ancestor branches. The sole base is `dashboard-v3@044b546` or a later verified integration head.
- No bulk generated artifact commit; promotion is explicit, hashable, size-bounded, and verdict-labeled.
- No broad dependency modernization, general refactor, or LSP cleanup outside changed files and named blockers.
- No F14 300-second retraining unless R5 returns exactly `TUNING_HELPED_COST` under its preregistered rule.

### Frozen-file and Gate-A contract
| Path | Default | Permitted in this plan | Required evidence/rollback |
| --- | --- | --- | --- |
| `webui/app.py` | frozen | Plan execution does not waive C5. Todo 4 must present the exact function/line diff allowlist, contract snapshot, tests, and rollback to the user and receive explicit Gate-A approval immediately before any edit. If denied, keep frozen and route through non-frozen adapters/config; no route additions. | explicit user approval receipt, contract snapshot before/after, route inventory, targeted API/security tests, one-commit revert |
| `webui/rl_dashboard_tables.py` | frozen | no edit; route freshness/authority through `rl_dashboard_runs.py`, `rl_dashboard_files.py`, run metadata, and existing payload consumers | tests prove archived API compatibility |
| `webui/v2/__init__.py` | frozen | no edit | `kronos-v2-shell` and blueprint isolation tests |
| `stom_rl/rl_events.py` | schema frozen | no schema-version change; use additive `info` metadata and run manifests for metric kind/unit/availability | live-event schema regression and archived-event read tests |

### Non-gameable scorecard
Each criterion is five fixed binary one-point checks: (1) contract/implementation, (2) happy-path automated test, (3) failure-path automated test, (4) real runtime/canonical evidence, and (5) independent review plus evidence hash. A criterion therefore scores any integer 0-5; a category scores any integer 0-20. There is no discretionary rounding or narrative bonus. The versioned JSON must spell out criterion-specific wording for all 100 one-point checks. Final scoring is performed by an independent reviewer.

| ID | Category | 5-point criterion | Required evidence |
| --- | --- | --- | --- |
| A1 | Evidence truth | Finished/stale/replay runs never render LIVE; status changes are freshness-aware | API fixture + live browser transition capture |
| A2 | Evidence truth | Missing action is NOT_RECORDED/—; reward/equity kind and unit are explicit | schema/adapter tests + populated UI capture |
| A3 | Evidence truth | Test OOS is primary; today/latest matches date, policy, split, and authority; smoke cannot steal latest | isolated-root API tests + canonical/smoke failure scenario |
| A4 | Evidence truth | Selected verdict, blockers, D0/D1/D5, cost, seed, split, and artifact freshness are visible | selected-run browser capture + payload assertion |
| B1 | UI quality | Four audited pages × 375/768/1280 × light/dark have `scrollWidth <= clientWidth` and no clipping/CJK collapse | automated measurements + 24 fresh captures |
| B2 | UI quality | WCAG AA contrast, keyboard/focus, aria state, chart text/data alternatives | axe/DOM assertions + keyboard trace |
| B3 | UI quality | Run changes cannot show mixed state; each card has independent loading/error/empty states | delayed/out-of-order request test + browser trace |
| B4 | UI quality | Representative corpus: first meaningful card <=3s, full critical hydration <=10s, warm critical APIs <=2s and cold <=5s | repeatable timing script + JSON results |
| C1 | Research engineering | Close-slot standard CLI writes events, reserves buy costs, honors tie-break, and uses honest algorithm identity | unit/integration tests + smoke manifest |
| C2 | Research engineering | Daily R3b adapter + 23bp SB3 + fold-specific fit + 5k smoke + >=200k/seed path exists | tests, model artifact, events, device/lineage summary |
| C3 | Research engineering | R5 deterministic pretrained/finetuned/random and tokenizer reconstruction results complete | dated result, JSON, hashes, seed42/sample5 |
| C4 | Research engineering | Registry/aliases, R6 sweep, Aim, and R7 rliable consume authoritative multi-seed outputs | SQLite query, stability JSON, Aim capture, IQM/CI report |
| D1 | Research integrity | Prereg, 23bp primary/0/46 controls, chronological purge/embargo, seed and source hashes | manifest/gate validation |
| D2 | Research integrity | Test OOS, no-trade, momentum/RULE, buy-hold where relevant, shuffle/negative controls all present | baseline/control tables and gate results |
| D3 | Research integrity | >=3 identical-config SB3 seeds plus planned 5×3 D4 sweep, MDD and bootstrap uncertainty | stability and rliable reports |
| D4 | Research integrity | Artifact promotion is explicit; NO-GO/NON_IMPROVING is never softened; positive result earns no bonus | promotion manifest + docs/AGENTS audit |
| E1 | Release quality | Targeted and full tests, npm check/build, changed-file LSP/static checks pass | logs/JUnit/LSP JSON/build hashes |
| E2 | Release quality | Loopback, restricted CORS/path roots, debug-off default, sanitized docs, bounded heavy inputs | security tests + runtime probes |
| E3 | Release quality | 0 high/critical advisories; production-reachable moderates fixed or explicitly isolated with owner/deadline | npm audit/outdated + disposition |
| E4 | Release quality | Clean tree, source/generated separation, current handoff, final four reviews and two visual reviews all approve | git audit + reviewer receipts |

Hard caps: any failed test/build, P0 evidence fabrication, missing required OOS/control evidence, unapproved frozen-file/API change, or dirty release tree caps below 90. Cherry-picking or presenting train/val as OOS caps below 95. Alpha/profit claims remain governed by a separate model gate.

### Baseline and exit ledger
The following 42-point distribution is provisional management evidence from the 2026-07-11 audit. Todo 1/5 must replace it with scorer-generated evidence; it may move up or down and must not be preserved for narrative consistency.

| Category | Provisional current | Gate-90 exit | Gate-95 exit | Owning todos | Current blockers |
| --- | ---: | ---: | ---: | --- | --- |
| A Evidence truth | 5/20 | >=19 | >=19 | 2,3,6,7,8 | false LIVE/HOLD/percent, mixed units, latest/today/OOS errors |
| B UI/performance/accessibility | 8/20 | >=18 | >=19 | 9,10,23 | 49s hydration, overflow, contrast, chart semantics, races |
| C Research engineering | 10/20 | >=17 | >=19 | 13,15-19,21 | R5 results absent, R3b missing, R6/R7 missing |
| D Research integrity/reproducibility | 12/20 | >=18 | >=19 | 1,13-19,21 | multi-seed/CI/shuffle/full OOS incomplete |
| E Release/security/quality | 7/20 | >=18 | >=19 | 4,5,11,22-25 | npm high/moderate, LSP unavailable/errors, security and final reviews fail |
| **Total** | **42/100 provisional** | **>=90** | **>=95** | all | any hard cap overrides arithmetic |

## Verification strategy
> Verification execution is agent-run; only the explicit frozen-file approval and final publication/merge decisions require the user.
- Test decision: TDD for semantic/API/accounting/authority/security boundaries; tests-after for CSS-only layout and dependency compatibility. Frameworks: pytest, svelte-check/Vite, existing Svelte source contracts, browser automation, LSP/static diagnostics, npm audit.
- Evidence convention: `.omo/evidence/task-{todo-number}-kronos-90-to-95-completion-master-plan/` with command logs, JSON, screenshots, hashes, and reviewer receipts inside that directory.
- Every evidence bundle records Git SHA, branch, OS, Python/Node/npm versions, data/run IDs, command, exit code, timestamps, and file hashes.
- Happy and failure scenarios are both required. A command timeout, ack-only reviewer, missing artifact, or inconclusive result is FAIL.
- Execution/QA is agent-run. Promotion, merge, and external publication wait for the user's explicit approval after final receipts.
- Targeted regression command is the handoff §3 suite. Gate 95 additionally runs full pytest or a documented complete shard matrix.
- Frontend gates run `npm ci`, `npm run check`, and `npm run build` in `webui/v2_src`.
- Runtime gates start the production-built Flask/Svelte surface on loopback and inspect HTTP, browser console/network, and actual page state.
- Research gates validate manifests rather than accepting trainer stdout.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.

- Wave 0, foundation (Todos 1-5): score freeze, authority/artifact contracts, metric semantics, branch/frozen-file safety, fresh baseline.
- Wave 1, P0 readiness (Todos 6-12): truth semantics, authoritative daily evidence, async/loading/performance, responsive/accessibility, local security/dependencies, and a no-score readiness checkpoint.
- Wave 2, research completion and Gate 90 (Todos 13-20): R5, conditional F14 decision, close-slot honesty, R3b prereg/adapter/smoke/full, R6 governance, then the first valid overall 90-point decision.
- Wave 3, Gate 95 (Todos 21-25): R7, static/dependency closure, all-tab QA, release candidate, final score/handoff/PR readiness.
- Parallelism rule: non-overlapping frontend and research branches may run concurrently only after Todos 1-5 merge. Todos sharing `webui/daily_ohlcv_dashboard.py`, `RLTradingTab.svelte`, manifests, registry, or package lock execute sequentially.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | all | none |
| 2 | 1 | 6,8,15,19 | 3,4 |
| 3 | 1 | 6,7,15 | 2,4 |
| 4 | 1 | 11,25 | 2,3 |
| 5 | 1-4 | 6-25 | none |
| 6 | 2,3,5 | 7,12 | 9,10,11 |
| 7 | 3,5,6 | 12 | 8-11 |
| 8 | 2,5 | 12,19 | 7,9-11 |
| 9 | 5,6 | 12 | 7,8,10,11 |
| 10 | 5 | 12,23 | 6-9,11 |
| 11 | 4,5 | 12,22,24 | 6-10 |
| 12 | 6-11 | 13-25 | none |
| 13 | 12 | 14,20 | 15,16 |
| 14 | 13 | conditional F14 only | 15-19 |
| 15 | 2,3,12 | 17,19,20 | 13,16 |
| 16 | 12 | 17,20 | 13,15 |
| 17 | 15,16 | 18,19,20,23 | 13,14 |
| 18 | 17 | 19,20,23 | 14 |
| 19 | 2,8,17,18 | 20,21,23 | 14 |
| 20 | 13-19 | 21-25 | none |
| 21 | 19,20 | 23-25 | 22 |
| 22 | 11,12 | 23,24 | 21 |
| 23 | 10,12,17-22 | 24,25 | none after source freeze |
| 24 | 13-23 | 25 | none |
| 25 | 24 | final handoff | none |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->

### Wave 0 - Freeze the measurement and contracts

- [ ] 1. Freeze and implement the non-gameable 100-point scorecard
  What to do / Must NOT do: Add `docs/kronos_90_to_95_scorecard_v1.json`, a human-readable rubric section, `scripts/score_kronos_90_to_95.py`, and focused tests. Encode the 20 criteria as exactly five criterion-specific binary one-point checks, category floors, hard caps, evidence hashes, and three separate outputs (dashboard/release, research pipeline, model verdict). Rebaseline the provisional 42 only from fresh evidence; do not introduce PARTIAL, discretionary rounding, backfit points to reach 90/95, or award alpha bonus.
  Parallelization: Wave 0 | Blocked by: none | Blocks: every later todo
  References: `AGENTS.md` Trading Honesty Rules; `docs/AGENTS.md`; `docs/kronos_rl_rebuild_and_visibility_handoff_2026-07-10.md:8-13,118-123`; scorecard table in this plan.
  Acceptance criteria: `py -3.11 -m pytest tests/test_kronos_90_to_95_scorecard.py -q` exits 0; tests enumerate the attainable integer totals and both gates' category floors, produce an exact-95 fixture, and prove the scorer rejects missing evidence, non-binary values, floor violations, and any active hard cap; two evaluators using the same fixture produce byte-identical JSON.
  QA scenarios: happy: score a complete synthetic 95 fixture and obtain exactly 95 with each category >=19; failure: inject a P0 truth defect into a 100-point fixture and prove the score is capped below 90. Evidence `.omo/evidence/task-1-scorecard-tests.txt` and `.omo/evidence/task-1-scorecard-fixtures.json`.
  Rollback: revert scorer, rubric JSON, and its direct tests together.
  Commit: Y | `feat(governance): freeze Kronos 90-to-95 scorecard`

- [ ] 2. Define authoritative run identity, artifact promotion, and isolated test roots
  What to do / Must NOT do: Extend existing run manifests/registry metadata with `stage`, `status`, `authoritative`, `completed_at`, `source_git_sha`, `prereg_doc`, `cost_bps`, split lineage, seed, hashes, and verdict. Selection order is explicit authority/status/completion, then mtime only as a final tie-break. Add a promotion command that validates schema/hash/size and moves or registers an ignored artifact as canonical. Make API tests override run roots so disposable smoke output can never become production `latest`. Do not add endpoints or infer authority from directory names.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 6,8,15,19
  References: `webui/daily_ohlcv_dashboard.py:173-196`; `webui/rl_dashboard_runs.py`; `webui/rl_dashboard_files.py`; `stom_rl/factory/run_registry.py`; `tests/test_daily_ohlcv_dashboard_api.py:1412`; `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:277-285`.
  Acceptance criteria: focused registry/dashboard tests pass; a newer disposable smoke remains non-authoritative; an explicit canonical run wins regardless of older mtime; invalid hash/schema/oversize artifacts fail promotion without partial registration.
  QA scenarios: happy: register canonical full and smoke runs and assert API/default selection chooses canonical full; failure: create a newer unregistered smoke in an isolated root and prove neither tests nor production selection changes. Evidence `.omo/evidence/task-2-run-authority.txt` and `.omo/evidence/task-2-promotion-fail.json`.
  Rollback: additive manifest fields remain readable; revert selection/promotion/tests in one commit.
  Commit: Y | `feat(governance): add authoritative run promotion contract`

- [ ] 3. Define additive event metric, action availability, and freshness semantics
  What to do / Must NOT do: Keep `stom_rl_live_event.v1` byte-compatible. Require trainer-emitted `info` metadata for `reward_kind`, `reward_unit`, `equity_kind`, `equity_unit`, `action_recorded`, and event/run status; add run-level defaults for archived artifacts. Define statuses `RUNNING`, `COMPLETED`, `STALE`, `REPLAY`, `IDLE`, `MISSING`. LIVE requires explicit running state and an advancing event file/step within two poll intervals; polling alone never means LIVE. Unknown values remain null/NOT_RECORDED and are never coerced to zero/HOLD/percent.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 6,7,15
  References: `stom_rl/rl_events.py:56-76`; `stom_rl/daily_close_slot_train.py:1087-1098`; `stom_rl/daily_rl_train.py:769-778,834-843`; `webui/v2_src/src/lib/rlRows.ts:14-20`; `webui/v2_src/src/tabs/rlTrading/RlLiveScreen.svelte:67-72`.
  Acceptance criteria: archived v1 fixtures still parse; new trainer fixtures carry the additive contract; mixed-unit overlays are rejected or separated; null action renders NOT_RECORDED; completed/stale events cannot satisfy LIVE.
  QA scenarios: happy: a running NAV-percent stream advances and displays declared units; failure: a month-old file with rows and null action renders STALE/NOT_RECORDED, never LIVE/HOLD. Evidence `.omo/evidence/task-3-event-contract.txt` and `.omo/evidence/task-3-stale-fixture.json`.
  Rollback: revert only producer metadata, adapters, and tests; do not change `rl_events.py` schema version.
  Commit: Y | `feat(stom_rl): add truthful live-event metric metadata`

- [ ] 4. Lock branch ancestry, file ownership, and the narrow Gate-A exception
  What to do / Must NOT do: Add an execution ledger to the plan/handoff that records the verified integration SHA, allowed purpose branches, owned files, dependency order, generated-evidence roots, and merge gates. Prove all historical branches are ancestors before declaring them archival. Prepare the exact `webui/app.py` function/line allowlist only for CORS/path/resource bounds and existing response wiring, snapshot routes/contracts, and request the user's explicit Gate-A approval immediately before any edit; denial routes the work through non-frozen adapters/config. Keep `webui/rl_dashboard_tables.py`, `webui/v2/__init__.py`, and `stom_rl/rl_events.py` frozen. Never develop in old worktrees.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 11,25
  References: `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:13-24`; Git baseline `dashboard-v3@044b546`; branch table in the approved audit.
  Acceptance criteria: a script/report verifies clean tree, current branch, integration SHA, upstream state, worktree list, and `merge-base --is-ancestor` for each archived branch; route inventory and contract snapshot hashes are captured before Gate-A; any diff outside the allowlist fails.
  QA scenarios: happy: purpose branch from the exact integration head passes ownership audit; failure: a branch based on `feature/stom-rl-lab` or an edit to frozen `rl_dashboard_tables.py` is rejected. Evidence `.omo/evidence/task-4-git-ancestry.txt` and `.omo/evidence/task-4-gatea-allowlist.json`.
  Rollback: documentation/test-only ledger can be reverted; no history rewrite is allowed.
  Commit: Y | `docs(governance): lock dashboard-v3 execution boundaries`

- [ ] 5. Produce the fresh HEAD baseline and point-loss ledger
  What to do / Must NOT do: At the then-current clean integration SHA, run the exact scoped suite, contract tests, npm check/build, runtime/API timing, npm audit/outdated, LSP/static probe, security probes, and fresh critical-page browser capture. Feed only these artifacts into the v1 scorer and publish a dated baseline result mapping every lost point to a todo. Historical 82/100, 100/100, 124-test, 144/2, or screenshot claims are context only.
  Parallelization: Wave 0 | Blocked by: 1-4 | Blocks: 6-25
  References: handoff §3 `docs/kronos_rl_rebuild_and_visibility_handoff_2026-07-10.md:53-73`; `docs/kronos_dashboard_v3_handoff_2026-07-10.md` stale score claims; Gate matrix in this plan.
  Acceptance criteria: baseline result includes commit/environment/commands/exits/hashes, all 20 criterion states, hard caps, point owner/todo, and separate model verdict; scorer output is reproducible; working tree remains clean except the intentional dated baseline doc if canonical promotion is approved.
  QA scenarios: happy: complete evidence produces a deterministic baseline; failure: remove one browser or OOS artifact and prove the criterion becomes FAIL rather than inheriting historical credit. Evidence `.omo/evidence/task-5-baseline/` and `docs/kronos_90_to_95_baseline_result_<date>.md`.
  Rollback: remove only the new dated baseline document; retain ignored execution logs as session evidence until the wave closes.
  Commit: Y | `docs(audit): establish Kronos 90-to-95 baseline`

### Wave 1 - Close P0 truth, usability, and security blockers

- [ ] 6. Make run lifecycle and LIVE/STALE/REPLAY status truthful end to end
  What to do / Must NOT do: Implement the Todo 3 lifecycle contract in run discovery/detail and `RlLiveScreen`; pass selected-run status into the live screen; derive Mission/Ops status from the same source. A completed run remains queryable and replayable but never LIVE. An actively advancing file transitions RUNNING→COMPLETED/STALE deterministically. Do not equate HTTP polling, row presence, or fetch time with source freshness.
  Parallelization: Wave 1 | Blocked by: 2,3,5 | Blocks: 7,12
  References: `webui/v2_src/src/tabs/rlTrading/RlLiveScreen.svelte:67,76-109,352-355`; `webui/v2_src/src/tabs/MissionControl.svelte:27-53,86-91`; `webui/v2_src/src/layout/OpsStrip.svelte:47-62`; `webui/rl_dashboard_runs.py`; Todo 3 contract.
  Acceptance criteria: unit/API/component tests cover all six statuses and transitions; browser shows RUNNING only while steps advance; stopping a disposable trainer changes status without reload; old June artifacts display REPLAY/STALE.
  QA scenarios: happy: launch bounded trainer, observe at least two advancing steps, stop, and observe completion; failure: serve a static historical JSONL and prove LIVE never appears. Evidence `.omo/evidence/task-6-lifecycle/`.
  Rollback: revert status adapter/UI/test commit; archived files remain untouched.
  Commit: Y | `fix(dashboard-v3): make RL lifecycle freshness-aware`

- [ ] 7. Preserve missing actions and render reward/equity only with compatible units
  What to do / Must NOT do: Remove null-to-zero/HOLD conversion from `rlRows.ts`; render explicit NOT_RECORDED/—; label raw score, return fraction/percent, normalized NAV, KRW NAV, and cumulative P&L according to Todo 3 metadata. Reject cross-unit overlays or normalize only when both series declare a compatible normalization. Episode summaries must ignore rows without a real episode ID. Do not multiply reward by 100 without a percent/return contract.
  Parallelization: Wave 1 | Blocked by: 3,5,6 | Blocks: 12
  References: `webui/v2_src/src/lib/rlRows.ts:14-20`; `webui/v2_src/src/tabs/rlTrading/RlLiveScreen.svelte:70-72,180-258,331-339,451-453`; `stom_rl/rl_events.py:64-76`.
  Acceptance criteria: source tests assert null preservation; overlay tests reject NAV-vs-KRW; daily-Q null action shows NOT_RECORDED; reward displays the declared unit; episode ticker excludes null episode evaluation rows.
  QA scenarios: happy: compare two normalized NAV runs and see an allowed overlay; failure: request normalized NAV vs KRW P&L and see an explicit incompatible-units message without a misleading chart. Evidence `.omo/evidence/task-7-metric-rendering/`.
  Rollback: revert frontend adapter/render/tests without modifying event archives.
  Commit: Y | `fix(dashboard-v3): preserve RL metric and action semantics`

- [ ] 8. Make latest/today/OOS headline and blocker evidence authoritative
  What to do / Must NOT do: Replace mtime-only `_latest_run_dir` selection with Todo 2 authority; select Close-slot latest rows by descending date and explicit `policy=contextual/linear`, `split=test` for OOS cards, and `cost=base_23bp`; display selected-run verdict, full blocker list from API, seed, split, cost, date, artifact age, and source run. Use test OOS as the primary result; train/val/val+test remain secondary. Rename “today” to “stored replay <date>” unless the data date equals the configured research date. Do not hardcode blocker count or normalization-bug text.
  Parallelization: Wave 1 | Blocked by: 2,5 | Blocks: 12,19
  References: `webui/daily_ohlcv_dashboard.py:173-196,865-883,2173-2176,2369-2394,5371-5381`; `webui/v2_src/src/tabs/dailyOhlcv/CloseSlotAgentScreen.svelte:78-112,193-218`; `webui/v2_src/src/tabs/DailyRlGuideTab.svelte:328,422-445`; `webui/v2_src/src/tabs/MissionControl.svelte:104-133`.
  Acceptance criteria: isolated-root tests cover canonical/smoke order, newest/oldest dates, policy/split/cost selection, full blocker count, and test-vs-combined headline; browser text never says today/latest without matching metadata.
  QA scenarios: happy: canonical run with test OOS -38% and combined +65% displays -38% primary plus combined diagnostic; failure: newer smoke/older date/first aggregate row cannot replace primary evidence. Evidence `.omo/evidence/task-8-authoritative-evidence/`.
  Rollback: revert backend selectors, UI labels, and direct tests together.
  Commit: Y | `fix(daily-ohlcv): make evidence selection authoritative`

- [ ] 9. Eliminate request races and replace monolithic hydration with independent states
  What to do / Must NOT do: Add AbortController/request-generation tokens to run selection and live refresh; clear prior run detail before changing selected labels; prevent overlapping polls; split Daily OHLCV `Promise.all` into independent critical-card loaders with explicit loading/empty/error/stale states. Add bounded backend memoization/indexing for repeated artifact validation and tail reading, keyed by path+mtime+size. Do not mask timeouts as NOT_STARTED/MISSING and do not cache across changed artifacts.
  Parallelization: Wave 1 | Blocked by: 5,6 | Blocks: 12
  References: `webui/v2_src/src/tabs/RLTradingTab.svelte:164-244`; `webui/v2_src/src/tabs/rlTrading/RlLiveScreen.svelte:76-140`; `webui/v2_src/src/tabs/DailyOhlcvTab.svelte`; `webui/daily_ohlcv_dashboard.py:199,368`; `stom_rl/rl_events.py:119-143`.
  Acceptance criteria: delayed-response tests prove an old request cannot overwrite a new run; first meaningful Daily card <=3s, all critical cards <=10s, warm critical API <=2s and cold <=5s on the recorded representative corpus; cache invalidates on mtime/size change; timeout renders ERROR/RETRY, not MISSING.
  QA scenarios: happy: rapidly select three runs under injected latency and end with only the third run’s data; failure: stall one noncritical endpoint and prove other cards hydrate while that card shows timeout. Evidence `.omo/evidence/task-9-async-performance/`.
  Rollback: disable memoization via one local flag and revert client coordination/tests if stale cache is observed.
  Commit: Y | `perf(dashboard-v3): isolate evidence loading and polling`

- [ ] 10. Repair responsive layout, dark contrast, keyboard semantics, and chart accessibility
  What to do / Must NOT do: Update `DESIGN.md` for S1-S4 primitives/states/tokens; remove raw light-surface colors and uncontrolled min/max-content widths; make four critical pages fit 375/768/1280; reserve or collapse floating utility controls; fix Mission desktop collisions; add `aria-pressed`, programmatic labels, focus-visible order, and a chart summary/data table or equivalent text alternative through `EChartsRenderer`. Do not solve by hiding evidence or shrinking text below design minima.
  Parallelization: Wave 1 | Blocked by: 5 | Blocks: 12,23
  References: `DESIGN.md:97-123`; `webui/v2_src/src/tabs/ResearchStatusShell.svelte:105,131`; `webui/v2_src/src/tabs/dailyOhlcv/DailyProgressTimeline.svelte:90`; `webui/v2_src/src/tabs/dailyOhlcv/DailyGateLadder.svelte:130`; `webui/v2_src/src/tabs/dailyOhlcv/CloseSlotAgentScreen.svelte:264-275,377`; `webui/v2_src/src/tabs/DailyRlGuideTab.svelte:294-305,1368-1390`; `webui/v2_src/src/charts/EChartsRenderer.svelte:80`.
  Acceptance criteria: automated DOM measurements show `scrollWidth <= clientWidth` for each of four pages × three widths × two themes; AA contrast for text/status controls; keyboard-only traversal and state announcement pass; every chart has an accessible name, trend summary, and data alternative.
  QA scenarios: happy: capture populated and empty/error states at all required widths/themes; failure: CI fixture injects an overlong Korean run ID and rejects overflow/one-character collapse. Evidence `.omo/evidence/task-10-responsive-a11y/`.
  Rollback: token/layout changes grouped by component; no dist-only fix without source.
  Commit: Y | `fix(dashboard-v3): meet responsive and accessibility contracts`

- [ ] 11. Close the trusted-local security boundary and direct dependency risk
  What to do / Must NOT do: Under the Todo 4 Gate-A allowlist, restrict CORS to configured loopback origins, constrain data/model paths to approved roots with resolved containment, cap lookback/pred_len/sample_count and heavy model actions, default debug off, sanitize rendered Markdown, and document pickle inputs as trusted-only with refusal/confirmation for unknown provenance. Upgrade only direct packages needed to remove reachable high/critical advisories; isolate or document remaining moderates with owner/deadline. Do not turn the app into an internet service or broaden auth scope.
  Parallelization: Wave 1 | Blocked by: 4,5 | Blocks: 12,22,24
  References: `webui/app.py:398,560,2070,2133,2355`; `webui/run.py:181,189,207`; `webui/v2_src/src/tabs/DocsTab.svelte:97,195`; `finetune/evaluate_stom_1s_checkpoint.py:72`; current npm audit 1 high/5 moderate.
  Acceptance criteria: API security tests reject arbitrary absolute paths, disallowed origins, oversized parameters, and remote debug; allowed local datasets still load; docs payload with script/event attributes renders inert; `npm audit --json` has no high/critical or an explicit 90-gate temporary reachability disposition.
  QA scenarios: happy: allowed root + loopback origin succeeds; failure: outside-root file, hostile origin, raw HTML payload, and oversized inference request all fail safely. Evidence `.omo/evidence/task-11-local-security/`.
  Rollback: one Gate-A security commit plus lockfile commit; if a major upgrade breaks compatibility, revert upgrade and record a separate migration blocker rather than weakening tests.
  Commit: Y | `fix(webui): harden trusted-local dashboard boundary`

- [ ] 12. Run and independently approve the P0 readiness checkpoint without awarding 90
  What to do / Must NOT do: Freeze the P0 source lanes, rebuild dist, run targeted regression/contract/honesty tests, npm check/build, runtime/API probes, four-page light/dark/width QA, and the security disposition. Spawn independent code, security, hands-on, and two visual reviewers. Fix every P0 blocker and repeat the checkpoint. Record all unexecuted research criteria as FAIL/zero; do not calculate, publish, or imply an overall 90-point pass before Todos 13-19 produce canonical evidence.
  Parallelization: Wave 1 terminal | Blocked by: 6-11 | Blocks: 13-25
  References: scorecard; handoff §3 command; verification strategy and hard caps in this plan.
  Acceptance criteria: all P0 truth/usability/security checks and reviewers terminal PASS; zero hard caps caused by Todos 6-11; evidence bundle points to the exact merged SHA; unexecuted research checks remain explicit FAIL/zero; no overall score or Gate-90 claim is emitted.
  QA scenarios: happy: reproduce the P0 checkpoint from a clean checkout/worktree while research remains visibly incomplete; failure: attempt to generate a 90-pass report with absent R5/R3b/R6 evidence and prove the report validator rejects it. Evidence `.omo/evidence/task-12-p0-readiness/` and `docs/kronos_p0_readiness_result_<date>.md`.
  Rollback: no source rollback from the checkpoint itself; failure produces a dated fail report and returns to the owning todo.
  Commit: Y | `docs(audit): record Kronos P0 readiness checkpoint`

### Wave 2 - Complete the research system without requiring positive alpha

- [ ] 13. Execute R5 deterministic attribution and tokenizer reconstruction
  What to do / Must NOT do: Generate the missing pretrained zero-shot comparison on the exact 681-window lineage used by finetuned/random, seed 42, sample_count 5, fixed decoding settings; execute base vs finetuned tokenizer reconstruction; verify input/output hashes; write one dated attribution result with `NO_SIGNAL`, `TUNING_HARMFUL`, `TUNING_HELPED_COST`, or `INCONCLUSIVE`. If required source comparison artifacts are missing, generate them through the preregistered evaluator rather than fabricating a wrapper result. Do not call this RL or trading alpha.
  Parallelization: Wave 2 | Blocked by: 12 | Blocks: 14,20 | Can parallelize with: 15,16
  References: `finetune/run_zeroshot_attribution_eval.py`; `finetune/evaluate_stom_1s_checkpoint.py`; `finetune/evaluate_tokenizer_reconstruction.py`; `docs/stom_kronos_attribution_prereg_2026-07-10.md`; `docs/kronos_research_runbook_2026-07-10.md:9-29`.
  Acceptance criteria: deterministic rerun yields identical comparison metrics within the preregistered tolerance; report contains all three model columns, reconstruction MSE, seed/sample settings, data/window/hash lineage, honest decision, and F14 status; missing/NaN/hash mismatch returns INCONCLUSIVE.
  QA scenarios: happy: complete all inputs and produce a deterministic decision; failure: corrupt/missing comparison file fails closed without interpreting partial metrics. Evidence `.omo/evidence/task-13-r5-attribution/` and `docs/stom_kronos_attribution_result_<date>.md`.
  Rollback: results are new dated evidence; never mutate prior verdict docs.
  Commit: Y | `docs(finetune): record deterministic Kronos attribution result`

- [ ] 14. Apply the R5 decision tree and keep F14 conditional
  What to do / Must NOT do: Encode the decision in a small ADR/result section. `NO_SIGNAL` freezes predictor retraining and redirects effort to data/horizon research; `TUNING_HARMFUL` freezes F14 and prioritizes data/tokenizer repair; `INCONCLUSIVE` allows exactly one preregistered rerun with the identified defect fixed; only `TUNING_HELPED_COST` permits a new dated 300-second F14 prereg, bounded smoke, and later full decision. Do not launch F14 because budget remains or because a 300-second historical curve looks better.
  Parallelization: Wave 2 | Blocked by: 13 | Blocks: conditional F14 only | Can parallelize with: 15-19
  References: `docs/kronos_research_runbook_2026-07-10.md:31-45,87-91`; `docs/kronos_rl_rebuild_and_visibility_handoff_2026-07-10.md:94-101`.
  Acceptance criteria: machine-readable decision value equals the report; disallowed branches have no runnable F14 job; permitted branch includes prereg, 23bp/0/46 cost controls, smoke/full stop criteria, and separate supervised-model labeling.
  QA scenarios: happy: synthetic TUNING_HELPED_COST fixture opens only the prereg task; failure: NO_SIGNAL fixture attempting F14 is rejected. Evidence `.omo/evidence/task-14-f14-decision.txt`.
  Rollback: revert decision wiring only; retain dated R5 evidence.
  Commit: Y | `docs(finetune): gate F14 on attribution evidence`

- [ ] 15. Finish close-slot accounting, event production, and honest model identity
  What to do / Must NOT do: Reserve buy-side costs when sizing shares, implement documented `tie_score` ordering, align manifest tie-break text with code, construct the event writer in the standard CLI, emit declared metric/action metadata, and replace contextual-bandit naming everywhere with `linear_score_and_pick_train_only` unless a separate preregistered exploration experiment is approved. Remove or replace absolute-return feedback with signed/neutral weighting under tests. Re-run the corrected full close-slot artifact; test OOS remains primary. Do not promote a positive aggregate with negative test OOS.
  Parallelization: Wave 2 | Blocked by: 2,3,12 | Blocks: 17,19,20 | Can parallelize with: 13,16
  References: `stom_rl/daily_close_slot_env.py:130-141,311-325,453-474`; `stom_rl/daily_close_slot_train.py:283-293,590-603,968-994,1271-1282,1355-1382`; `tests/test_stom_rl_close_slot_wp_r2.py:329-357`; `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:227-236`.
  Acceptance criteria: new tests enforce cash including buy costs, deterministic tie_score, manifest/code tie-break identity, default CLI live events, signed/neutral feedback, RULE/RL labels, and 23bp test headline; canonical rerun passes artifact hashes/gate and receives WATCH/NO-GO as dictated by evidence.
  QA scenarios: happy: bounded real-data smoke produces nonempty truthful events and complete test ledger; failure: aggregate positive/test negative fixture cannot obtain GO or primary positive headline. Evidence `.omo/evidence/task-15-close-slot/` and a new dated result doc.
  Rollback: one code/test commit and one separate canonical-result commit; prior artifacts remain immutable.
  Commit: Y | `fix(stom_rl): make close-slot policy and accounting truthful`

- [ ] 16. Preregister and implement the genuine daily SB3 R3b adapter
  What to do / Must NOT do: Write the dated R3b prereg first. Add `stom_rl/daily_portfolio_sb3_dataset.py` mapping official daily predictions to `timestamp/symbol/rank_score/price/fill_price/future return` with zero-padded codes, fail-closed next-day rows, source hashes, split lineage, and 23bp defaults. Make device configurable, train inside each fold from that fold’s train_frame, and expose PPO/DQN selection without silently changing the official daily tabular lane. Add end-to-end tests through model/run manifest/default dashboard discovery. Do not feed Close-slot CSV directly to generic `PortfolioEnv` without the adapter.
  Parallelization: Wave 2 | Blocked by: 12 | Blocks: 17,20 | Can parallelize with: 13,15
  References: implementation plan `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:204-223`; `stom_rl/portfolio_env.py:310-354`; `stom_rl/portfolio_sb3_adapter.py:25-55`; `stom_rl/portfolio_sb3_train.py:75-100,291-361,679-700,737-778`; `stom_rl/portfolio_walk_forward.py:589-615`.
  Acceptance criteria: adapter rejects missing lineage/schema/next-day price, preserves `000250`, uses 23bp primary and 0/46 controls, trains from each fold’s train_frame, writes model ZIP/manifest/events/device/source hashes, and is discovered under the default dashboard root in an isolated E2E test.
  QA scenarios: happy: synthetic chronological daily fixture trains a 512-step test model and appears in dashboard APIs; failure: shuffled/missing-hash/wrong-cost input fails before model.learn. Evidence `.omo/evidence/task-16-r3b-adapter/`.
  Rollback: adapter/trainer/tests are isolated; no change to legacy daily Q artifact semantics.
  Commit: Y | `feat(stom_rl): add preregistered daily SB3 adapter`

- [ ] 17. Run the 5k R3b smoke and prove artifact-to-dashboard lineage
  What to do / Must NOT do: Execute exactly the preregistered 5k smoke on the official daily lineage, configurable GPU/auto device, one declared smoke seed, 23bp primary with controls, no-trade/momentum/RULE/shuffle baselines, live event stream, model artifact, validation callback, and authoritative-but-smoke status. Capture S1 while running and after completion. Stop expansion if schema, NaN, invalid-action, split, baseline, event, or dashboard lineage gates fail. Do not call smoke full or alpha.
  Parallelization: Wave 2 | Blocked by: 15,16 | Blocks: 18,19,20,23 | Can parallelize with: 13,14
  References: `docs/kronos_research_runbook_2026-07-10.md:49-68`; Todo 2 promotion contract; Todo 3 event contract.
  Acceptance criteria: 5k completes with finite metrics/model, declared device, exact hashes, OOS evaluation and controls, advancing RUNNING→COMPLETED UI, no fabricated action/unit, and explicit `stage=smoke`; failing learning quality yields a complete NON_IMPROVING smoke result, not an execution failure.
  QA scenarios: happy: complete smoke and replay it from the dashboard; failure: inject split/hash mismatch or event stagnation and prove expansion is blocked with a dated NO-GO/INCONCLUSIVE artifact. Evidence `.omo/evidence/task-17-r3b-smoke/`.
  Rollback: smoke output remains ignored until explicit promotion; source commit is retained if plumbing passes.
  Commit: Y | `docs(stom_rl): record daily SB3 smoke verdict`

- [ ] 18. Execute the >=200k multi-seed R3b full gate or record the preregistered stop result
  What to do / Must NOT do: Expansion requires Todo 17 plumbing/data gates to pass, not positive reward. Run >=200k per seed on at least three identical-config seeds, fold-specific training, 23bp/0/46, untouched test OOS, MDD, no-trade/momentum/RULE/buy-hold where relevant, shuffled-label retraining, and ablations. If a stop-loss trigger fires (NaN, invalid action, schema, resource, or prereg criterion), record a complete NO-GO/INCONCLUSIVE result and do not force additional compute. Positive train/validation does not override negative test.
  Parallelization: Wave 2 | Blocked by: 17 | Blocks: 19,20,23 | Can parallelize with: 14
  References: `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:210-223`; `docs/kronos_research_runbook_2026-07-10.md:49-68`; project AGENTS negative/shuffle/OOS requirements.
  Acceptance criteria: either (A) all planned seeds/folds complete with model/event/manifest/hash/baseline/control evidence, or (B) preregistered stop artifact precisely names the blocker and preserves all evidence gathered; both count as engineering completion. Model promotion remains separate and requires test OOS superiority with uncertainty and drawdown gates.
  QA scenarios: happy: reproduce one seed summary from raw ledgers and aggregate all seeds; failure: a seed with negative test or high MDD cannot be omitted and the result remains NO-GO. Evidence `.omo/evidence/task-18-r3b-full/` and `docs/stom_daily_sb3_ppo_result_<date>.md`.
  Rollback: never delete failed runs; canonical promotion metadata can be reverted without deleting evidence.
  Commit: Y | `docs(stom_rl): record daily SB3 multi-seed verdict`

- [ ] 19. Complete R6 registry, aliases, readiness, and the fixed D4 stability sweep
  What to do / Must NOT do: Register new daily Q/SB3 runs with stage/status/verdict/prereg/cost/seed/hash, mark known duplicates with `ALIAS_OF.txt`, keep checkpoint readiness separate from environment readiness, and execute exactly seeds `{7,17,29,41,53}` × episodes `{8,32,128}` under a dated prereg. Produce `stability_summary.json` with val+test and test-separated return, trade count, never-trade, MDD, baseline deltas, source hashes, and failures. Do not treat aliases as independent seeds or use mtime as authority.
  Parallelization: Wave 2 | Blocked by: 2,8,17,18 | Blocks: 20,21,23
  References: `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:277-285`; `docs/kronos_research_runbook_2026-07-10.md:72-83`; `stom_rl/daily_scenario_batch.py`; `stom_rl/factory/run_registry.py`.
  Acceptance criteria: registry SQL query returns one authoritative row per real run and aliases separately; all 15 cells or explicit failure records exist; readiness never reports model-ready without checkpoint; stability summary is reproducible and test OOS is not hidden by val+test.
  QA scenarios: happy: complete 5×3 matrix and query it from factory/dashboard; failure: duplicate directories with one seed cannot inflate sample size or rliable inputs. Evidence `.omo/evidence/task-19-r6-governance/`.
  Rollback: registry entries are reversible transactions; evidence files remain immutable.
  Commit: Y | `feat(stom_rl): register and summarize daily RL stability`

### Wave 2 terminal - Run the first valid overall Gate-90 decision

- [ ] 20. Independently rescore and approve the overall Gate-90 result after research completion
  What to do / Must NOT do: Freeze Todos 13-19 with the P0 lanes, regenerate the criterion-specific 100-check JSON, and independently recompute all 20 criteria from canonical R5, close-slot, R3b, and R6 evidence. Run the targeted automated/runtime/security/visual gates again on the exact integration SHA. Require category floors A>=19, B>=18, C>=17, D>=18, E>=18 and total>=90 with zero hard caps. A complete honest NO-GO/INCONCLUSIVE model result can earn engineering/reproducibility checks; positive alpha cannot substitute for missing controls. Do not award points from trainer stdout, smoke-only evidence, historical screenshots, or Todo 12.
  Parallelization: Wave 2 terminal | Blocked by: 13-19 | Blocks: 21-25
  References: scorecard and baseline/exit ledger; Todo 1 scorer; Todos 12-19 evidence; project Trading Honesty Rules.
  Acceptance criteria: independent score JSON and human report agree at >=90; category floors pass; all 100 binary checks link to exact evidence/hash or explicit zero; no hard cap; model verdict remains separate; a clean-worktree replay reproduces the decision.
  QA scenarios: happy: reconstruct the complete score from canonical bundles and obtain the same total/floors; failure: remove R5 lineage, one R3b seed, shuffle control, or test-OOS evidence and prove the affected binary checks fall to zero and Gate 90 fails. Evidence `.omo/evidence/task-20-gate90/` and `docs/kronos_90_gate_result_<date>.md`.
  Rollback: no source rollback from scoring; a failed gate creates a dated fail report and returns to the exact owning todo/check.
  Commit: Y | `docs(audit): record verified Kronos 90-point gate`

### Wave 3 - Close Gate 95 and prepare release

- [ ] 21. Build R7 local Aim tracking and rliable reports from R6/R3b real seeds
  What to do / Must NOT do: Add research-only requirements and optional localhost Aim adapter, default off; record data/config/artifact hashes and training/eval metrics without external upload. Generate rliable IQM, stratified bootstrap CI, and performance profiles only from authoritative identical-config seeds produced by Todos 18-19. Display generation time, cost, split, seed set, and RESEARCH_ONLY on dashboard/report. Do not treat run IDs from the same seed as seeds and do not reuse the stale generic rliable snapshot.
  Parallelization: Wave 3 | Blocked by: 19,20 | Blocks: 23-25 | Can parallelize with: 22
  References: `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:289-295`; `artifacts/rl_runs_rliable.json`; `scripts/gen_rliable_stats.py`; `stom_rl/experiment_tracking.py` NOT WIRED shim.
  Acceptance criteria: Aim launches on loopback with the new runs visible; disabling the env flag imports/runs without Aim; rliable input validator rejects duplicate seeds/mixed configs/missing 23bp/test metadata; report metrics reproduce from stability inputs.
  QA scenarios: happy: compute IQM/CI/profile from three+ authoritative seeds and show timestamp/config; failure: six run IDs all seed100 are rejected. Evidence `.omo/evidence/task-21-r7/` and dated reliability report.
  Rollback: optional adapter/requirements/report code is isolated; default dashboard remains dependency-clean.
  Commit: Y | `feat(stom_rl): add local Aim and verified rliable reporting`

- [ ] 22. Close changed-scope LSP/static and dependency compatibility debt
  What to do / Must NOT do: Repair LSP daemon/config or document the exact environment fix, then eliminate error diagnostics in all changed Python/TS/Svelte files plus named pre-existing blockers that directly affect the audited surface (`daily_close_slot_train.py`, `daily_rl_train.py`, `daily_ohlcv_dashboard.py`). Upgrade only direct packages required by Todo 11/95 security; use `npm ci`, migration notes, and full frontend verification. Do not perform unrelated repository-wide type cleanup or unreviewed major upgrades.
  Parallelization: Wave 3 | Blocked by: 11,12 | Blocks: 23,24 | Can parallelize with: 21
  References: current LSP pipe `EADDRINUSE` evidence; Python Optional diagnostics; `webui/v2_src/package.json`; `webui/v2_src/package-lock.json`; npm audit/outdated evidence.
  Acceptance criteria: LSP status is reachable with configured servers; diagnostics severity error is zero for changed/named files; npm check/build pass; `npm ci` is reproducible; audit has zero high/critical and no unmitigated production-reachable moderate.
  QA scenarios: happy: clean checkout installs and runs diagnostics/build; failure: stop the LSP server or restore vulnerable lockfile and prove Gate 95 blocks rather than accepting surrogate evidence. Evidence `.omo/evidence/task-22-static-deps/`.
  Rollback: dependency upgrade remains its own commit and can be reverted independently from type fixes.
  Commit: Y | `chore(quality): close dashboard static and dependency gates`

- [ ] 23. Run fresh all-tab production visual, interaction, CJK, and performance QA
  What to do / Must NOT do: After source freeze and final build, enumerate all 12 tabs, both themes, 375/768/1280 where responsive, and meaningful populated/loading/empty/error/stale/replay/live states. For S1-S4 include real API-loaded data, run switching, replay keyboard controls, stale/completed lifecycle, test OOS headline, and failure recovery. Capture real PNG evidence after the last build, console/network/timing traces, DOM overflow measurements, axe/keyboard results. Run two independent read-only reviewers on the same captures. Do not reuse historical/JPEG-mislabeled captures or approve from source markers.
  Parallelization: Wave 3 after source freeze | Blocked by: 10,12,17-22 | Blocks: 24,25
  References: `DESIGN.md`; project AGENTS capture rule; visual QA failures from the 2026-07-11 audit.
  Acceptance criteria: page/state inventory complete; 0 console errors, 0 unexpected failed requests, 0 overflow, AA/keyboard/chart semantics pass; first-card/full-hydration/API targets pass; both visual reviewers return unconditional PASS with no blocking finding.
  QA scenarios: happy: production build passes the complete matrix; failure: inject stale event, null action, long Korean ID, delayed endpoint, and negative test/positive combined artifact and prove the UI remains truthful and usable. Evidence `.omo/evidence/task-23-all-tab-visual/`.
  Rollback: failed QA returns to owning source todo; never edit generated dist directly as the fix.
  Commit: N | evidence-only gate; canonical summary committed with Todo 24

- [ ] 24. Build the clean 95 release candidate and run complete automated/runtime gates
  What to do / Must NOT do: Merge verified lanes sequentially into `release/dashboard-v3-95`, resolve by intent, regenerate dist once, and run full pytest or a documented complete shard matrix, targeted contracts/honesty/security, npm ci/check/build/audit, LSP/static, runtime HTTP/API, artifact hash/promotion audit, database read-only check, source/generated separation, and Git cleanliness. Record three runtime-debug hypotheses with actual evidence. Run review-work goal/code/security/hands-on/context lanes. Timeout, missing deliverable, ack-only, or inconclusive is FAIL.
  Parallelization: Wave 3 terminal integration | Blocked by: 13-23 | Blocks: 25
  References: project AGENTS commands; verification strategy; `review-work` and debugging gates; Todo 4 branch rules.
  Acceptance criteria: all automated/runtime gates exit 0 or have only documented expected skips; no unapproved route/frozen-file diff; no missing canonical hashes; clean tree after generated cleanup; every review lane terminal PASS; scorecard evidence paths resolve to this exact SHA.
  QA scenarios: happy: reproduce release candidate in a fresh worktree; failure: leave an ignored smoke as newest, modify a frozen route, make DB writable, or omit a reviewer and prove release gate fails. Evidence `.omo/evidence/task-24-release-candidate/`.
  Rollback: abort integration on conflict/gate failure; preserve individual verified branches and use revertable atomic merges, never reset user work.
  Commit: Y | `chore(release): assemble dashboard-v3 95-point candidate`

- [ ] 25. Independently rescore 95, publish the final handoff, and prepare the master PR
  What to do / Must NOT do: Have an independent scorer recompute all 20 criteria from Todo 24/23 artifacts; run final plan compliance, code quality, security, hands-on QA, scope fidelity, and two visual receipts. Require total >=95, every category >=19, no cap, clean tree, and separate model verdict. Write a new dated self-contained handoff with exact branch/SHA, scores, commands, artifact inventory, verdicts, remaining NO-GO/risks, rollback/recovery, and master merge instructions. Publish `origin/dashboard-v3` and prepare the PR only after the user approves final receipts. Do not describe 95 as profitability or push/merge without approval.
  Parallelization: Final | Blocked by: 24 | Blocks: none
  References: scorecard; `docs/AGENTS.md`; current handoff structure; Git ancestry/upstream evidence.
  Acceptance criteria: independent score JSON and human report agree; >=95 and category floors pass; model verdict remains explicit; handoff alone can resume; `git status --short` clean; user receives final receipts before any external publication/merge.
  QA scenarios: happy: rescore from a fresh clone/evidence bundle and reproduce 95+; failure: substitute a positive val+test curve for negative test or remove one review receipt and prove score/PR gate fails. Evidence `.omo/evidence/task-25-final-score/` and `docs/kronos_95_completion_handoff_<date>.md`.
  Rollback: docs and branch publication can be reverted/closed; never rewrite master history.
  Commit: Y | `docs(dashboard-v3): record verified 95-point completion handoff`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance and independent score audit
  Verify every todo’s acceptance/evidence/commit, dependency ordering, category points, hard caps, frozen-file changes, and separate model verdict. Recompute the score from raw evidence without using worker summaries. PASS requires >=95, each category >=19, zero missing evidence, and an unconditional reviewer receipt at `.omo/evidence/final-f1-score-audit.md`.
- [ ] F2. Code, static, dependency, and security quality audit
  Review changed Python/TS/Svelte/config/lockfile code, LSP/static output, npm audit disposition, CORS/path/debug/docs rendering, resource bounds, database read-only behavior, and source/generated separation. PASS requires no blocking correctness/security/type/dependency issue and receipt `.omo/evidence/final-f2-quality-security.md`.
- [ ] F3. Real production-surface manual QA
  Re-run the full all-tab visual/state matrix, selected-run transitions, stale/live/completed, null action, mixed units, negative test/positive combined, long Korean strings, keyboard, console/network, and latency from the production build. Two independent visual reviewers must PASS the same evidence. Receipt `.omo/evidence/final-f3-manual-visual.md`.
- [ ] F4. Scope, branch, artifact, and honesty fidelity
  Audit clean ancestry from the approved integration base, atomic commits, no old-branch replay, no unauthorized API/frozen-file edit, no generated bulk commit, exact 23bp/OOS/seed/baseline/control labels, preserved NO-GO, and no live/profit claim. PASS requires clean Git state and receipt `.omo/evidence/final-f4-scope-honesty.md`.

## Commit strategy
- One purpose branch per lane, all forked from the latest verified `dashboard-v3` integration head: `fix/dashboard-v3-evidence-truth`, `fix/dashboard-v3-responsive-a11y`, `fix/dashboard-v3-local-security`, `research/kronos-r5-results`, `feature/daily-close-sb3-r3b`, `research/daily-close-r4-honesty`, `feature/rl-governance-r6-r7`, and `release/dashboard-v3-95`.
- Never develop in `master`, `dashboard-remodel`, `feature/stom-rl-lab`, `feature/dashboard-research-command-center`, review branches, research history branches, or backup worktrees.
- Before creating each lane: clean-tree assertion, `merge-base --is-ancestor <integration> HEAD`, and current scorecard/evidence SHA record.
- Each todo names its atomic commit. Implementation and direct tests stay together. Generated evidence is excluded unless explicitly promoted.
- Merge order follows the dependency matrix. Re-run the lane gate after updating from the latest integration head.
- The plan-writing turn commits only `docs/kronos_90_to_95_completion_master_plan_2026-07-11.md` with `docs(plan): define Kronos 90-to-95 completion roadmap`.

## Success criteria
- The versioned scorecard independently computes >=90 at Gate 90 and >=95 at Gate 95 with no category below its floor and no hard cap active.
- Dashboard/release quality, research-pipeline completion, and model verdict are shown separately; model verdict may remain NO-GO without reducing a correctly completed engineering score.
- All program-level outcomes in `docs/kronos_rl_rebuild_implementation_plan_2026-07-10.md:395-406` are observable or honestly blocked by recorded research results.
- The four critical pages and all 12 tabs meet the specified truth, accessibility, responsive, performance, and failure-state gates on fresh production-build captures.
- R5, R3b, R4, R6, and R7 produce preregistered, hashable, reproducible artifacts or explicit NO-GO stop artifacts.
- Security is suitable for a trusted local research workstation; the plan makes no internet-service or live-trading claim.
- `dashboard-v3` is clean, current, documented, and ready to publish to `origin/dashboard-v3` for a user-approved PR to `master`.

# Kronos V5.1 exact 15:20 causal source and panel ADR — 2026-07-17

## Status

Accepted for additive research-only implementation. This ADR does not authorize live execution, broker integration, paper trading, model promotion, profitability, official-close, or GO/readiness claims. V3 remains the default production dashboard boundary unless a separate release decision changes that.

## Decision

Kronos V5.1 will use a new exact 15:20 KST source contract and a new causal panel/evaluator boundary instead of patching legacy daily-close artifacts.

The source contract is `kronos_daily_1520_source.v1`:

- `schema_version="kronos_daily_1520_source.v1"`.
- `causal_cutoff_kst="15:20:00"`; runtime artifacts do not carry a separate `timezone` field, and emitted timestamps carry the `+09:00` KST offset.
- `price_basis="15:20_bar_close_proxy"` and `official_close=false`.
- `source_db_path` is the resolved read-only DB path ending `_database/Stock_Database_ohlcv_5min.db`; `source_db_sha256=<64 lowercase hex>` and `source_hash_basis="ACTUAL_FILE_BYTES_STREAMING_SHA256"`.
- source tables are numeric `A######` table names, symbols are numeric six-character strings such as `000250`, and source row columns are exactly `date/open/high/low/close/volume`. Panel `exactSourceColumnSet` audit fields serialize the same identity as sorted `close/date/high/low/open/volume` for deterministic digests and validation.
- `timestamp_kst` must be an exact `YYYY-MM-DDT15:20:00+09:00` timestamp. Runtime dataclasses keep the compact timestamp as an integer, while JSON artifacts encode `timestamp_yyyymmddhhmm` as an exact `YYYYMMDD1520` string so standard JSON Schema can enforce the 15:20 suffix; timestamps after 15:20 are invalid.
- no nearest fallback, no full-day daily OHLCV substitution, and no `price * volume` amount approximation.
- `bar_volume_1520` is the 5-minute bar volume only. `volume_to_1520` and `cumulative_volume_to_1520` are `null` with `*_status="NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY"` until a verified cumulative source exists.
- amount is unavailable unless a verified cumulative amount source exists: current 5-minute DB rows use `amount_to_1520=null` and `amount_to_1520_status="NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME"`.
- row, coverage, and missing-date statuses fail closed rather than silently filling values.
- `false_research_locks` and `six_locks_false` are closed objects with all values false for `promotion_allowed`, `model_build_allowed`, `paper_forward_allowed`, `live_broker_order_allowed`, `profitability_claim_allowed`, and `go_summary_allowed`; `no_claim_flags` is a closed object with all claim flags false.

The panel contract is `kronos_daily_v51_causal_panel.v1`:

- it consumes validated `kronos_daily_1520_source.v1` artifacts plus approved offline source artifacts.
- each row carries `causal_cutoff_kst`, `cutoff`, `cutoff_timestamp`, `max_observation_timestamp`, `entry_1520_status`, nested `entry_1520`, nested `exit_1520_by_label`, `labels`, and `label_statuses`; entry/exit marks carry `price_basis`, `official_close=false`, `close`, `price`, `price_1520_close_proxy`, and `bar_volume_1520`.
- labels are exact 15:20-to-15:20 returns: `future_return_h1_1520_proxy`, `future_return_h3_1520_proxy`, and `future_return_h5_1520_proxy`.
- each label has a status payload with exact values `available`, `missing_entry`, or `missing_exit`; missing labels publish `null`, not a synthetic return.
- legacy `future_return_1d`, full-day/daily/final/one-day OHLCV and amount fields, official close, daily OHLCV sources, and price×volume amount fields are forbidden causal inputs.
- `source_identity` is a required closed object with `schema_version`, `identity_basis="explicit"`, `source_db_path`/`source_db_paths`, non-null lowercase 64-hex `source_db_sha256`, `source_tables`, `schema_versions`, table-order `source_columns`, `exact_1520_row_count`, and `source_identity_sha256`; derived or null hash modes are invalid. `audit.observation_sources`, `audit.observation_field_policy`, `audit.exact_1520_source`, and `audit.source_audit` are closed, schema-validated audit objects. Runtime validation also enforces equality between duplicate top-level label fields and the nested `labels` map because JSON Schema cannot cross-compare those values.
- `locks` has six booleans and all remain false: `official_close`, `full_day_daily_ohlcv`, `live_trading`, `profit_claim`, `paper_trading`, and `broker_integration`. `promotion_claims` is a closed object with `live_trading`, `profit`, `paper_trading`, and `broker_integration` all false.

The evaluator boundary starts after panel validation. Evaluators may compute costs, NAV, baseline/control metrics, and split-specific reports from the validated panel, but may not reread `_database/Stock_Database_ohlcv_1day.db`, repair missing labels, substitute a nearest bar, use UI payloads as truth, or convert research evidence into live/paper/broker/profit claims.

## Drivers

- The approved V5.1 requirement sets D-day 15:20 KST as the decision cutoff and uses the 15:20 bar close as a research proxy, not the KRX official 15:30 close.
- `_database/Stock_Database_ohlcv_5min.db` has observed 15:20 rows and source columns `date/open/high/low/close/volume`; the 5-minute DB does not provide verified amount.
- The existing daily OHLCV source cannot be treated as 15:20 evidence because it is full-day data.
- Leading-zero symbols must remain strings.
- Existing V3/V5 honesty boundaries, prior NO-GO verdicts, read-only database access, and false locks must remain intact.
- User display should show costs as percentages, while internal JSON/API identifiers such as `round_trip_cost_bp` and `base_23bp` remain stable legacy identifiers.

## Selected boundary

1. Source adapter: read-only access to `_database/Stock_Database_ohlcv_5min.db`, select exact `YYYYMMDD1520` rows, emit `kronos_daily_1520_source.v1`, and record source SHA-256/table/column identity.
2. Causal panel builder: consume only validated source artifacts, derive causal features whose maximum observation timestamp is no later than D 15:20, and derive H1/H3/H5 labels from D+N exact 15:20 rows.
3. Evaluator: consume only validated panel artifacts and preregistered split/cost configuration. It may score research runs but cannot fill source gaps or widen the data boundary.
4. UI/reporting: display validated artifacts and warnings only. UI is not the source of truth and must keep V3/default/no-claim boundaries.

## Rejected alternatives

- Patch legacy daily-close/D3 artifacts: rejected because legacy `future_return_1d` and full-day daily OHLCV semantics can leak information after 15:20 and blur the proxy/official-close distinction.
- UI-first implementation: rejected because dashboard rendering cannot define source authority, label causality, or amount/volume provenance. The schema and evaluator boundary must be stable before UI consumption.
- Nearest-bar fallback: rejected because it would silently turn missing 15:20 evidence into a synthetic fill.
- Full-day daily OHLCV fallback: rejected because it uses information after the 15:20 decision cutoff.
- Price×volume amount approximation: rejected because the source DB does not verify cumulative traded amount to 15:20.

## PyKRX-only offline artifact policy

Only PyKRX-derived universe/calendar/index inputs may enter this boundary, and they must be captured as local offline artifacts with SHA-256 identity before evaluation. Network access is not part of panel/evaluator execution. Naver-derived or Naver-fallback sources are forbidden by policy and are never an allowed fallback. Runtime rejects forbidden sources before artifact creation, so successful artifacts keep `audit.source_audit.forbidden_sources=[]` as the empty list of encountered forbidden sources; Naver mutations remain schema/runtime-negative cases. If an approved PyKRX offline artifact is absent, the dependent series or universe field remains missing/blocked rather than falling back to Naver or a full-day proxy.

## Consequences

- Missing entry or exit rows reduce coverage and label availability; they do not become zero returns or nearest-bar returns.
- H1/H3/H5 labels are explicit new fields; `future_return_1d` remains forbidden at the V5.1 causal boundary.
- Amount remains `amount_to_1520=null` with the exact unavailable status until independently verified cumulative amount data is connected.
- `bar_volume_1520` can be used only as a 5-minute bar value; `volume_to_1520` and `cumulative_volume_to_1520` remain `null` with explicit unavailable statuses until a separate verified cumulative source is connected.
- Existing BP identifiers remain in internal artifacts for compatibility. User-facing Korean documents and dashboards convert them to exact percentages such as `23bp -> 0.23%` without renaming the schema/API fields.
- The change is additive: it creates new schemas and a new ADR; it does not mutate product code, generated dist, `.gjc`, or existing NO-GO evidence.

## Rollback

Rollback is removal or non-use of the additive V5.1 source/panel schemas and any future modules that depend on them. Because the boundary is additive and read-only, rollback does not require database migration and does not alter V3/V5 existing behavior. If any source/panel validation conflict appears, the evaluator must stop at `BLOCKED_SOURCE_CONTRACT` or equivalent and leave prior research verdicts unchanged.

## No-claim and V3 boundaries

This decision preserves read-only DB access, string symbols, internal bp identifiers, prior NO-GO conclusions, and all false locks. It makes no live, broker, order, paper, profit, official-close, model-promotion, or default-dashboard claim. V3 remains available/default; V5.1 artifacts are research evidence until separately verified and released.

# Forward/Paper Evidence Ledger 결과 — 2026-06-11

## Verdict

```text
P3 read-only forward/paper evidence ledger: COMPLETE
Schema version: 1
Writer location: stom_rl/factory/forward_ledger.py
Dashboard/webui role: read-only consumer only
```

이 ledger는 모델 결정과 후행 outcome을 연구 artifact로 기록하는 장치다. 주문, broker 연동, live-trading readiness, 수익 보장 주장이 아니다.

## Writer contract

- Writer module: `stom_rl/factory/forward_ledger.py`
- Write target: generated artifacts under `webui/rl_runs/forward_ledger/`
- Duplicate policy: `skip_existing_record_id`
- Path policy: CLI default `--output-root webui/rl_runs/forward_ledger` rejects outputs outside the generated forward-ledger root; dashboard/webui는 쓰지 않는다.
- Schema version: `1`

Required record fields:

| Field | Meaning |
|---|---|
| `schema_version` | ledger schema version, fixed at 1 |
| `record_id` | `<run_id>:<session>:<code>` idempotency key |
| `recorded_at_utc` | writer timestamp |
| `session` | YYYYMMDD session |
| `code` | stock code as string, leading zeros preserved |
| `run_id` / `model_version` | model lineage labels |
| `p_win`, `edge_pct`, `decision` | model score and TAKE/SKIP |
| `fill_assumption` | realized_full / slgap_full / future assumption |
| `realized_outcome_pct` | resolved outcome when known, otherwise null |
| `baseline_outcome_pct` | same universe baseline outcome when known |
| `outcome_status` | `pending` or `resolved` |
| `cost_bps` | 23bp basis |

## Generated ledgers

| Run | Output | Existing | Appended | Duplicates skipped | Total | Status counts |
|---|---|---:|---:|---:|---:|---|
| `probability_lane_stacked_realized_full_2026_06_11` | `webui/rl_runs/forward_ledger/probability_lane_stacked_realized_full_2026_06_11/ledger.jsonl` | 4,469 | 0 | 4,469 | 4,469 | resolved 4,469 |
| `probability_lane_stacked_slgap_full_2026_06_11` | `webui/rl_runs/forward_ledger/probability_lane_stacked_slgap_full_2026_06_11/ledger.jsonl` | 4,469 | 0 | 4,469 | 4,469 | resolved 4,469 |

Initial generation appended 4,469 records per fill mode. The latest summaries above are idempotency reruns: existing=4,469, appended=0, skipped_duplicate=4,469.

## Commands

```powershell
py -3.11 -m stom_rl.factory.forward_ledger --edge-ledger webui/rl_runs/probability_lane/probability_lane_stacked_realized_full_2026_06_11/edge_ledger.json --output webui/rl_runs/forward_ledger/probability_lane_stacked_realized_full_2026_06_11/ledger.jsonl --run-id probability_lane_stacked_realized_full_2026_06_11 --model-version probability_lane_stacked_realized_full_2026_06_11@summary --fill-assumption realized_full
py -3.11 -m stom_rl.factory.forward_ledger --edge-ledger webui/rl_runs/probability_lane/probability_lane_stacked_slgap_full_2026_06_11/edge_ledger.json --output webui/rl_runs/forward_ledger/probability_lane_stacked_slgap_full_2026_06_11/ledger.jsonl --run-id probability_lane_stacked_slgap_full_2026_06_11 --model-version probability_lane_stacked_slgap_full_2026_06_11@summary --fill-assumption slgap_full
```

## Verification

```powershell
py -3.11 -m pytest tests/test_stom_rl_factory_forward_ledger.py tests/test_stom_rl_factory_registry.py tests/test_stom_rl_dashboard_factory_api.py -q
# 34 passed
```

P3 schema is now frozen enough for P4 read-only dashboard exposure. P5 remains blocked by P2 evidence even though P3 itself is complete.

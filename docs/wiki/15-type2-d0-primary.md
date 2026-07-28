# Type2-D0 Primary Reviewed Evidence

> Final review: 2026-07-28 KST  
> Experiment completed: 2026-07-27 KST  
> Authority: `REVIEWED_SNAPSHOT`

## Decision

| Field | Value |
|---|---|
| Run | `type2-d0-primary-20260727` |
| Matrix | 4 arms × 3 seeds = 12/12 |
| Status | `PRIMARY_COMPLETE` |
| Verdict | `PPO_ONLY_OVERFIT_NOT_CONFIRMED` |
| Research disposition | `NO-GO` |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Promotion / profitability / live | blocked / blocked / blocked |

The D0 run created real local SB3 model bundles, but PPO-only did not reliably
memorize the synthetic train-only task. BC-only reached the perfect synthetic
fit, and shuffled-reward PPO collapsed. This is a research failure record, not
profitability or live-readiness evidence. `ts_imb` remains a RULE baseline.

## Evidence paths

The dashboard document reader serves only Markdown inside `docs/wiki`, so the
authoritative repository paths are listed as code rather than broken links:

- Result: `docs/kronos_rl_discovery_type2_d0_primary_result_2026-07-27.md`
- Lifecycle/full-page review: `docs/kronos_rl_model_lifecycle_and_page_execution_2026-07-27.md`
- Evidence inventory: `docs/evidence/type2-d0-primary-20260727.custody.json`
- Reviewed UI snapshot: `webui/v2_src/src/v6shell/discovery/reviewedDiscoverySnapshot.ts`

The 40-file inventory covers 596,114,829 bytes and has evidence-manifest SHA-256
`f44fc17a587050c865b22ba1cd671e276f768282afc91a6ed4168619cec59825`.
The legacy receipt did not record the fixture SHA, so fixture provenance is
explicitly `PRODUCER_DECLARED_LEGACY_UNVERIFIED`. Future lifecycle v2 runs bind
exact input snapshots and each completed outcome/model/normalizer digest.

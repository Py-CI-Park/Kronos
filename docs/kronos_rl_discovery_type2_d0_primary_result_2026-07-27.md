# Type2-D0 Primary attribution result

**Completed:** 2026-07-27 KST  
**Run:** `webui/rl_runs/rl_discovery/type2-d0-primary-20260727`  
**Profile:** `PRIMARY`  
**Experiment:** `type2-d0-ppo-attribution-v0`  
**Prereg SHA-256:** `2c3bced20fc6b718f7c2f37963501e962b2198b8b620fd6a1e4a91e20ff0ce4d`  
**Elapsed:** 9,546.2 seconds, approximately 2 hours 39 minutes  
**Verdict:** `PPO_ONLY_OVERFIT_NOT_CONFIRMED`

## Evidence scope

This result is valid only for the reduced executable D0 contract in
`docs/kronos_rl_discovery_type2_d0_prereg_2026-07-26.json`. Earlier planning
notes described a richer diagnostic program; those extra diagnostics were not
silently treated as executed and are not part of this result. Any expanded
reward/action study must be registered as a separate D1 experiment before it
runs.

## Terminal decision

| Field | Value |
|---|---|
| Status | `PRIMARY_COMPLETE` |
| Verdict | `PPO_ONLY_OVERFIT_NOT_CONFIRMED` |
| Promotion allowed | `false` |
| Profitability claim allowed | `false` |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Research disposition | `NO-GO` for the current PPO-only attribution hypothesis |

The run completed all 12 preregistered arm/seed units. It did not confirm that
PPO alone can reliably overfit the train-only synthetic task. The result closes
this D0 hypothesis as a documented failure; it does not open Fresh OOS, a
profitability claim, or live trading.

## Arm and seed results

| Arm | Seed | PPO steps | Reward ratio | Exact basket accuracy | Dominant action rate |
|---|---:|---:|---:|---:|---:|
| A_PPO_ONLY | 0 | 104,000 | 0.750000 | 0.812500 | 0.437500 |
| A_PPO_ONLY | 1 | 104,000 | 0.125000 | 0.343750 | 0.906250 |
| A_PPO_ONLY | 2 | 104,000 | 0.500000 | 0.625000 | 0.625000 |
| B_BC_THEN_PPO | 0 | 104,000 | 0.875000 | 0.906250 | 0.343750 |
| B_BC_THEN_PPO | 1 | 104,000 | 0.770833 | 0.828125 | 0.421875 |
| B_BC_THEN_PPO | 2 | 104,000 | 1.000000 | 1.000000 | 0.250000 |
| C_BC_ONLY | 0 | 0 | 1.000000 | 1.000000 | 0.250000 |
| C_BC_ONLY | 1 | 0 | 1.000000 | 1.000000 | 0.250000 |
| C_BC_ONLY | 2 | 0 | 1.000000 | 1.000000 | 0.250000 |
| D_SHUFFLED_REWARD_PPO | 0 | 104,000 | 0.000000 | 0.250000 | 1.000000 |
| D_SHUFFLED_REWARD_PPO | 1 | 104,000 | 0.000000 | 0.250000 | 1.000000 |
| D_SHUFFLED_REWARD_PPO | 2 | 104,000 | 0.000000 | 0.250000 | 1.000000 |

## Arm aggregates

| Arm | Mean reward ratio | Mean exact accuracy | Mean dominant action rate | Interpretation |
|---|---:|---:|---:|---|
| A_PPO_ONLY | 0.458333 | 0.593750 | 0.656250 | Unstable and below the 0.90 threshold for every seed |
| B_BC_THEN_PPO | 0.881944 | 0.911458 | 0.338542 | Better after oracle BC, but not PPO-only attribution |
| C_BC_ONLY | 1.000000 | 1.000000 | 0.250000 | Oracle BC alone fully memorized the synthetic task |
| D_SHUFFLED_REWARD_PPO | 0.000000 | 0.250000 | 1.000000 | Negative control collapsed and did not learn the task |

## Findings

1. PPO-only failed the preregistered memorization threshold on all three seeds.
2. Shuffled-reward PPO collapsed to one action and achieved zero reward ratio,
   so the native reward contains usable task information.
3. BC-only reached 1.0 for every seed without PPO. The synthetic oracle labels,
   not PPO, explain the perfect fit.
4. BC-then-PPO was weaker than BC-only on two seeds, so the PPO phase did not
   consistently preserve the calibrated policy.
5. Seed variance in PPO-only is large. A single seed would have produced a
   misleading conclusion.

## Durable artifacts

| Artifact | Count / value |
|---|---:|
| Model ZIP files | 12 |
| Normalizer files | 12 |
| Per-seed outcome files | 12 |
| Total model/normalizer bytes | 596,099,180 |
| Lifecycle completed units | 12 / 12 |
| Terminal receipt | Present |
| Custody manifest | `docs/evidence/type2-d0-primary-20260727.custody.json` |
| Custody files / bytes | 40 / 596,114,829 |
| Evidence manifest SHA-256 | `f44fc17a587050c865b22ba1cd671e276f768282afc91a6ed4168619cec59825` |
| Producer commit | `9b555f52275bdae8f13c3c7190817a7290097b08` |
| Fixture binding | `PRODUCER_DECLARED_LEGACY_UNVERIFIED` |

The legacy D0 receipt binds the preregistration SHA but did not record a
fixture SHA. The manifest therefore inventories the fixture selected by the
producer commit, but it cannot prove that the runtime read those exact fixture
bytes. This limitation is explicit and prevents treating D0 as fully input-bound
custody. Lifecycle v2 snapshots and hashes exact input bytes for future runs.

## Next research action

Do not tune the same PPO-only run after seeing this result and call it a new
confirmatory test. Close D0 as `NO-GO`, then preregister a distinct D1
falsification question. A useful D1 can test whether a redesigned action/reward
contract enables PPO to preserve or improve a policy without oracle labels.

The D1 contract should remain train-only and must include:

- an explicit hypothesis and failure threshold;
- PPO-only, BC-only, BC-then-PPO, and shuffled-reward controls where applicable;
- at least three seeds;
- action-collapse metrics;
- no Fresh OOS access;
- no profitability or live-readiness claim.

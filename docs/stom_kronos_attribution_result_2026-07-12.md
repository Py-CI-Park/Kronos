# STOM/Kronos attribution result — 2026-07-12

> Research-only supervised/forecast attribution. No live/broker/profit/GO/RL/trading-alpha claim. Cost references use the platform primary 23bp gate; this result does not claim a tradable edge.

## Decision: TUNING_HARMFUL

The preregistered 681-window 36×3×50 lineage was recovered and the missing pretrained zero-shot comparison was generated through the existing evaluator. With `--seed 42 --sample-count 5` fixed decoding, fine-tuning is harmful under ε=0.005: finetuned direction accuracy `0.447870778267254` is below pretrained zero-shot `0.4552129221732746` by `0.0073421439060206`. The seed-42 random baseline is `0.4199706314243759`.

## Three-column attribution metrics

| column | direction_accuracy | rows | windows | MAE | RMSE | top-k hit_rate |
|---|---:|---:|---:|---:|---:|---:|
| finetuned seed42/sample5 | 0.447870778267 | 40860 | 681 | 469.373392 | 935.108633 | 0.464814814815 |
| pretrained zero-shot seed42/sample5 | 0.455212922173 | 40860 | 681 | 237.609682 | 510.238673 | 0.466666666667 |
| random seed42 | 0.419970631424 | 40860 | 681 | 220.131866 | 490.597258 | 0.407407407407 |

Persistence direction accuracy: `0.12041116005873716`.

Recovered prior lineage: existing unseeded/single-sample finetuned comparison has 681 windows, finetuned `0.447870778267254`, random `0.44933920704845814`, persistence `0.12041116005873716`, model path `finetune/outputs/stom_1s_grid_pred60_2025_full_small/finetune_predictor/checkpoints/best_model`, tokenizer path `finetune/outputs/stom_1s_grid_pred60_2025_full_small/finetune_tokenizer/checkpoints/latest_train_model`.

## Tokenizer reconstruction

| tokenizer | windows | MSE mean |
|---|---:|---:|
| NeoQuasar/Kronos-Tokenizer-base | 50 | 0.006195815294050 |
| finetuned latest_train_model | 50 | 0.003023716867901 |

Finetuned-minus-base MSE delta: `-0.003172098426148295`.

## Determinism and integrity

Zero-shot run1/run2 metric deltas are `0.0` at tolerance `0.0` for direction accuracy, MAE, RMSE, random, and persistence metrics. Command logs, source/input/output hashes, HF revisions, and missing/NaN/hash checks are under `.omo/evidence/task-13-r5-attribution/`, with the consolidated manifest at `.omo/evidence/task-13-r5-attribution/evidence_summary.json` and hash manifest at `.omo/evidence/task-13-r5-attribution/hashes.json`.

## F14 status

Not launched. Under the preregistered decision tree, `TUNING_HARMFUL` blocks F14 until tokenizer/data-representation investigation; this remains supervised forecast attribution only and is distinct from RL/trading alpha.

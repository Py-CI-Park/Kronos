"""WP-R5a — Kronos zero-shot attribution runner (research-only).

Answers the single decision-blocking question about the Kronos fine-tune:
*did fine-tuning fail, or is there simply no extractable signal at this
horizon/cost?* The flagship fine-tuned checkpoint scored direction accuracy
~0.4479 vs random ~0.4493 on 681 walk-forward windows — but the un-finetuned
pretrained Kronos was never evaluated on the same windows, so the outcome is
unattributed.

This runner evaluates the pretrained ``NeoQuasar/Kronos-small`` +
``NeoQuasar/Kronos-Tokenizer-base`` on the IDENTICAL 36x3x50 walk-forward as the
flagship run (seeded, sample_count=5 per WP-R5b), then compares direction
accuracy across finetuned / pretrained / random and emits an attribution report
with an explicit, pre-registered decision rule.

The heavy evaluation is delegated to ``finetune/evaluate_stom_1s_checkpoint.py``
(which owns torch/CUDA); this module only *builds* the command, optionally runs
it as a subprocess (``--run``), and assembles the report — so it imports and
unit-tests without torch or a GPU. Research-only: no profitability/GO claim.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Flagship 36x3x50 walk-forward config (docs/stom_2025_full_small_walkforward_eval_dashboard.md §3) ──
FLAGSHIP: dict[str, Any] = {
    "dataset_path": "finetune/qlib_exports/stom_1s_grid_pred60_2025/processed_datasets",
    "output_dir": "webui/stom_predictions",
    "lookback_window": 300,
    "predict_window": 60,
    "max_symbols": 50,
    "max_asofs": 3,
    "max_sessions": 36,
    "stride": 300,
    "batch_size": 8,
    "top_k": 5,
}
FINETUNED_PREFIX = "stom_1s_pred60_2025_full_small_walkforward36x3x50_eval"
ZEROSHOT_PREFIX = "stom_1s_pred60_2025_pretrained_zeroshot36x3x50_eval"
PRETRAINED_MODEL = "NeoQuasar/Kronos-small"
PRETRAINED_TOKENIZER = "NeoQuasar/Kronos-Tokenizer-base"

# Decision threshold: a direction-accuracy edge below this (in absolute terms) is
# treated as indistinguishable from random / from the other model.
DEFAULT_EPSILON = 0.005  # 0.5 percentage points


def build_pretrained_eval_cmd(
    *,
    python_exe: str | None = None,
    output_dir: str | None = None,
    prefix: str = ZEROSHOT_PREFIX,
    seed: int = 42,
    sample_count: int = 5,
    device: str = "cuda:0",
    eval_script: str = "finetune/evaluate_stom_1s_checkpoint.py",
) -> list[str]:
    """Build the exact zero-shot pretrained-baseline eval command.

    Mirrors the flagship 36x3x50 walk-forward flags but points ``--model-path`` /
    ``--tokenizer-path`` at the pretrained NeoQuasar models and adds the WP-R5b
    determinism flags (``--seed`` + ``--sample-count``).
    """
    cfg = FLAGSHIP
    return [
        python_exe or sys.executable,
        eval_script,
        "--dataset-path", cfg["dataset_path"],
        "--model-path", PRETRAINED_MODEL,
        "--tokenizer-path", PRETRAINED_TOKENIZER,
        "--output-dir", output_dir or cfg["output_dir"],
        "--prefix", prefix,
        "--lookback-window", str(cfg["lookback_window"]),
        "--predict-window", str(cfg["predict_window"]),
        "--max-symbols", str(cfg["max_symbols"]),
        "--max-asofs", str(cfg["max_asofs"]),
        "--max-sessions", str(cfg["max_sessions"]),
        "--stride", str(cfg["stride"]),
        "--batch-size", str(cfg["batch_size"]),
        "--top-k", str(cfg["top_k"]),
        "--seed", str(seed),
        "--sample-count", str(sample_count),
        "--device", device,
    ]


def load_comparison(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "metrics" not in data:
        raise ValueError(f"not a comparison JSON (missing 'metrics'): {path}")
    return data


def _direction_accuracy(comparison: Mapping[str, Any], mode: str) -> float | None:
    metrics = comparison.get("metrics", {})
    entry = metrics.get(mode) if isinstance(metrics, Mapping) else None
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("direction_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


def decide(
    finetuned_dir_acc: float | None,
    pretrained_dir_acc: float | None,
    random_dir_acc: float | None,
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> dict[str, str]:
    """Apply the pre-registered attribution decision rule.

    Verdicts:
      NO_SIGNAL           — finetuned and pretrained both ~= random -> no
                            extractable direction signal at this horizon/cost;
                            fine-tuning is not the culprit.
      TUNING_HARMFUL      — finetuned < pretrained -> fine-tuning degraded a
                            working pretrained model; investigate data/tokenizer.
      TUNING_HELPED_COST  — finetuned > pretrained (fine-tuning added value) yet
                            both fail the 25bp gate -> horizon/cost mismatch;
                            gate F14 (dedicated 300s refinetune).
      INCONCLUSIVE        — finetuned ~= pretrained but above random, or missing
                            data -> need the seeded/5-sample rerun or more seeds.
    """
    if finetuned_dir_acc is None or pretrained_dir_acc is None or random_dir_acc is None:
        return {
            "verdict": "INCONCLUSIVE",
            "rationale": "missing direction_accuracy for one or more of finetuned/pretrained/random",
        }
    fine_edge = finetuned_dir_acc - random_dir_acc
    pre_edge = pretrained_dir_acc - random_dir_acc
    if abs(fine_edge) <= epsilon and abs(pre_edge) <= epsilon:
        return {
            "verdict": "NO_SIGNAL",
            "rationale": (
                f"both finetuned ({finetuned_dir_acc:.4f}) and pretrained "
                f"({pretrained_dir_acc:.4f}) are within +/-{epsilon} of random "
                f"({random_dir_acc:.4f}); no direction signal at 60s — fine-tuning is not the failure."
            ),
        }
    if finetuned_dir_acc < pretrained_dir_acc - epsilon:
        return {
            "verdict": "TUNING_HARMFUL",
            "rationale": (
                f"finetuned ({finetuned_dir_acc:.4f}) < pretrained ({pretrained_dir_acc:.4f}); "
                "fine-tuning degraded the pretrained model — investigate data representation "
                "(close_only/O=H=L=C) and the unvalidated tokenizer (WP-R5c) before more training."
            ),
        }
    if finetuned_dir_acc > pretrained_dir_acc + epsilon:
        return {
            "verdict": "TUNING_HELPED_COST",
            "rationale": (
                f"finetuned ({finetuned_dir_acc:.4f}) > pretrained ({pretrained_dir_acc:.4f}); "
                "fine-tuning added value but 60s cannot beat cost — proceed to F14 (dedicated 300s "
                "refinetune, 23bp gate) rather than a bigger 60s run."
            ),
        }
    return {
        "verdict": "INCONCLUSIVE",
        "rationale": (
            f"finetuned ({finetuned_dir_acc:.4f}) ~= pretrained ({pretrained_dir_acc:.4f}) "
            "but not clearly at random; rerun seeded with more sample_count/seeds to resolve."
        ),
    }


def build_attribution(
    finetuned_comparison: Mapping[str, Any],
    zeroshot_comparison: Mapping[str, Any],
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> dict[str, Any]:
    """Assemble the attribution table + decision from the two comparison JSONs."""
    fine = _direction_accuracy(finetuned_comparison, "kronos")
    pre = _direction_accuracy(zeroshot_comparison, "kronos")
    # Prefer the finetuned run's random baseline; fall back to the zero-shot run's.
    rnd = _direction_accuracy(finetuned_comparison, "random")
    if rnd is None:
        rnd = _direction_accuracy(zeroshot_comparison, "random")
    persistence = _direction_accuracy(finetuned_comparison, "persistence")
    decision = decide(fine, pre, rnd, epsilon=epsilon)
    return {
        "schema": "kronos_zeroshot_attribution.v1",
        "research_only": True,
        "no_claim": "RESEARCH_ONLY; no profitability/GO/model-build claim.",
        "horizon_seconds": FLAGSHIP["predict_window"],
        "epsilon": epsilon,
        "direction_accuracy": {
            "finetuned": fine,
            "pretrained_zeroshot": pre,
            "random": rnd,
            "persistence": persistence,
        },
        "edges_vs_random": {
            "finetuned": None if (fine is None or rnd is None) else fine - rnd,
            "pretrained_zeroshot": None if (pre is None or rnd is None) else pre - rnd,
        },
        "decision": decision,
        "next_action": {
            "NO_SIGNAL": "Freeze Kronos refinetune; document no-signal at 60s. Optionally test 300s (F14) for exploration only.",
            "TUNING_HARMFUL": "Run WP-R5c tokenizer reconstruction + fix data representation before any refinetune.",
            "TUNING_HELPED_COST": "Proceed to F14: dedicated 300s refinetune with the 23bp cost gate.",
            "INCONCLUSIVE": "Rerun the zero-shot eval seeded with more sample_count/seeds; then re-decide.",
        }[decision["verdict"]],
    }


def write_report(attribution: Mapping[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(attribution, ensure_ascii=False, indent=2), encoding="utf-8")
    da = attribution["direction_accuracy"]
    edges = attribution["edges_vs_random"]

    def _fmt(x: Any) -> str:
        return f"{x:.4f}" if isinstance(x, (int, float)) else "—"

    md = f"""# Kronos zero-shot attribution — {FLAGSHIP['predict_window']}s (research-only)

> {attribution['no_claim']}

## Direction accuracy (681-window 36x3x50 walk-forward)

| model | direction_accuracy | edge vs random |
| --- | ---: | ---: |
| fine-tuned (flagship) | {_fmt(da['finetuned'])} | {_fmt(edges['finetuned'])} |
| pretrained zero-shot | {_fmt(da['pretrained_zeroshot'])} | {_fmt(edges['pretrained_zeroshot'])} |
| random | {_fmt(da['random'])} | — |
| persistence | {_fmt(da['persistence'])} | — |

## Verdict — {attribution['decision']['verdict']}

{attribution['decision']['rationale']}

**Next action:** {attribution['next_action']}
"""
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")


def _comparison_path(output_dir: str, prefix: str) -> Path:
    return REPO_ROOT / output_dir / f"{prefix}_comparison.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WP-R5a Kronos zero-shot attribution runner (research-only).")
    parser.add_argument("--run", action="store_true", help="Execute the pretrained zero-shot eval subprocess (needs GPU/models). Without this flag, only the report is built from existing comparison JSONs.")
    parser.add_argument("--report-only", action="store_true", help="Only build the report from existing comparison JSONs; never run the eval (default behaviour when --run is absent).")
    parser.add_argument("--python-exe", default=None, help="Python used for the eval subprocess (default: this interpreter).")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--output-dir", default=FLAGSHIP["output_dir"], help="Where the eval writes prediction/comparison JSONs.")
    parser.add_argument("--finetuned-comparison", default=None, help="Path to the flagship fine-tuned comparison JSON (default: derived from the flagship prefix).")
    parser.add_argument("--zeroshot-comparison", default=None, help="Path to the pretrained zero-shot comparison JSON (default: derived from the zero-shot prefix).")
    parser.add_argument("--report-dir", default="docs", help="Where to write the attribution report md.")
    parser.add_argument("--report-json", default="webui/stom_predictions/stom_1s_pred60_zeroshot_attribution.json")
    parser.add_argument("--epsilon", type=float, default=DEFAULT_EPSILON)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.run and not args.report_only:
        cmd = build_pretrained_eval_cmd(
            python_exe=args.python_exe,
            output_dir=args.output_dir,
            seed=args.seed,
            sample_count=args.sample_count,
            device=args.device,
        )
        print("[R5a] running pretrained zero-shot eval:\n  " + " ".join(cmd), flush=True)
        completed = subprocess.run(cmd, cwd=str(REPO_ROOT))
        if completed.returncode != 0:
            print(f"[R5a] eval subprocess failed (exit {completed.returncode})", file=sys.stderr)
            return completed.returncode

    finetuned_path = Path(args.finetuned_comparison) if args.finetuned_comparison else _comparison_path(args.output_dir, FINETUNED_PREFIX)
    zeroshot_path = Path(args.zeroshot_comparison) if args.zeroshot_comparison else _comparison_path(args.output_dir, ZEROSHOT_PREFIX)
    for label, path in (("finetuned", finetuned_path), ("zero-shot", zeroshot_path)):
        if not path.exists():
            print(
                f"[R5a] {label} comparison JSON not found: {path}\n"
                "      Run the corresponding eval first (use --run for the zero-shot one).",
                file=sys.stderr,
            )
            return 2

    attribution = build_attribution(
        load_comparison(finetuned_path),
        load_comparison(zeroshot_path),
        epsilon=args.epsilon,
    )
    out_json = REPO_ROOT / args.report_json
    out_md = REPO_ROOT / args.report_dir / "stom_kronos_attribution_report_generated.md"
    write_report(attribution, out_json, out_md)
    print(f"[R5a] verdict={attribution['decision']['verdict']}  report={out_md}", flush=True)
    print(json.dumps(attribution["direction_accuracy"], ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

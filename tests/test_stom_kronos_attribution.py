"""WP-R5a unit tests — Kronos zero-shot attribution runner.

Exercises the command builder + pre-registered decision rule + report assembly
without torch, a GPU, or any actual model (the heavy eval is delegated to
finetune/evaluate_stom_1s_checkpoint.py via subprocess and is never run here).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from finetune.run_zeroshot_attribution_eval import (  # noqa: E402
    PRETRAINED_MODEL,
    PRETRAINED_TOKENIZER,
    build_attribution,
    build_pretrained_eval_cmd,
    decide,
)


def _cmd_map(cmd):
    """Turn a flag list into {flag: value} for easy assertions."""
    out = {}
    i = 0
    while i < len(cmd):
        tok = cmd[i]
        if isinstance(tok, str) and tok.startswith("--"):
            out[tok] = cmd[i + 1] if i + 1 < len(cmd) else True
            i += 2
        else:
            i += 1
    return out


def test_pretrained_eval_cmd_mirrors_flagship_and_adds_determinism():
    cmd = build_pretrained_eval_cmd(python_exe="python", seed=42, sample_count=5, device="cpu")
    m = _cmd_map(cmd)
    # points at the pretrained models, not a fine-tuned checkpoint
    assert m["--model-path"] == PRETRAINED_MODEL
    assert m["--tokenizer-path"] == PRETRAINED_TOKENIZER
    # identical 36x3x50 walk-forward as the flagship run
    assert m["--lookback-window"] == "300"
    assert m["--predict-window"] == "60"
    assert m["--max-symbols"] == "50"
    assert m["--max-asofs"] == "3"
    assert m["--max-sessions"] == "36"
    assert m["--stride"] == "300"
    assert m["--top-k"] == "5"
    # WP-R5b determinism flags
    assert m["--seed"] == "42"
    assert m["--sample-count"] == "5"
    # distinct prefix so it never overwrites the flagship artifacts
    assert m["--prefix"].startswith("stom_1s_pred60_2025_pretrained_zeroshot")
    assert cmd[0] == "python" and cmd[1].endswith("evaluate_stom_1s_checkpoint.py")


def test_decide_no_signal_when_both_near_random():
    v = decide(0.4479, 0.4490, 0.4493)
    assert v["verdict"] == "NO_SIGNAL"


def test_decide_tuning_harmful_when_finetuned_below_pretrained():
    v = decide(0.44, 0.47, 0.4493)
    assert v["verdict"] == "TUNING_HARMFUL"


def test_decide_tuning_helped_cost_when_finetuned_above_pretrained():
    v = decide(0.49, 0.45, 0.4493)
    assert v["verdict"] == "TUNING_HELPED_COST"


def test_decide_inconclusive_when_missing_or_tied_above_random():
    assert decide(None, 0.45, 0.44)["verdict"] == "INCONCLUSIVE"
    assert decide(0.47, 0.47, 0.44)["verdict"] == "INCONCLUSIVE"  # tied but above random


def test_build_attribution_extracts_metrics_and_decides():
    finetuned = {"metrics": {
        "kronos": {"direction_accuracy": 0.4479},
        "random": {"direction_accuracy": 0.4493},
        "persistence": {"direction_accuracy": 0.5011},
    }}
    zeroshot = {"metrics": {"kronos": {"direction_accuracy": 0.4485}}}
    att = build_attribution(finetuned, zeroshot)
    assert att["research_only"] is True
    assert att["direction_accuracy"]["finetuned"] == 0.4479
    assert att["direction_accuracy"]["pretrained_zeroshot"] == 0.4485
    assert att["direction_accuracy"]["random"] == 0.4493
    # 0.4479 & 0.4485 both within 0.005 of random 0.4493 -> NO_SIGNAL
    assert att["decision"]["verdict"] == "NO_SIGNAL"
    assert "profitability" in att["no_claim"].lower()
    assert att["next_action"]  # non-empty guidance


def test_build_attribution_missing_pretrained_is_inconclusive():
    finetuned = {"metrics": {"kronos": {"direction_accuracy": 0.44}, "random": {"direction_accuracy": 0.4493}}}
    zeroshot = {"metrics": {"random": {"direction_accuracy": 0.4493}}}  # no kronos key
    att = build_attribution(finetuned, zeroshot)
    assert att["decision"]["verdict"] == "INCONCLUSIVE"

"""WP-R1 unit tests — close-slot linear-score feature normalization.

Guards the fix for the 0-symbol bug: a large-scale feature (e.g.
institutional_net_buy ~1e6) must no longer dominate the linear score after the
weighted-covariance + L1 fit, because features are z-scored with frozen
train-only statistics before fitting and at scoring time.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_train import (  # noqa: E402
    _fit_linear_score_weights,
    _linear_score,
)


def _train_rows(big_scale: float):
    """Two features both linearly tied to the label, on wildly different scales.

    'inst' is `big_scale` x the signal, 'ret' is 1x. Under a raw-covariance fit
    the L1-normalized weight collapses onto 'inst'; under z-scoring the two
    become identical standardized vectors and split the weight evenly.
    """
    rows = []
    for idx, signal in enumerate([-2.0, -1.0, 1.0, 2.0, -1.5, 1.5]):
        rows.append(
            {
                "split": "train",
                "date": f"2024-01-{idx + 1:02d}",
                "table": f"A{idx:06d}",
                "code": f"{idx:06d}".zfill(6),
                "eligible_for_selection": True,
                "entry_close": 1000,
                "next_close": 1000 + signal,
                "future_return_1d": 0.01 * signal,
                "inst": big_scale * signal,
                "ret": signal,
            }
        )
    return rows


def test_fit_no_single_weight_dominance():
    features = ["inst", "ret"]
    model = _fit_linear_score_weights(_train_rows(big_scale=1_000_000.0), features)
    weights = model["weights"]
    l1 = sum(abs(v) for v in weights.values()) or 1.0
    top_share = max(abs(v) for v in weights.values()) / l1
    # Raw-covariance fit would give ~0.9999 to 'inst'; z-scoring balances them.
    assert top_share <= 0.7, f"a single feature still dominates the L1 mass: {weights}"
    assert model["fit_method"] == "train_only_zscore_covariance_l1_v1"
    # Scaler frozen for both features.
    assert set(model["feature_mean"]) == set(features)
    assert model["feature_std"]["inst"] > model["feature_std"]["ret"]  # scale preserved in std


def test_score_uses_frozen_train_stats():
    features = ["inst", "ret"]
    rows = _train_rows(big_scale=1_000_000.0)
    model = _fit_linear_score_weights(rows, features)
    mean = model["feature_mean"]
    std = model["feature_std"]
    # A row sitting exactly at the train mean scores 0 (all z=0).
    at_mean = {"inst": mean["inst"], "ret": mean["ret"]}
    assert abs(_linear_score(at_mean, model)) < 1e-9
    # A row one std above the mean on each feature scores exactly sum(weights).
    one_std = {"inst": mean["inst"] + std["inst"], "ret": mean["ret"] + std["ret"]}
    expected = model["weights"]["inst"] + model["weights"]["ret"]
    assert abs(_linear_score(one_std, model) - expected) < 1e-9


def test_missing_value_imputed_to_train_mean():
    features = ["inst", "ret"]
    model = _fit_linear_score_weights(_train_rows(big_scale=1_000_000.0), features)
    mean = model["feature_mean"]
    # Missing 'inst' must score identically to 'inst' at the train mean (z=0).
    missing = {"ret": mean["ret"]}
    imputed = {"inst": mean["inst"], "ret": mean["ret"]}
    assert abs(_linear_score(missing, model) - _linear_score(imputed, model)) < 1e-9


def test_legacy_bare_weight_map_still_scores_raw():
    # Back-compat: a plain {feature: weight} map (no scaler keys) uses the raw dot product.
    legacy = {"ret": 2.0}
    assert abs(_linear_score({"ret": 3.0}, legacy) - 6.0) < 1e-9

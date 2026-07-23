from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import sb3_contrib
import torch

from stom_rl.daily_type1_env import ACTION_COUNT, EXTRACTOR_WIDTH, STOP
from stom_rl import daily_type1_train
from stom_rl.daily_type1_train import (
    SUCCESS_LABEL,
    TrainingConfig,
    _oracle_calibration,
    _sha256_file,
    create_model,
    evaluate_model,
    load_synthetic_fixture,
    run_synthetic_overfit,
    train_model,
    train_synthetic_calibrated_model,
    verify_model,
)

FIXTURE = Path(__file__).with_name("fixtures") / "type1_synthetic_fixture.json"


def _small_config() -> TrainingConfig:
    return TrainingConfig(seed=7, synthetic_timesteps=20, n_steps=10, batch_size=10, oracle_calibration_epochs=2)


class _OraclePolicy:
    def predict(self, observation, deterministic=True, action_masks=None):
        del deterministic
        call = round(float(observation["portfolio_state"][0]) * 10)
        if call:
            return STOP, None
        signals = np.flatnonzero((observation["candidate_values"][:, 0] > 0) & (observation["availability_mask"] == 1))
        return (STOP if not len(signals) else int(signals[0]) + 1), None


def test_synthetic_fixture_has_exact_64_pair_g001_distribution_and_oracle_gate() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pairs = load_synthetic_fixture(FIXTURE)
    assert raw["label"] == SUCCESS_LABEL
    assert len(pairs) == 64
    assert [item["signal_slot"] is None for item in raw["pairs"]] == [index % 4 == 0 for index in range(64)]
    assert sum(pair["candidate_values"][:, 0].max() > 0 for pair in pairs) == 48
    assert sum(pair["candidate_values"][:, 0].max() <= 0 for pair in pairs) == 16
    assert all(pair["gross_returns"][0] in {"0.0200", "-0.0100"} for pair in pairs)

    events, metrics = evaluate_model(_OraclePolicy(), pairs)
    assert len(events) == 640
    assert [(event["pair_index"], event["call_index"]) for event in events] == [(pair, call) for pair in range(64) for call in range(10)]
    assert metrics["oracle_selection_count"] == 48
    assert metrics["oracle_no_trade_count"] == 16
    assert metrics["exact_basket_count"] == 64
    assert float(metrics["final_four_exact_mean"]) == 1.0
    assert float(metrics["achieved_reward_ratio"]) == 1.0
    assert float(metrics["final_four_reward_ratio"]) == 1.0
    assert metrics["invalid_action_count"] == metrics["block_count"] == metrics["no_fill_count"] == 0
    assert metrics["overfit_pass"] is True
    for pair in range(64):
        basket = events[pair * 10:(pair + 1) * 10]
        expected = basket[0]["oracle_action"]
        assert [event["action"] for event in basket] == [expected] + [STOP] * 9

@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.pop("pairs"), "schema is unsupported"),
        (lambda raw: raw.update({"unknown_root_key": None}), "schema is unsupported"),
        (lambda raw: raw.__setitem__("schema_version", "2"), "schema is unsupported"),
        (lambda raw: raw.__setitem__("schema_version", 1.0), "schema is unsupported"),
        (lambda raw: raw.__setitem__("label", "MARKET"), "explicitly TRAIN_ONLY"),
        (lambda raw: raw.__setitem__("partition", "VALIDATION"), "explicitly TRAIN_ONLY"),
        (lambda raw: raw.__setitem__("symbols", ["000001"] * 8), "pairs are malformed"),
        (lambda raw: raw.__setitem__("symbols", raw["symbols"][:-1]), "eight six-digit"),
        (lambda raw: raw.__setitem__("symbols", ["broken"] * 8), "eight six-digit"),
        (lambda raw: raw.__setitem__("pairs", "not-a-list"), "pairs are malformed"),
        (lambda raw: raw.__setitem__("pairs", raw["pairs"][:-1]), "pairs are malformed"),
        (lambda raw: raw["pairs"].__setitem__(0, None), "exactly signal_slot"),
        (lambda raw: raw["pairs"][0].pop("signal_slot"), "exactly signal_slot"),
        (lambda raw: raw["pairs"][0].update({"typo_slot": None}), "exactly signal_slot"),
        (lambda raw: raw["pairs"].__setitem__(1, {"signal_slot": None}), "ordinal-mod-4"),
        (lambda raw: raw["pairs"].__setitem__(1, {"signal_slot": True}), "invalid signal_slot"),
        (lambda raw: raw["pairs"].__setitem__(1, {"signal_slot": -1}), "invalid signal_slot"),
        (lambda raw: raw["pairs"].__setitem__(1, {"signal_slot": 8}), "invalid signal_slot"),
        (lambda raw: raw.__setitem__("pair_count", 63), "exactly 64"),
    ],
)
def test_synthetic_fixture_rejects_malformed_or_non_amendment_a1_layout(
    tmp_path: Path, mutation, message: str,
) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mutation(raw)
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_synthetic_fixture(path)

@pytest.mark.parametrize("raw_value", [None, [], "not-a-mapping"])
def test_synthetic_fixture_rejects_non_mapping_root(tmp_path: Path, raw_value: object) -> None:
    path = tmp_path / "non-mapping-root.json"
    path.write_text(json.dumps(raw_value), encoding="utf-8")
    with pytest.raises(ValueError, match="schema is unsupported"):
        load_synthetic_fixture(path)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda pairs: pairs[0].__setitem__("partition_label", "REUSED_VALIDATION"),
        lambda pairs: pairs[1]["candidate_values"].__setitem__((0, 0), 99.0),
        lambda pairs: pairs[1]["gross_returns"].__setitem__(0, "0.0300"),
    ],
)
def test_synthetic_calibration_rejects_mutated_expanded_fixture_snapshot(mutation) -> None:
    pairs = load_synthetic_fixture(FIXTURE)
    model, _ = create_model(pairs, _small_config())
    mutation(pairs)
    with pytest.raises(ValueError, match="loaded fixture snapshot"):
        _oracle_calibration(model, pairs, epochs=2)


def test_model_uses_frozen_8514_extractor_and_ppo_policy_contract() -> None:
    model, normalizer = create_model(load_synthetic_fixture(FIXTURE), _small_config())
    policy = model.policy
    assert policy.features_extractor.features_dim == EXTRACTOR_WIDTH
    assert policy.features_extractor.__class__.__name__ == "Type1SB3FeaturesExtractor"
    assert [layer.out_features for layer in policy.mlp_extractor.policy_net if isinstance(layer, torch.nn.Linear)] == [256, 128]
    assert [layer.out_features for layer in policy.mlp_extractor.value_net if isinstance(layer, torch.nn.Linear)] == [256, 128]
    config = _small_config()
    assert (
        model.seed == config.seed
        and str(model.device) == "cpu"
        and model.action_space.n == ACTION_COUNT
        and model.gamma == config.gamma
        and model.gae_lambda == config.gae_lambda
        and model.learning_rate == model.lr_schedule(1.0) == config.learning_rate
        and model.n_steps == config.n_steps
        and model.batch_size == config.batch_size
        and model.clip_range(1.0) == config.clip_range
        and model.ent_coef == config.ent_coef
        and model.n_epochs == config.n_epochs
        and model.normalize_advantage is config.normalize_advantage
        and model.vf_coef == config.vf_coef
        and model.max_grad_norm == config.max_grad_norm
    )
    assert isinstance(policy.activation_fn(), torch.nn.Tanh) and policy.ortho_init is True
    assert policy.optimizer_class is torch.optim.Adam and policy.optimizer_kwargs == {"eps": 1e-5}
    assert normalizer.norm_obs is False and normalizer.norm_reward is False


def test_oracle_calibration_uses_full_native_fixture_and_rejects_invalid_epochs() -> None:
    pairs = load_synthetic_fixture(FIXTURE)
    model, _ = create_model(pairs, _small_config())
    before = {
        key: value.detach().cpu().clone()
        for key, value in model.policy.state_dict().items()
    }
    loss = _oracle_calibration(model, pairs, epochs=2)
    trace = model._type1_last_calibration_trace
    assert np.isfinite(loss)
    assert any(not torch.equal(before[key], value) for key, value in model.policy.state_dict().items())
    assert trace["observation_count"] == 128
    assert trace["call_index_counts"] == {"call0": 64, "call1": 64}
    assert trace["label_counts"] == {"slot": 48, "STOP": 80}
    assert trace["native_masks"]["shape"] == [128, ACTION_COUNT]
    assert trace["native_masks"]["all_labels_valid"] is True
    with pytest.raises(ValueError, match="positive integer"):
        _oracle_calibration(model, pairs, epochs=0)
    with pytest.raises(ValueError, match="strict synthetic fixture"):
        _oracle_calibration(model, tuple(pairs), epochs=2)


def test_same_seed_training_has_identical_canonical_parameters_and_native_trace() -> None:
    pairs = load_synthetic_fixture(FIXTURE)
    config = TrainingConfig(seed=11, synthetic_timesteps=10, n_steps=10, batch_size=10, oracle_calibration_epochs=2)
    first_model, _ = train_synthetic_calibrated_model(pairs, config, timesteps=10)
    second_model, _ = train_synthetic_calibrated_model(pairs, config, timesteps=10)
    first_parameters = {
        key: value.detach().cpu().contiguous().numpy().tobytes()
        for key, value in first_model.policy.state_dict().items()
    }
    second_parameters = {
        key: value.detach().cpu().contiguous().numpy().tobytes()
        for key, value in second_model.policy.state_dict().items()
    }
    assert first_parameters == second_parameters
    assert evaluate_model(first_model, pairs, seed=config.seed) == evaluate_model(second_model, pairs, seed=config.seed)
    assert first_model._type1_training_trace["train_only_oracle_calibration"]["pass_order"] == ["pre_ppo", "post_ppo"]


def test_generic_training_cannot_reach_oracle_calibration(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = load_synthetic_fixture(FIXTURE)
    config = _small_config()

    def forbidden(*args, **kwargs):
        raise AssertionError("generic PPO-only training must not calibrate")

    monkeypatch.setattr(daily_type1_train, "_oracle_calibration", forbidden)
    model, _ = train_model(tuple(pairs), config, timesteps=10)
    assert model._type1_training_trace["train_only_oracle_calibration"] is None


@pytest.mark.parametrize("return_value", ["0.0000", "-0.0200"])
def test_evaluation_rejects_non_positive_oracle_denominators(return_value: str) -> None:
    pairs = [
        dict(pair, gross_returns=[None if value is None else return_value for value in pair["gross_returns"]])
        for pair in load_synthetic_fixture(FIXTURE)
    ]
    with pytest.raises(ValueError, match="oracle total reward must be positive"):
        evaluate_model(_OraclePolicy(), pairs)


def test_synthetic_calibration_runs_once_on_each_side_of_ppo(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = load_synthetic_fixture(FIXTURE)
    order: list[object] = []
    original_create = daily_type1_train.create_model
    original_calibration = daily_type1_train._oracle_calibration

    def create_with_record(*args, **kwargs):
        model, normalizer = original_create(*args, **kwargs)
        original_learn = model.learn

        def learn_with_record(*learn_args, **learn_kwargs):
            order.append("ppo")
            return original_learn(*learn_args, **learn_kwargs)

        model.learn = learn_with_record
        return model, normalizer

    def calibration_with_record(*args, **kwargs):
        order.append(("calibration", kwargs["epochs"]))
        return original_calibration(*args, **kwargs)

    monkeypatch.setattr(daily_type1_train, "create_model", create_with_record)
    monkeypatch.setattr(daily_type1_train, "_oracle_calibration", calibration_with_record)
    train_synthetic_calibrated_model(pairs, _small_config(), timesteps=10)
    assert order == [("calibration", 2), "ppo", ("calibration", 2)]


def test_reload_manifest_rejects_each_frozen_ppo_setting(tmp_path: Path) -> None:
    root = tmp_path / "ppo-contract"
    run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    path = root / "model_manifest.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    for field, value in original["ppo"].items():
        mutated = json.loads(json.dumps(original))
        mutated["ppo"][field] = (not value) if isinstance(value, bool) else value + 1
        path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="frozen policy settings"):
            daily_type1_train._load_manifest(root, FIXTURE)
    path.write_text(json.dumps(original), encoding="utf-8")


@pytest.mark.parametrize("schema_version", [1.0, "1"])
def test_manifest_schema_version_requires_exact_int_type(tmp_path: Path, schema_version: object) -> None:
    root = tmp_path / "manifest-schema"
    run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    path = root / "model_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["schema_version"] = schema_version
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="model manifest schema is unsupported"):
        daily_type1_train._load_manifest(root, FIXTURE)


@pytest.mark.parametrize("schema_version", [1.0, "1"])
def test_terminal_receipt_schema_version_requires_exact_int_type(tmp_path: Path, schema_version: object) -> None:
    root = tmp_path / "receipt-schema"
    run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    receipt_path = root / "terminal_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema_version"] = schema_version
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    manifest_path = root / "model_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["terminal_receipt_sha256"] = _sha256_file(receipt_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="terminal receipt schema is unsupported"):
        daily_type1_train._load_terminal_pass_receipt(root, manifest)


def test_short_run_uses_two_internal_reloads_and_is_not_an_accepted_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "short-attempt"
    calls = 0
    original = daily_type1_train._verify_stored_model

    def counted_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(daily_type1_train, "_verify_stored_model", counted_verify)
    manifest = run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    assert calls == 2
    assert manifest["training"]["actual_sb3_timesteps"] == 20
    calibration = manifest["training"]["train_only_oracle_calibration"]
    assert calibration["epochs_per_pass"] == 2
    assert calibration["pass_order"] == ["pre_ppo", "post_ppo"]
    assert calibration["passes"]["pre_ppo"]["label_counts"] == {"slot": 48, "STOP": 80}
    with pytest.raises(ValueError, match="frozen 104000-step"):
        daily_type1_train._training_trace_is_valid(manifest["training"], manifest["config"], accepted=True)
    assert json.loads((root / "terminal_receipt.json").read_text())["terminal_status"] == "ABORTED"
    with pytest.raises(ValueError, match="terminal receipt is not an untampered PASS"):
        verify_model(root, FIXTURE)
    with pytest.raises(FileExistsError, match="unique caller-supplied"):
        run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)


def test_verify_refuses_status_source_and_manifest_tampering_and_failure_is_durable(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    run_synthetic_overfit(root, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    manifest_path = root / "model_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unknown_claim"] = "not part of the frozen schema"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="schema is unsupported"):
        daily_type1_train._load_manifest(root, FIXTURE)
    manifest.pop("unknown_claim")
    manifest["source_inputs"]["runtime_type1_json"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="source/runtime input hash"):
        verify_model(root, FIXTURE)

    failed = tmp_path / "failed-attempt"
    with pytest.raises(ValueError, match="exact seed 0"):
        run_synthetic_overfit(failed, FIXTURE, _small_config(), timesteps=20)
    receipts = list(failed.glob("terminal_receipt.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["terminal_status"] == "FAIL"
    with pytest.raises(ValueError, match="terminal PASS receipt is missing"):
        verify_model(failed, FIXTURE)

    tampered = tmp_path / "tampered-attempt"
    run_synthetic_overfit(tampered, FIXTURE, _small_config(), timesteps=20, require_overfit=False)
    receipt_path = tampered / "terminal_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["terminal_status"] = "PASS"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    tampered_manifest_path = tampered / "model_manifest.json"
    tampered_manifest = json.loads(tampered_manifest_path.read_text(encoding="utf-8"))
    tampered_manifest["terminal_receipt_sha256"] = _sha256_file(receipt_path)
    tampered_manifest_path.write_text(json.dumps(tampered_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="terminal receipt is not an untampered PASS"):
        verify_model(tampered, FIXTURE)

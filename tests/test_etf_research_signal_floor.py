from stom_rl.etf_research.signal_floor import SignalFloorThresholds, SignalSample, evaluate_signal_floor


def _predictive_samples() -> tuple[SignalSample, ...]:
    rows: list[SignalSample] = []
    for day in range(100):
        rows.append(SignalSample(day=20260000 + day, code="069500", score=1.0, gross_return=0.0100))
        rows.append(SignalSample(day=20260000 + day, code="102110", score=-1.0, gross_return=-0.0020))
    return tuple(rows)


def test_signal_floor_passes_predictive_native_score_against_shuffle() -> None:
    # Given: a deterministic cross-sectional score ranks the positive ETF first.
    samples = _predictive_samples()

    # When: five chronological folds and three shuffled controls use the 23bp gate.
    receipt = evaluate_signal_floor(
        samples,
        SignalFloorThresholds.registered(),
        shuffle_seeds=(0, 1, 2),
    )

    # Then: native is positive, stable, and materially above shuffle.
    assert receipt.verdict == "PASS_SIGNAL_FLOOR"
    assert receipt.positive_fold_count == 5
    assert receipt.positive_seed_count >= 2
    assert receipt.native_mean_bps > 0
    assert receipt.native_minus_shuffle_bps >= 10.0


def test_signal_floor_fails_when_cost_exceeds_native_return() -> None:
    # Given: the top-ranked trade earns only 10bp gross before 23bp cost.
    samples = tuple(
        SignalSample(day=20260000 + day, code="069500", score=1.0, gross_return=0.0010)
        for day in range(50)
    )

    # When: the preregistered signal floor is evaluated.
    receipt = evaluate_signal_floor(
        samples,
        SignalFloorThresholds.registered(),
        shuffle_seeds=(0, 1, 2),
    )

    # Then: native net return is negative and Q2-A is NO-GO.
    assert receipt.verdict == "NO_GO_SIGNAL_FLOOR"
    assert receipt.native_mean_bps < 0
    assert receipt.positive_fold_count == 0


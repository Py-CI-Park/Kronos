from stom_rl.rl_discovery.d6r_execution import D6RRunProfile, registered_d6r_schedule


def test_d6r_smoke_schedule_is_the_exact_four_unit_matrix() -> None:
    # Given / When
    profiles, arms, seeds, folds, steps = registered_d6r_schedule(D6RRunProfile.SMOKE)

    # Then
    assert profiles == ("COST_ONLY", "TURNOVER_10BP")
    assert arms == ("NATIVE", "SHUFFLED")
    assert seeds == (0,)
    assert folds == (0,)
    assert steps == 4_096
    assert len(profiles) * len(arms) * len(seeds) * len(folds) == 4


def test_d6r_primary_schedule_is_the_exact_sixty_unit_matrix() -> None:
    # Given / When
    profiles, arms, seeds, folds, steps = registered_d6r_schedule(D6RRunProfile.PRIMARY)

    # Then
    assert profiles == ("COST_ONLY", "TURNOVER_10BP")
    assert arms == ("NATIVE", "SHUFFLED")
    assert seeds == (0, 1, 2)
    assert folds == (0, 1, 2, 3, 4)
    assert steps == 50_000
    assert len(profiles) * len(arms) * len(seeds) * len(folds) == 60

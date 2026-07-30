from stom_rl.rl_discovery.d5s_execution import D5SProfile, registered_d5s_schedule


def test_d5s_schedule_is_frozen_for_smoke_and_primary() -> None:
    assert registered_d5s_schedule(D5SProfile.SMOKE) == (
        ("NATIVE", "SHUFFLED"),
        (0,),
        (4096,),
    )
    assert registered_d5s_schedule(D5SProfile.PRIMARY) == (
        ("NATIVE", "SHUFFLED"),
        (0, 1, 2),
        (50_000, 100_000, 150_000, 200_000, 300_000, 400_000),
    )

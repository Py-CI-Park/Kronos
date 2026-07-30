from stom_rl.rl_discovery.d5r_capacity_runner import (
    D5RCapacityProfile,
    _registered_schedule,
)


def test_d5r_capacity_profiles_freeze_smoke_and_primary_matrix() -> None:
    assert _registered_schedule(D5RCapacityProfile.SMOKE) == (
        ("NATIVE", "SHUFFLED"),
        (0,),
        (2048,),
    )
    assert _registered_schedule(D5RCapacityProfile.PRIMARY) == (
        ("NATIVE", "SHUFFLED"),
        (0, 1, 2),
        (400_000, 800_000),
    )

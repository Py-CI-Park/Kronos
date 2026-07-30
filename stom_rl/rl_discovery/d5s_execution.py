"""D5S registered execution profiles and schedule."""

from enum import StrEnum


class D5SProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


def registered_d5s_schedule(
    profile: D5SProfile,
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    match profile:
        case D5SProfile.SMOKE:
            return ("NATIVE", "SHUFFLED"), (0,), (4096,)
        case D5SProfile.PRIMARY:
            return (
                ("NATIVE", "SHUFFLED"),
                (0, 1, 2),
                (50_000, 100_000, 150_000, 200_000, 300_000, 400_000),
            )

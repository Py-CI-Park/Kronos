from pathlib import Path

from stom_rl.rl_discovery.d6r_source import load_d6r_source


def test_d6r_source_loads_only_the_custody_bound_train_partition() -> None:
    # Given
    repo_root = Path.cwd()

    # When
    source = load_d6r_source(repo_root)

    # Then
    assert len(source.episodes) == 573
    assert source.episode_sha256 == "8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40"
    assert source.prereg.prior_d6.use_in_d6r_training_or_selection is False
    assert source.prereg.execution.d6_validation_read_allowed is False
    assert source.episodes[0].decision_date < source.episodes[-1].decision_date
    assert dict(source.input_hashes)["d6_result_document"] == "d32bf82c333c0794c9c8eb60c3dd0a7826a7200628adcc015372ae789cfb3b6b"

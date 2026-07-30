from pathlib import Path

from stom_rl.rl_discovery.d5_inputs import load_d5_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_d5_inputs_materialize_all_573_train_sessions_only() -> None:
    bundle = load_d5_inputs(ROOT)
    assert len(bundle.episodes) == 573
    assert bundle.episodes[0].decision_date == "2019-05-10"
    assert bundle.episodes[-1].decision_date == "2023-12-26"
    assert all(len(symbol) == 6 for episode in bundle.episodes for symbol, _features, _reward in episode.candidates)

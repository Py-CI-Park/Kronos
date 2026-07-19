import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui.app import app as flask_app  # noqa: E402

METRIC_KEYS = {'point', 'ci_lower', 'ci_upper'}


def test_rl_rliable_stats_returns_real_json_shape():
    client = flask_app.test_client()
    response = client.get('/api/rl/rliable-stats')
    assert response.status_code == 200
    payload = response.get_json()

    # Top-level shape written by scripts/gen_rliable_stats.py.
    assert payload['schema'] == 'kronos_rliable_stats.v1'
    assert payload['research_only'] is True
    assert payload['confidence_interval'] == 0.95
    assert isinstance(payload['algorithms'], list) and payload['algorithms']

    aggregates = payload['aggregates']
    metadata = payload['metadata']
    assert isinstance(aggregates, dict)
    assert isinstance(metadata, dict)

    for algorithm in payload['algorithms']:
        assert algorithm in aggregates
        assert algorithm in metadata
        per_metric = aggregates[algorithm]
        for metric in ('iqm', 'mean', 'median', 'optimality_gap'):
            entry = per_metric[metric]
            assert METRIC_KEYS <= set(entry)
            assert isinstance(entry['point'], (int, float))
        meta = metadata[algorithm]
        assert isinstance(meta['seed_count'], int)
        assert meta['seed_count'] >= 1
        assert 'cost_bps' in meta


def test_rl_rliable_stats_missing_artifact_fails_closed(monkeypatch, tmp_path):
    import webui.app as webui_app

    missing = tmp_path / 'rl_runs_rliable.json'
    assert not missing.exists()
    monkeypatch.setattr(webui_app, 'RLIABLE_STATS_PATH', missing)

    client = flask_app.test_client()
    response = client.get('/api/rl/rliable-stats')
    assert response.status_code == 404
    payload = response.get_json()
    assert payload['available'] is False
    assert payload['error'] == 'rliable stats not generated yet'

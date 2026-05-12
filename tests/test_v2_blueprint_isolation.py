"""Verify v2 blueprint catch-all does not shadow existing routes (REV-2)."""
from webui.app import app


def test_existing_routes_still_match_first():
    client = app.test_client()
    # 기존 3개 라우트가 /v2/<path:subpath>에 잡히지 않음
    for path in ['/', '/training', '/stom']:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} broke"

    # API 라우트도 안전
    resp = client.get('/api/training/status')
    assert resp.status_code == 200


def test_v2_blueprint_only_owns_v2_prefix():
    rules = [str(r) for r in app.url_map.iter_rules()]
    v2_rules = [r for r in rules if '/v2' in r]
    # /v2 prefix 외 catch-all 없음
    for r in v2_rules:
        assert r.startswith('/v2') or r.startswith('/static'), f"v2 leaked: {r}"
    # 글로벌 /<path:p> 없음
    assert '/<path:subpath>' not in rules
    assert not any(r == '/<path:p>' for r in rules)

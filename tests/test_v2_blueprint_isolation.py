"""Verify P6 cutover: `/` serves v2, `/v1/*` serves legacy, `/v2` redirects."""
from webui.app import app


def test_root_serves_v2_after_cutover():
    """P6: 루트 `/` 는 v2 SPA shell 을 서빙해야 한다."""
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200, "/ broke after cutover"
    body = resp.data.decode('utf-8')
    # v2 SSR meta marker 가 노출되어야 한다 (Jinja shell or dist 둘 다 포함)
    assert 'kronos-v2-shell' in body


def test_v1_legacy_routes_still_available():
    """P6: 기존 v1 페이지 3종은 /v1/ prefix 로 보존 (6개월 archive)."""
    client = app.test_client()
    for path in ['/v1/', '/v1/training', '/v1/stom']:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} broke"


def test_v2_legacy_url_redirects_to_root():
    """기존 /v2 북마크는 / 로 301 영구 리다이렉트."""
    client = app.test_client()
    resp = client.get('/v2', follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers.get('Location', '').rstrip('/') in ('', 'http://localhost')


def test_api_routes_unchanged():
    """모든 /api/* 라우트는 cutover 영향 없음."""
    client = app.test_client()
    for path in [
        '/api/training/status',
        '/api/training/history',
        '/api/training/artifacts',
        '/api/training/gpu',
        '/api/training/runs',
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} broke"


def test_no_global_catchall():
    """글로벌 /<path:p> 없이 v1/v2/api/static 만 매칭됨을 확인."""
    rules = [str(r) for r in app.url_map.iter_rules()]
    # 글로벌 catch-all 없음
    assert '/<path:subpath>' not in rules
    assert not any(r == '/<path:p>' for r in rules)

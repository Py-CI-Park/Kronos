"""Verify P6 cutover: `/` serves SSR markers in either P1 (Jinja) or P1.5 (Vite dist) mode."""
from webui.app import app


VALID_VERSIONS = {'p1-ssr', 'p1-5-spa'}


def test_root_returns_200_and_ssr_markers():
    """P6: `/` 는 v2 SPA shell 을 서빙하고 SSR meta marker 가 포함되어야 한다."""
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')

    # B-2: SSR marker meta tags 가 두 모드 모두에서 동일하게 노출되어야 한다.
    assert '<meta name="kronos-v2-shell"' in body
    assert 'kronos-v2-version' in body
    # version 값은 p1-ssr (P1 Jinja) 또는 p1-5-spa (P1.5 dist) 중 하나
    assert any(f'content="{v}"' in body for v in VALID_VERSIONS), \
        f"version meta 가 {VALID_VERSIONS} 중 하나여야 함"


def test_v2_legacy_url_still_routes():
    """기존 /v2 북마크는 / 로 영구 리다이렉트되어 깨지지 않아야 한다."""
    client = app.test_client()
    resp = client.get('/v2', follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert '<meta name="kronos-v2-shell"' in body

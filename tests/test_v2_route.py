"""Verify /v2 returns SSR markers in either P1 (Jinja) or P1.5 (Vite dist) mode."""
from webui.app import app


VALID_VERSIONS = {'p1-ssr', 'p1-5-spa'}


def test_v2_returns_200_and_ssr_markers():
    client = app.test_client()
    resp = client.get('/v2')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')

    # B-2: SSR marker meta tags 가 두 모드 모두에서 동일하게 노출되어야 한다.
    assert '<meta name="kronos-v2-shell"' in body
    assert 'content="hero,live-training' in body
    assert 'kronos-v2-version' in body
    # version 값은 p1-ssr (P1 Jinja) 또는 p1-5-spa (P1.5 dist) 중 하나
    assert any(f'content="{v}"' in body for v in VALID_VERSIONS), \
        f"version meta 가 {VALID_VERSIONS} 중 하나여야 함"

    # 첫 페인트 marker — dist mode 에서도 SPA 마운트 전 fallback div 가 노출됨
    assert 'data-tab="live-training"' in body
    assert 'id="hero-strip"' in body


def test_v2_subpath_falls_back_to_index():
    client = app.test_client()
    resp = client.get('/v2/anything/deep')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert '<meta name="kronos-v2-shell"' in body

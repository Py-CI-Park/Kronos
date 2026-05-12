"""Verify /v2 SSR shell returns SSR markers (B-2)."""
import re
from webui.app import app


def test_v2_returns_200_and_ssr_markers():
    client = app.test_client()
    resp = client.get('/v2')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert '<meta name="kronos-v2-shell"' in body
    assert 'content="hero,live-training' in body
    assert '<meta name="kronos-v2-version" content="p1-ssr">' in body
    assert 'data-tab="live-training"' in body
    assert 'id="hero-strip"' in body


def test_v2_subpath_falls_back_to_index():
    client = app.test_client()
    resp = client.get('/v2/anything/deep')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert '<meta name="kronos-v2-shell"' in body

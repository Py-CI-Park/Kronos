"""[B-2] SSR marker 가 Vite 빌드 후에도 보존됨을 검증."""
import os
import pytest


DIST_INDEX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'webui', 'static', 'v2', 'dist', 'index.html'
)


@pytest.mark.skipif(not os.path.exists(DIST_INDEX), reason="P1.5 dist 아직 빌드 안 됨")
def test_dist_marker_preserved_after_build():
    with open(DIST_INDEX, 'r', encoding='utf-8') as f:
        body = f.read()
    assert 'kronos-v2-shell' in body, "SSR marker 'kronos-v2-shell' 가 dist/index.html 에 없음"
    assert 'kronos-v2-version' in body, "SSR marker 'kronos-v2-version' 가 dist/index.html 에 없음"
    assert 'p1-5-spa' in body, "version 'p1-5-spa' 가 dist/index.html 에 없음"


@pytest.mark.skipif(not os.path.exists(DIST_INDEX), reason="P1.5 dist 아직 빌드 안 됨")
def test_dist_base_url_matches_flask_static():
    """Vite base 가 /static/v2/dist/ 로 빌드돼야 Flask 기본 정적 서빙과 매핑된다."""
    with open(DIST_INDEX, 'r', encoding='utf-8') as f:
        body = f.read()
    # asset 참조가 /static/v2/dist/ prefix 로 시작해야 함
    assert '/static/v2/dist/assets/' in body, \
        "asset URL 이 /static/v2/dist/assets/ 로 시작하지 않음 — vite base 설정 확인 필요"


@pytest.mark.skipif(not os.path.exists(DIST_INDEX), reason="P1.5 dist 아직 빌드 안 됨")
def test_dist_fallback_first_paint_present():
    """SPA hydration 전 첫 페인트 marker (#hero-strip + data-tab) 가 dist 에 박혀 있어야 한다."""
    with open(DIST_INDEX, 'r', encoding='utf-8') as f:
        body = f.read()
    assert 'id="hero-strip"' in body
    assert 'data-tab="live-training"' in body

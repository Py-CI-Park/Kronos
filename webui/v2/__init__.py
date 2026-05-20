from flask import Blueprint, render_template, send_from_directory, current_app, redirect
import os

v2_bp = Blueprint('v2', __name__)


def _serve_v2_shell():
    """디자인 시스템 v2 SPA 진입점.

    `KRONOS_V2_DIST=1` 이고 빌드 산출물(`webui/static/v2/dist/index.html`)이 존재하면 dist 모드,
    아니면 P1 SSR Jinja shell(`templates/v2_shell.html`) 폴백.
    """
    dist_dir = os.path.join(current_app.static_folder, 'v2', 'dist')
    dist_index = os.path.join(dist_dir, 'index.html')
    if os.path.exists(dist_index) and os.environ.get('KRONOS_V2_DIST', '0') == '1':
        return send_from_directory(dist_dir, 'index.html')
    return render_template('v2_shell.html')


# ── P6 cutover: 루트 `/` 가 v2 SPA 를 서빙 ─────────────────────
@v2_bp.route('/')
def v2_root():
    """루트 진입점 — 새 통합 대시보드."""
    return _serve_v2_shell()


# ── 하위 호환: `/v2` 는 `/` 로 영구 리다이렉트 ────────────────

# Direct dashboard bookmarks used during long-running training.
#
# The v2 UI is a single-page shell and selects the live-training view by
# default. Serving the same shell for these explicit paths keeps operator
# bookmarks such as http://127.0.0.1:5070/training working without adding a
# broad Flask catch-all that could mask API/static mistakes.
@v2_bp.route('/training')
@v2_bp.route('/dashboard')
def v2_training_alias():
    """Serve the v2 live-training shell for direct dashboard bookmarks."""
    return _serve_v2_shell()


@v2_bp.route('/v2')
def v2_legacy_redirect():
    """기존 북마크/링크 호환용 영구 리다이렉트."""
    return redirect('/', code=301)


@v2_bp.route('/v2/<path:subpath>')
def v2_legacy_subpath(subpath):
    """기존 /v2/anything 도 루트로 리다이렉트 (해시 라우팅이라 subpath 무의미)."""
    return redirect('/', code=301)

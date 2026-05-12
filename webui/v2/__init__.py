from flask import Blueprint, render_template, send_from_directory, current_app
import os

v2_bp = Blueprint('v2', __name__)

@v2_bp.route('/v2')
def v2_index():
    """P1 SSR Jinja shell. P1.5에서 KRONOS_V2_DIST=1로 dist/index.html 토글."""
    dist_index = os.path.join(current_app.static_folder, 'v2', 'dist', 'index.html')
    if os.path.exists(dist_index) and os.environ.get('KRONOS_V2_DIST', '0') == '1':
        return send_from_directory(
            os.path.join(current_app.static_folder, 'v2', 'dist'),
            'index.html',
        )
    return render_template('v2_shell.html')

@v2_bp.route('/v2/<path:subpath>')
def v2_spa_fallback(subpath):
    """v2 prefix 내부 catch-all만. 글로벌 /<path:p>는 절대 금지."""
    return v2_index()

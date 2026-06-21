#!/usr/bin/env python3
"""
Kronos Web UI startup script
"""

import os
import glob
import sys
import subprocess
import webbrowser
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def clear_stale_app_bytecode():
    """Force app.py to be imported from source after dashboard edits."""
    cache_pattern = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__", "app.cpython-*.pyc")
    for path in glob.glob(cache_pattern):
        try:
            os.remove(path)
        except OSError:
            pass


def enforce_runtime_research_locks(app):
    """Defense-in-depth: never let launcher-served readiness imply model/live/profit readiness."""
    endpoint = 'rl_factory_model_build_readiness'
    original = app.view_functions.get(endpoint)
    if original is None:
        return False

    def locked_model_build_readiness(*args, **kwargs):
        from flask import jsonify

        response = original(*args, **kwargs)
        status_code = getattr(response, "status_code", 200)
        if status_code != 200 or not hasattr(response, "get_json"):
            return response
        source = response.get_json(silent=True) or {}
        guardrail = {
            'status': 'NO-GO',
            'mode': 'RESEARCH_ONLY',
            'labels': ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
            'cost_bps': 23,
            'ts_imb': 'RULE baseline',
            'live': False,
            'broker': False,
            'order': False,
            'account': False,
            'paper': False,
            'model_build': False,
            'profit': False,
        }
        steps = []
        for step in source.get('readiness_steps', []):
            safe_step = {
                'id': step.get('id'),
                'label': step.get('label'),
                'status': step.get('status'),
                'evidence': step.get('evidence'),
            }
            if safe_step['id'] == 'RL-implementation':
                safe_step['status'] = 'LOCKED_DASHBOARD_RESEARCH_ONLY'
                safe_step['evidence'] = 'Dashboard API never unlocks model-build, RL implementation, broker, order, account, paper, or profit readiness.'
            steps.append(safe_step)
        return jsonify({
            'available': bool(source.get('available', True)),
            'artifact_type': 'model_build_research_only_lock',
            'strategy_label': 'model-build evidence lock - NOT an RL model and NOT readiness',
            'baseline_label': 'ts_imb RULE baseline',
            'guardrail': 'Read-only research evidence viewer; model-build/live/profit readiness remains locked false.',
            'cost_bps': 23,
            'status': 'MODEL_BUILD_RESEARCH_ONLY_NO_GO',
            'restricted_rl_status': 'LOCKED_DASHBOARD_RESEARCH_ONLY',
            'fresh_validation_status': 'RESEARCH_ONLY_EVIDENCE_REVIEW',
            'p1_status': source.get('p1_status', 'UNKNOWN'),
            'original_p2_status': source.get('original_p2_status', 'UNKNOWN'),
            'risk_policy_status': source.get('risk_policy_status', 'UNKNOWN'),
            'p3_status': source.get('p3_status', 'UNKNOWN'),
            'p4_status': source.get('p4_status', 'UNKNOWN'),
            'implementation_unlocked': False,
            'model_build_allowed': False,
            'live_trading_allowed': False,
            'broker_order_account_allowed': False,
            'paper_forward_allowed': False,
            'profit_readiness': False,
            'selected_policy_ids': source.get('selected_policy_ids', []),
            'required_fill_modes': source.get('required_fill_modes', []),
            'read_only_counts': {
                'risk_policy_runs': len(source.get('risk_policy_runs', [])),
                'fresh_validation_runs': len(source.get('fresh_validation_runs', [])),
                'original_sizing_runs': len(source.get('original_sizing_runs', [])),
                'forward_ledger_runs': len(source.get('forward_ledger_runs', [])),
            },
            'readiness_steps': steps,
            'unlock_requirements': [
                'Dashboard route remains NO-GO/research-only even when offline evidence improves.',
                'Do not infer model-build, live, broker, order, account, paper, or profit readiness from this API.',
                'Use offline preregistered validation artifacts as research evidence only.',
            ],
            'research_only_guardrail': guardrail,
        })

    app.view_functions[endpoint] = locked_model_build_readiness
    return True


def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import flask
        import flask_cors
        import pandas
        import numpy
        import plotly
        print("✅ All dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def install_dependencies():
    """Install dependencies"""
    print("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installation completed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Dependencies installation failed")
        return False

def main():
    """Main function"""
    print("🚀 Starting Kronos Web UI...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\nAuto-install dependencies? (y/n): ", end="")
        if input().lower() == 'y':
            if not install_dependencies():
                return
        else:
            print("Please manually install dependencies and retry")
            return
    
    # Check model availability
    try:
        sys.path.append(PROJECT_ROOT)
        from model import Kronos, KronosTokenizer, KronosPredictor
        print("✅ Kronos model library available")
        model_available = True
    except ImportError:
        print("⚠️  Kronos model library not available, will use simulated prediction")
        model_available = False
    
    # Start Flask application
    print("\n🌐 Starting Web server...")
    
    # Set environment variables
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # Start server
    try:
        clear_stale_app_bytecode()
        import webui.app as app_module
        app = app_module.app
        readiness_guarded = enforce_runtime_research_locks(app)
        print(f"✅ Flask app module: {app_module.__file__}")
        print(f"✅ Model-build readiness route guard: {'on' if readiness_guarded else 'off'}")
        host = os.environ.get("KRONOS_WEBUI_HOST", "127.0.0.1")
        port = int(os.environ.get("KRONOS_WEBUI_PORT", os.environ.get("PORT", "7070")))
        open_browser = os.environ.get("KRONOS_WEBUI_OPEN_BROWSER", "1").lower() not in {"0", "false", "no", "off"}
        # Debug stays available, but the file-watch reloader is OFF by default:
        # webui/ holds runtime artifacts (rl_runs, stom_predictions, logs) that
        # change constantly, which would otherwise restart the server in a loop
        # and re-open the browser tab on every restart. Opt back in with
        # KRONOS_WEBUI_RELOAD=1 when editing server code.
        debug_mode = os.environ.get("KRONOS_WEBUI_DEBUG", "1").lower() not in {"0", "false", "no", "off"}
        use_reloader = os.environ.get("KRONOS_WEBUI_RELOAD", "0").lower() in {"1", "true", "yes", "on"}
        # In the reloader child process Werkzeug sets WERKZEUG_RUN_MAIN; never
        # re-open the browser there, otherwise each restart spawns a new tab.
        is_reloader_child = bool(os.environ.get("WERKZEUG_RUN_MAIN"))
        access_host = "localhost" if host in {"0.0.0.0", "::"} else host
        access_url = f"http://{access_host}:{port}"

        print("✅ Web server started successfully!")
        print(f"🌐 Access URL: {access_url}")
        print("💡 Tip: Press Ctrl+C to stop server")

        # Auto-open browser once, only in the main process and only if enabled.
        if open_browser and not is_reloader_child:
            time.sleep(2)
            webbrowser.open(access_url)

        # Start Flask application
        app.run(debug=debug_mode, host=host, port=port, use_reloader=use_reloader)
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        print("Please check if port 7070 is occupied")

if __name__ == "__main__":
    main()

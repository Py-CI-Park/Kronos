import os
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, Response, render_template, request, jsonify
from flask_cors import CORS
import sys
import warnings
import datetime
warnings.filterwarnings('ignore')

# Add project root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

Kronos = None
KronosTokenizer = None
KronosPredictor = None
MODEL_AVAILABLE = True
MODEL_IMPORT_ERROR = None

def ensure_kronos_imported():
    """Import Kronos lazily so dashboard routes work even when torch/model deps are broken."""
    global Kronos, KronosTokenizer, KronosPredictor, MODEL_AVAILABLE, MODEL_IMPORT_ERROR
    if Kronos is not None and KronosTokenizer is not None and KronosPredictor is not None:
        return True
    try:
        from model import Kronos as _Kronos
        from model import KronosPredictor as _KronosPredictor
        from model import KronosTokenizer as _KronosTokenizer

        Kronos = _Kronos
        KronosTokenizer = _KronosTokenizer
        KronosPredictor = _KronosPredictor
        MODEL_AVAILABLE = True
        MODEL_IMPORT_ERROR = None
        return True
    except Exception as exc:
        MODEL_AVAILABLE = False
        MODEL_IMPORT_ERROR = str(exc)
        print(f"Warning: Kronos model cannot be imported ({exc}), prediction model loading is disabled")
        return False

try:
    try:
        from .stom_dashboard import (
            list_filter_report_files,
            list_qlib_backtest_files,
            list_prediction_files,
            load_filter_report_artifact,
            load_qlib_backtest_artifact,
            load_prediction_frame,
            load_training_summary,
            prediction_chart_json,
            prediction_diagnostics,
            prediction_metrics,
            qlib_backtest_chart_json,
            recommendation_export_csv,
            recommendation_export_payload,
            ranked_recommendations,
            recommendation_summary,
            score_backtest_report,
            topk_rows,
        )
    except ImportError:
        from stom_dashboard import (
            list_filter_report_files,
            list_qlib_backtest_files,
            list_prediction_files,
            load_filter_report_artifact,
            load_qlib_backtest_artifact,
            load_prediction_frame,
            load_training_summary,
            prediction_chart_json,
            prediction_diagnostics,
            prediction_metrics,
            qlib_backtest_chart_json,
            recommendation_export_csv,
            recommendation_export_payload,
            ranked_recommendations,
            recommendation_summary,
            score_backtest_report,
            topk_rows,
        )
except Exception as exc:
    print(f"Warning: STOM dashboard helpers cannot be imported ({exc})")
    list_filter_report_files = None
    list_qlib_backtest_files = None
    list_prediction_files = None
    load_filter_report_artifact = None
    load_qlib_backtest_artifact = None
    load_prediction_frame = None
    load_training_summary = None
    prediction_chart_json = None
    prediction_diagnostics = None
    prediction_metrics = None
    qlib_backtest_chart_json = None
    recommendation_export_csv = None
    recommendation_export_payload = None
    ranked_recommendations = None
    recommendation_summary = None
    score_backtest_report = None
    topk_rows = None

try:
    try:
        from .training_monitor import (
            inspect_training_artifacts,
            list_training_runs,
            load_training_history,
            load_training_status,
            query_gpu_status,
            tail_training_log,
        )
    except ImportError:
        from training_monitor import (
            inspect_training_artifacts,
            list_training_runs,
            load_training_history,
            load_training_status,
            query_gpu_status,
            tail_training_log,
        )
except Exception as exc:
    print(f"Warning: STOM training monitor helpers cannot be imported ({exc})")
    inspect_training_artifacts = None
    list_training_runs = None
    load_training_history = None
    load_training_status = None
    query_gpu_status = None
    tail_training_log = None

app = Flask(__name__)
CORS(app)

# Global variables to store models
tokenizer = None
model = None
predictor = None

# Available model configurations
AVAILABLE_MODELS = {
    'kronos-mini': {
        'name': 'Kronos-mini',
        'model_id': 'NeoQuasar/Kronos-mini',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-2k',
        'context_length': 2048,
        'params': '4.1M',
        'description': 'Lightweight model, suitable for fast prediction'
    },
    'kronos-small': {
        'name': 'Kronos-small',
        'model_id': 'NeoQuasar/Kronos-small',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'context_length': 512,
        'params': '24.7M',
        'description': 'Small model, balanced performance and speed'
    },
    'kronos-base': {
        'name': 'Kronos-base',
        'model_id': 'NeoQuasar/Kronos-base',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'context_length': 512,
        'params': '102.3M',
        'description': 'Base model, provides better prediction quality'
    }
}

MIN_TRAINING_REFRESH_SECONDS = 2
MAX_TRAINING_REFRESH_SECONDS = 3600


def _default_training_refresh_seconds():
    try:
        return int(float(os.environ.get("STOM_TRAINING_REFRESH_SECONDS", "5") or 5))
    except (TypeError, ValueError):
        return 5


DEFAULT_TRAINING_REFRESH_SECONDS = _default_training_refresh_seconds()


def resolve_training_refresh_seconds(raw_value=None):
    """Return a safe UI auto-refresh interval in seconds."""
    if raw_value in (None, ""):
        raw_value = DEFAULT_TRAINING_REFRESH_SECONDS
    try:
        seconds = int(float(raw_value))
    except (TypeError, ValueError):
        seconds = DEFAULT_TRAINING_REFRESH_SECONDS
    return max(MIN_TRAINING_REFRESH_SECONDS, min(seconds, MAX_TRAINING_REFRESH_SECONDS))


def build_training_readiness(status_payload):
    """Return a shared read-only readiness policy for all training widgets.

    The web UI intentionally distinguishes "training is progressing" from
    "a usable predictor/checkpoint exists" so an in-progress tokenizer run is
    not interpreted as a completed forecasting model.
    """
    payload = status_payload or {}
    stages = payload.get("stages") or []
    latest = payload.get("latest_stage") or {}
    run_status = str(payload.get("status") or latest.get("status") or "unknown").lower()

    def stage_name(stage):
        return str((stage or {}).get("train_stage") or (stage or {}).get("stage") or "").lower()

    def stage_status(stage):
        return str((stage or {}).get("status") or "").lower()

    def safe_percent(stage):
        try:
            return float((stage or {}).get("stage_percent") or 0)
        except (TypeError, ValueError):
            return 0.0

    predictor_stage = next((stage for stage in stages if stage_name(stage) == "predictor"), None)
    latest_stage_name = stage_name(latest)
    predictor_status = stage_status(predictor_stage)
    complete_statuses = {"complete", "completed", "done", "finished", "success", "succeeded"}
    pending_statuses = {"", "dry_run", "pending", "queued", "not_started", "waiting"}

    predictor_started = bool(predictor_stage) and predictor_status not in pending_statuses
    predictor_complete = (
        bool(predictor_stage)
        and (
            predictor_status in complete_statuses
            or (
                stage_name(predictor_stage) == "predictor"
                and safe_percent(predictor_stage) >= 100
                and run_status in complete_statuses
            )
        )
    )

    if predictor_complete:
        level = "ready"
        label = "예측 성과 확인 가능"
        message = "predictor 학습이 완료된 상태입니다. 이제 실제값/예측값 검증과 성과 지표 확인이 가능합니다."
        performance_ready = True
    elif predictor_started:
        level = "training"
        label = "predictor 학습 중"
        message = "predictor 단계가 진행 중입니다. checkpoint가 저장되기 전까지 성과 수치를 확정하지 않습니다."
        performance_ready = False
    elif latest_stage_name == "tokenizer" or run_status == "running":
        level = "waiting"
        label = "성과 대기: tokenizer 학습 중"
        message = "현재 tokenizer 단계입니다. checkpoint와 predictor가 아직 준비되지 않아 예측 정확도/수익률을 판단하지 않습니다."
        performance_ready = False
    else:
        level = "waiting"
        label = "성과 대기"
        message = "학습 산출물 또는 predictor 완료 상태가 확인되기 전까지 예측 성과는 대기 상태로 표시합니다."
        performance_ready = False

    return {
        "level": level,
        "label": label,
        "message": message,
        "performance_ready": performance_ready,
        "checkpoint_expected": not performance_ready,
        "predictor_started": predictor_started,
        "predictor_complete": predictor_complete,
        "latest_stage": latest_stage_name or "-",
    }

def load_data_files():
    """Scan data directory and return available data files"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    data_files = []
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith(('.csv', '.feather')):
                file_path = os.path.join(data_dir, file)
                file_size = os.path.getsize(file_path)
                data_files.append({
                    'name': file,
                    'path': file_path,
                    'size': f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
                })
    
    return data_files

def load_data_file(file_path):
    """Load data file"""
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.feather'):
            df = pd.read_feather(file_path)
        else:
            return None, "Unsupported file format"
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            return None, f"Missing required columns: {required_cols}"
        
        # Process timestamp column
        if 'timestamps' in df.columns:
            df['timestamps'] = pd.to_datetime(df['timestamps'])
        elif 'timestamp' in df.columns:
            df['timestamps'] = pd.to_datetime(df['timestamp'])
        elif 'date' in df.columns:
            # If column name is 'date', rename it to 'timestamps'
            df['timestamps'] = pd.to_datetime(df['date'])
        else:
            # If no timestamp column exists, create one
            df['timestamps'] = pd.date_range(start='2024-01-01', periods=len(df), freq='1H')
        
        # Ensure numeric columns are numeric type
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Process volume column (optional)
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # Process amount column (optional, but not used for prediction)
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Remove rows containing NaN values
        df = df.dropna()
        
        return df, None
        
    except Exception as e:
        return None, f"Failed to load file: {str(e)}"

def save_prediction_results(file_path, prediction_type, prediction_results, actual_data, input_data, prediction_params):
    """Save prediction results to file"""
    try:
        # Create prediction results directory
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prediction_results')
        os.makedirs(results_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'prediction_{timestamp}.json'
        filepath = os.path.join(results_dir, filename)
        
        # Prepare data for saving
        save_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'file_path': file_path,
            'prediction_type': prediction_type,
            'prediction_params': prediction_params,
            'input_data_summary': {
                'rows': len(input_data),
                'columns': list(input_data.columns),
                'price_range': {
                    'open': {'min': float(input_data['open'].min()), 'max': float(input_data['open'].max())},
                    'high': {'min': float(input_data['high'].min()), 'max': float(input_data['high'].max())},
                    'low': {'min': float(input_data['low'].min()), 'max': float(input_data['low'].max())},
                    'close': {'min': float(input_data['close'].min()), 'max': float(input_data['close'].max())}
                },
                'last_values': {
                    'open': float(input_data['open'].iloc[-1]),
                    'high': float(input_data['high'].iloc[-1]),
                    'low': float(input_data['low'].iloc[-1]),
                    'close': float(input_data['close'].iloc[-1])
                }
            },
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'analysis': {}
        }
        
        # If actual data exists, perform comparison analysis
        if actual_data and len(actual_data) > 0:
            # Calculate continuity analysis
            if len(prediction_results) > 0 and len(actual_data) > 0:
                last_pred = prediction_results[0]  # First prediction point
            first_actual = actual_data[0]      # First actual point
                
            save_data['analysis']['continuity'] = {
                    'last_prediction': {
                        'open': last_pred['open'],
                        'high': last_pred['high'],
                        'low': last_pred['low'],
                        'close': last_pred['close']
                    },
                    'first_actual': {
                        'open': first_actual['open'],
                        'high': first_actual['high'],
                        'low': first_actual['low'],
                        'close': first_actual['close']
                    },
                    'gaps': {
                        'open_gap': abs(last_pred['open'] - first_actual['open']),
                        'high_gap': abs(last_pred['high'] - first_actual['high']),
                        'low_gap': abs(last_pred['low'] - first_actual['low']),
                        'close_gap': abs(last_pred['close'] - first_actual['close'])
                    },
                    'gap_percentages': {
                        'open_gap_pct': (abs(last_pred['open'] - first_actual['open']) / first_actual['open']) * 100,
                        'high_gap_pct': (abs(last_pred['high'] - first_actual['high']) / first_actual['high']) * 100,
                        'low_gap_pct': (abs(last_pred['low'] - first_actual['low']) / first_actual['low']) * 100,
                        'close_gap_pct': (abs(last_pred['close'] - first_actual['close']) / first_actual['close']) * 100
                    }
                }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        print(f"Prediction results saved to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"Failed to save prediction results: {e}")
        return None

def create_prediction_chart(df, pred_df, lookback, pred_len, actual_df=None, historical_start_idx=0):
    """Create prediction chart"""
    # Use specified historical data start position, not always from the beginning of df
    if historical_start_idx + lookback + pred_len <= len(df):
        # Display lookback historical points + pred_len prediction points starting from specified position
        historical_df = df.iloc[historical_start_idx:historical_start_idx+lookback]
        prediction_range = range(historical_start_idx+lookback, historical_start_idx+lookback+pred_len)
    else:
        # If data is insufficient, adjust to maximum available range
        available_lookback = min(lookback, len(df) - historical_start_idx)
        available_pred_len = min(pred_len, max(0, len(df) - historical_start_idx - available_lookback))
        historical_df = df.iloc[historical_start_idx:historical_start_idx+available_lookback]
        prediction_range = range(historical_start_idx+available_lookback, historical_start_idx+available_lookback+available_pred_len)
    
    # Create chart
    fig = go.Figure()
    
    # Add historical data (candlestick chart)
    fig.add_trace(go.Candlestick(
        x=historical_df['timestamps'] if 'timestamps' in historical_df.columns else historical_df.index,
        open=historical_df['open'],
        high=historical_df['high'],
        low=historical_df['low'],
        close=historical_df['close'],
        name='Historical Data (400 data points)',
        increasing_line_color='#26A69A',
        decreasing_line_color='#EF5350'
    ))
    
    # Add prediction data (candlestick chart)
    if pred_df is not None and len(pred_df) > 0:
        # Calculate prediction data timestamps - ensure continuity with historical data
        if 'timestamps' in df.columns and len(historical_df) > 0:
            # Start from the last timestamp of historical data, create prediction timestamps with the same time interval
            last_timestamp = historical_df['timestamps'].iloc[-1]
            time_diff = df['timestamps'].iloc[1] - df['timestamps'].iloc[0] if len(df) > 1 else pd.Timedelta(hours=1)
            
            pred_timestamps = pd.date_range(
                start=last_timestamp + time_diff,
                periods=len(pred_df),
                freq=time_diff
            )
        else:
            # If no timestamps, use index
            pred_timestamps = range(len(historical_df), len(historical_df) + len(pred_df))
        
        fig.add_trace(go.Candlestick(
            x=pred_timestamps,
            open=pred_df['open'],
            high=pred_df['high'],
            low=pred_df['low'],
            close=pred_df['close'],
            name='Prediction Data (120 data points)',
            increasing_line_color='#66BB6A',
            decreasing_line_color='#FF7043'
        ))
    
    # Add actual data for comparison (if exists)
    if actual_df is not None and len(actual_df) > 0:
        # Actual data should be in the same time period as prediction data
        if 'timestamps' in df.columns:
            # Actual data should use the same timestamps as prediction data to ensure time alignment
            if 'pred_timestamps' in locals():
                actual_timestamps = pred_timestamps
            else:
                # If no prediction timestamps, calculate from the last timestamp of historical data
                if len(historical_df) > 0:
                    last_timestamp = historical_df['timestamps'].iloc[-1]
                    time_diff = df['timestamps'].iloc[1] - df['timestamps'].iloc[0] if len(df) > 1 else pd.Timedelta(hours=1)
                    actual_timestamps = pd.date_range(
                        start=last_timestamp + time_diff,
                        periods=len(actual_df),
                        freq=time_diff
                    )
                else:
                    actual_timestamps = range(len(historical_df), len(historical_df) + len(actual_df))
        else:
            actual_timestamps = range(len(historical_df), len(historical_df) + len(actual_df))
        
        fig.add_trace(go.Candlestick(
            x=actual_timestamps,
            open=actual_df['open'],
            high=actual_df['high'],
            low=actual_df['low'],
            close=actual_df['close'],
            name='Actual Data (120 data points)',
            increasing_line_color='#FF9800',
            decreasing_line_color='#F44336'
        ))
    
    # Update layout
    fig.update_layout(
        title='Kronos Financial Prediction Results - 400 Historical Points + 120 Prediction Points vs 120 Actual Points',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_white',
        height=600,
        showlegend=True
    )
    
    # Ensure x-axis time continuity
    if 'timestamps' in historical_df.columns:
        # Get all timestamps and sort them
        all_timestamps = []
        if len(historical_df) > 0:
            all_timestamps.extend(historical_df['timestamps'])
        if 'pred_timestamps' in locals():
            all_timestamps.extend(pred_timestamps)
        if 'actual_timestamps' in locals():
            all_timestamps.extend(actual_timestamps)
        
        if all_timestamps:
            all_timestamps = sorted(all_timestamps)
            fig.update_xaxes(
                range=[all_timestamps[0], all_timestamps[-1]],
                rangeslider_visible=False,
                type='date'
            )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def index():
    """Home page"""
    return render_template(
        'index.html',
        default_training_refresh_seconds=resolve_training_refresh_seconds(request.args.get('refresh_interval')),
    )

@app.route('/stom')
def stom_dashboard_page():
    """STOM OHLCV actual-vs-predicted dashboard."""
    return render_template(
        'stom_dashboard.html',
        default_training_refresh_seconds=resolve_training_refresh_seconds(request.args.get('refresh_interval')),
    )

@app.route('/training')
def training_dashboard_page():
    """Live STOM Kronos fine-tuning monitor."""
    return render_template(
        'training_dashboard.html',
        default_training_refresh_seconds=resolve_training_refresh_seconds(request.args.get('refresh_interval')),
        min_training_refresh_seconds=MIN_TRAINING_REFRESH_SECONDS,
        max_training_refresh_seconds=MAX_TRAINING_REFRESH_SECONDS,
    )

@app.route('/api/training/runs')
def training_runs():
    if list_training_runs is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    try:
        limit = int(request.args.get('limit', 50))
        return jsonify({'runs': list_training_runs(limit=limit)})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/training/status')
def training_status():
    if load_training_status is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    run_name = request.args.get('run') or None
    try:
        status_payload = load_training_status(run_name)
        status_payload['readiness'] = build_training_readiness(status_payload)
        return jsonify(status_payload)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/training/logs')
def training_logs():
    if tail_training_log is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    run_name = request.args.get('run') or None
    stage = request.args.get('stage') or None
    try:
        lines = int(request.args.get('lines', 200))
        return jsonify(tail_training_log(run_name=run_name, stage=stage, lines=lines))
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/training/artifacts')
def training_artifacts():
    if inspect_training_artifacts is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    run_name = request.args.get('run') or None
    try:
        limit = int(request.args.get('limit', 50))
        return jsonify(inspect_training_artifacts(run_name=run_name, limit=limit))
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/training/history')
def training_history():
    if load_training_history is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    run_name = request.args.get('run') or None
    stage = request.args.get('stage') or None
    try:
        limit = int(request.args.get('limit', 40))
        return jsonify(load_training_history(run_name=run_name, stage=stage, limit=limit))
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/training/gpu')
def training_gpu():
    if query_gpu_status is None:
        return jsonify({'error': 'STOM training monitor helper is not available'}), 500
    return jsonify(query_gpu_status())

@app.route('/api/stom/summary')
def stom_summary():
    if load_training_summary is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    return jsonify(load_training_summary())

@app.route('/api/stom/prediction-files')
def stom_prediction_files():
    if list_prediction_files is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    return jsonify({'files': list_prediction_files()})

@app.route('/api/stom/qlib-backtests')
def stom_qlib_backtests():
    if list_qlib_backtest_files is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    file_name = request.args.get('file')
    try:
        if not file_name:
            return jsonify({'files': list_qlib_backtest_files()})
        if load_qlib_backtest_artifact is None or qlib_backtest_chart_json is None:
            return jsonify({'error': 'Qlib backtest helper is not available'}), 500
        payload = load_qlib_backtest_artifact(file_name)
        return jsonify({
            'artifact': payload,
            'chart': qlib_backtest_chart_json(payload),
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/stom/filter-reports')
def stom_filter_reports():
    if list_filter_report_files is None:
        return jsonify({'error': 'STOM filter report helper is not available'}), 500
    file_name = request.args.get('file')
    try:
        if not file_name:
            return jsonify({'files': list_filter_report_files()})
        if load_filter_report_artifact is None:
            return jsonify({'error': 'STOM filter report loader is not available'}), 500
        return jsonify({'artifact': load_filter_report_artifact(file_name)})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/stom/prediction')
def stom_prediction_file():
    if load_prediction_frame is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'error': 'file query parameter is required'}), 400
    try:
        df = load_prediction_frame(file_name)
        window_id_arg = request.args.get('window_id')
        window_id = int(window_id_arg) if window_id_arg not in (None, '') else None
        recommendations = ranked_recommendations(df) if ranked_recommendations else []
        return jsonify({
            'metrics': prediction_metrics(df),
            'chart': prediction_chart_json(df, window_id=window_id),
            'topk': topk_rows(df),
            'recommendations': recommendations,
            'recommendation_summary': recommendation_summary(recommendations) if recommendation_summary else {},
            'windows': sorted(int(v) for v in df['window_id'].dropna().unique().tolist())[:500],
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/api/stom/diagnostics')
def stom_prediction_diagnostics():
    if load_prediction_frame is None or prediction_diagnostics is None:
        return jsonify({'error': 'STOM diagnostics helper is not available'}), 500
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'error': 'file query parameter is required'}), 400
    try:
        max_symbols = int(request.args.get('max_symbols', 50))
        min_windows = int(request.args.get('min_windows', 1))
        df = load_prediction_frame(file_name)
        return jsonify(prediction_diagnostics(df, max_symbols=max_symbols, min_windows=min_windows))
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/stom/recommendations')
def stom_recommendations():
    if load_prediction_frame is None or ranked_recommendations is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'error': 'file query parameter is required'}), 400
    try:
        k = int(request.args.get('k', 20))
        min_score_arg = request.args.get('min_score')
        min_score = float(min_score_arg) if min_score_arg not in (None, '') else None
        long_only = request.args.get('long_only', '1').lower() not in {'0', 'false', 'no', 'off'}
        df = load_prediction_frame(file_name)
        recommendations = ranked_recommendations(df, k=k, long_only=long_only, min_score=min_score)
        return jsonify({
            'recommendations': recommendations,
            'summary': recommendation_summary(recommendations) if recommendation_summary else {},
            'metrics': prediction_metrics(df),
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/stom/backtest-report')
def stom_backtest_report():
    if load_prediction_frame is None or score_backtest_report is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'error': 'file query parameter is required'}), 400
    try:
        top_k_arg = request.args.get('top_k')
        top_k = int(top_k_arg) if top_k_arg not in (None, '') else None
        df = load_prediction_frame(file_name)
        return jsonify(score_backtest_report(df, top_k=top_k))
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/stom/recommendation-export')
def stom_recommendation_export():
    if load_prediction_frame is None or recommendation_export_payload is None:
        return jsonify({'error': 'STOM dashboard helper is not available'}), 500
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({'error': 'file query parameter is required'}), 400
    try:
        output_format = request.args.get('format', 'json').lower()
        limit_arg = request.args.get('limit', request.args.get('k', '20'))
        limit = int(limit_arg) if limit_arg not in (None, '') else None
        min_score_arg = request.args.get('min_score')
        min_score = float(min_score_arg) if min_score_arg not in (None, '') else None
        selected_filter = request.args.get('filter', 'buy_candidate_score60')
        long_only = request.args.get('long_only', '1').lower() not in {'0', 'false', 'no', 'off'}
        df = load_prediction_frame(file_name)
        payload = recommendation_export_payload(
            df,
            source_file=file_name,
            limit=limit,
            min_score=min_score,
            selected_filter=selected_filter,
            long_only=long_only,
        )
        if output_format == 'json':
            return jsonify(payload)
        if output_format == 'csv':
            if recommendation_export_csv is None:
                return jsonify({'error': 'CSV export helper is not available'}), 500
            safe_name = ''.join(ch if ch.isalnum() or ch in ('-', '_', '.') else '_' for ch in file_name)
            csv_text = recommendation_export_csv(payload['records'])
            return Response(
                csv_text,
                mimetype='text/csv; charset=utf-8',
                headers={'Content-Disposition': f'attachment; filename="{safe_name}.kronos_recommendations.csv"'},
            )
        return jsonify({'error': 'format must be json or csv'}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

@app.route('/api/data-files')
def get_data_files():
    """Get available data file list"""
    data_files = load_data_files()
    return jsonify(data_files)

@app.route('/api/load-data', methods=['POST'])
def load_data():
    """Load data file"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        # Detect data time frequency
        def detect_timeframe(df):
            if len(df) < 2:
                return "Unknown"
            
            time_diffs = []
            for i in range(1, min(10, len(df))):  # Check first 10 time differences
                diff = df['timestamps'].iloc[i] - df['timestamps'].iloc[i-1]
                time_diffs.append(diff)
            
            if not time_diffs:
                return "Unknown"
            
            # Calculate average time difference
            avg_diff = sum(time_diffs, pd.Timedelta(0)) / len(time_diffs)
            
            # Convert to readable format
            if avg_diff < pd.Timedelta(minutes=1):
                return f"{avg_diff.total_seconds():.0f} seconds"
            elif avg_diff < pd.Timedelta(hours=1):
                return f"{avg_diff.total_seconds() / 60:.0f} minutes"
            elif avg_diff < pd.Timedelta(days=1):
                return f"{avg_diff.total_seconds() / 3600:.0f} hours"
            else:
                return f"{avg_diff.days} days"
        
        # Return data information
        data_info = {
            'rows': len(df),
            'columns': list(df.columns),
            'start_date': df['timestamps'].min().isoformat() if 'timestamps' in df.columns else 'N/A',
            'end_date': df['timestamps'].max().isoformat() if 'timestamps' in df.columns else 'N/A',
            'price_range': {
                'min': float(df[['open', 'high', 'low', 'close']].min().min()),
                'max': float(df[['open', 'high', 'low', 'close']].max().max())
            },
            'prediction_columns': ['open', 'high', 'low', 'close'] + (['volume'] if 'volume' in df.columns else []),
            'timeframe': detect_timeframe(df)
        }
        
        return jsonify({
            'success': True,
            'data_info': data_info,
            'message': f'Successfully loaded data, total {len(df)} rows'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to load data: {str(e)}'}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    """Perform prediction"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        lookback = int(data.get('lookback', 400))
        pred_len = int(data.get('pred_len', 120))
        
        # Get prediction quality parameters
        temperature = float(data.get('temperature', 1.0))
        top_p = float(data.get('top_p', 0.9))
        sample_count = int(data.get('sample_count', 1))
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        # Load data
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        if len(df) < lookback:
            return jsonify({'error': f'Insufficient data length, need at least {lookback} rows'}), 400
        
        # Perform prediction
        if MODEL_AVAILABLE and predictor is not None:
            try:
                # Use real Kronos model
                # Only use necessary columns: OHLCV, excluding amount
                required_cols = ['open', 'high', 'low', 'close']
                if 'volume' in df.columns:
                    required_cols.append('volume')
                
                # Process time period selection
                start_date = data.get('start_date')
                
                if start_date:
                    # Custom time period - fix logic: use data within selected window
                    start_dt = pd.to_datetime(start_date)
                    
                    # Find data after start time
                    mask = df['timestamps'] >= start_dt
                    time_range_df = df[mask]
                    
                    # Ensure sufficient data: lookback + pred_len
                    if len(time_range_df) < lookback + pred_len:
                        return jsonify({'error': f'Insufficient data from start time {start_dt.strftime("%Y-%m-%d %H:%M")}, need at least {lookback + pred_len} data points, currently only {len(time_range_df)} available'}), 400
                    
                    # Use first lookback data points within selected window for prediction
                    x_df = time_range_df.iloc[:lookback][required_cols]
                    x_timestamp = time_range_df.iloc[:lookback]['timestamps']
                    
                    # Use last pred_len data points within selected window as actual values
                    y_timestamp = time_range_df.iloc[lookback:lookback+pred_len]['timestamps']
                    
                    # Calculate actual time period length
                    start_timestamp = time_range_df['timestamps'].iloc[0]
                    end_timestamp = time_range_df['timestamps'].iloc[lookback+pred_len-1]
                    time_span = end_timestamp - start_timestamp
                    
                    prediction_type = f"Kronos model prediction (within selected window: first {lookback} data points for prediction, last {pred_len} data points for comparison, time span: {time_span})"
                else:
                    # Use latest data
                    x_df = df.iloc[:lookback][required_cols]
                    x_timestamp = df.iloc[:lookback]['timestamps']
                    y_timestamp = df.iloc[lookback:lookback+pred_len]['timestamps']
                    prediction_type = "Kronos model prediction (latest data)"
                
                # Ensure timestamps are Series format, not DatetimeIndex, to avoid .dt attribute error in Kronos model
                if isinstance(x_timestamp, pd.DatetimeIndex):
                    x_timestamp = pd.Series(x_timestamp, name='timestamps')
                if isinstance(y_timestamp, pd.DatetimeIndex):
                    y_timestamp = pd.Series(y_timestamp, name='timestamps')
                
                pred_df = predictor.predict(
                    df=x_df,
                    x_timestamp=x_timestamp,
                    y_timestamp=y_timestamp,
                    pred_len=pred_len,
                    T=temperature,
                    top_p=top_p,
                    sample_count=sample_count
                )
                
            except Exception as e:
                return jsonify({'error': f'Kronos model prediction failed: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Kronos model not loaded, please load model first'}), 400
        
        # Prepare actual data for comparison (if exists)
        actual_data = []
        actual_df = None
        
        if start_date:  # Custom time period
            # Fix logic: use data within selected window
            # Prediction uses first 400 data points within selected window
            # Actual data should be last 120 data points within selected window
            start_dt = pd.to_datetime(start_date)
            
            # Find data starting from start_date
            mask = df['timestamps'] >= start_dt
            time_range_df = df[mask]
            
            if len(time_range_df) >= lookback + pred_len:
                # Get last 120 data points within selected window as actual values
                actual_df = time_range_df.iloc[lookback:lookback+pred_len]
                
                for i, (_, row) in enumerate(actual_df.iterrows()):
                    actual_data.append({
                        'timestamp': row['timestamps'].isoformat(),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']) if 'volume' in row else 0,
                        'amount': float(row['amount']) if 'amount' in row else 0
                    })
        else:  # Latest data
            # Prediction uses first 400 data points
            # Actual data should be 120 data points after first 400 data points
            if len(df) >= lookback + pred_len:
                actual_df = df.iloc[lookback:lookback+pred_len]
                for i, (_, row) in enumerate(actual_df.iterrows()):
                    actual_data.append({
                        'timestamp': row['timestamps'].isoformat(),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']) if 'volume' in row else 0,
                        'amount': float(row['amount']) if 'amount' in row else 0
                    })
        
        # Create chart - pass historical data start position
        if start_date:
            # Custom time period: find starting position of historical data in original df
            start_dt = pd.to_datetime(start_date)
            mask = df['timestamps'] >= start_dt
            historical_start_idx = df[mask].index[0] if len(df[mask]) > 0 else 0
        else:
            # Latest data: start from beginning
            historical_start_idx = 0
        
        chart_json = create_prediction_chart(df, pred_df, lookback, pred_len, actual_df, historical_start_idx)
        
        # Prepare prediction result data - fix timestamp calculation logic
        if 'timestamps' in df.columns:
            if start_date:
                # Custom time period: use selected window data to calculate timestamps
                start_dt = pd.to_datetime(start_date)
                mask = df['timestamps'] >= start_dt
                time_range_df = df[mask]
                
                if len(time_range_df) >= lookback:
                    # Calculate prediction timestamps starting from last time point of selected window
                    last_timestamp = time_range_df['timestamps'].iloc[lookback-1]
                    time_diff = df['timestamps'].iloc[1] - df['timestamps'].iloc[0]
                    future_timestamps = pd.date_range(
                        start=last_timestamp + time_diff,
                        periods=pred_len,
                        freq=time_diff
                    )
                else:
                    future_timestamps = []
            else:
                # Latest data: calculate from last time point of entire data file
                last_timestamp = df['timestamps'].iloc[-1]
                time_diff = df['timestamps'].iloc[1] - df['timestamps'].iloc[0]
                future_timestamps = pd.date_range(
                    start=last_timestamp + time_diff,
                    periods=pred_len,
                    freq=time_diff
                )
        else:
            future_timestamps = range(len(df), len(df) + pred_len)
        
        prediction_results = []
        for i, (_, row) in enumerate(pred_df.iterrows()):
            prediction_results.append({
                'timestamp': future_timestamps[i].isoformat() if i < len(future_timestamps) else f"T{i}",
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']) if 'volume' in row else 0,
                'amount': float(row['amount']) if 'amount' in row else 0
            })
        
        # Save prediction results to file
        try:
            save_prediction_results(
                file_path=file_path,
                prediction_type=prediction_type,
                prediction_results=prediction_results,
                actual_data=actual_data,
                input_data=x_df,
                prediction_params={
                    'lookback': lookback,
                    'pred_len': pred_len,
                    'temperature': temperature,
                    'top_p': top_p,
                    'sample_count': sample_count,
                    'start_date': start_date if start_date else 'latest'
                }
            )
        except Exception as e:
            print(f"Failed to save prediction results: {e}")
        
        return jsonify({
            'success': True,
            'prediction_type': prediction_type,
            'chart': chart_json,
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'has_comparison': len(actual_data) > 0,
            'message': f'Prediction completed, generated {pred_len} prediction points' + (f', including {len(actual_data)} actual data points for comparison' if len(actual_data) > 0 else '')
        })
        
    except Exception as e:
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

@app.route('/api/load-model', methods=['POST'])
def load_model():
    """Load Kronos model"""
    global tokenizer, model, predictor
    
    try:
        if not ensure_kronos_imported():
            return jsonify({'error': f'Kronos model library not available: {MODEL_IMPORT_ERROR}'}), 400
        
        data = request.get_json()
        model_key = data.get('model_key', 'kronos-small')
        device = data.get('device', 'cpu')
        
        if model_key not in AVAILABLE_MODELS:
            return jsonify({'error': f'Unsupported model: {model_key}'}), 400
        
        model_config = AVAILABLE_MODELS[model_key]
        
        # Load tokenizer and model
        tokenizer = KronosTokenizer.from_pretrained(model_config['tokenizer_id'])
        model = Kronos.from_pretrained(model_config['model_id'])
        
        # Create predictor
        predictor = KronosPredictor(model, tokenizer, device=device, max_context=model_config['context_length'])
        
        return jsonify({
            'success': True,
            'message': f'Model loaded successfully: {model_config["name"]} ({model_config["params"]}) on {device}',
            'model_info': {
                'name': model_config['name'],
                'params': model_config['params'],
                'context_length': model_config['context_length'],
                'description': model_config['description']
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Model loading failed: {str(e)}'}), 500

@app.route('/api/available-models')
def get_available_models():
    """Get available model list"""
    return jsonify({
        'models': AVAILABLE_MODELS,
        'model_available': MODEL_AVAILABLE,
        'model_import_error': MODEL_IMPORT_ERROR
    })

@app.route('/api/model-status')
def get_model_status():
    """Get model status"""
    if MODEL_AVAILABLE:
        if predictor is not None:
            return jsonify({
                'available': True,
                'loaded': True,
                'message': 'Kronos model loaded and available',
                'current_model': {
                    'name': predictor.model.__class__.__name__,
                    'device': str(next(predictor.model.parameters()).device)
                }
            })
        else:
            return jsonify({
                'available': True,
                'loaded': False,
                'message': 'Kronos model available but not loaded'
            })
    else:
        return jsonify({
            'available': False,
            'loaded': False,
            'message': f'Kronos model library not available: {MODEL_IMPORT_ERROR}'
        })

if __name__ == '__main__':
    print("Starting Kronos Web UI...")
    print("Tip: Kronos model is imported lazily when /api/load-model is called")
    
    app.run(debug=True, host='0.0.0.0', port=7070)

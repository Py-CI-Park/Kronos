@echo off
setlocal EnableExtensions
rem =====================================================================
rem  Kronos remodeled dashboard launcher (single Svelte app)
rem  - Starts Flask on 127.0.0.1:8122, opens the released V6 research dashboard.
rem  - No Next.js / trading_src dependency (retired in consolidation A).
rem  - Stop with stop_kronos_dashboard.bat, or close the minimized window.
rem =====================================================================

cd /d "%~dp0"

if not defined KRONOS_WEBUI_HOST set "KRONOS_WEBUI_HOST=127.0.0.1"
if not defined KRONOS_WEBUI_PORT set "KRONOS_WEBUI_PORT=8122"
set "KRONOS_WEBUI_OPEN_BROWSER=0"

set "PYTHON_CMD=py -3.11"
%PYTHON_CMD% --version >NUL 2>&1
if errorlevel 1 (
  set "PYTHON_CMD=python"
  python --version >NUL 2>&1
  if errorlevel 1 (
    echo [ERROR] Python 3.11 not found. Install Python or put py/python on PATH.
    pause
    exit /b 1
  )
)

if not exist "webui\run.py" (
  echo [ERROR] webui\run.py not found. Run this file from the Kronos repo root.
  pause
  exit /b 1
)

set "LOG_DIR=%CD%\artifacts"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\kronos_dashboard_%KRONOS_WEBUI_PORT%.log"

echo [Kronos] Remodeled dashboard - single Svelte app
echo [Kronos] URL : http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/
echo [Kronos] Log : %LOG_FILE%
echo(

echo [Kronos] Stopping any stale dashboard on port %KRONOS_WEBUI_PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=[int]$env:KRONOS_WEBUI_PORT; Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $pr=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_) -ErrorAction SilentlyContinue; if ($pr -and $pr.CommandLine -match 'run\.py|webui') { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Milliseconds 500"

echo [Kronos] Starting dashboard (minimized window)...
start "Kronos Dashboard %KRONOS_WEBUI_PORT%" /min cmd /c "cd /d "%CD%\webui" && %PYTHON_CMD% run.py > "%LOG_FILE%" 2>&1"

echo [Kronos] Waiting for readiness...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$u='http://' + $env:KRONOS_WEBUI_HOST + ':' + $env:KRONOS_WEBUI_PORT + '/'; for ($i=0; $i -lt 40; $i++){ try { $r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2; if ($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Milliseconds 700 }; exit 1"
if errorlevel 1 (
  echo [ERROR] Dashboard did not respond. Check the log: %LOG_FILE%
  pause
  exit /b 1
)

echo [OK] Ready. Opening the released V6 dashboard in your browser...
start "" "http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/"
echo(
echo [OK] V6 Dashboard   : http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/
echo [OK] Daily OHLCV     : http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/daily-ohlcv
echo [OK] RL Trading      : http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/rl
echo [OK] Stop            : stop_kronos_dashboard.bat  (or close the minimized window)
echo(
timeout /t 5 >NUL
exit /b 0

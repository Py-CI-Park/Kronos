@echo off
setlocal EnableExtensions

rem Kronos quiet dashboard launcher.
rem - Starts the local dashboard on 8122 by default.
rem - Stops stale Kronos dashboard listeners first.
rem - Runs Flask in a background window and writes noisy access logs to artifacts\kronos_dashboard_8122_quiet.log.
rem - Use stop_kronos_dashboard.bat to stop it.

cd /d "%~dp0"

if not defined KRONOS_WEBUI_HOST set "KRONOS_WEBUI_HOST=127.0.0.1"
if not defined KRONOS_WEBUI_PORT set "KRONOS_WEBUI_PORT=8122"
if not defined KRONOS_WEBUI_OPEN_BROWSER set "KRONOS_WEBUI_OPEN_BROWSER=1"
if not defined KRONOS_WEBUI_DEBUG set "KRONOS_WEBUI_DEBUG=0"
if not defined KRONOS_WEBUI_RELOAD set "KRONOS_WEBUI_RELOAD=0"

set "PYTHON_CMD=py -3.11"
%PYTHON_CMD% --version >NUL 2>&1
if errorlevel 1 (
  set "PYTHON_CMD=python"
  python --version >NUL 2>&1
  if errorlevel 1 (
    echo [ERROR] Python was not found. Install Python 3.11 or ensure py/python is on PATH.
    exit /b 1
  )
)

if not exist "webui\run.py" (
  echo [ERROR] webui\run.py was not found. Run this file from the Kronos repository root.
  exit /b 1
)

if not exist "webui\app.py" (
  echo [ERROR] webui\app.py was not found. The Flask dashboard entrypoint is missing.
  exit /b 1
)

if not exist "webui\trading_src\out\index.html" (
  echo [ERROR] webui\trading_src\out\index.html was not found. Run npm install and npm run build in webui\trading_src.
  exit /b 1
)

set "LOG_DIR=%CD%\artifacts"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\kronos_dashboard_%KRONOS_WEBUI_PORT%_quiet.log"

echo [Kronos] Quiet dashboard launcher
echo [Kronos] Repository: %CD%
echo [Kronos] URL: http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/
echo [Kronos] Log file: %LOG_FILE%
echo [Kronos] Python: %PYTHON_CMD%

if /I "%~1"=="--check" (
  echo [OK] Quiet launcher preflight passed.
  exit /b 0
)

echo [Kronos] Stopping stale Kronos dashboard servers on 8103 and %KRONOS_WEBUI_PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "for ($attempt = 0; $attempt -lt 5; $attempt++) { $ports = @(8103, [int]$env:KRONOS_WEBUI_PORT); $owners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique; if (-not $owners) { break }; foreach ($owner in $owners) { $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $owner) -ErrorAction SilentlyContinue; if ($proc -and $proc.CommandLine -match 'webui/run\.py|webui\\run\.py|webui\.app|import run; run\.main|(^|\s)run\.py(\s|$)') { Write-Host ('Stopping stale Kronos dashboard PID ' + $owner); Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Milliseconds 400 }"

echo [Kronos] Starting dashboard quietly in a background window...
start "Kronos Dashboard %KRONOS_WEBUI_PORT%" /min cmd /c "cd /d "%CD%\webui" && %PYTHON_CMD% run.py > "%LOG_FILE%" 2>&1"

echo [Kronos] Waiting for dashboard readiness...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$url='http://' + $env:KRONOS_WEBUI_HOST + ':' + $env:KRONOS_WEBUI_PORT + '/'; for ($i=0; $i -lt 30; $i++) { try { $r=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { }; Start-Sleep -Milliseconds 700 }; exit 1"
if errorlevel 1 (
  echo [ERROR] Dashboard did not answer within the readiness window.
  echo [ERROR] Check log: %LOG_FILE%
  exit /b 1
)

echo [OK] Dashboard started quietly: http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%/
echo [OK] Access logs are redirected to: %LOG_FILE%
echo [OK] Stop with: stop_kronos_dashboard.bat
exit /b 0

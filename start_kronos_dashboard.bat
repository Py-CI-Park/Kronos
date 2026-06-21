@echo off
setlocal EnableExtensions

rem Kronos unified dashboard launcher.
rem - Uses one local dashboard port only: 8122 by default.
rem - Stops stale Kronos dashboard listeners on 8103 and the selected port.
rem - Runs from webui\ so local imports resolve correctly.

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

if not exist "webui\static\v2\dist\index.html" (
  echo [WARN] webui\static\v2\dist\index.html was not found. Run npm build in webui\v2_src if the v2 UI is missing.
)
if not exist "webui\trading_src\out\index.html" (
  echo [ERROR] webui\trading_src\out\index.html was not found. Run npm install and npm run build in webui\trading_src.
  exit /b 1
)

echo [Kronos] Unified dashboard launcher
echo [Kronos] Repository: %CD%
echo [Kronos] URL: http://%KRONOS_WEBUI_HOST%:%KRONOS_WEBUI_PORT%
echo [Kronos] Python: %PYTHON_CMD%

if /I "%~1"=="--check" (
  echo [OK] Launcher preflight passed.
  exit /b 0
)

echo [Kronos] Stopping stale Kronos dashboard servers on 8103 and %KRONOS_WEBUI_PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "for ($attempt = 0; $attempt -lt 5; $attempt++) { $ports = @(8103, [int]$env:KRONOS_WEBUI_PORT); $owners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique; if (-not $owners) { break }; foreach ($owner in $owners) { $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $owner) -ErrorAction SilentlyContinue; if ($proc -and $proc.CommandLine -match 'webui/run\.py|webui\\run\.py|webui\.app|import run; run\.main|(^|\s)run\.py(\s|$)') { Write-Host ('Stopping stale Kronos dashboard PID ' + $owner); Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Milliseconds 400 }" 2>NUL

echo [Kronos] Starting Flask dashboard. Press Ctrl+C in this window to stop.
pushd "webui"
%PYTHON_CMD% run.py
set "KRONOS_EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %KRONOS_EXIT_CODE%

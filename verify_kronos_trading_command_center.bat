@echo off
setlocal EnableExtensions

rem Focused verification wrapper for the Kronos Trading Command Center.
rem Runs only research-dashboard gates and writes receipts under artifacts\.

cd /d "%~dp0"

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

if not exist "verify_kronos_trading_command_center.py" (
  echo [ERROR] verify_kronos_trading_command_center.py was not found. Run this wrapper from the Kronos repository root.
  exit /b 1
)

%PYTHON_CMD% verify_kronos_trading_command_center.py %*
exit /b %ERRORLEVEL%

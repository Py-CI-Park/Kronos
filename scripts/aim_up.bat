@echo off
setlocal

rem Research-only local Aim UI. Binds loopback only; no external upload.
set "AIM_HOST=127.0.0.1"
if "%AIM_PORT%"=="" set "AIM_PORT=43800"
if "%AIM_REPO%"=="" set "AIM_REPO=.aim"

python -c "import aim" >nul 2>nul
if not errorlevel 1 (
  aim up --repo "%AIM_REPO%" --host "%AIM_HOST%" --port "%AIM_PORT%"
  exit /b %errorlevel%
)

where wsl.exe >nul 2>nul
if errorlevel 1 (
  echo Aim is unavailable in native Python and WSL is not installed. 1>&2
  exit /b 1
)

for %%I in ("%AIM_REPO%") do set "AIM_REPO_ABS=%%~fI"
for /f "usebackq delims=" %%I in (`wsl.exe -d Ubuntu -- wslpath -a "%AIM_REPO_ABS%"`) do set "AIM_REPO_WSL=%%I"
for /f "usebackq delims=" %%I in (`wsl.exe -d Ubuntu -- printenv HOME`) do set "AIM_WSL_HOME=%%I"
wsl.exe -d Ubuntu -- "%AIM_WSL_HOME%/.local/bin/aim" up --repo "%AIM_REPO_WSL%" --host "%AIM_HOST%" --port "%AIM_PORT%"
exit /b %errorlevel%
@echo off
setlocal EnableExtensions

rem Stop local Kronos dashboard listeners started by the batch launchers.

cd /d "%~dp0"
if not defined KRONOS_WEBUI_PORT set "KRONOS_WEBUI_PORT=8122"

echo [Kronos] Stopping Kronos dashboard servers on 8103 and %KRONOS_WEBUI_PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(8103, [int]$env:KRONOS_WEBUI_PORT); $owners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique; $stopped = 0; foreach ($owner in $owners) { $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $owner) -ErrorAction SilentlyContinue; if ($proc -and $proc.CommandLine -match 'webui/run\.py|webui\\run\.py|webui\.app|import run; run\.main|(^|\s)run\.py(\s|$)') { Write-Host ('Stopping Kronos dashboard PID ' + $owner); Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue; $stopped++ } }; if ($stopped -eq 0) { Write-Host 'No Kronos dashboard listener found.' }"
exit /b %ERRORLEVEL%

@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Build
if errorlevel 1 (
  echo Installer build failed. See runtime\logs\startup.log
  pause
  exit /b 1
)
echo Installer build completed. See the dist folder.
pause

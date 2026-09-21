@echo off
setlocal
cd /d "%~dp0"
title Logistics - Startup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Details: runtime\logs\startup.log
  pause
  exit /b 1
)
exit /b 0

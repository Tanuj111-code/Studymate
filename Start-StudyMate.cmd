@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Open-StudyMate.ps1"
if errorlevel 1 (
  echo.
  echo StudyMate could not start. See the error above.
  pause
)

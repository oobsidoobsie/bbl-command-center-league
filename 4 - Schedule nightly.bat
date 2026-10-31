@echo off
REM Adds (or updates) a Windows scheduled task that runs the Command Center every night. The time is run_time= in config.txt.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (echo Run "1 - Setup" first. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cc\schedule.ps1"
if errorlevel 1 (echo Couldn't create the scheduled task. & pause & exit /b 1)
echo To stop it later, double-click "5 - Remove schedule".
pause

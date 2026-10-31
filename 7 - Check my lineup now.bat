@echo off
REM Pre-lock lineup check right now: compares your CBS lineup for today with the best lineup from the players who play tonight.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run "1 - Setup" first. & pause & exit /b 1)
.venv\Scripts\python -X utf8 cc\lineup_check.py --now
pause

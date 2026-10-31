@echo off
REM Builds tonight's Command Center for your team right now (doesn't wait for late games).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run "1 - Setup" first. & pause & exit /b 1)
.venv\Scripts\python -X utf8 cc\run.py --now %*
if exist "BBL Command Center.html" start "BBL Command Center" ".venv\Scripts\python" -X utf8 cc\serve.py
pause

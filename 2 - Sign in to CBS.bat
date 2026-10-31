@echo off
REM Opens a browser window on your CBS league. Sign in yourself; the window remembers it for the nightly run.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run "1 - Setup" first. & pause & exit /b 1)
.venv\Scripts\python -X utf8 cc\browser.py
pause

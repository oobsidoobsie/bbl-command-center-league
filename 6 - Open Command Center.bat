@echo off
REM Opens your Command Center from a small server on this PC so the Watchlist tab can add and remove players.
REM Close this window when you are done (the page then turns read-only).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run "1 - Setup" first. & pause & exit /b 1)
if not exist "BBL Command Center.html" (echo No page yet - run "3 - Run now" first. & pause & exit /b 1)
title BBL Command Center
.venv\Scripts\python -X utf8 cc\serve.py
if errorlevel 1 pause
